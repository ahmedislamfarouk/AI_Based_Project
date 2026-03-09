import serial
import time
import numpy as np

class BiometricProcessor:
    def __init__(self, port='/dev/ttyUSB0', baudrate=9600):
        # We scan for the first available port if default fails
        self.ser = None
        self._initialize_serial(port, baudrate)
        self.last_heart_rate = 70.0
        self.last_eda = 100.0

    def _initialize_serial(self, port, baudrate):
        try:
            self.ser = serial.Serial(port, baudrate, timeout=1)
            print(f"Connected to Biometric Sensor on {port}")
        except FileNotFoundError:
            # Try /dev/ttyACM0 for some Arduino models
            try:
                self.ser = serial.Serial('/dev/ttyACM0', baudrate, timeout=1)
                print(f"Connected to Biometric Sensor on /dev/ttyACM0")
            except Exception:
                print("No sensor found. Running in MOCK biometric mode.")

    def analyze_biometrics(self):
        if self.ser is None or not self.ser.is_open:
            # Mock data: fluctuates around baseline
            self.last_heart_rate += np.random.normal(0, 1)
            self.last_eda += np.random.normal(0, 5)
            # Clip values
            self.last_heart_rate = np.clip(self.last_heart_rate, 40, 180)
            self.last_eda = np.clip(self.last_eda, 0, 1000)
            return f"HR: {self.last_heart_rate:.1f}, EDA: {self.last_eda:.1f}"

        try:
            line = self.ser.readline().decode('utf-8', errors='ignore').strip()
            # Expecting format: HR,EDA
            if ',' in line:
                parts = line.split(',')
                self.last_heart_rate = float(parts[0])
                self.last_eda = float(parts[1])
            return f"HR: {self.last_heart_rate}, EDA: {self.last_eda}"
        except Exception as e:
            return f"Serial Error: {e}"

    def close(self):
        if self.ser:
            self.ser.close()

if __name__ == "__main__":
    b_processor = BiometricProcessor()
    try:
        while True:
            data = b_processor.analyze_biometrics()
            print(f"Biometric Signal: {data}")
            time.sleep(1)
    except KeyboardInterrupt:
        b_processor.close()
