"""
Contains the hardware interface and drivers for the fantastic Pinball platform
hardware. See for details:
https://github.com/yetifrisstlama/Fan-Tas-Tic-Firmware

Required modifications:
    # mpfconfig.yaml
    fantastic: mpf.platforms.fantastic.fantastic_hardware_platform.FanTasTicHardwarePlatform

    # core/config_validator.py
    fantastic:
      __valid_in__: machine
      port: single|str|None
      led_clock_0: single|int|3200000
      led_clock_1: single|int|3200000
      led_clock_2: single|int|3200000

    pulse_power: single|int|None
    hold_power: single|int|None
"""

import logging
import struct
import asyncio
from collections import defaultdict     # For dict of lists
from mpf.core.platform import LightsPlatform, SwitchPlatform, DriverPlatform, \
    DriverConfig, DriverSettings, SwitchSettings, SwitchConfig
from fantastic_platform.fantastic_serial_communicator import \
    FanTasTicSerialCommunicator
from fantastic_platform.fantastic_driver import FanTasTicDriver
from fantastic_platform.fantastic_light import FanTasTicLight
from fantastic_platform.fantastic_switch import FanTasTicSwitch
import atexit


class FanTasTicHardwarePlatform(
    SwitchPlatform, DriverPlatform, LightsPlatform
):
    MAX_QUICK_RULES = 64    # must match bit_rules.h

    def __init__(self, machine) -> None:
        """ Initialize FanTasTic PCB """
        super().__init__(machine)
        atexit.register(self.stop)
        self.log = logging.getLogger("FanTasTic")
        self.log.debug("Configuring FanTasTic hardware interface.")
        self.features['tickless'] = True
        # ----------------------------------------------------------------
        #  Global (state) variables
        # ----------------------------------------------------------------
        self.serialCom = None  # Serial communicator object
        # State of _ALL_ posisble input switches as Binary bit-field
        self.hw_switch_data = None
        self.hw_switch_gotit = asyncio.Event()
        # Keep the state of the WS2811 LEDs in bytearrays
        # This is efficient and close to the hardware
        # as data can be dumped to serial port without conversion
        # We got 3 channels of up to 1024 LEDs with 3 bytes
        # These arrays start with size 0 and are extended on demand
        self.ledByteData = [bytearray(), bytearray(), bytearray()]
        self.flag_led_tick_registered = False
        # List to store all configured rules (active and inactive) in tuple fmt
        self.configuredRules = [None] * \
            FanTasTicHardwarePlatform.MAX_QUICK_RULES
        self.swNameToRuleIdDict = defaultdict(list)

    @classmethod
    def get_config_spec(cls):
        return "fantastic", """
    __valid_in__: machine
    debug:       single|bool|False
    port:        single|str|None
    led_clock_0: single|int|3200000
    led_clock_1: single|int|3200000
    led_clock_2: single|int|3200000
    pulse_power: single|int|None
    hold_power:  single|int|None
        """

    @asyncio.coroutine
    def initialize(self):
        # ----------------------------------------------------------------
        #  Register fantastic specific .yaml keys
        # ----------------------------------------------------------------
        if 'fantastic' not in self.machine.config:
            raise AssertionError('Add `fantastic:` to your machine config')
        self.config = self.machine.config_validator.validate_config(
            "fantastic",
            self.machine.config['fantastic']
        )
        # ----------------------------------------------------------------
        #  Open serial connection (baudrate is ignored by hardware)
        # ----------------------------------------------------------------
        comm = FanTasTicSerialCommunicator(
            platform=self,
            port=self.config["port"],
            serialCommandCallbacks={
                b'SW': self.receive_sw,  # States of all switches
                b'SE': self.receive_se   # States of changed switches
            }
        )
        self.serialCom = comm
        yield from comm.connect()
        # ----------------------------------------------------------------
        #  Set some global firmware parameters
        # ----------------------------------------------------------------
        comm.send("SWE 0\n")
        comm.send("SOE 0\n")
        CMD = ""
        for rulId in range(FanTasTicHardwarePlatform.MAX_QUICK_RULES):
            CMD += "RULE {0} 0\n".format(rulId)
        comm.send(CMD)
        # ----------------------------------------------------------------
        #  Configure LED channel speeds
        # ----------------------------------------------------------------
        for i in range(3):
            ledKey = "led_clock_{0}".format(i)
            if ledKey in self.config:
                tempSpeed = int(self.config[ledKey])
                comm.send("LEC {0} {1}\n".format(i, tempSpeed))
                self.log.debug("LEC {0} {1}\n".format(i, tempSpeed))

    def stop(self):
        if self.serialCom:
            # Disable 24 V solenoid power
            self.serialCom.send("SOE 0\n")
            # Disable all quickfire rules
            CMD = ""
            for rulId in range(FanTasTicHardwarePlatform.MAX_QUICK_RULES):
                CMD += "RULE {0} 0\n".format(rulId)
            self.serialCom.send(CMD)
            # Turn off leds
            for channel, ledDat in enumerate(self.ledByteData):
                if len(ledDat) > 0:
                    msg = bytes(
                        "LED {0} {1}\n".format(channel, len(ledDat)), "utf8"
                    ) + b"\0" * len(ledDat)
                    self.serialCom.send(msg)
            # Close serial connection
            self.serialCom.stop()

    def __repr__(self):
        """String name you'd like to show up in logs and stuff when a
        reference to this platform is printed."""
        return '<Platform.FanTasTic>'

    # ----------------------------------------------------------------------
    #  Solenoid Drivers !!!
    # ----------------------------------------------------------------------
    def configure_driver(
        self,
        config: DriverConfig,
        number: str,
        platform_settings: dict
    ) -> FanTasTicDriver:
        """
        This method returns a reference to a driver's platform interface
        object which will be called to access the hardware.
        """
        return FanTasTicDriver(config, number, self.serialCom)

    # ----------------------------------------------------------------------
    #  Hardware quickfire rules !!!
    # ----------------------------------------------------------------------
    # First some helper functions ...
    def _findFreeSpotForRules(self, nFree=1):
        """
        Find `nFree` consequtive `None` elements in a list
        and return the first index
        """
        nFound = 0
        for i, rulTuple in enumerate(self.configuredRules):
            if rulTuple is None:
                nFound += 1
            else:
                nFound = 0
            if nFound >= nFree:
                return i - (nFree - 1)
        raise OverflowError(
            "_findFreeSpotForRules(): No free slot for quick-fire rule found!"
        )

    def write_hw_rule(self, switch_obj, sw_activity, driver_obj, driver_action,
                      disable_on_release=True, drive_now=False, trHoldOff=25):
        """
        Args:
            switch_obj: Which switch you're creating this rule for. The
                parameter is a reference to the switch object itself.
            sw_activity: Int which specifies whether this coil should fire when
                the switch becomes active (1) or inactive (0)
            driver_obj: Driver object this rule is being set for.
            driver_action: String 'pulse' or 'hold' which describe what action
                will be applied to this driver
            disable_on_release: Actually put a second rule to disable the coil
                again
            drive_now: Should the hardware check the state of the switches when
                this rule is first applied, and fire the coils if they should
                be? Typically this is True, especially with flippers because u
                want them to fire if the player is holding in the buttons when
                the machine enables the flippers (which is done via several
                calls to this method.)
            trHoldOff: Equivalent to a hold-off time on a scope trigger in [ms]
        """
        isPosEdge = sw_activity == 1
        tPulse = driver_obj.tPulse
        pwmHigh = driver_obj.pwmHigh
        # pwmLow is the power setting after the ON time, which is zero if a
        # `pulse` is requested
        if driver_action == "pulse":
            pwmLow = 0
        else:
            pwmLow = driver_obj.pwmLow
        hwIndexSw = switch_obj.number
        hwIndexOut = driver_obj.number
        # `triggerHoldOff` is equivalent to the trigger-hold-off time on a
        # scope (dead time after trigger)
        # TODO: Add custom property to set triggerHoldOff in yaml
        # Get the next free index for a quick-fire-rule slot
        rulId = self._findFreeSpotForRules(1)
        rulTuple = (
            rulId,
            hwIndexSw,
            hwIndexOut,
            trHoldOff,
            tPulse,
            pwmHigh,
            pwmLow,
            int(isPosEdge)
        )
        CMD = "RUL {0} {1} {2} {3} {4} {5} {6} {7}\n".format(*rulTuple)
        # Remember which rules are associated with this switch-name
        self.swNameToRuleIdDict[switch_obj.number].append(rulId)
        # We keep the current state of all rule-slots
        self.configuredRules[rulId] = rulTuple
        # --------------------------------------------------
        #  For `disable_on_release` we need to configure a
        #  second quickfirerule, triggering on the other
        #  edge, disabling the coil
        # --------------------------------------------------
        if disable_on_release:
            rulId = self._findFreeSpotForRules(1)
            rulTuple = (
                rulId,
                hwIndexSw,
                hwIndexOut,
                0, 0, 0, 0,
                int(not isPosEdge)
            )
            CMD += "RUL {0} {1} {2} {3} {4} {5} {6} {7}\n".format(*rulTuple)
            self.swNameToRuleIdDict[switch_obj.number].append(rulId)
            self.configuredRules[rulId] = rulTuple
        self.log.info(
            "{0} [{1}]".format(
                CMD.replace('\n', ', '),
                switch_obj.number
            )
        )
        self.serialCom.send(CMD)

    def clear_hw_rule(self, switch: SwitchSettings, coil: DriverSettings):
        """Clear a hardware switch rule for this switch.

        Clearing a hardware rule means actions on this switch will no longer
        affect coils.

        Another way to think of this is that it 'disables' a hardware rule.
        This is what you'd use to disable flippers and autofire_coils during
        tilt, game over, etc.

        """
        sw_name = switch.hw_switch.number
        rulIds = self.swNameToRuleIdDict.pop(sw_name)
        # print( "clear_hw_rule:", rulIds, self.configuredRules )
        CMD = ""
        for rulId in rulIds:
            rulTuple = self.configuredRules[rulId]
            self.configuredRules[rulId] = None
            # Disable the rule
            CMD += "RULE {0} 0\n".format(rulId)
            # Just in case the flipper still in hold state, reset the coil
            CMD += "OUT {0} 0\n".format(rulTuple[2])
        del rulIds
        self.log.info("{0} [{1}]".format(CMD.replace('\n', ', '), sw_name))
        self.serialCom.send(CMD)

    def set_pulse_on_hit_and_release_rule(
        self,
        enable_switch: SwitchSettings,
        coil: DriverSettings
    ):
        raise NotImplementedError

    def set_pulse_on_hit_and_enable_and_release_rule(
        self,
        enable_switch: SwitchSettings,
        coil: DriverSettings
    ):
        self.write_hw_rule( enable_switch.hw_switch, 0, coil.hw_driver, "hold", disable_on_release=True )

    def set_pulse_on_hit_and_enable_and_release_and_disable_rule(
        self,
        enable_switch: SwitchSettings,
        disable_switch: SwitchSettings,
        coil: DriverSettings
    ):
        raise NotImplementedError

    def set_pulse_on_hit_rule(
        self,
        enable_switch: SwitchSettings,
        coil: DriverSettings
    ):
        self.write_hw_rule(
            enable_switch.hw_switch,
            0,
            coil.hw_driver,
            "pulse",
            disable_on_release=False
        )

    # ----------------------------------------------------------------------
    #  Switches !!!
    # ----------------------------------------------------------------------
    def configure_switch(
        self,
        number: str,
        config: SwitchConfig,
        platform_config: dict
    ) -> "SwitchPlatformInterface":
        """
        This method should returns the reference to the switch's platform
        interface object which will be called to access the hardware.
        """
        return FanTasTicSwitch(config, number, self.serialCom)

    @asyncio.coroutine
    def get_hw_switch_states(self):
        """get the state of all Switches at once"""
        self.hw_switch_gotit.clear()
        self.serialCom.send("SW?\n")  # Request current state of all switches
        self.log.info("Waiting for response to `SW?` command")
        yield from self.hw_switch_gotit.wait()
        # ----------------------------------------------------------------
        #  Engage Solenoid 24 V power relay and start reporting switches
        # ----------------------------------------------------------------
        self.serialCom.send("SOE 1\n")
        self.serialCom.send("SWE 1\n")
        return self.hw_switch_data

    def receive_sw(self, payload):
        """Callback for the SW: command response.
        Payload contains state of all switches.
        Parse data and set hw_switch_data to bitArray
        """
        # msg = b"00000000123456789ABCDEF0AFFE0000DEAD0000BEEF0000 ...
        # Process Hex values in groups of 8 (little endian)
        # hwIndex[0] = 0: b"FFFFFFFE...
        # self.log.debug("Received SW: %s", payload)
        hwBytes = bytearray.fromhex(payload.decode())
        hwLongs = struct.unpack(">{0}I".format(len(hwBytes) // 4), hwBytes)
        # Now we have an array of bytes, but MPF expects an array of bits
        # so lets go ahead with extracting them
        hwBits = bytearray(len(hwLongs) * 32)
        i = 0
        for hwLong in hwLongs:
            for n in range(32):
                hwBits[i] = ((hwLong >> n) & 0x01)  # == 0
                i += 1
        self.hw_switch_data = hwBits
        self.hw_switch_gotit.set()

    def receive_se(self, payload):
        """Callback for the SE: command response.
            Payload contains a list of switches which have changed state
        """
        # payload = b"0f8=1 0fa=1 0fc=0 0fe=1 "
        for se in payload.split(b' '):
            if len(se) <= 0:
                continue
            swId, swState = se.split(b'=')
            self.machine.switch_controller.process_switch_by_num(
                num=int(swId, 16),
                state=int(swState),
                platform=self
            )

    # ----------------------------------------------------------------------
    #  Lights !!!
    # ----------------------------------------------------------------------
    def parse_light_number_to_channels(self, number: str, subtype: str):
        """Parse light number to a list of channels.
        A `channel` is a byte - index in the data array, setting the
        brightness of a single led (r, g or b)
        """
        # number = 1-38, 1-39
        if not(subtype is None or subtype == "led"):
            raise AssertionError("Unknown subtype {}".format(subtype))
        # For each color, Wow, this is so ugly
        # number = <colorIndex>, 1-38, 1-39
        return [{"number": "{}, {}".format(i, number)} for i in range(3)]

    def configure_light(
        self, number: str, subtype: str, platform_settings: dict
    ) -> FanTasTicLight:
        """ This method should returns a reference to the light
        object which will be called to access the hardware.

        A WS2811 led is identified by its channel number (0-3)
            and position along the chain (0-1023)
            Syntax for channel 1, led 45 and 46 (will be driven in parallel):

                l_captive_t:
                    number: 1-45, 1-46
        """
        # **************** configure_light() ****** 1-38:1 None None
        # **************** configure_light() ****** 1-38:2 None None
        # **************** configure_light() ****** 1-38:0 None None
        if not self.flag_led_tick_registered:
            # Update leds every frame
            self.machine.clock.schedule_interval(
                self.update_leds,
                1 / self.machine.config['mpf']['default_light_hw_update_hz']
            )
            self.flag_led_tick_registered = True
        software_fade_ms = int(
            1 / self.machine.config['mpf']['default_light_hw_update_hz'] * 1000
        )
        # number = <colorIndex>, 1-38, 1-39
        return FanTasTicLight(
            self.machine.clock.loop,
            software_fade_ms,
            number,
            self.ledByteData
        )

    def update_leds(self):
        """
        Fire the LED command to update the 3 strings of WS2811 LEDs.
        This is done once per game loop. All LEDs must be updated at once by
        duming the bytearray `self.ledByteData` to the hardware.
        Note that inidividual adressing of LEDs is not supported.
        """
        for channel, ledDat in enumerate(self.ledByteData):
            if len(ledDat) > 0:
                msg = bytes(
                    "LED {0} {1}\n".format(channel, len(ledDat)),
                    "utf8"
                ) + ledDat
                self.serialCom.send(msg)
