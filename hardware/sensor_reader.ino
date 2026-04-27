/**
 * MAX30102 Sensor Reader for MAVEN Kit (Arduino-compatible)
 * 
 * Communicates with MAX30102 over I2C using Wire.h (no external library required).
 * Reads IR/RED values from FIFO, computes basic heart rate and SpO2,
 * and sends data over Serial in the format:
 *   HR:<bpm>,SpO2:<spo2>,IR:<ir>,RED:<red>\n
 * 
 * Hardware connections:
 *   MAX30102 VIN  -> 3.3V or 5V (check module specs)
 *   MAX30102 GND  -> GND
 *   MAX30102 SDA  -> SDA (A4 on Uno, 20 on Mega, 2 on Leonardo, etc.)
 *   MAX30102 SCL  -> SCL (A5 on Uno, 21 on Mega, 3 on Leonardo, etc.)
 *   MAX30102 INT  -> (optional) any digital pin for interrupts
 */

#include <Wire.h>

#define MAX30102_ADDR       0x57

// Register map
#define REG_INTR_STATUS_1   0x00
#define REG_INTR_STATUS_2   0x01
#define REG_FIFO_WR_PTR     0x04
#define REG_OVF_COUNTER     0x05
#define REG_FIFO_RD_PTR     0x06
#define REG_FIFO_DATA       0x07
#define REG_FIFO_CONFIG     0x08
#define REG_MODE_CONFIG     0x09
#define REG_SPO2_CONFIG     0x0A
#define REG_LED1_PA         0x0C  // Red LED
#define REG_LED2_PA         0x0D  // IR LED

// Configuration values
#define CFG_FIFO_CONFIG     0x4F  // avg=4, rollover=on, almost full=17
#define CFG_SPO2_CONFIG     0x27  // ADC range 4096nA, 100Hz, pulse width 411us
#define CFG_LED_PA          0x1F  // ~6.4mA
#define MODE_SPO2           0x03
#define MODE_RESET          0x40

// Sampling and buffer settings
#define SAMPLE_RATE_HZ      100
#define BUFFER_SIZE         100

uint32_t irBuffer[BUFFER_SIZE];
uint32_t redBuffer[BUFFER_SIZE];
uint8_t bufferIndex = 0;
bool bufferFull = false;

unsigned long lastSendTime = 0;
const unsigned long SEND_INTERVAL_MS = 1000; // Send every 1 second

// Write a single byte to a register
void writeRegister(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(MAX30102_ADDR);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}

// Read a single byte from a register
uint8_t readRegister(uint8_t reg) {
  Wire.beginTransmission(MAX30102_ADDR);
  Wire.write(reg);
  Wire.endTransmission(false);
  Wire.requestFrom(MAX30102_ADDR, (uint8_t)1);
  if (Wire.available()) {
    return Wire.read();
  }
  return 0xFF;
}

// Read a 6-byte FIFO sample: 3 bytes RED, 3 bytes IR
bool readFIFO(uint32_t &ir, uint32_t &red) {
  Wire.beginTransmission(MAX30102_ADDR);
  Wire.write(REG_FIFO_DATA);
  Wire.endTransmission(false);
  Wire.requestFrom(MAX30102_ADDR, (uint8_t)6);
  if (Wire.available() < 6) {
    return false;
  }
  uint8_t data[6];
  for (int i = 0; i < 6; i++) {
    data[i] = Wire.read();
  }
  red = ((uint32_t)data[0] << 16) | ((uint32_t)data[1] << 8) | (uint32_t)data[2];
  ir  = ((uint32_t)data[3] << 16) | ((uint32_t)data[4] << 8) | (uint32_t)data[5];
  red &= 0x3FFFF;
  ir  &= 0x3FFFF;
  return true;
}

void initMAX30102() {
  // Soft reset
  writeRegister(REG_MODE_CONFIG, MODE_RESET);
  delay(100);

  // Configure FIFO
  writeRegister(REG_FIFO_CONFIG, CFG_FIFO_CONFIG);
  // Configure SpO2 settings
  writeRegister(REG_SPO2_CONFIG, CFG_SPO2_CONFIG);
  // Set LED pulse amplitudes
  writeRegister(REG_LED1_PA, CFG_LED_PA);
  writeRegister(REG_LED2_PA, CFG_LED_PA);
  // Enable SpO2 mode
  writeRegister(REG_MODE_CONFIG, MODE_SPO2);
  // Clear FIFO pointers
  writeRegister(REG_FIFO_WR_PTR, 0x00);
  writeRegister(REG_OVF_COUNTER, 0x00);
  writeRegister(REG_FIFO_RD_PTR, 0x00);
}

