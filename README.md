# 每日廢話機 📜💬

> 每天醒來抬頭看一眼，給你一句神級廢話。  
> ESP32 + 2.13 吋電子紙 + 純離線優先 + 每週增量同步

![device](https://img.shields.io/badge/hardware-ESP32-blue) ![e-paper](https://img.shields.io/badge/display-2.13"_ePaper-lightgrey) ![battery](https://img.shields.io/badge/battery-1800mAh-green) ![discontinued](https://img.shields.io/badge/Waveshare-EOL-red)

---

## 🤔 為什麼做這個

廢話文學是中國互聯網最被低估的哲學流派。  
**「聽君一席話，如聽一席話」** — 短短幾個字，省你讀十年書。

這個項目讓一塊停產的電子紙模組每天給你一句神級廢話，搭配廢話指數 ★★★★★ 顯示。  
放辦公桌、放廁所、放床頭都行。抬頭就有心靈雞湯（誤）。

---

## ✨ 功能

- 📜 **每日一廢話** — 每天 0 點自動換一句（部分刷新 0.3s）
- ⭐ **廢話指數** — 每句有 1-5 星評級，5 星 = 神級廢話
- 🌐 **離線優先** — 內建 130 條精選，沒 WiFi 也能用
- 🔄 **每週增量同步** — 每 7 天連一次 WiFi 拉 GitHub 上的 JSON
- 🔋 **超省電** — 1800mAh 電池可撐 **2-3 個月**
- 📖 **週末長文** — 內建《武二郎廟碑文》等經典，分段顯示
- 🐱 **沒有內購** — 沒有訂閱、沒有廣告、沒有課金

---

## 🚀 快速開始（15 分鐘搞定）

### 1. 燒錄硬體

#### 1.1 接線
直接用 Waveshare 2.13" Cloud Module 模組上的腳位，**不用額外接線**：

| 腳位 | 功能 |
|------|------|
| GPIO 15 | EPD CS |
| GPIO 27 | EPD DC |
| GPIO 26 | EPD RST |
| GPIO 25 | EPD BUSY |
| GPIO 13 | EPD SCK |
| GPIO 14 | EPD MOSI |
| GPIO 12 | 按鈕 (KEY) |
| GPIO 36 | 電池電壓 ADC |
| Type-C | 供電 + 燒錄 |

#### 1.2 Arduino IDE 設定
1. 安裝 ESP32 board：  
   `檔案 → 偏好設定 → Additional Board URLs` 加入  
   `https://dl.espressif.com/dl/package_esp32_index.json`
2. 工具 → 開發板 → ESP32 Dev Module
3. 安裝函式庫：
   - `GxEPD2` (e-paper)
   - `ArduinoJson` v6+
   - `LittleFS` (ESP32 內建)

#### 1.3 設定 WiFi
複製 `firmware/wifi_config.h.example` 為 `firmware/wifi_config.h`，填入：
```cpp
#define WIFI_SSID  "你的 WiFi 名稱"
#define WIFI_PASS  "你的 WiFi 密碼"
```

#### 1.4 設定 GitHub URL
修改 `firmware/daily-feihua.ino` 裡的：
```cpp
#define JSON_URL  "https://raw.githubusercontent.com/你的帳號/daily-feihua/main/data/quotes.json"
```

#### 1.5 燒錄
- 工具 → Partition Scheme → **"Huge APP (3MB No OTA/1MB SPIFFS)"**  
  (因為 font_zh.h 有 ~400KB)
- 上傳

第一次開機會：
1. 連 WiFi → 抓 JSON → 存到 LittleFS
2. 顯示第一條廢話
3. 進 deep sleep

---

## 📁 專案結構

```
daily-feihua/
├── data/
│   └── quotes.json          # 130 條精選廢話（可手動加）
├── firmware/
│   ├── daily-feihua.ino     # 主程式
│   ├── font_zh.h            # 中文字型（自動生成，~380KB）
│   └── wifi_config.h        # WiFi 設定（git ignored）
├── scripts/
│   ├── generate_font.py     # 重新生成字型
│   ├── feihua_crawler.py    # 每週抓新廢話
│   └── quality_filter.py    # 品質過濾 + 評分
├── .github/workflows/
│   └── weekly-update.yml    # 每週日早上 8 點自動跑
└── docs/
    └── wiring.md
```

---

## 🤖 自動化

把這個 repo 推到 GitHub 後，`.github/workflows/weekly-update.yml` 會：
- 每週日早上 8 點（台北時間）
- 抓「廢話文學」相關超話的 RSS
- 跑品質過濾
- 自動重生成字型（如果加了新字）
- commit 推回 main

ESP32 模組會在每週連一次 WiFi 時，自動拿到新內容。

### 觸發手動更新
到 GitHub → Actions → 點 "Run workflow"

---

## 🎨 螢幕排版

```
┌────────────────────────────┐
│ 💬 每日廢話      06/16    │  ← 12px 標題 + 日期
│ ─────────────────────────  │
│                            │
│   聽君一席話，              │  ← 20px 主廢話
│   如聽一席話。              │  ← 自動斷行
│                            │
│                            │
│ 廢話指數 ★★★★★   第7天   │  ← footer + 電量
└────────────────────────────┘
```

---

## 🔋 功耗分析

| 模式 | 電流 | 持續時間 | 一天耗電 |
|------|------|----------|----------|
| Deep sleep | 10 µA | 24h × 6/7 = 20.6h | ~0.2 mAh |
| Wake + 顯示更新 | 25 mA | 5s × 1 = 5s | ~0.04 mAh |
| Wake + WiFi sync | 80 mA | 15s × 1/7 = 2s | ~0.06 mAh |
| **每日總計** | | | **~0.3 mAh** |
| 1800mAh 預估 | | | **~2000 天 (5+ 年)** |

實際會因 WiFi 連線成功率、自放電等打個 3 折，預估 **2-3 個月**。

---

## 🐛 常見問題

**Q: 螢幕沒反應？**  
A: 確認你用的是 2.13" 黑白版（SKU 對應 `GxEPD2_213_BN`）。如果你的版本是 B73 紅黑白三色，把 `display` 物件改用 `GxEPD2_213_B73`。

**Q: 顯示亂碼？**  
A: `font_zh.h` 沒編譯進去，確認檔案有在 firmware/ 資料夾裡。

**Q: WiFi 連不上？**  
A: SSID/密碼不對、或是 5GHz WiFi（這模組只支援 2.4GHz）。

**Q: 想加新廢話？**  
A: 直接編輯 `data/quotes.json` 加進去，重新燒一次 firmware，  
或推到 GitHub 等模組下週自動 sync。

**Q: 怎麼重置 WiFi 設定？**  
A: 長按按鈕 5 秒（程式會進 reset 模式 — TODO: 尚未實作，目前要重燒）。

---

## 🛠️ 進階玩法

### 改顯示排版
編輯 `firmware/daily-feihua.ino` 的 `renderDisplay()` 函式。

### 加自訂來源
在 `scripts/feihua_crawler.py` 的 `SOURCES` 列表加新來源。

### 用 LLM 評分
把 `quality_filter.py` 的 `heuristic_level` 換成呼叫 OpenAI API。

### 改字體大小
`generate_font.py` 的 `FONT_SIZES` 改 `[16, 24]`，重新跑。

### 改成 7.5 吋大螢幕
換 `GxEPD2_750` 類別，重新編譯。

---

## 📜 廢話金句

這個項目最有 sense 的 5 條：

1. 聽君一席話，如聽一席話。
2. 我曾在極度憕怒的情況下極度憕怒！
3. 子曰：三人行，必有三人。
4. 俗話說得好：俗話說得好。
5. 7 日不見，如隔一週。

---

## 📄 License

MIT — 隨便用，但記得也做一個給你自己笑。

---

## 🙏 致謝

- 廢話文學原作者：全體中國網民（B 站評論區為發源地）
- 《武二郎廟碑文》：《梁山民間故事》
- 硬體：Waveshare 2.13" e-Paper Cloud Module
- 寫程式：Mavis（你的 AI 助理）

🌟 覺得有用，給個 star，你的支持是我繼續寫廢話的動力。  
（雖然事實上，你不 star 我也會繼續寫，廢話文學的精神就是如此。）
