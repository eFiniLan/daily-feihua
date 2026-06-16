/* wifi_test.ino — 獨立 WiFi 連線診斷
 * 不碰電子紙 / JSON / 睡眠，只測：連線 → DNS/NTP → HTTPS 抓取。
 * 用同一份 wifi_config.h（SSID / 密碼）。結果全部印到 serial @115200。
 */
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <time.h>
#include "wifi_config.h"

// 測試抓取用的公開檔案（證明 DNS + 路由 + HTTPS 都通）
#define TEST_URL "https://raw.githubusercontent.com/octocat/Hello-World/master/README"

static const char* statusName(wl_status_t s) {
  switch (s) {
    case WL_NO_SSID_AVAIL: return "NO_SSID_AVAIL (找不到此 SSID — 名稱錯或非 2.4GHz)";
    case WL_CONNECT_FAILED: return "CONNECT_FAILED (密碼錯?)";
    case WL_CONNECTION_LOST: return "CONNECTION_LOST";
    case WL_DISCONNECTED: return "DISCONNECTED";
    case WL_IDLE_STATUS: return "IDLE";
    case WL_CONNECTED: return "CONNECTED";
    default: return "UNKNOWN";
  }
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\n\n===== WiFi 測試開始 =====");
  Serial.printf("目標 SSID: \"%s\"\n", WIFI_SSID);

  // 先掃描，確認這個 SSID 在不在範圍內 + 訊號強度
  Serial.println("[scan] 掃描中...");
  int n = WiFi.scanNetworks();
  bool seen = false;
  for (int i = 0; i < n; i++) {
    bool match = (WiFi.SSID(i) == String(WIFI_SSID));
    if (match) seen = true;
    Serial.printf("  %2d) %-28s RSSI=%4d ch=%2d %s\n",
                  i + 1, WiFi.SSID(i).c_str(), WiFi.RSSI(i), WiFi.channel(i),
                  match ? "  <-- 你的網路" : "");
  }
  Serial.printf("[scan] 共 %d 個網路；目標 SSID %s\n", n, seen ? "有掃到 ✅" : "沒掃到 ❌(名稱錯/5GHz/太遠)");

  // 連線
  Serial.println("[wifi] 連線中...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 15000) {
    delay(300);
    Serial.print(".");
  }
  Serial.println();
  wl_status_t st = WiFi.status();
  Serial.printf("[wifi] 狀態: %s\n", statusName(st));
  if (st != WL_CONNECTED) {
    Serial.println("===== 結果: WiFi 連線失敗 ❌ =====");
    return;
  }
  Serial.printf("[wifi] 連上了 ✅  IP=%s  RSSI=%d dBm  GW=%s\n",
                WiFi.localIP().toString().c_str(), WiFi.RSSI(),
                WiFi.gatewayIP().toString().c_str());

  // NTP（證明 DNS + 對外網路）
  Serial.println("[ntp] 對時中...");
  configTime(8 * 3600, 0, "pool.ntp.org", "time.nist.gov");
  struct tm ti;
  if (getLocalTime(&ti, 8000)) {
    char b[40]; strftime(b, sizeof(b), "%Y-%m-%d %H:%M:%S", &ti);
    Serial.printf("[ntp] 時間 OK ✅  台北時間: %s\n", b);
  } else {
    Serial.println("[ntp] 對時失敗 ⚠️ (連上 WiFi 但對外可能不通)");
  }

  // HTTPS 抓取
  Serial.println("[http] HTTPS GET 測試...");
  WiFiClientSecure client;
  client.setInsecure();              // 測試用：不驗證憑證
  HTTPClient http;
  http.begin(client, TEST_URL);
  http.setTimeout(10000);
  int code = http.GET();
  Serial.printf("[http] HTTP 回應碼: %d\n", code);
  if (code > 0) {
    String body = http.getString();
    Serial.printf("[http] 內容長度: %d bytes，開頭: %.40s\n", body.length(), body.c_str());
    Serial.println("===== 結果: WiFi + 對外網路 全部正常 ✅ =====");
  } else {
    Serial.printf("[http] 失敗: %s\n", http.errorToString(code).c_str());
    Serial.println("===== 結果: 連上 WiFi 但 HTTPS 抓取失敗 ⚠️ =====");
  }
  http.end();
  WiFi.disconnect(true);
}

void loop() {}
