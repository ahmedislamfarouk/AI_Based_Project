"""
MAX30102 Heart Rate and SpO2 Sensor Driver
Uses smbus2 for I2C communication on Linux (e.g., Jetson Nano, Raspberry Pi).
Falls back to mock mode if the sensor is unavailable.
"""

import time
import threading
import statistics
import random
import math

try:
    from smbus2 import SMBus
    _SMBUS_AVAILABLE = True
except ImportError:
    _SMBUS_AVAILABLE = False

# MAX30102 Register Addresses
MAX30102_I2C_ADDR = 0x57

REG_INTR_STATUS_1 = 0x00
REG_INTR_STATUS_2 = 0x01
REG_INTR_ENABLE_1 = 0x02
REG_INTR_ENABLE_2 = 0x03
REG_FIFO_WR_PTR = 0x04
REG_OVF_COUNTER = 0x05
REG_FIFO_RD_PTR = 0x06
REG_FIFO_DATA = 0x07
REG_FIFO_CONFIG = 0x08
REG_MODE_CONFIG = 0x09
REG_SPO2_CONFIG = 0x0A
REG_LED1_PA = 0x0C  # Red LED
REG_LED2_PA = 0x0D  # IR LED
REG_PILOT_PA = 0x10
REG_MULTI_LED_CTRL1 = 0x11
REG_MULTI_LED_CTRL2 = 0x12
REG_TEMP_INTR = 0x1F
REG_TEMP_FRAC = 0x20
REG_TEMP_CONFIG = 0x21
REG_PROX_INT_THRESH = 0x30
REG_REV_ID = 0xFE
REG_PART_ID = 0xFF

# Mode configuration values
MODE_HR = 0x02
MODE_SPO2 = 0x03
MODE_MULTI_LED = 0x07
MODE_RESET = 0x40
MODE_SHDN = 0x80

# Default configuration constants
DEFAULT_LED_PA = 0x1F  # ~6.4mA pulse amplitude
DEFAULT_SPO2_CONFIG = 0x27  # ADC range 4096nA, 100Hz sample rate, 411us pulse width
DEFAULT_FIFO_CONFIG = 0x4F  # Sample average = 4, FIFO rollover enabled, almost full = 17


