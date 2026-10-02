/***********************************************************************
 * ROSiK LiDAR UART bridge + 8-sector WS2812 ring
 *
 * LiDAR input: Camsense/Xiaomi-style 36-byte packets
 *   55 AA 03 08 | speed(2) | start(2) | 8*(dist(2)+quality(1)) | end(2) | tail(2)
 *
 * Host output: binary full-scan frames over USB Serial (UART0), 460800 baud.
 * The packet format is documented in docs/PROTOCOL.md.
 *
 * Optional: one-byte red-sector mask on GPIO4 / UART1 at 115200 baud.
 ***********************************************************************/
#include <Arduino.h>
#include <FastLED.h>

// -------------------------- LiDAR ------------------------------------
static constexpr uint32_t LIDAR_BAUD = 115200;
static constexpr int LIDAR_RX_PIN = 16;  // LiDAR TX -> ESP32 RX2
static constexpr int LIDAR_TX_PIN = 17;  // normally unused
HardwareSerial &LIDAR = Serial2;

static constexpr uint8_t LIDAR_HDR[4] = {0x55, 0xAA, 0x03, 0x08};
static constexpr uint8_t LIDAR_BODY_LEN = 32;
static constexpr uint8_t HOST_INTENSITY_MIN = 2;
static constexpr uint8_t RING_INTENSITY_MIN = 15;
static constexpr float MAX_PACKET_SPREAD_DEG = 20.0f;

// -------------------------- Host UART --------------------------------
static constexpr uint32_t HOST_BAUD = 460800;
static constexpr uint8_t PROTO_VERSION = 1;
static constexpr uint8_t MSG_SCAN = 1;
static constexpr uint8_t MAGIC[4] = {'R', 'L', 'D', 'R'};

// Packed LiDAR fragment: start angle cdeg, end angle cdeg, 8 distances mm.
static constexpr size_t FRAME_LEN = 20;
static constexpr uint8_t MAX_FRAMES = 64;
static uint8_t scanBuf[MAX_FRAMES * FRAME_LEN];
static size_t scanLen = 0;
static uint8_t frameCount = 0;
static float prevStartAngle = -1.0f;
static uint32_t scanSequence = 0;

// -------------------------- 8-sector ring -----------------------------
#define LED_PIN      14
#define LED_COUNT    8
#define LED_TYPE     WS2812
#define COLOR_ORDER  GRB
#define BRIGHTNESS   60
CRGB leds[LED_COUNT];

static constexpr uint8_t NUM_SECTORS = 8;
static constexpr float NO_VALUE = 9.9e4f;
static constexpr float ALARM_DIST_MM = 150.0f;
static constexpr float WARNING_DIST_MM = 300.0f;
static constexpr uint32_t ALARM_HOLD_MS = 300;
static constexpr uint32_t STALE_MS = 500;
static constexpr uint8_t SECTOR_OFFSET = 7;

float sectorDist[NUM_SECTORS];
uint32_t sectorTime[NUM_SECTORS];
uint32_t alarmTill[NUM_SECTORS];

// Optional one-byte sector mask output, kept for compatibility.
static constexpr bool ENABLE_MASK_UART = true;
static constexpr int MASK_UART_TX_PIN = 4;
static constexpr uint32_t MASK_UART_BAUD = 115200;
HardwareSerial MASK_UART(1);
static constexpr uint32_t MASK_INTERVAL_MS = 100;

// -------------------------- helpers ----------------------------------
inline float decodeAngle(uint16_t raw) {
  float a = (float(raw) - 0xA000) / 64.0f;
  while (a < 0.0f) a += 360.0f;
  while (a >= 360.0f) a -= 360.0f;
  return a;
}

bool readBytes(HardwareSerial &serial, uint8_t *dst, size_t n,
               uint32_t timeoutMs = 300) {
  const uint32_t t0 = millis();
  size_t i = 0;
  while (i < n) {
    if (serial.available()) {
      dst[i++] = uint8_t(serial.read());
    } else {
      if (millis() - t0 > timeoutMs) return false;
      delay(0);
    }
  }
  return true;
}

bool waitLidarHeader(HardwareSerial &serial) {
  uint8_t pos = 0;
  const uint32_t t0 = millis();
  while (millis() - t0 <= 200) {
    if (!serial.available()) {
      delay(0);
      continue;
    }
    const uint8_t b = uint8_t(serial.read());
    if (b == LIDAR_HDR[pos]) {
      if (++pos == 4) return true;
    } else {
      // Handle an overlapping first header byte robustly.
      pos = (b == LIDAR_HDR[0]) ? 1 : 0;
    }
  }
  return false;
}

