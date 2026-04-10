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
        import glob
        # Common Linux serial port patterns
        potential_ports = [port, '/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyUSB0', '/dev/ttyUSB1']
        potential_ports.extend(glob.glob('/dev/ttyUSB*'))
        potential_ports.extend(glob.glob('/dev/ttyACM*'))
        
        # Unique set of ports
        potential_ports = list(dict.fromkeys(potential_ports))

        for p in potential_ports:
            try:
                self.ser = serial.Serial(p, baudrate, timeout=1)
                print(f"Connected to Biometric Sensor on {p}")
                return
            except (ConnectionError, serial.SerialException, FileNotFoundError):
                continue
        
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
