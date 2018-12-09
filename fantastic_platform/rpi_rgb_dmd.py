"""
Contains support for the Raspi low-level RGB LED tile driver of hzeller
https://github.com/hzeller/rpi-rgb-led-matrix
"""
import logging
import asyncio
from mpf.core.platform import RgbDmdPlatform
from mpf.platforms.interfaces.dmd_platform import DmdPlatformInterface
from PIL import Image
import atexit
# the hzeller library (external dependency)
from rgbmatrix import RGBMatrix, RGBMatrixOptions


class RpiRgbDmd(RgbDmdPlatform):
    """Raspberry Pi GPIO RGB DMD."""
    __slots__ = ["_dmd", "config"]

    def __init__(self, machine):
        """Initialise RGB DMD."""
        super().__init__(machine)
        self.features['tickless'] = True
        self._dmd = None
        self.config = None
        atexit.register(self.stop)

    @classmethod
    def get_config_spec(cls):
        return "rpi_dmd", """
__valid_in__:       machine
console_log:        single|enum(none,basic,full)|none
file_log:           single|enum(none,basic,full)|basic
x_size:             single|int|32
y_size:             single|int|32
hardware_mapping:   single|str|regular
rows:               single|int|32
chain_length:       single|int|1
parallel:           single|int|1
pwm_bits:           single|int|11
pwm_lsb_nanoseconds: single|int|130
brightness:         single|int|100
scan_mode:          single|int|0
led_rgb_sequence:   single|str|RGB
disable_hardware_pulsing: single|bool|False
inverse_colors:     single|bool|False
gpio_slowdown:      single|int|1
debug:              single|bool|False
    """

    @asyncio.coroutine
    def initialize(self):
        """Initialise platform."""
        self.config = self.machine.config_validator.validate_config(
            config_spec='rpi_dmd',
            source=self.machine.config.get('rpi_dmd', {})
        )

    def stop(self):
        """Stop platform."""
        if self._dmd:
            self._dmd.stop()

    def __repr__(self):
        """Return string representation."""
        return '<Platform.RpiDmd>'

    def configure_rgb_dmd(self, name: str):
        """Configure rgb dmd."""
        if not self._dmd:
            self._dmd = RpiRgbDmdDevice(self.config)
        return self._dmd


class RpiRgbDmdDevice(DmdPlatformInterface):
    """A RpiRgbDmd device."""

    def __init__(self, config):
        """Initialise RpiRgbDmd device."""
        self.config = config
        xs = config["x_size"]
        ys = config["y_size"]
        self.img = Image.frombytes("RGB", (xs, ys), b'\x11' * xs * ys * 3)
        self.rgbOpts = RGBMatrixOptions()
        self.rgbOpts.drop_privileges = 0
        # Rudeboy way of setting the RGBMatrixOptions
        for k, v in config.items():
            if k in ("console_log", "file_log", "x_size", "y_size"):
                continue
            try:
                setattr(self.rgbOpts, k, v)
            except Exception:
                print("RpiRgbDmdDevice: couldn't set", k, v)
        self.matrix = RGBMatrix(options=self.rgbOpts)
        self.matrix.SetImage(self.img)

    def update(self, data):
        """Update DMD data."""
        self.img.frombytes(data)
        self.matrix.SetImage(self.img)

    def set_brightness(self, brightness: float):
        """ brightness [0.0 ... 1.0] """
        self.matrix.brightness = brightness * 100

    def stop(self):
        self.matrix.Clear()
