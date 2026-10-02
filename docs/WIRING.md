# Wiring

## LiDAR -> ESP32

| LiDAR | ESP32 | Note |
|---|---|---|
| TX / DATA OUT | GPIO16 (RX2) | LiDAR stream, 115200 8N1 |
| RX | GPIO17 (TX2) | Normally not required |
| GND | GND | Common ground required |
| Power | according to your LiDAR board | Do not assume 3.3 V power |

## 8-pixel WS2812 ring

Data input -> **GPIO14**. Power the ring appropriately and share GND with the ESP32.

## Host computer

Use the ESP32 USB/programming serial port. Firmware sends binary data at **460800 baud**. Do not open Arduino Serial Monitor at the same time as the Python/ROS application.

## Optional sector-mask output

GPIO4 (UART1 TX) sends one byte every 100 ms. Bit `0..7` corresponds to the eight sectors; `1` means the sector is in the red/alarm state. This preserves compatibility with the original ring sketch.
