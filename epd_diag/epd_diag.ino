/* epd_diag.ino — minimal display diagnostic for the 2.13" Cloud Module.
 * NO Chinese font, NO JSON, NO WiFi, NO deep sleep — isolates the display
 * driver (panel class + rotation) from every other confounder.
 *
 * To try a different panel controller, change PANEL_CLASS below and re-flash.
 * Candidates for a Waveshare/TTGO 2.13" BW panel:
 *   GxEPD2_213_BN  (DEPG0213BN, SSD1680)   <-- current guess
 *   GxEPD2_213_B74 (GDEM0213B74, SSD1680, "DKE")
 *   GxEPD2_213_B73 (GDEH0213B73)
 *   GxEPD2_213_B72 (GDEH0213B72, SSD1675)
 *   GxEPD2_213     (GDE0213B1, old 128x250)
 */
#include <SPI.h>
#include <GxEPD2_BW.h>
#include <Fonts/FreeMonoBold9pt7b.h>

#define EPD_CS    15
#define EPD_DC    27
#define EPD_RST   26
#define EPD_BUSY  25
#define EPD_SCK   13
#define EPD_MOSI  14

// === change this one line to test a different controller ===
#define PANEL_CLASS GxEPD2_213_BN

GxEPD2_BW<PANEL_CLASS, PANEL_CLASS::HEIGHT> display(
  PANEL_CLASS(/*cs=*/EPD_CS, /*dc=*/EPD_DC, /*rst=*/EPD_RST, /*busy=*/EPD_BUSY)
);

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\n[diag] start");

  SPI.end();
  SPI.begin(EPD_SCK, /*MISO=*/-1, EPD_MOSI, EPD_CS);

  display.init(115200);
  display.setRotation(1);  // 1 = landscape 250x122 (the layout the app expects)
  Serial.printf("[diag] panel reports w=%d h=%d\n", display.width(), display.height());

  display.setFullWindow();
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    int W = display.width();
    int H = display.height();
    // double border around the WHOLE visible area
    display.drawRect(0, 0, W, H, GxEPD_BLACK);
    display.drawRect(2, 2, W - 4, H - 4, GxEPD_BLACK);
    // diagonal corner-to-corner
    display.drawLine(0, 0, W - 1, H - 1, GxEPD_BLACK);
    // solid box in the TOP-LEFT so orientation is unambiguous
    display.fillRect(6, 6, 34, 22, GxEPD_BLACK);
    // ASCII text (built-in font, no CJK)
    display.setFont(&FreeMonoBold9pt7b);
    display.setTextColor(GxEPD_BLACK);
    display.setCursor(50, 24);  display.print("EPD OK");
    display.setCursor(50, 50);  display.print("250 x 122");
    display.setCursor(8, H - 8); display.print("bottom-left");
  } while (display.nextPage());

  Serial.println("[diag] drawn, hibernating");
  display.hibernate();
}

void loop() {}