class MAX30102Sensor:
    """
    Driver for the MAX30102 pulse oximeter and heart-rate sensor.
    Supports real I2C communication via smbus2 and a realistic mock fallback.
    """

    def __init__(self, i2c_bus=1, address=MAX30102_I2C_ADDR):
        self.address = address
        self.i2c_bus_num = i2c_bus
        self.bus = None
        self._mock_mode = False
        self._lock = threading.Lock()

        # Circular buffer for the last 100 (ir, red) samples
        self._buffer_size = 100
        self._ir_buffer = [0] * self._buffer_size
        self._red_buffer = [0] * self._buffer_size
        self._buffer_index = 0
        self._buffer_filled = False

        # Heart rate state
        self._last_peak_time = None
        self._peak_intervals = []
        self._bpm = 0.0

        # SpO2 state
        self._spo2 = 98.0

        self._initialize()

    def _initialize(self):
        if not _SMBUS_AVAILABLE:
            print("[MAX30102] smbus2 not installed. Falling back to MOCK mode.")
            self._mock_mode = True
            return

        try:
            self.bus = SMBus(self.i2c_bus_num)
            # Soft reset
            self._write_register(REG_MODE_CONFIG, MODE_RESET)
            time.sleep(0.1)

            # Check if sensor responds by reading PART_ID (expected 0x15 for MAX30102)
            part_id = self._read_register(REG_PART_ID)
            if part_id is None:
                raise RuntimeError("No response from MAX30102 on I2C bus.")

            # Configure FIFO: sample avg=4, rollover=enabled, almost full=17
            self._write_register(REG_FIFO_CONFIG, DEFAULT_FIFO_CONFIG)
            # Configure SpO2 mode: ADC range 4096nA, 100Hz, pulse width 411us
            self._write_register(REG_SPO2_CONFIG, DEFAULT_SPO2_CONFIG)
            # Set LED pulse amplitude
            self._write_register(REG_LED1_PA, DEFAULT_LED_PA)
            self._write_register(REG_LED2_PA, DEFAULT_LED_PA)
            # Enter SpO2 mode
            self._write_register(REG_MODE_CONFIG, MODE_SPO2)
            # Clear FIFO pointers
            self._write_register(REG_FIFO_WR_PTR, 0x00)
            self._write_register(REG_OVF_COUNTER, 0x00)
            self._write_register(REG_FIFO_RD_PTR, 0x00)

            print(f"[MAX30102] Sensor initialized on bus {self.i2c_bus_num} (PART_ID=0x{part_id:02X}).")
        except Exception as e:
            print(f"[MAX30102] Initialization failed: {e}. Falling back to MOCK mode.")
            self._mock_mode = True
            if self.bus:
                try:
                    self.bus.close()
                except Exception:
                    pass
                self.bus = None

    def _write_register(self, reg, value):
        if self.bus:
            self.bus.write_byte_data(self.address, reg, value)

    def _read_register(self, reg):
        if self.bus:
            try:
                return self.bus.read_byte_data(self.address, reg)
            except Exception:
                return None
        return None

    def _read_fifo_sample(self):
        """
        Read one 6-byte sample from the FIFO and return (ir, red).
        Each LED value is 3 bytes (18 bits), MSB first.
        """
        try:
            data = self.bus.read_i2c_block_data(self.address, REG_FIFO_DATA, 6)
            red = (data[0] << 16) | (data[1] << 8) | data[2]
            ir = (data[3] << 16) | (data[4] << 8) | data[5]
            # Mask to 18 bits
            red &= 0x3FFFF
            ir &= 0x3FFFF
            return ir, red
        except Exception:
            return None, None

    def _mock_sample(self):
        """Generate realistic fluctuating IR/RED values for mock mode."""
        t = time.time()
        # Simulate a pulse waveform
        base_ir = 100000
        base_red = 90000
        # Heartbeat oscillation ~1.2 Hz (72 BPM)
        osc = math.sin(2 * math.pi * 1.2 * t)
        ir = int(base_ir + osc * 8000 + random.gauss(0, 500))
        red = int(base_red + osc * 7000 + random.gauss(0, 500))
        # Ensure positive
        ir = max(0, ir)
        red = max(0, red)
        return ir, red

    def is_connected(self):
        """Check whether the sensor (or mock mode) is active."""
        if self._mock_mode:
            return True
        try:
            val = self._read_register(REG_PART_ID)
            return val is not None
        except Exception:
            return False

    def read_fifo(self):
        """
        Read the next (ir, red) sample from the FIFO.
        In mock mode, returns synthetic data.
        """
        if self._mock_mode:
            ir, red = self._mock_sample()
        else:
            ir, red = self._read_fifo_sample()
            if ir is None or red is None:
                # I2C transient failure; reuse last values
                with self._lock:
                    idx = (self._buffer_index - 1) % self._buffer_size
                    ir = self._ir_buffer[idx]
                    red = self._red_buffer[idx]

        with self._lock:
            self._ir_buffer[self._buffer_index] = ir
            self._red_buffer[self._buffer_index] = red
            self._buffer_index = (self._buffer_index + 1) % self._buffer_size
            if self._buffer_index == 0:
                self._buffer_filled = True

        return ir, red

    def _get_recent_samples(self, count=None):
        """Return the most recent count samples as two lists (ir, red)."""
        if count is None:
            count = self._buffer_size
        with self._lock:
            if not self._buffer_filled:
                count = min(count, self._buffer_index)
            idx = self._buffer_index
            ir = []
            red = []
            for i in range(1, count + 1):
                pos = (idx - i) % self._buffer_size
                ir.insert(0, self._ir_buffer[pos])
                red.insert(0, self._red_buffer[pos])
            return ir, red

    def _detect_peaks(self, signal):
        """
        Simple threshold-based peak detection.
        Returns list of peak indices.
        """
        if len(signal) < 3:
            return []
        mean_sig = statistics.mean(signal)
        try:
            std_sig = statistics.stdev(signal)
        except statistics.StatisticsError:
            std_sig = 0.0
        threshold = mean_sig + 0.5 * std_sig
        peaks = []
        for i in range(1, len(signal) - 1):
            if signal[i] > threshold and signal[i] > signal[i - 1] and signal[i] > signal[i + 1]:
                peaks.append(i)
        return peaks

    def get_heart_rate(self):
        """
        Compute BPM from recent IR samples using simple peak detection.
        Returns a float BPM value.
        """
        if self._mock_mode:
            # Realistic fluctuating HR
            self._bpm = 70.0 + random.gauss(0, 3)
            self._bpm = max(55.0, min(110.0, self._bpm))
            return self._bpm

        ir, _ = self._get_recent_samples(100)
        if len(ir) < 30:
            return self._bpm

        peaks = self._detect_peaks(ir)
        if len(peaks) < 2:
            return self._bpm

        # Compute intervals in seconds assuming 100 Hz sample rate
        intervals = []
        for i in range(1, len(peaks)):
            diff = peaks[i] - peaks[i - 1]
            if diff > 0:
                intervals.append(diff / 100.0)

        if not intervals:
            return self._bpm

        avg_interval = statistics.mean(intervals)
        if avg_interval > 0:
            self._bpm = 60.0 / avg_interval
            # Sanity clamp
            self._bpm = max(40.0, min(200.0, self._bpm))
        return self._bpm

    def get_spo2(self):
        """
        Compute SpO2 using the ratio-of-ratios method on recent samples.
        Returns a float percentage (0-100).
        """
        if self._mock_mode:
            self._spo2 = 97.0 + random.gauss(0, 1)
            self._spo2 = max(95.0, min(99.0, self._spo2))
            return self._spo2

        ir, red = self._get_recent_samples(100)
        if len(ir) < 30 or len(red) < 30:
            return self._spo2

        try:
            dc_ir = statistics.mean(ir)
            dc_red = statistics.mean(red)
            ac_ir = statistics.stdev(ir)
            ac_red = statistics.stdev(red)
        except statistics.StatisticsError:
            return self._spo2

        if dc_ir == 0 or dc_red == 0:
            return self._spo2

        ratio_ir = ac_ir / dc_ir
        ratio_red = ac_red / dc_red
        if ratio_ir == 0:
            return self._spo2

        r = ratio_red / ratio_ir
        # Basic empirical approximation
        spo2 = 110.0 - 25.0 * r
        spo2 = max(70.0, min(100.0, spo2))
        self._spo2 = spo2
        return self._spo2

    def get_raw_data(self):
        """Return the latest (ir, red) tuple."""
        with self._lock:
            idx = (self._buffer_index - 1) % self._buffer_size
            return self._ir_buffer[idx], self._red_buffer[idx]

    def close(self):
        """Release I2C resources."""
        if self.bus:
            try:
                self.bus.close()
            except Exception:
                pass
            self.bus = None
        print("[MAX30102] Sensor closed.")


if __name__ == "__main__":
    sensor = MAX30102Sensor()
    print(f"Connected: {sensor.is_connected()}")
    try:
        while True:
            ir, red = sensor.read_fifo()
            hr = sensor.get_heart_rate()
            spo2 = sensor.get_spo2()
            print(f"IR={ir}, RED={red}, HR={hr:.1f}, SpO2={spo2:.1f}")
            time.sleep(0.01)
    except KeyboardInterrupt:
        sensor.close()
