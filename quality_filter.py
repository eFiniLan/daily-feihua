#!/usr/bin/env python3
"""
quality_filter.py — 對 _staging.json 裡的候選廢句做品質過濾 + 去重，併入 quotes.json。

quotes.json 格式為「純字串陣列」：
  { "version": "...", "count": N, "quotes": ["句一", "句二", ...] }

策略：
  1. 長度過濾 (4-60 字) + 必須含中文 + 排除明顯垃圾
  2. 去重：與現有 quotes 比對，且用「去標點/空白後」的正規化字串抓近似重複
  3. 追加到 quotes.json 尾端，更新 count / version
"""

import json
import re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
JSON_PATH = ROOT / "quotes.json"
STAGING = ROOT / "_staging.json"


def normalize(text):
    """去掉空白與標點，用來偵測近似重複（如只差一個逗號的兩句）。"""
    return re.sub(r"[\s\W_]+", "", text)


def is_good(text):
    if not (4 <= len(text) <= 60):
        return False
    if not re.search(r"[一-鿿]", text):  # 必須含中文
        return False
    bad = ["轉發", "微博", "鏈接", "链接", "http", "廣告", "贊助"]
    return not any(b in text for b in bad)


def main():
    if not STAGING.exists():
        print("[filter] 沒有 _staging.json，無事可做")
        return

    candidates = json.load(open(STAGING, encoding="utf-8"))
    data = json.load(open(JSON_PATH, encoding="utf-8"))
    quotes = data.get("quotes", [])

    seen_norm = {normalize(q) for q in quotes}

    accepted, rejected = [], 0
    for c in candidates:
        text = (c if isinstance(c, str) else c.get("text", "")).strip()
        n = normalize(text)
        if not text or n in seen_norm or not is_good(text):
            rejected += 1
            continue
        seen_norm.add(n)
        accepted.append(text)

    if not accepted:
        print(f"[filter] 沒有新句被接受（拒絕 {rejected}）")
        STAGING.unlink()
        return

    quotes.extend(accepted)
    data["quotes"] = quotes
    data["count"] = len(quotes)
    data["version"] = datetime.now().strftime("%Y-%m-%d")

    json.dump(data, open(JSON_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[filter] 接受 {len(accepted)}，拒絕 {rejected}，目前共 {data['count']} 句")
    STAGING.unlink()
    print(f"[filter] 已更新 {JSON_PATH}")


if __name__ == "__main__":
    main()
