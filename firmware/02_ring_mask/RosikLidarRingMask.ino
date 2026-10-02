/*******************************************************************
 *  ESP32 + 8-секторное кольцо WS2812 (FastLED)
 *******************************************************************/
#include <Arduino.h>
#include <FastLED.h>

/* ------------------- основные параметры ------------------- */
#define NUM_SECTORS 8              // 8 × 45°
#define LED_PIN      14
#define LED_COUNT    NUM_SECTORS
#define LED_TYPE     WS2812
#define COLOR_ORDER  GRB
#define BRIGHTNESS   60            // 0…255

CRGB leds[LED_COUNT];

/* ---------- аппаратные порты ---------- */
#define BAUDRATE       115200
#define LIDAR_RX_PIN   16          // UART2 RX
#define LIDAR_TX_PIN   17          // UART2 TX
#define UART_OUT_TX    4           // UART1 TX (выход маски)

HardwareSerial& LIDAR = Serial2;
HardwareSerial  UART1(1);

/* ---------- пороги дистанций ---------- */
#define ALARM_DIST      150        // <→красный
#define WARNING_DIST    300        // <→жёлтый
#define ALARM_HOLD_MS   300
static const float NO_VALUE = 9.9e4f;

/* ---------- тайминги ---------- */
const uint32_t STATUS_PRINT_INTERVAL = 100; // мс
const uint8_t  SECTOR_OFFSET = 7;           // «поворот» логических секторов

/* ---------- формат пакета TF03-LRS point cloud ---------- */
static const uint8_t HDR[] = { 0x55, 0xAA, 0x03, 0x08 };
constexpr uint8_t HDR_LEN  = 4;
constexpr uint8_t BODY_LEN = 32;

/* ---------- глобальные массивы ---------- */
float    sectorDist [NUM_SECTORS] = { 0 };
uint32_t sectorTime [NUM_SECTORS] = { 0 };
uint32_t alarmTill  [NUM_SECTORS] = { 0 };

/* ========================================================== */
/*                       ВСПОМОГАТЕЛЬНЫЕ                      */
/* ========================================================== */
bool readBytes(HardwareSerial& s, uint8_t* buf,
               size_t n, uint32_t tout = 500)
{
  uint32_t t0 = millis(); size_t i = 0;
  while (i < n) {
    if (s.available()) buf[i++] = s.read();
    if (millis() - t0 > tout) return false;
  }
  return true;
}

bool seekHeader(HardwareSerial& s)
{
  uint8_t pos = 0; uint32_t t0 = millis();
  while (millis() - t0 < 100) {
    if (s.available()) {
      uint8_t v = s.read();
      pos = (v == HDR[pos]) ? pos + 1 : 0;
      if (pos == HDR_LEN) return true;
    }
  }
  return false;
}

inline float decodeAngle(uint16_t raw)
{
  float d = (float)(raw - 0xA000) / 64.0f;
  if (d < 0)   d += 360.0f;
  if (d >= 360) d -= 360.0f;
  return d;
}

/* угол → сектор 0..7 (по 45°) c учётом SECTOR_OFFSET */
int angleToSector(float deg)
{
  constexpr float W = 360.0f / NUM_SECTORS;   // 45°
  float shifted = deg + W / 2.0f;
  if (shifted >= 360) shifted -= 360.0f;

  int idx = (int)(shifted / W) % NUM_SECTORS;
  idx = (idx + SECTOR_OFFSET + NUM_SECTORS) % NUM_SECTORS;
  return idx;
}

/* ========================================================== */
/*                   ПАРСИНГ ОДНОГО ПАКЕТА                    */
/* ========================================================== */
bool parsePacket()
{
  if (!seekHeader(LIDAR)) return false;

  uint8_t buf[BODY_LEN];
  if (!readBytes(LIDAR, buf, BODY_LEN)) return false;

  /* --- углы ------------------------------------------------ */
  uint16_t rawStart = buf[2]  | (buf[3]  << 8);
  uint16_t rawEnd   = buf[28] | (buf[29] << 8);
  float aStart = decodeAngle(rawStart);
  float aEnd   = decodeAngle(rawEnd);
  if (aEnd < aStart) aEnd += 360.0f;
  float aStep = (aEnd - aStart) / 7.0f; // 8 точек включают начальный и конечный углы

  /* --- локальные минимумы по секторам --------------------- */
  float tMin[NUM_SECTORS]; for (float& v : tMin) v = NO_VALUE;

  uint8_t off = 4;
  for (int i = 0; i < 8; ++i) {
    uint16_t dist  = buf[off] | (buf[off + 1] << 8);
    uint8_t  inten = buf[off + 2];
    off += 3;

    if (inten < 15) continue;                   // мусор
    float deg = aStart + i * aStep;
    if (deg >= 360) deg -= 360.0f;

    int sec = angleToSector(deg);
    if (dist < tMin[sec]) tMin[sec] = dist;
  }

  /* --- обновляем глобальные ------------------------------- */
  uint32_t now = millis();
  for (int s = 0; s < NUM_SECTORS; ++s) {
    if (tMin[s] != NO_VALUE) {
      sectorDist[s] = tMin[s];
      sectorTime[s] = now;
      if (tMin[s] < ALARM_DIST) alarmTill[s] = now + ALARM_HOLD_MS;
    }
    if (now - sectorTime[s] > 500) sectorDist[s] = NO_VALUE;
  }

  /* --- отрисовываем кольцо (FastLED) ---------------------- */
  for (int s = 0; s < NUM_SECTORS; ++s) {
    float d = sectorDist[s]; CRGB col;
    bool red = (d != NO_VALUE && d < ALARM_DIST) ||
               (now < alarmTill[s]);

    if (red)                           col = CRGB(255, 0, 0);
    else if (d != NO_VALUE && d < WARNING_DIST)
                                       col = CRGB(255, 255, 0);
    else                               col = CRGB(0, 255, 0);
    leds[s] = col;
  }
  FastLED.show();
  return true;
}

/* ========================================================== */
/*                            SETUP                           */
/* ========================================================== */
void setup()
{
  Serial.begin(BAUDRATE);

  LIDAR.begin(BAUDRATE, SERIAL_8N1, LIDAR_RX_PIN, LIDAR_TX_PIN);
  UART1.begin(BAUDRATE, SERIAL_8N1, -1, UART_OUT_TX);

  FastLED.addLeds<LED_TYPE, LED_PIN, COLOR_ORDER>(leds, LED_COUNT)
         .setCorrection(TypicalLEDStrip);
  FastLED.setBrightness(BRIGHTNESS);
  FastLED.show();

  Serial.println(F("ESP32 8-sector lidar visualiser [FastLED]"));
}

/* ========================================================== */
/*                            LOOP                            */
/* ========================================================== */
void loop()
{
  parsePacket();                              // при наличии — парсим

  /* --------- отправляем 1-байтовую маску красных ---------- */
  static uint32_t tMask = 0;
  if (millis() - tMask >= STATUS_PRINT_INTERVAL) {
    tMask = millis();

    uint8_t mask = 0;
    for (int s = 0; s < NUM_SECTORS; ++s) {
      bool red = (sectorDist[s] != NO_VALUE &&
                  sectorDist[s] < ALARM_DIST) ||
                 (millis() < alarmTill[s]);
      if (red) mask |= (1 << s);
    }
    UART1.write(mask); UART1.flush();

    Serial.print(F("MASK 0x"));
    if (mask < 0x10) Serial.print('0');
    Serial.println(mask, HEX);
  }
}