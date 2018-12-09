# MPF platform for FanTasTic

This is an external platform (driver) module for Mission Pinball 0.51+.

Install this platform using:

```bash
$ pip3 install -e .
```

Also install the python bindings of (rpi-rgb-led-matrix)[https://github.com/hzeller/rpi-rgb-led-matrix/tree/master/bindings/python#python-3].

Then use it in your `config.yaml` like this:

```yaml
hardware:
  rgb_dmd: rpi_dmd

rpi_dmd:
  cols: 32
  rows: 32
  gpio_slowdown: 2
  pwm_lsb_nanoseconds: 300
```
__Note__ all properties in
[core.pyx](https://github.com/hzeller/rpi-rgb-led-matrix/blob/master/bindings/python/rgbmatrix/core.pyx#L97)
are valid configuration keys in the `rpi_dmd` section.

__Caveat__ `mpf` must be run as root because the library needs to access `/dev/mem`.

More info here: [rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix)