uint16_t crc16Update(uint16_t crc, uint8_t v) {
  crc ^= v;
  for (uint8_t i = 0; i < 8; ++i) {
    crc = (crc & 1) ? (crc >> 1) ^ 0xA001 : (crc >> 1);
  }
  return crc;
}

void writeU16LE(Stream &s, uint16_t v) {
  s.write(uint8_t(v & 0xFF));
  s.write(uint8_t(v >> 8));
}

void writeU32LE(Stream &s, uint32_t v) {
  s.write(uint8_t(v & 0xFF));
  s.write(uint8_t((v >> 8) & 0xFF));
  s.write(uint8_t((v >> 16) & 0xFF));
  s.write(uint8_t((v >> 24) & 0xFF));
}

uint16_t crcFeedU16(uint16_t crc, uint16_t v) {
  crc = crc16Update(crc, uint8_t(v & 0xFF));
  return crc16Update(crc, uint8_t(v >> 8));
}

uint16_t crcFeedU32(uint16_t crc, uint32_t v) {
  crc = crc16Update(crc, uint8_t(v & 0xFF));
  crc = crc16Update(crc, uint8_t((v >> 8) & 0xFF));
  crc = crc16Update(crc, uint8_t((v >> 16) & 0xFF));
  return crc16Update(crc, uint8_t((v >> 24) & 0xFF));
}

int angleToSector(float deg) {
  constexpr float W = 360.0f / NUM_SECTORS;
  float shifted = deg + W * 0.5f;
  while (shifted >= 360.0f) shifted -= 360.0f;
  while (shifted < 0.0f) shifted += 360.0f;
  int idx = int(shifted / W) % NUM_SECTORS;
  idx = (idx + SECTOR_OFFSET + NUM_SECTORS) % NUM_SECTORS;
  return idx;
}

void updateRingFromPacket(float startDeg, float endDeg,
                          const uint16_t dist[8], const uint8_t quality[8]) {
  float endUnwrapped = endDeg;
  if (endUnwrapped < startDeg) endUnwrapped += 360.0f;

  float localMin[NUM_SECTORS];
  for (uint8_t s = 0; s < NUM_SECTORS; ++s) localMin[s] = NO_VALUE;

  // 8 samples include both the start and end angle -> denominator is 7.
  for (uint8_t i = 0; i < 8; ++i) {
    if (quality[i] < RING_INTENSITY_MIN || dist[i] == 0 || dist[i] == 0x8000)
      continue;
    float a = startDeg + (endUnwrapped - startDeg) * (float(i) / 7.0f);
    while (a >= 360.0f) a -= 360.0f;
    const int sec = angleToSector(a);
    if (dist[i] < localMin[sec]) localMin[sec] = float(dist[i]);
  }

  const uint32_t now = millis();
  for (uint8_t s = 0; s < NUM_SECTORS; ++s) {
    if (localMin[s] != NO_VALUE) {
      sectorDist[s] = localMin[s];
      sectorTime[s] = now;
      if (localMin[s] < ALARM_DIST_MM) alarmTill[s] = now + ALARM_HOLD_MS;
    }
    if (now - sectorTime[s] > STALE_MS) sectorDist[s] = NO_VALUE;

    const bool red =
        (sectorDist[s] != NO_VALUE && sectorDist[s] < ALARM_DIST_MM) ||
        (int32_t(alarmTill[s] - now) > 0);

    if (red) {
      leds[s] = CRGB(255, 0, 0);
    } else if (sectorDist[s] != NO_VALUE && sectorDist[s] < WARNING_DIST_MM) {
      leds[s] = CRGB(255, 255, 0);
    } else {
      leds[s] = CRGB(0, 255, 0);
    }
  }
  FastLED.show();
}

void sendMaskIfDue() {
  if (!ENABLE_MASK_UART) return;
  static uint32_t lastMs = 0;
  const uint32_t now = millis();
  if (now - lastMs < MASK_INTERVAL_MS) return;
  lastMs = now;

  uint8_t mask = 0;
  for (uint8_t s = 0; s < NUM_SECTORS; ++s) {
    const bool red =
        (sectorDist[s] != NO_VALUE && sectorDist[s] < ALARM_DIST_MM) ||
        (int32_t(alarmTill[s] - now) > 0);
    if (red) mask |= uint8_t(1u << s);
  }
  MASK_UART.write(mask);
}

