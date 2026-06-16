# 接線說明

## 硬體
- **Waveshare 2.13inch e-Paper Cloud Module** (停產 SKU)
- ESP32-WROOM-32 (4MB Flash)
- 2.13" 黑白電子紙顯示器 (250×122)
- 1800mAh 鋰電池 (內建充電電路)
- CP2102 USB-to-UART

## 預設腳位對照

| 模組腳位 | ESP32 GPIO | 功能 |
|----------|------------|------|
| EPD CS   | GPIO 15    | SPI Chip Select |
| EPD DC   | GPIO 27    | Data/Command |
| EPD RST  | GPIO 26    | Reset |
| EPD BUSY | GPIO 25    | Busy status |
| EPD SCK  | GPIO 13    | SPI Clock |
| EPD MOSI | GPIO 14    | SPI MOSI |
| KEY      | GPIO 12    | 使用者按鈕 |
| BAT_ADC  | GPIO 36    | 電池電壓偵測 (1/3 分壓) |
| VCC      | 3.3V       | 電源輸入 |
| GND      | GND        | 接地 |
| Type-C   | -          | USB 供電/燒錄/充電 |

## 額外可接 (選配)
- **GPIO 36** → 已內建電池分壓電阻，可以直接 `analogRead(36)` 讀電壓
- **GPIO 12** → 板載按鈕
- **GPIO 0** → 板載 BOOT 按鈕 (燒錄時用)

## 燒錄步驟
1. 用 Type-C 線接電腦
2. 確認 CP2102 驅動已裝 (macOS 內建，Windows 需裝)
3. Arduino IDE 選 ESP32 Dev Module
4. 選對的 COM port / serial port
5. 上傳

## 首次開機
1. 螢幕會閃爍（顯示器初始化）
2. 大約 10 秒內連上 WiFi（LED 會閃）
3. 抓 JSON、存檔、顯示第一條廢話
4. 進 deep sleep
5. 螢幕會持續顯示（電子紙特性）

## 異常排除
- **上傳失敗** → 按住 BOOT 按鈕時按一下 RESET
- **WiFi 連不上** → 確認 2.4GHz (這模組不支援 5GHz)
- **螢幕全白** → 檢查 SPI 線 (CS/SCK/MOSI 對應)
- **按鈕沒反應** → 確認 GPIO 12 設為 INPUT_PULLUP
