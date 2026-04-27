import serial
import time
import numpy as np
import re

try:
    from modules.biometrics.max30102_interface import MAX30102Sensor
    _MAX30102_AVAILABLE = True
except ImportError:
    _MAX30102_AVAILABLE = False


class BiometricProcessor:
    """
    Unified biometric processor supporting MAX30102 (I2C), serial sensors,
    and mock fallback mode.
    """

    def __init__(self, port='/dev/ttyUSB0', baudrate=9600, source='auto'):
        self.source = source
        self.port = port
        self.baudrate = baudrate

        self.ser = None
        self.max30102 = None
        self._mode = None  # 'max30102', 'serial', 'mock'

        # State variables
        self.last_heart_rate = 70.0
        self.last_spo2 = 98.0
        self.last_eda = 100.0

        self._initialize_source()

    def _initialize_source(self):
        if self.source == 'max30102':
            self._try_max30102()
            if self._mode != 'max30102':
                print("[BiometricProcessor] MAX30102 requested but not available. Falling back to mock.")
                self._mode = 'mock'
            return

        if self.source == 'serial':
            self._try_serial()
            if self._mode != 'serial':
                print("[BiometricProcessor] Serial requested but not available. Falling back to mock.")
                self._mode = 'mock'
            return

        if self.source == 'mock':
            self._mode = 'mock'
            print("[BiometricProcessor] Running in MOCK biometric mode (explicit).")
            return

        # source == 'auto'
        self._try_max30102()
        if self._mode == 'max30102':
            return
        self._try_serial()
        if self._mode == 'serial':
            return
        self._mode = 'mock'
        print("[BiometricProcessor] No sensor found. Running in MOCK biometric mode.")

    def _try_max30102(self):
        if not _MAX30102_AVAILABLE:
            return
        try:
            self.max30102 = MAX30102Sensor()
            if self.max30102.is_connected():
                self._mode = 'max30102'
                print("[BiometricProcessor] MAX30102 connected via I2C.")
            else:
                self.max30102.close()
                self.max30102 = None
        except Exception as e:
            print(f"[BiometricProcessor] MAX30102 init error: {e}")
            if self.max30102:
                self.max30102.close()
                self.max30102 = None

    def _try_serial(self, port=None, baudrate=None):
        import glob
        p = port or self.port
        br = baudrate or self.baudrate
        potential_ports = [p, '/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyUSB0', '/dev/ttyUSB1']
        potential_ports.extend(glob.glob('/dev/ttyUSB*'))
        potential_ports.extend(glob.glob('/dev/ttyACM*'))
        potential_ports = list(dict.fromkeys(potential_ports))

        for candidate in potential_ports:
            try:
                self.ser = serial.Serial(candidate, br, timeout=1)
                print(f"[BiometricProcessor] Connected to Biometric Sensor on {candidate}")
                self._mode = 'serial'
                return
            except (ConnectionError, serial.SerialException, FileNotFoundError):
                continue
        self.ser = None

    def analyze_biometrics(self):
        if self._mode == 'max30102':
            return self._analyze_max30102()
        if self._mode == 'serial':
            return self._analyze_serial()
        return self._analyze_mock()

    def _analyze_max30102(self):
        try:
            # Pull a few samples to keep the buffer fresh
            for _ in range(5):
                self.max30102.read_fifo()
                time.sleep(0.01)
            bpm = self.max30102.get_heart_rate()
            spo2 = self.max30102.get_spo2()
            # MAX30102 does not provide EDA; keep a drifting mock EDA
            self.last_eda += np.random.normal(0, 5)
            self.last_eda = float(np.clip(self.last_eda, 0, 1000))
            self.last_heart_rate = float(bpm)
            self.last_spo2 = float(spo2)
        except Exception as e:
            return f"MAX30102 Error: {e}"
        return f"HR: {self.last_heart_rate:.1f}, SpO2: {self.last_spo2:.1f}%, EDA: {self.last_eda:.1f}"

    def _analyze_serial(self):
        if self.ser is None or not self.ser.is_open:
            return self._analyze_mock()

        try:
            line = self.ser.readline().decode('utf-8', errors='ignore').strip()
            if not line:
                # No new data; return last known values
                return f"HR: {self.last_heart_rate:.1f}, SpO2: {self.last_spo2:.1f}%, EDA: {self.last_eda:.1f}"

            # Try new format first: HR:{bpm},SpO2:{spo2},IR:{ir},RED:{red}
            if 'HR:' in line and 'SpO2:' in line:
                hr_match = re.search(r'HR:([\d.]+)', line)
                spo2_match = re.search(r'SpO2:([\d.]+)', line)
                if hr_match:
                    self.last_heart_rate = float(hr_match.group(1))
                if spo2_match:
                    self.last_spo2 = float(spo2_match.group(1))
                # EDA may not be present from the new Arduino sketch; keep drifting mock
                self.last_eda += np.random.normal(0, 5)
                self.last_eda = float(np.clip(self.last_eda, 0, 1000))
            elif ',' in line:
                parts = line.split(',')
                # Old format: HR,EDA or HR,SpO2,EDA
                if len(parts) >= 2:
                    self.last_heart_rate = float(parts[0])
                    self.last_eda = float(parts[1])
                if len(parts) >= 3:
                    try:
                        self.last_spo2 = float(parts[1])
                        self.last_eda = float(parts[2])
                    except ValueError:
                        pass
            return f"HR: {self.last_heart_rate:.1f}, SpO2: {self.last_spo2:.1f}%, EDA: {self.last_eda:.1f}"
        except Exception as e:
            return f"Serial Error: {e}"

    def _analyze_mock(self):
        self.last_heart_rate += np.random.normal(0, 1)
        self.last_spo2 += np.random.normal(0, 0.2)
        self.last_eda += np.random.normal(0, 5)
        self.last_heart_rate = float(np.clip(self.last_heart_rate, 40, 180))
        self.last_spo2 = float(np.clip(self.last_spo2, 85, 100))
        self.last_eda = float(np.clip(self.last_eda, 0, 1000))
        return f"HR: {self.last_heart_rate:.1f}, SpO2: {self.last_spo2:.1f}%, EDA: {self.last_eda:.1f}"

    def close(self):
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
        if self.max30102:
            try:
                self.max30102.close()
            except Exception:
                pass
            self.max30102 = None

    def __del__(self):
        self.close()


if __name__ == "__main__":
    b_processor = BiometricProcessor()
    try:
        while True:
            data = b_processor.analyze_biometrics()
            print(f"Biometric Signal: {data}")
            time.sleep(1)
    except KeyboardInterrupt:
        b_processor.close()
