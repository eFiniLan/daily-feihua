/* ============================================================================
 * daily-feihua.ino — 每日廢話機
 * 適用於 Waveshare 2.13inch e-Paper Cloud Module (ESP32)
 *
 * 功能：
 *   - 每天 0 點自動更新一條廢話（部分刷新，0.3s）
 *   - 每 7 天連 WiFi 增量同步 GitHub 上的 JSON
 *   - 完全離線也能用 6 個月（1800mAh 電池）
 *   - 按鈕 (GPIO12) 短按 = 下一條，長按 = 重置 WiFi 設定
 *
 * 接線（直接用模組上的腳位，不需額外接線）：
 *   CS=15, RST=26, DC=27, BUSY=25, SCK=13, MOSI=14
 *   按鈕 = GPIO12, 電池ADC = GPIO36
 *
 * 編譯環境：Arduino IDE + ESP32 board + GxEPD2 + ArduinoJson + LittleFS
 * ============================================================================ */

#include <WiFi.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <ArduinoJson.h>
#include <LittleFS.h>
#include <Preferences.h>
#include <GxEPD2_BW.h>
#include <Adafruit_GFX.h>
#include <time.h>

#include "font_zh.h"
#include "wifi_config.h"

// ----------------------------------------------------------------------------
// 硬體腳位（Waveshare 2.13" Cloud Module 預設）
// ----------------------------------------------------------------------------
#define EPD_CS    15
#define EPD_DC    27
#define EPD_RST   26
#define EPD_BUSY  25
#define EPD_SCK   13
#define EPD_MOSI  14
#define BTN_PIN   12
#define BAT_ADC   36

// ----------------------------------------------------------------------------
// 顯示器
// ----------------------------------------------------------------------------
GxEPD2_BW<GxEPD2_213_BN, GxEPD2_213_BN::HEIGHT> display(
  GxEPD2_213_BN(/*cs=*/EPD_CS, /*dc=*/EPD_DC, /*rst=*/EPD_RST, /*busy=*/EPD_BUSY)
);

// ----------------------------------------------------------------------------
// 設定
// ----------------------------------------------------------------------------
#define SYNC_INTERVAL_DAYS   7
#define JSON_URL             "https://raw.githubusercontent.com/eFiniLan/daily-feihua/main/quotes.json"
#define NTP_SERVER           "pool.ntp.org"
#define TZ_OFFSET_SECONDS    8 * 3600    // 台北時間
#define BOOT_REASON_CHECK    1

// ----------------------------------------------------------------------------
// 全域狀態
// ----------------------------------------------------------------------------
Preferences prefs;
uint32_t bootCount = 0;
uint32_t epochDay = 0;        // 自 1970-01-01 起的天數，用來算今天該顯示第幾條
int      todayIdx = 0;        // 今天的 index
String   todayText = "";      // 今天的廢話內容
bool     isWeekend = false;   // 週末長文模式

// ----------------------------------------------------------------------------
// 內建 fallback 廢句（離線時保證有東西顯示）
// ----------------------------------------------------------------------------
static const char* FALLBACK[] = {
  "聽君一席話，如聽一席話。",
  "吃麵不吃蒜，等於沒吃蒜。",
  "上次這麼無語還是上次。",
  "子曰：三人行，必有三人。",
  "俗話說得好：俗話說得好。",
  "我曾在極度憤怒的情況下極度憤怒！",
  "七日不見，如隔一週。",
  "據我所知，我一無所知。",
};
static const int FALLBACK_COUNT = sizeof(FALLBACK) / sizeof(FALLBACK[0]);

// ----------------------------------------------------------------------------
// 工具函式
// ----------------------------------------------------------------------------

// 取自 1970-01-01 起的天數
uint32_t epochDayNow() {
  time_t now = time(nullptr);
  if (now < 100000) return bootCount;  // 沒同步時間就用開機次數代替
  return now / 86400;
}

// 取得台北時間
void syncTimeIfNeeded() {
  if (WiFi.status() == WL_CONNECTED) {
    configTime(TZ_OFFSET_SECONDS, 0, NTP_SERVER, "time.nist.gov");
    struct tm timeinfo;
    if (getLocalTime(&timeinfo, 5000)) {
      // 標記週末
      isWeekend = (timeinfo.tm_wday == 0 || timeinfo.tm_wday == 6);
    }
  }
}

// 從 LittleFS 載入 JSON
bool loadJsonFromFS(JsonDocument& doc) {
  if (!LittleFS.exists("/quotes.json")) return false;
  File f = LittleFS.open("/quotes.json", "r");
  if (!f) return false;
  DeserializationError err = deserializeJson(doc, f);
  f.close();
  if (err) {
    Serial.printf("JSON parse err: %s\n", err.c_str());
    return false;
  }
  return true;
}

