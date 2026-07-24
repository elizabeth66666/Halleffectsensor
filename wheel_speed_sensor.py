#!/usr/bin/env python3
"""Wheel speed measurement using two KY-003 (A3144) Hall effect sensors on a Raspberry Pi 4.

Hardware setup
--------------
- Two KY-003 modules are mounted around the wheel's circumference, offset
  from each other by ~90 degrees, both facing the same ring of
  equally-spaced magnets on the wheel.
- Every magnet trips sensor A once and sensor B once per revolution, so
  using both sensors doubles the pulse resolution compared to a single
  sensor and lets us tell rotation direction from which sensor fires first
  for a given magnet.
- KY-003 output (SIG/DO pin) is open-collector, pulled LOW when a magnet's
  south pole faces the marked side of the chip.

Wiring (BCM numbering)
----------------------
Sensor A SIG -> GPIO17 (pin 11)
Sensor B SIG -> GPIO27 (pin 13)
VCC          -> 3V3 or 5V (check module silkscreen)
GND          -> GND

Why polling instead of interrupts
----------------------------------
Earlier versions used RPi.GPIO's add_event_detect() and then gpiozero's
when_pressed callbacks; both depend on the kernel's GPIO edge-detection
subsystem, which can silently fail to deliver edges on some Pi setups. This
version reads GPIO.input() directly in a tight loop instead - the same
memory-mapped register read Arduino's digitalRead() performs - so it has no
dependency on interrupt delivery at all. Run detect_magnet.py first to
confirm this baseline read works for your wiring before trusting the RPM
numbers below.
"""

import time

import RPi.GPIO as GPIO

# ---- Configuration ---------------------------------------------------------

SENSOR_A_PIN = 17
SENSOR_B_PIN = 27

MAGNETS_PER_REV = 4          # number of equally-spaced magnets on the wheel
WHEEL_DIAMETER_M = 0.65      # wheel diameter in metres, for linear speed

DEBOUNCE_S = 0.002           # ignore a new falling edge on the same pin sooner than this
STALE_TIMEOUT_S = 2.0        # report 0 speed if no pulses arrive within this
PRINT_INTERVAL_S = 0.5
POLL_SLEEP_S = 0.0005        # ~2 kHz poll rate: fast enough for short pulses, light on CPU

# Each magnet trips both sensors once per revolution.
PULSES_PER_REV = MAGNETS_PER_REV * 2


class SensorChannel:
    """Tracks one sensor pin and reports debounced falling edges via polling."""

    def __init__(self, pin):
        self.pin = pin
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.last_state = GPIO.input(pin)
        self.last_edge_time = None

    def poll(self, now):
        state = GPIO.input(self.pin)
        edge = False
        if self.last_state == GPIO.HIGH and state == GPIO.LOW:
            if self.last_edge_time is None or (now - self.last_edge_time) >= DEBOUNCE_S:
                self.last_edge_time = now
                edge = True
        self.last_state = state
        return edge


def _linear_speed_ms(rpm):
    circumference_m = 3.14159265358979 * WHEEL_DIAMETER_M
    return (rpm / 60.0) * circumference_m


def main():
    GPIO.setmode(GPIO.BCM)
    sensor_a = SensorChannel(SENSOR_A_PIN)
    sensor_b = SensorChannel(SENSOR_B_PIN)
    channels = ((SENSOR_A_PIN, sensor_a), (SENSOR_B_PIN, sensor_b))

    pulse_count = 0
    last_edge_time = None
    last_pulse_dt = None
    last_edge_pin = None
    prev_edge_pin = None
    direction = "-"

    window_start = time.monotonic()
    print("Measuring wheel speed. Press Ctrl+C to stop.")

    try:
        while True:
            now = time.monotonic()

            for pin, sensor in channels:
                if not sensor.poll(now):
                    continue
                pulse_count += 1
                if last_edge_time is not None:
                    last_pulse_dt = now - last_edge_time
                last_edge_time = now
                prev_edge_pin, last_edge_pin = last_edge_pin, pin
                # Two sensors offset ~90 degrees: the order a single magnet
                # trips them in reveals rotation direction, like a quadrature
                # encoder. Requires magnet spacing wider than the sensor
                # offset so one magnet's A/B pair isn't split by the next.
                if prev_edge_pin == SENSOR_A_PIN and last_edge_pin == SENSOR_B_PIN:
                    direction = "forward"
                elif prev_edge_pin == SENSOR_B_PIN and last_edge_pin == SENSOR_A_PIN:
                    direction = "reverse"

            elapsed = now - window_start
            if elapsed >= PRINT_INTERVAL_S:
                stale = last_edge_time is None or (now - last_edge_time) > STALE_TIMEOUT_S
                if stale:
                    rpm = 0.0
                    direction = "-"
                else:
                    rpm = (pulse_count / PULSES_PER_REV) * (60.0 / elapsed)
                    if rpm == 0.0 and last_pulse_dt:
                        rpm = (1.0 / PULSES_PER_REV) / last_pulse_dt * 60.0

                speed_ms = _linear_speed_ms(rpm)
                print(
                    f"RPM: {rpm:6.1f}  Speed: {speed_ms:5.2f} m/s "
                    f"({speed_ms * 3.6:5.2f} km/h)  Direction: {direction}"
                )

                pulse_count = 0
                window_start = now

            time.sleep(POLL_SLEEP_S)
    except KeyboardInterrupt:
        pass
    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    main()
