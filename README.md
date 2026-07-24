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