void appendScanFrame(float startDeg, float endDeg,
                     const uint16_t dist[8], const uint8_t quality[8]) {
  if (frameCount >= MAX_FRAMES || scanLen + FRAME_LEN > sizeof(scanBuf)) {
    frameCount = 0;
    scanLen = 0;
  }

  const uint16_t s = uint16_t(startDeg * 100.0f + 0.5f);
  const uint16_t e = uint16_t(endDeg * 100.0f + 0.5f);
  scanBuf[scanLen++] = uint8_t(s & 0xFF);
  scanBuf[scanLen++] = uint8_t(s >> 8);
  scanBuf[scanLen++] = uint8_t(e & 0xFF);
  scanBuf[scanLen++] = uint8_t(e >> 8);

  for (uint8_t i = 0; i < 8; ++i) {
    uint16_t d = 0;
    if (quality[i] >= HOST_INTENSITY_MIN && dist[i] != 0x8000) d = dist[i];
    scanBuf[scanLen++] = uint8_t(d & 0xFF);
    scanBuf[scanLen++] = uint8_t(d >> 8);
  }
  ++frameCount;
}

void sendHostScan() {
  if (frameCount < 30 || scanLen == 0) return;

  const uint16_t payloadLen = uint16_t(scanLen);
  const uint32_t sequence = scanSequence++;
  const uint32_t timestampMs = millis();

  // CRC covers header after MAGIC plus payload.
  uint16_t crc = 0xFFFF;
  crc = crc16Update(crc, PROTO_VERSION);
  crc = crc16Update(crc, MSG_SCAN);
  crc = crcFeedU16(crc, payloadLen);
  crc = crcFeedU32(crc, sequence);
  crc = crcFeedU32(crc, timestampMs);
  for (size_t i = 0; i < scanLen; ++i) crc = crc16Update(crc, scanBuf[i]);

  Serial.write(MAGIC, sizeof(MAGIC));
  Serial.write(PROTO_VERSION);
  Serial.write(MSG_SCAN);
  writeU16LE(Serial, payloadLen);
  writeU32LE(Serial, sequence);
  writeU32LE(Serial, timestampMs);
  Serial.write(scanBuf, scanLen);
  writeU16LE(Serial, crc);
}

bool readLidarPacket(float &startDeg, float &endDeg,
                     uint16_t dist[8], uint8_t quality[8]) {
  if (!waitLidarHeader(LIDAR)) return false;
  uint8_t body[LIDAR_BODY_LEN];
  if (!readBytes(LIDAR, body, sizeof(body))) return false;

  startDeg = decodeAngle(uint16_t(body[2]) | (uint16_t(body[3]) << 8));
  size_t off = 4;
  for (uint8_t i = 0; i < 8; ++i) {
    dist[i] = uint16_t(body[off]) | (uint16_t(body[off + 1]) << 8);
    quality[i] = body[off + 2];
    off += 3;
  }
  endDeg = decodeAngle(uint16_t(body[28]) | (uint16_t(body[29]) << 8));

  float spread = endDeg - startDeg;
  if (spread < 0.0f) spread += 360.0f;
  return spread <= MAX_PACKET_SPREAD_DEG;
}

void setup() {
  // IMPORTANT: Serial is binary-only after this point. Do not print debug text here.
  Serial.begin(HOST_BAUD);
  LIDAR.begin(LIDAR_BAUD, SERIAL_8N1, LIDAR_RX_PIN, LIDAR_TX_PIN);
  if (ENABLE_MASK_UART) MASK_UART.begin(MASK_UART_BAUD, SERIAL_8N1, -1, MASK_UART_TX_PIN);

  FastLED.addLeds<LED_TYPE, LED_PIN, COLOR_ORDER>(leds, LED_COUNT)
      .setCorrection(TypicalLEDStrip);
  FastLED.setBrightness(BRIGHTNESS);

  for (uint8_t i = 0; i < NUM_SECTORS; ++i) {
    sectorDist[i] = NO_VALUE;
    sectorTime[i] = 0;
    alarmTill[i] = 0;
    leds[i] = CRGB(0, 255, 0);
  }
  FastLED.show();
}

void loop() {
  float startDeg = 0.0f, endDeg = 0.0f;
  uint16_t dist[8];
  uint8_t quality[8];

  if (readLidarPacket(startDeg, endDeg, dist, quality)) {
    updateRingFromPacket(startDeg, endDeg, dist, quality);

    // Detect the 360->0 transition BEFORE appending the first frame of a new scan.
    const bool wrapped =
        prevStartAngle >= 0.0f && prevStartAngle > 300.0f && startDeg < 60.0f;
    if (wrapped && frameCount >= 30) {
      sendHostScan();
      scanLen = 0;
      frameCount = 0;
    }

    appendScanFrame(startDeg, endDeg, dist, quality);
    prevStartAngle = startDeg;
  }

  sendMaskIfDue();
}
