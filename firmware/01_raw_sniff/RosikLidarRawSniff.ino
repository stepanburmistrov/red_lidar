void setup() {
  Serial.begin(115200);
  Serial2.begin(115200, SERIAL_8N1, 16, 17);   // RX2=16, TX2=17
  Serial.println("Raw sniff:");
}

void loop() {
  if (Serial2.available()) {
    uint8_t b = Serial2.read();
    Serial.print("0x");
    if (b < 0x10) Serial.print('0');
    Serial.print(b, HEX);
    Serial.println(' ');
  }
}