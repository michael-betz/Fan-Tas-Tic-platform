from mpf.platforms.interfaces.i2c_platform_interface \
    import I2cPlatformInterface


class FanTasTicI2c(I2cPlatformInterface):
    """
    Represents a device with a certain address
    on one of the four I2C channels
    """
    __slots__ = ["platform", "address", "channel"]

    def __init__(self, number: str, platform) -> None:
        if type(number) is not str or '-' not in number:
            RuntimeError(
                "I2C number must be of format `<CHANNEL>-<I2C_ADDR[7]>`"
            )
        super().__init__(number)
        self.platform = platform
        ch, adr, = number.lower().replace('bus', '').split("-")
        self.channel = int(ch)
        self.address = int(adr)  # 7 bit I2C address
        if 0 > self.channel > 3:
            raise RuntimeError("Invalid I2C channel {:}".format(self.channel))
        if 0 > self.address > 127:
            raise RuntimeError("Invalid I2C address {:}".format(self.address))

    def i2c_write8(self, register, value):
        self.platform.debug_log(
            "i2c_write8() CH %x  ADDR %x  VAL %x",
            self.channel,
            self.address,
            value
        )
        # Crashes the firmware on init when servoController is used :(
        self.platform.serialCom.send("I2C {:d} {:d} {:02x}{:02x} 0\n".format(
            self.channel, self.address, register & 0xFF, value & 0xFF
        ))

    async def i2c_read_block(self, register, count):
        if self.platform.i2c_gotit.is_set():
            RuntimeError("I2C RX: another already in progress?")
        self.platform.serialCom.send("I2C {:d} {:d} {:02x} {:d}\n".format(
            self.channel, self.address, register & 0xFF, count
        ))
        await self.platform.i2c_gotit.wait()
        self.platform.i2c_gotit.clear()
        rx_len = len(self.platform.i2c_rx_data)
        if rx_len != count:
            RuntimeError("I2C RX: Not received enough bytes, ", rx_len)
        return self.platform.i2c_rx_data

    async def i2c_read8(self, register):
        return self.i2c_read_block(register, 1)
