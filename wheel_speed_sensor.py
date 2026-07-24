#!/usr/bin/env python3
"""Wheel speed measurement using two KY-003 (A3144) Hall effect sensors on a Raspberry Pi 4.

Hardware setup
--------------
- Two KY-003 modules are mounted around the wheel's circumference, offset from
  each other by SENSOR_SEPARATION_DEG (default 90 degrees), both facing the
  same ring of equally-spaced magnets on the wheel.
- Every magnet trips sensor A once and sensor B once per revolution, so using
  both sensors doubles the pulse resolution compared to a single sensor and
  lets us tell rotation direction from which sensor fires first for a given
  magnet.
- KY-003 output (SIG/DO pin) is open-collector, pulled LOW when a magnet's
  south pole faces the marked side of the chip. Wire SIG to a GPIO pin, VCC
  to 3.3V or 5V (per your module), GND to GND.

Wiring (BCM numbering)
----------------------
Sensor A SIG -> GPIO17 (pin 11)
Sensor B SIG -> GPIO27 (pin 13)
VCC          -> 3V3 or 5V (check module silkscreen)
GND          -> GND
"""

import signal
import sys
import time
from collections import deque
from threading import Lock

import RPi.GPIO as GPIO

# ---- Configuration ---------------------------------------------------------

SENSOR_A_PIN = 17
SENSOR_B_PIN = 27

MAGNETS_PER_REV = 4          # number of equally-spaced magnets on the wheel
WHEEL_DIAMETER_M = 0.65      # wheel diameter in metres, for linear speed

DEBOUNCE_MS = 2              # ignore edges on the same pin closer than this
STALE_TIMEOUT_S = 2.0        # report 0 speed if no pulses arrive within this
PRINT_INTERVAL_S = 0.5

# Pulses produced by one full revolution, summed across both sensors.
PULSES_PER_REV = MAGNETS_PER_REV * 2

# ---- Shared state (written by GPIO callbacks, read by the main loop) ------

_lock = Lock()
_edge_log = deque(maxlen=32)   # recent (channel, timestamp) edges, for direction + instant speed
_pulse_count = 0               # total pulses since the last window snapshot
_last_edge_time = None


def _on_edge(channel):
    global _pulse_count, _last_edge_time
    now = time.monotonic()
    with _lock:
        _pulse_count += 1
        _last_edge_time = now
        _edge_log.append((channel, now))


def _setup_gpio():
    GPIO.setmode(GPIO.BCM)
    for pin in (SENSOR_A_PIN, SENSOR_B_PIN):
        # KY-003 output is open-collector; PUD_UP gives a clean HIGH at rest.
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(pin, GPIO.FALLING, callback=_on_edge, bouncetime=DEBOUNCE_MS)


def _snapshot_pulse_count():
    global _pulse_count
    with _lock:
        count, _pulse_count = _pulse_count, 0
        last_time = _last_edge_time
    return count, last_time


def _direction():
    """Infer rotation direction from which sensor fired first for the last magnet.

    Requires magnets spaced further apart (in degrees) than the two sensors'
    separation, so a single magnet's A/B pair of edges isn't interleaved with
    the next magnet's pair.
    """
    with _lock:
        if len(_edge_log) < 2:
            return None
        (chan_prev, _), (chan_last, _) = _edge_log[-2], _edge_log[-1]
    if chan_prev == chan_last:
        return None
    if chan_prev == SENSOR_A_PIN and chan_last == SENSOR_B_PIN:
        return "forward"
    if chan_prev == SENSOR_B_PIN and chan_last == SENSOR_A_PIN:
        return "reverse"
    return None


def _instantaneous_rpm():
    """Low-latency RPM estimate from the time between the last two edges.

    More responsive than the windowed count at low speed, since it doesn't
    need to wait for a full print interval to accumulate pulses.
    """
    with _lock:
        if len(_edge_log) < 2:
            return None
        (_, t_prev), (_, t_last) = _edge_log[-2], _edge_log[-1]
    dt = t_last - t_prev
    if dt <= 0:
        return None
    revs_per_pulse = 1.0 / PULSES_PER_REV
    return (revs_per_pulse / dt) * 60.0


def _windowed_rpm(pulses, window_s):
    if window_s <= 0:
        return 0.0
    return (pulses / PULSES_PER_REV) * (60.0 / window_s)


def _linear_speed_ms(rpm):
    circumference_m = 3.14159265358979 * WHEEL_DIAMETER_M
    return (rpm / 60.0) * circumference_m


def main():
    _setup_gpio()

    def cleanup(*_args):
        GPIO.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print("Measuring wheel speed. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(PRINT_INTERVAL_S)
            pulses, last_edge_time = _snapshot_pulse_count()

            now = time.monotonic()
            if last_edge_time is None or (now - last_edge_time) > STALE_TIMEOUT_S:
                rpm = 0.0
            else:
                rpm = _windowed_rpm(pulses, PRINT_INTERVAL_S)
                instant = _instantaneous_rpm()
                if instant is not None and rpm == 0.0:
                    rpm = instant

            speed_ms = _linear_speed_ms(rpm)
            direction = _direction() or "-"

            print(
                f"RPM: {rpm:6.1f}  Speed: {speed_ms:5.2f} m/s "
                f"({speed_ms * 3.6:5.2f} km/h)  Direction: {direction}"
            )
    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    main()
