"""
Contains support for the Raspi low-level RGB LED tile driver of hzeller
https://github.com/hzeller/rpi-rgb-led-matrix
"""
import logging
import asyncio
from mpf.core.platform import RgbDmdPlatform
from mpf.platforms.interfaces.dmd_platform import DmdPlatformInterface
from PIL import Image
from rgbmatrix import RGBMatrix, RGBMatrixOptions
import atexit


class RpiRgbDmd(RgbDmdPlatform):
    """Raspberry Pi GPIO RGB DMD."""

    def __init__(self, machine):
        """Initialise RGB DMD."""
        super().__init__(machine)
        self.features['tickless'] = True

        self.log = logging.getLogger('RpiDmd')
        self.log.info("Configuring RpiDmd hardware interface.")

        self.config = self.machine.config_validator.validate_config(
            config_spec='rpi_dmd',
            source=self.machine.config['rpi_dmd']
        )

        self._dmd = None
        atexit.register(self.stop)

    @asyncio.coroutine
    def initialize(self):
        """Initialise platform."""
        pass

    def stop(self):
        """Stop platform."""
        if self._dmd:
            self._dmd.stop()

    def __repr__(self):
        """Return string representation."""
        return '<Platform.RpiDmd>'

    def configure_rgb_dmd(self, name: str):
        """Configure rgb dmd."""
        return RpiRgbDmdDevice(self.config)


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
        # Dirty brute force way of setting the RGBMatrixOptions ;)
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
        self.matrix.brightness = brightness * 100

    def stop(self):
        self.matrix.Clear()