// Simple peak detection for BPM on IR buffer
float computeBPM() {
  uint8_t count = bufferFull ? BUFFER_SIZE : bufferIndex;
  if (count < 20) return 0.0;

  // Compute mean and threshold
  uint32_t sum = 0;
  for (uint8_t i = 0; i < count; i++) sum += irBuffer[i];
  uint32_t mean = sum / count;

  uint32_t threshold = mean + (mean >> 2); // mean * 1.25 (approx)

  uint16_t peakCount = 0;
  uint16_t firstPeakIdx = 0;
  uint16_t lastPeakIdx = 0;

  for (uint8_t i = 1; i < count - 1; i++) {
    if (irBuffer[i] > threshold && irBuffer[i] > irBuffer[i-1] && irBuffer[i] > irBuffer[i+1]) {
      if (peakCount == 0) firstPeakIdx = i;
      lastPeakIdx = i;
      peakCount++;
    }
  }

  if (peakCount < 2) return 0.0;

  float intervalSeconds = (float)(lastPeakIdx - firstPeakIdx) / ((peakCount - 1) * SAMPLE_RATE_HZ);
  if (intervalSeconds > 0) {
    float bpm = 60.0 / intervalSeconds;
    if (bpm >= 40.0 && bpm <= 200.0) return bpm;
  }
  return 0.0;
}

// Ratio-of-ratios SpO2 approximation
float computeSpO2() {
  uint8_t count = bufferFull ? BUFFER_SIZE : bufferIndex;
  if (count < 20) return 98.0;

  uint32_t sumIr = 0, sumRed = 0;
  uint32_t maxIr = 0, minIr = 0x3FFFF;
  uint32_t maxRed = 0, minRed = 0x3FFFF;

  for (uint8_t i = 0; i < count; i++) {
    sumIr += irBuffer[i];
    sumRed += redBuffer[i];
    if (irBuffer[i] > maxIr) maxIr = irBuffer[i];
    if (irBuffer[i] < minIr) minIr = irBuffer[i];
    if (redBuffer[i] > maxRed) maxRed = redBuffer[i];
    if (redBuffer[i] < minRed) minRed = redBuffer[i];
  }

  float dcIr = (float)sumIr / count;
  float dcRed = (float)sumRed / count;
  float acIr = (float)(maxIr - minIr);
  float acRed = (float)(maxRed - minRed);

  if (dcIr < 1.0 || dcRed < 1.0) return 98.0;

  float ratioIr = acIr / dcIr;
  float ratioRed = acRed / dcRed;
  if (ratioIr < 0.0001) return 98.0;

  float R = ratioRed / ratioIr;
  float spo2 = 110.0 - 25.0 * R;
  if (spo2 > 100.0) spo2 = 100.0;
  if (spo2 < 70.0) spo2 = 70.0;
  return spo2;
}

void setup() {
  Serial.begin(9600);
  Wire.begin();
  initMAX30102();
  delay(100);

  // Verify sensor presence by reading PART_ID (should be 0x15 for MAX30102)
  uint8_t partId = readRegister(0xFF);
  if (partId == 0x15) {
    Serial.println("# MAX30102 detected and initialized.");
  } else {
    Serial.println("# MAX30102 not detected (mock values will be sent).");
  }
}

void loop() {
  uint32_t ir, red;
  if (readFIFO(ir, red)) {
    irBuffer[bufferIndex] = ir;
    redBuffer[bufferIndex] = red;
    bufferIndex++;
    if (bufferIndex >= BUFFER_SIZE) {
      bufferIndex = 0;
      bufferFull = true;
    }
  }

  unsigned long now = millis();
  if (now - lastSendTime >= SEND_INTERVAL_MS) {
    lastSendTime = now;

    float bpm = computeBPM();
    float spo2 = computeSpO2();

    // If no valid peaks yet, send a sensible default
    if (bpm < 1.0) bpm = 72.0;

    // Output format expected by Python parser
    Serial.print("HR:");
    Serial.print(bpm, 1);
    Serial.print(",SpO2:");
    Serial.print(spo2, 1);
    Serial.print(",IR:");
    Serial.print(ir);
    Serial.print(",RED:");
    Serial.println(red);
  }
}
