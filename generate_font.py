#!/usr/bin/env python3
"""
generate_font.py — 為 daily-feihua 生成「子集中文點陣字型」(font_zh.h)

與舊版差異：
  - 舊版輸出 Adafruit GFX 格式，但 Adafruit_GFX 的 write() 只認單一 byte，
    無法處理多 byte UTF-8 / 繁體中文（first/last 還會被截成 8-bit）。
  - 新版輸出「codepoint 排序的 glyph 表 + 1bpp bitmap」，搭配 firmware 內
    自己的 UTF-8 解碼 + 二分搜尋 + drawPixel blitter（見 daily-feihua.ino）。

策略：
  1. 收集 quotes.json + firmware fallback 字串 + UI 標籤 + ASCII 用到的字
  2. 用 Noto Sans CJK TC 在目標像素高度渲染成 1bpp
  3. 依 unicode 排序輸出，方便 firmware 端二分搜尋

使用：
    python3 generate_font.py          # 旗標路徑為扁平 repo（與本檔同層）
產出：
    font_zh.h  (含 font12 與 font16 兩套字型)
"""

import json
import glob
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
JSON_PATH = ROOT / "quotes.json"
OUT_PATH = ROOT / "daily-feihua" / "font_zh.h"   # 直接寫進 Arduino sketch 資料夾

# 主字型來源：使用者自製的 opfonts 專案（IBM Plex Sans 子集，繁體 MOE 標準字集）
OPFONTS = Path("/home/ricklan/op/opfonts")
OPFONT_BOLD = OPFONTS / "dist" / "OpFont-Bold.otf"
OPFONT_REG  = OPFONTS / "dist" / "OpFont-Regular.otf"
# 後備字型：OpFont 缺字（如「斕」）時改用系統 Noto，避免顯示空白
NOTO_BOLD = "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc"
NOTO_REG  = "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"
NOTO_TC_FACE = 3  # .ttc 內的 Traditional Chinese 字面

# (size_px, name, 主字型, 後備字型)
#   font10 = 底列狀態；font30 = 主廢句（短句大字）；font24 = 長句自動縮小用
FONT_SIZES = [
    (10, "font10", str(OPFONT_BOLD), NOTO_BOLD),
    (24, "font24", str(OPFONT_REG),  NOTO_REG),
    (30, "font30", str(OPFONT_REG),  NOTO_REG),
]

# UI 標籤 + firmware 內建 fallback 廢句（必須一起進字型，否則離線時顯示空白）
UI_CHARS = "每日廢話指數第天VD/:.！？，。、；：「」『』（）《》0123456789"
FALLBACK_STRINGS = [
    "聽君一席話，如聽一席話。",
    "吃麵不吃蒜，等於沒吃蒜。",
    "上次這麼無語還是上次。",
    "子曰：三人行，必有三人。",
    "俗話說得好：俗話說得好。",
    "我曾在極度憤怒的情況下極度憤怒！",
    "七日不見，如隔一週。",
    "據我所知，我一無所知。",
]


def opfont_cjk_coverage():
    """opfonts 的 OTF 是依 charsets/*.txt 子集出來的，讀這些清單就知道含哪些漢字。"""
    cov = set()
    for f in glob.glob(str(OPFONTS / "charsets" / "*.txt")):
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if line:
                cov.add(line[0])
    return cov


def collect_codepoints():
    cps = set()
    # 把整份「教育部常用國字標準字體表」(4,808 字) 都收進來，
    # 這樣未來 AI 每週新生成的廢話用到任何常用字都已經有 glyph，
    # 裝置端不必在 CI 重新產字型。
    tc_std = OPFONTS / "charsets" / "tc_edu_standard_1.txt"
    if tc_std.exists():
        for line in open(tc_std, encoding="utf-8"):
            line = line.strip()
            if line:
                cps.add(ord(line[0]))
    for c in UI_CHARS:
        cps.add(ord(c))
    for s in FALLBACK_STRINGS:
        for c in s:
            cps.add(ord(c))
    if JSON_PATH.exists():
        data = json.load(open(JSON_PATH, encoding="utf-8"))
        for q in data.get("quotes", []):
            text = q if isinstance(q, str) else q.get("text", "")
            for c in text:
                cps.add(ord(c))
    # ASCII 可印字元
    for cp in range(0x20, 0x7F):
        cps.add(cp)
    # 只保留 BMP（firmware 用 uint16 存 codepoint）
    return sorted(cp for cp in cps if 0x20 <= cp <= 0xFFFF)


