from typing import Any
from mpf.platforms.interfaces.switch_platform_interface import SwitchPlatformInterface

class FanTasTicSwitch(SwitchPlatformInterface):
    """ Represents a switch input """
    __slots__ = ["serialCom", "hwIndex"]

    def __init__(self, config: "SwitchConfig", number: Any, serialCom) -> None:
        self.serialCom = serialCom
        self.hwIndex = int(number)
        super().__init__(config, self.hwIndex)
        # sanity check the hwIndex
        if (
            self.hwIndex < 0 or
            self.hwIndex > 0x13F or            # Out of range
            self.hwIndex in range(0x40, 0x47)  # I2C Solenoid driver
        ):
            raise ValueError(
                "Invalid switch hwIndex: 0x{0:02x}".format(self.hwIndex)
            )

        # Enable / disable the debouncing with DEB command
        if config.debounce:
            self.serialCom.send("DEB {0:d} 1\n".format(self.hwIndex))
        else:
            self.serialCom.send("DEB {0:d} 0\n".format(self.hwIndex))

        # Enable PCF internal pullups
        if self.hwIndex >= 0x48:
            self.serialCom.send("HI {0:d}\n".format(self.hwIndex))

    def get_board_name(self):
        """Return the name of the board of this driver."""
        return "FanTasTic-board"
