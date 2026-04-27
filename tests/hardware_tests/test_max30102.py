#!/usr/bin/env python3
"""
Hardware test script for the MAX30102 pulse oximeter sensor.

Imports MAX30102Sensor, prints connection status, and continuously
reads heart rate, SpO2, and raw IR/RED values.

Usage:
    python3 tests/hardware_tests/test_max30102.py
"""

import sys
import os
import time

# Ensure the project modules are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from modules.biometrics.max30102_interface import MAX30102Sensor


def main():
    print("=" * 50)
    print("MAX30102 Hardware Test")
    print("=" * 50)

    sensor = MAX30102Sensor(i2c_bus=1, address=0x57)
    print(f"Sensor connected: {sensor.is_connected()}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            ir, red = sensor.read_fifo()
            hr = sensor.get_heart_rate()
            spo2 = sensor.get_spo2()
            print(
                f"IR={ir:7d} | RED={red:7d} | "
                f"HR={hr:6.1f} bpm | SpO2={spo2:5.1f}%"
            )
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[Test] Stopping MAX30102 test...")
    finally:
        sensor.close()
        print("[Test] Sensor closed.")


if __name__ == "__main__":
    main()