def render_glyph(font, baseline_ascent, descent, cp):
    """回傳 (bitmap_bytes, w, h, xoff, yoff, xadv)。baseline 固定在 baseline_ascent，
    讓主字型與後備字型畫在同一條基線上。bitmap 為 1bpp、每列 byte 對齊。"""
    ch = chr(cp)
    xadv = round(font.getlength(ch))
    H = baseline_ascent + descent + 4
    canvas_w = max(xadv, 1) + 6
    img = Image.new("L", (canvas_w, H), 0)
    d = ImageDraw.Draw(img)
    d.text((0, baseline_ascent), ch, font=font, fill=255, anchor="ls")  # 左對齊、基線對齊
    bbox = img.getbbox()
    if bbox is None:  # 空白字（如 space）
        return b"", 0, 0, 0, 0, xadv
    x0, y0, x1, y1 = bbox
    crop = img.crop(bbox)
    w, h = crop.size
    px = crop.load()
    bpr = (w + 7) // 8
    out = bytearray(bpr * h)
    for y in range(h):
        for x in range(w):
            if px[x, y] >= 128:
                out[y * bpr + (x >> 3)] |= (0x80 >> (x & 7))
    xoff = x0
    yoff = y0 - baseline_ascent  # 相對基線（上方為負）
    return bytes(out), w, h, xoff, yoff, xadv


def emit():
    cps = collect_codepoints()
    opcov = opfont_cjk_coverage()
    print(f"[gen] opfont charset coverage={len(opcov)} chars; total chars={len(cps)}")

    L = []
    L.append("// ============================================================================")
    L.append("// font_zh.h — 自動生成 (generate_font.py)，請勿手動編輯")
    L.append("// 來源字型: opfonts (OpFont-Bold 12px / OpFont-Regular 16px) + Noto 後備")
    L.append(f"// 字數: {len(cps)}")
    L.append("// 格式: codepoint 排序的 glyph 表 + 1bpp bitmap，搭配 firmware 端 UTF-8 blitter")
    L.append("// ============================================================================")
    L.append("#pragma once")
    L.append("#include <stdint.h>")
    L.append("")
    L.append("struct ZHGlyph {")
    L.append("  uint16_t cp;        // unicode codepoint (BMP)")
    L.append("  uint32_t off;       // bitmap 起始 offset")
    L.append("  uint8_t  w, h;      // bitmap 寬高")
    L.append("  int8_t   xoff, yoff;// 相對 cursor/baseline 的位移")
    L.append("  uint8_t  xadv;      // 水平前進量")
    L.append("};")
    L.append("struct ZHFont {")
    L.append("  const uint8_t* bitmap;")
    L.append("  const ZHGlyph* glyphs;  // 依 cp 升冪排序")
    L.append("  uint16_t count;")
    L.append("  uint8_t  yAdvance;      // 建議行高")
    L.append("};")
    L.append("")

    for size_px, name, primary_path, fallback_path in FONT_SIZES:
        primary = ImageFont.truetype(primary_path, size_px)
        try:
            fallback = ImageFont.truetype(fallback_path, size_px, index=NOTO_TC_FACE)
        except Exception:
            fallback = ImageFont.truetype(fallback_path, size_px)
        ascent, descent = primary.getmetrics()  # 以主字型基線為準

        bitmap = bytearray()
        glyphs = []  # (cp, off, w, h, xoff, yoff, xadv)
        nfallback = 0
        for cp in cps:
            ch = chr(cp)
            # CJK 漢字若不在 OpFont 字集內，改用 Noto 後備
            use_fallback = (0x4E00 <= cp <= 0x9FFF) and (ch not in opcov)
            font = fallback if use_fallback else primary
            if use_fallback:
                nfallback += 1
            bmp, w, h, xoff, yoff, xadv = render_glyph(font, ascent, descent, cp)
            glyphs.append((cp, len(bitmap), w, h, xoff, yoff, xadv))
            bitmap.extend(bmp)
        print(f"[gen] {name}: {len(glyphs)} glyphs, {len(bitmap)} bytes, {nfallback} via Noto fallback")

        L.append(f"// ---- {name} ({size_px}px, {len(glyphs)} glyphs, {len(bitmap)} bytes) ----")
        L.append(f"static const uint8_t {name}_bitmap[] = {{")
        for i in range(0, len(bitmap), 16):
            chunk = bitmap[i:i + 16]
            L.append("  " + ", ".join(f"0x{b:02x}" for b in chunk) + ",")
        L.append("};")
        L.append(f"static const ZHGlyph {name}_glyphs[] = {{")
        for (cp, off, w, h, xoff, yoff, xadv) in glyphs:
            L.append(f"  {{0x{cp:04X},{off:>6},{w:>2},{h:>2},{xoff:>3},{yoff:>3},{xadv:>2}}},")
        L.append("};")
        L.append(f"const ZHFont {name} = {{ {name}_bitmap, {name}_glyphs, "
                 f"{len(glyphs)}, {ascent + descent} }};")
        L.append("")

    OUT_PATH.write_text("\n".join(L), encoding="utf-8")
    print(f"[gen] wrote {OUT_PATH} ({OUT_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    emit()
