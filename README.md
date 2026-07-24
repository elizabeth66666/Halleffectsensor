# Halleffectsensor

## Wheel speed with two KY-003 sensors (Raspberry Pi 4)

`wheel_speed_sensor.py` reads two KY-003 (A3144) Hall effect modules mounted
around a wheel's circumference, offset ~90 degrees from each other, both
facing a ring of equally-spaced magnets. It reports RPM, linear speed, and
rotation direction.

Wiring (BCM numbering):
- Sensor A `SIG` -> GPIO17 (pin 11)
- Sensor B `SIG` -> GPIO27 (pin 13)
- `VCC` -> 3V3 or 5V (per module), `GND` -> GND

Edit `MAGNETS_PER_REV` and `WHEEL_DIAMETER_M` at the top of the script to
match your wheel, then run:

```bash
pip install -r requirements.txt
python3 wheel_speed_sensor.py
```

If a magnet visibly triggers a sensor (e.g. its onboard LED lights up) but
the script never registers it, run `detect_magnet.py` first — it polls a
single sensor's pin directly and rules out GPIO backend/edge-detection
issues before you debug the RPM logic. Both scripts use `gpiozero` on the
`lgpio` backend rather than `RPi.GPIO`, since `RPi.GPIO`'s interrupt-driven
edge detection relies on the legacy sysfs GPIO interface that current
Raspberry Pi OS (Bookworm) removed, which is the usual cause of a sensor
that clearly works but produces no pulses in code.