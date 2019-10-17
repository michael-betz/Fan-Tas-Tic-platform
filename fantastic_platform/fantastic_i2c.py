from mpf.platforms.interfaces.switch_platform_interface import \
    I2cPlatformInterface


class FanTasTicI2c(I2cPlatformInterface):
    """
    Represents a device with a certain address
    on one of the four I2C channels
    """
    __slots__ = ["platform", "address"]

    def __init__(self, number: str, serialCom) -> None:
        super().__init__(number)
        self.serialCom = serialCom
        ch, adr = number.split("-")
        self.channel = int(ch)
        self.address = int(adr)  # 7 bit I2C address
        if 0 > self.channel > 3:
            raise RuntimeError("Invalid I2C channel {:}".format(self.channel))
        if 0 > self.address > 127:
            raise RuntimeError("Invalid I2C address {:}".format(self.address))

    def i2c_write8(self, register, value):
        self.serialCom.send("I2C {:d} {:d} {:02x}{:02x} 0\n".format(
            self.channel, self.address, register & 0xFF, value & 0xFF
        ))

    async def i2c_read8(self, register):
        self.serialCom.send("I2C {:d} {:d} {:02x} 1\n".format(
            self.channel, self.address, register & 0xFF
        ))
        data = 0
        return data & 0xFF

    async def i2c_read_block(self, register, count):
        self.serialCom.send("I2C {:d} {:d} {:02x} {:d}\n".format(
            self.channel, self.address, register & 0xFF, count
        ))
        result = []
        return result