// 從 GitHub 拉新版 JSON
bool syncFromCloud() {
  Serial.println("[sync] connecting WiFi...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(250);
    attempts++;
    Serial.print(".");
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\n[sync] WiFi failed, fallback");
    WiFi.mode(WIFI_OFF);
    return false;
  }
  Serial.println("\n[sync] WiFi OK");

  // 記下這次連到的 IP，供畫面底列顯示（即使後面 JSON 抓取失敗也已存好）
  prefs.putString("lastIP", WiFi.localIP().toString());

  // 先抓時間
  syncTimeIfNeeded();

  // 抓 JSON
  HTTPClient http;
  http.begin(JSON_URL);
  http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
  http.setTimeout(10000);
  int code = http.GET();
  if (code != 200) {
    Serial.printf("[sync] HTTP %d\n", code);
    http.end();
    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);
    return false;
  }
  String payload = http.getString();
  http.end();

  // 簡單校驗
  JsonDocument probe;
  if (deserializeJson(probe, payload.substring(0, 1024)) != DeserializationError::Ok) {
    Serial.println("[sync] bad JSON");
    WiFi.mode(WIFI_OFF);
    return false;
  }

  File f = LittleFS.open("/quotes.json", "w");
  if (!f) {
    Serial.println("[sync] cannot write FS");
    WiFi.mode(WIFI_OFF);
    return false;
  }
  f.print(payload);
  f.close();
  Serial.printf("[sync] saved %d bytes\n", payload.length());

  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);
  delay(100);
  return true;
}

// 決定今天該顯示哪一條
void pickTodayQuote() {
  // 先試 LittleFS
  JsonDocument doc;
  if (loadJsonFromFS(doc)) {
    JsonArray arr = doc["quotes"];   // 純字串陣列
    if (arr.size() > 0) {
      todayIdx  = epochDay % arr.size();
      todayText = arr[todayIdx].as<String>();
      Serial.printf("[pick] from FS idx=%d text=%s\n", todayIdx, todayText.c_str());
      return;
    }
  }
  // fallback
  todayIdx  = epochDay % FALLBACK_COUNT;
  todayText = FALLBACK[todayIdx];
  Serial.printf("[pick] fallback idx=%d\n", todayIdx);
}

// ----------------------------------------------------------------------------
// 顯示佈局
// ----------------------------------------------------------------------------

// ---- 自製 UTF-8 中文 blitter（font_zh.h 提供 font12 / font16）----------------

// 解碼一個 UTF-8 字元，回傳 codepoint，並把 p 前進到下一字
static uint32_t utf8Next(const char*& p) {
  uint8_t b = (uint8_t)*p++;
  if (b < 0x80) return b;
  if ((b >> 5) == 0x6)  { uint32_t c = b & 0x1F; c = (c << 6) | ((*p++) & 0x3F); return c; }
  if ((b >> 4) == 0xE)  { uint32_t c = b & 0x0F; c = (c << 6) | ((*p++) & 0x3F);
                          c = (c << 6) | ((*p++) & 0x3F); return c; }
  if ((b >> 3) == 0x1E) { uint32_t c = b & 0x07; for (int i = 0; i < 3; i++) c = (c << 6) | ((*p++) & 0x3F); return c; }
  return b;
}

// 在排序好的 glyph 表裡二分搜尋
static const ZHGlyph* zhFind(const ZHFont& f, uint16_t cp) {
  int lo = 0, hi = (int)f.count - 1;
  while (lo <= hi) {
    int mid = (lo + hi) >> 1;
    uint16_t c = f.glyphs[mid].cp;
    if (c == cp) return &f.glyphs[mid];
    if (c < cp)  lo = mid + 1; else hi = mid - 1;
  }
  return nullptr;
}

static void zhDrawGlyph(int x, int baseline, const ZHFont& f, const ZHGlyph* g) {
  int bpr = (g->w + 7) >> 3;
  for (int yy = 0; yy < g->h; yy++) {
    for (int xx = 0; xx < g->w; xx++) {
      if (f.bitmap[g->off + yy * bpr + (xx >> 3)] & (0x80 >> (xx & 7)))
        display.drawPixel(x + g->xoff + xx, baseline + g->yoff + yy, GxEPD_BLACK);
    }
  }
}

// 量測一段 UTF-8 文字的像素寬度
static int zhWidth(const ZHFont& f, const char* s) {
  int w = 0; const char* p = s;
  while (*p) { uint32_t cp = utf8Next(p); const ZHGlyph* g = zhFind(f, (uint16_t)cp); if (g) w += g->xadv; }
  return w;
}

// 從 (x, baseline) 畫一段 UTF-8 文字，回傳結束的 x
static int zhDraw(int x, int baseline, const ZHFont& f, const char* s) {
  const char* p = s;
  while (*p) {
    uint32_t cp = utf8Next(p);
    const ZHGlyph* g = zhFind(f, (uint16_t)cp);
    if (g) { zhDrawGlyph(x, baseline, f, g); x += g->xadv; }
  }
  return x;
}

