#!/usr/bin/env python3
"""Poll a single KY-003 Hall sensor and report magnet presence.

Python port of the Arduino "Detect a Magnet" sketch. Use this first to
confirm wiring and GPIO numbering before trusting the interrupt-driven
wheel_speed_sensor.py script — it polls the pin directly instead of relying
on edge-detection callbacks, so it will show a magnet even if
add_event_detect()/when_pressed callbacks aren't firing on your setup.
"""

import os

# Force the modern lgpio backend: RPi.GPIO's edge detection relies on the
# legacy sysfs GPIO interface, which Raspberry Pi OS Bookworm removed, and
# that's the usual reason a sensor visibly toggles but code never sees it.
os.environ.setdefault("GPIOZERO_PIN_FACTORY", "lgpio")

import time

from gpiozero import Button

SENSOR_PIN = 23  # change to test the other sensor (e.g. 27)


def main():
    # KY-003 output is open-collector: pull_up=True gives a clean HIGH at
    # rest, LOW ("pressed") when a magnet's south pole is near the sensor.
    sensor = Button(SENSOR_PIN, pull_up=True)
    print(f"Polling GPIO{SENSOR_PIN} (BCM). Press Ctrl+C to stop.")
    try:
        while True:
            print("MAGNET DETECTED" if sensor.is_pressed else "no magnet")
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
