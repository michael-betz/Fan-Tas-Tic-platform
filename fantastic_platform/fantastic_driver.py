from mpf.platforms.interfaces.driver_platform_interface import \
    DriverPlatformInterface, PulseSettings, HoldSettings


class FanTasTicDriver(DriverPlatformInterface):
    """ Represents and handles one solenoid PWM output """
    MAX_PWM_VALUE = 7           # Max value for PWM drivers
    MAX_HW_PWM_VALUE = 4000     # Max value for HW PWM drivers
    # Channels which support high resolution hardware PWM
    HW_PWM_CHANNELS = (0x3C, 0x3D, 0x3E, 0x3F)
    __slots__ = ["serialCom", "hwIndex", "tPulse", "pwmHigh", "pwmLow"]

    def __init__(self, config, number, serialCom):
        super().__init__(config, number)
        self.serialCom = serialCom
        self.hwIndex = int(number)
        # TODO sanity check the hwIndex
        # -------------------------------------------------------------
        #  Parse default values (used to setup quickfire rules)
        # -------------------------------------------------------------
        # config = DriverConfig(
        #     default_pulse_ms=45,
        #     default_pulse_power=0.5,
        #     default_hold_power=None,
        #     default_recycle=False,
        #     max_pulse_ms=None,
        #     max_pulse_power=1.0,
        #     max_hold_power=None
        # )
        self.tPulse = int(config.default_pulse_ms)
        self.pwmHigh = self.getPwmValue(config.default_pulse_power)
        self.pwmLow = self.getPwmValue(config.default_hold_power)
        self.disable()

    def pulse(self, pulse_settings: PulseSettings):
        """Pulse a driver.

        Pulse this driver for a pre-determined amount of time, after which
        this driver is turned off automatically. Note that on most platforms,
        pulse times are a max of 255ms. (Beyond that MPF will send separate
        enable() and disable() commands.
        """
        self.setSolenoid(0, pulse_settings.duration, pulse_settings.power)

    def enable(
        self, pulse_settings: PulseSettings, hold_settings: HoldSettings
    ):
        """Enable this driver, which means it's held "on" indefinitely """
        self.setSolenoid(
            hold_settings.power,
            pulse_settings.duration,
            pulse_settings.power
        )

    def disable(self):
        """Disable the driver."""
        self.setSolenoid(0)

    def setSolenoid(self, powerOff, tOn=None, powerOn=None):
        """ Send the command  OUT   : <hwIndex> <PWMlow> [tPulse] [PWMhigh] """
        pwmOff = self.getPwmValue(powerOff)
        cmd = "OUT {:d} {:d}".format(self.hwIndex, pwmOff)
        if tOn is not None:
            if not (0 < tOn < 32760):
                raise ValueError(
                    "pulse_settings.duration is out of range:", tOn
                )
            if powerOn is None:
                raise ValueError("powerOn (during tOn) must be defined!")
            pwmOn = self.getPwmValue(powerOn)
            cmd += " {:d} {:d}".format(tOn, pwmOn)
        cmd += "\n"
        self.serialCom.send(cmd)

    def getPwmValue(self, power):
        """
        returns integer pwm value for a power in the range of [0.0 - 1.0]
        """
        if power is None:
            power = 0
        if not (0 <= power <= 1):
            raise ValueError("PWM power level outside range", power)
        if(self.hwIndex in FanTasTicDriver.HW_PWM_CHANNELS):
            maxPwm = FanTasTicDriver.MAX_HW_PWM_VALUE  # Hardware PWM channel
        else:
            maxPwm = FanTasTicDriver.MAX_PWM_VALUE    # I2C BCM channel
        # round result up so maxPwm can be reached
        return int(power * maxPwm + 0.5)

    def get_board_name(self):
        """Return the name of the board of this driver."""
        return "Fan-Tas-Tic-Driver"
