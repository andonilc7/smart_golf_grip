// Seeed Studio XIAO ESP32C3 tactile sensor + LSM6DSOX streamer.
// Select XIAO_ESP32C3 and enable USB CDC On Boot in Arduino IDE.
// Wiring: see README.md. Muxes must be 3.3 V-compatible 74HC4067s.
// Sends one line per scan:
//   F,<70 raw readings>          order: A0B0, A0B1 ... A0B6, A1B0 ... A9B6
//   I,ax,ay,az,gx,gy,gz          accel m/s^2, gyro rad/s
// Lines starting with # are status messages.

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_LSM6DSOX.h>

#if !defined(ARDUINO_XIAO_ESP32C3)
#error "Select the Seeed Studio XIAO_ESP32C3 board; this pin map is board-specific."
#endif
#if !ARDUINO_USB_CDC_ON_BOOT
#error "Enable Tools > USB CDC On Boot so Serial uses the USB-C connector."
#endif

// D labels are XIAO board labels, not GPIO numbers.
const uint8_t rowSel[] = {D2, D3, D6, D7}; // GPIO 4,5,21,20; Mux A S0-S3
const uint8_t colSel[] = {D8, D9, D10};    // GPIO 8,9,10; Mux B S0-S2 ONLY
const size_t ROW_SELECT_BITS = sizeof(rowSel) / sizeof(rowSel[0]);
const size_t COL_SELECT_BITS = sizeof(colSel) / sizeof(colSel[0]);
// Mux A SIG connects directly to 3V3. Mux B S3 connects directly to GND.
// Mux B SIG -> 4.7k resistor -> D1; D1 -> 10k resistor -> GND.
// Both mux EN pins connect to GND. Leave D0/GPIO2 unused.
const uint8_t COL_SIG = D1;               // GPIO3 / ADC1_CH3
const int ROWS = 10, COLS = 7;     // 10 leads along the grip (Mux A), 7 around it (Mux B)
const long BAUD = 460800;                 // must match heatmap.py

int vals[ROWS][COLS];
Adafruit_LSM6DSOX imu;
bool imuOK = false;

void setMux(const uint8_t *pins, size_t count, int ch) {
  for (size_t i = 0; i < count; i++) digitalWrite(pins[i], (ch >> i) & 1);
}

void setup() {
  Serial.begin(BAUD);
  // Give a USB host time to connect, but also allow startup without a computer.
  const unsigned long started = millis();
  while (!Serial && millis() - started < 2000) delay(10);
  for (size_t i = 0; i < ROW_SELECT_BITS; i++) {
    digitalWrite(rowSel[i], LOW);
    pinMode(rowSel[i], OUTPUT);
  }
  for (size_t i = 0; i < COL_SELECT_BITS; i++) {
    digitalWrite(colSel[i], LOW);
    pinMode(colSel[i], OUTPUT);
  }
  pinMode(COL_SIG, INPUT);
  analogReadResolution(12);
  analogSetPinAttenuation(COL_SIG, ADC_11db);

  Wire.begin(D4, D5);                     // IMU: GPIO6 SDA, GPIO7 SCL
  Wire.setClock(400000);
  imuOK = imu.begin_I2C(0x6A, &Wire) || imu.begin_I2C(0x6B, &Wire);
  Serial.println("#XIAO ESP32C3: 10x7 tactile stream, 12-bit ADC, USB serial");
  Serial.println(imuOK ? "#IMU found" : "#IMU NOT found - check the IMU wires");
}

void loop() {
  // Scan all 70 points
  for (int a = 0; a < ROWS; a++) {
    setMux(rowSel, ROW_SELECT_BITS, a);
    for (int b = 0; b < COLS; b++) {
      setMux(colSel, COL_SELECT_BITS, b);
      delayMicroseconds(100);
      // Discard the first conversion after switching the analog path.
      analogRead(COL_SIG);
      vals[a][b] = analogRead(COL_SIG);
    }
  }

  // Send the frame
  Serial.print('F');
  for (int a = 0; a < ROWS; a++)
    for (int b = 0; b < COLS; b++) {
      Serial.print(',');
      Serial.print(vals[a][b]);
    }
  Serial.println();

  // Send IMU
  if (imuOK) {
    sensors_event_t accel, gyro, temp;
    imu.getEvent(&accel, &gyro, &temp);
    Serial.printf("I,%.2f,%.2f,%.2f,%.3f,%.3f,%.3f\n",
                  accel.acceleration.x, accel.acceleration.y, accel.acceleration.z,
                  gyro.gyro.x, gyro.gyro.y, gyro.gyro.z);
  }
  delay(10);
}