// 依像素寬度自動斷行（CJK 沒空白，逐字測寬累加）
static int wrapUtf8(const ZHFont& f, const String& text, int maxWidthPx, String* out, int maxLines) {
  int n = 0, i = 0, L = text.length(), curW = 0;
  String cur = "";
  while (i < L && n < maxLines) {
    uint8_t b = (uint8_t)text[i];
    int clen = (b >= 0xF0) ? 4 : (b >= 0xE0) ? 3 : (b >= 0xC0) ? 2 : 1;
    if (i + clen > L) clen = 1;
    String ch = text.substring(i, i + clen);
    int chW = zhWidth(f, ch.c_str());
    if (curW + chW > maxWidthPx && cur.length() > 0) {
      out[n++] = cur; cur = ch; curW = chW;
    } else {
      cur += ch; curW += chW;
    }
    i += clen;
  }
  if (n < maxLines && cur.length() > 0) out[n++] = cur;
  return n;
}

void drawQuoteBlock() {
  const int lineH = 32;
  String lines[3];
  int n = wrapUtf8(font30, todayText, 234, lines, 3);   // 左右各留 8px
  // 大字主廢句，垂直置中於 2..104 區（baseOff 約等於字高的 ascent）
  int top = 2, bot = 104, baseOff = 24;
  int y = top + ((bot - top) - n * lineH) / 2 + baseOff;
  for (int i = 0; i < n; i++) {
    zhDraw(8, y, font30, lines[i].c_str());
    y += lineH;
  }
}

// 底列：右下角顯示「IP (電壓)」，整串靠右對齊
void drawFooter() {
  String ip = prefs.getString("lastIP", "");
  int raw = analogRead(BAT_ADC);
  float voltage = raw * 3.3f / 4095.0f * 3.0f;
  char buf[40];
  snprintf(buf, sizeof(buf), "%s | %.1fv", ip.length() ? ip.c_str() : "no ip", voltage);
  int w = zhWidth(font10, buf);
  zhDraw(250 - w, 120, font10, buf);
}

void renderDisplay() {
  display.setFullWindow();
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    drawQuoteBlock();
    drawFooter();
  } while (display.nextPage());
}

// ----------------------------------------------------------------------------
// 按鈕處理
// ----------------------------------------------------------------------------
void IRAM_ATTR onButtonISR() {
  // 在 ISR 裡只做標記，主迴圈處理
  // 用 debounce: 觸發 ext0 wakeup
}

// 檢查開機原因
bool wokeByButton() {
  return esp_sleep_get_wakeup_cause() == ESP_SLEEP_WAKEUP_EXT0;
}

// ----------------------------------------------------------------------------
// 設定與睡眠
// ----------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("\n[boot] daily-feihua starting...");

  // 腳位
  pinMode(BTN_PIN, INPUT_PULLUP);

  // 顯示器
  // Cloud Module 的 SPI 接在 SCK=13 / MOSI=14，不是 ESP32 預設腳位，
  // 必須先 remap，否則 GxEPD2 走預設腳位、螢幕不會有反應。
  SPI.end();
  SPI.begin(EPD_SCK, /*MISO=*/-1, EPD_MOSI, EPD_CS);
  display.init(115200);
  display.setRotation(3);   // 3 = 橫向 250x122 翻轉 180°（USB 朝上）

  // Preferences
  prefs.begin("feihua", false);
  bootCount = prefs.getUInt("bootCount", 0) + 1;
  prefs.putUInt("bootCount", bootCount);

  // File system
  if (!LittleFS.begin(true)) {
    Serial.println("[boot] LittleFS mount failed");
  }

  // 決定今天顯示哪一條
  epochDay = epochDayNow();
  pickTodayQuote();

  // 判斷是否要 sync
  uint32_t lastSync = prefs.getUInt("lastSyncDay", 0);
  bool shouldSync = (bootCount == 1) ||       // 第一次開機
                    ((epochDay - lastSync) >= SYNC_INTERVAL_DAYS);

  if (shouldSync) {
    Serial.println("[boot] syncing...");
    if (syncFromCloud()) {
      prefs.putUInt("lastSyncDay", epochDay);
      // 重新挑選（因為可能資料量變了）
      pickTodayQuote();
    }
  }

  // 顯示
  renderDisplay();

  // 進 deep sleep
  Serial.println("[boot] sleeping...");
  display.hibernate();
  delay(50);

  // wake sources
  esp_sleep_enable_timer_wakeup(24UL * 3600 * 1000000ULL);  // 24h
  esp_sleep_enable_ext0_wakeup((gpio_num_t)BTN_PIN, LOW);   // 按鈕

  esp_deep_sleep_start();
}

void loop() {
  // 永遠不會到這裡
}
