#include <Wire.h>
#include "MAX30205.h" // Assuming MAX30205 as it's common for body temp/pulse

MAX30205 bodyTempSensor;

const int GSR_PIN = A0; // Analog pin for Galvanic Skin Response
unsigned long lastMillis = 0;
const int interval = 1000; // 1 second interval

void setup() {
  Serial.begin(9600);
  Wire.begin();
  
  // Initialize MAX30205 if available, otherwise just use mock/analog
  bodyTempSensor.begin();
}

void loop() {
  if (millis() - lastMillis >= interval) {
    lastMillis = millis();

    // Read Heart Rate (Simplified: Using MAX30205 as a proxy or simple pulse sensor)
    // In a real scenario, you'd use a dedicated library for the MAX30200/MAX30205
    float heartRate = 72.0 + random(-2, 3); // Mock HR logic if library call isn't direct
    
    // Read GSR (EDA)
    int gsrValue = analogRead(GSR_PIN);
    float eda = (float)gsrValue;

    // Send data in format expected by Python: HR,EDA
    Serial.print(heartRate);
    Serial.print(",");
    Serial.println(eda);
  }
}
