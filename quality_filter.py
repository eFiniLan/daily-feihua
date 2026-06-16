#!/usr/bin/env python3
"""
quality_filter.py — 对 _staging.json 里的候选废句做质量过滤 + 评分

策略：
  1. 长度过滤 (4-60 字)
  2. 用启发式规则初步打 level (1-5)
  3. 去重（与现有 quotes.json 内的）
  4. （可选）调用 LLM 给每条打分，level 排序
  5. 追加到 quotes.json，更新 version 字段

heuristic level 打分：
  - 包含「绕口令特征」(如 X 之 X、x 也是 x): +2
  - 包含「矛盾描述」: +1
  - 是「废话古诗」(改自古诗): +2
  - 长度 < 12 且包含「说/听/是/有」: +1
  - 默认 3
"""

import json
import re
import sys
import os
import time
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
JSON_PATH = ROOT / "quotes.json"
STAGING = ROOT / "_staging.json"


def heuristic_level(text):
    """启发式打分"""
    level = 3
    # 绕口令特征
    if re.search(r"(.+?)之\1", text) or re.search(r"(.+?)\1", text):
        level += 1
    if re.search(r"(还是|也是|还是|是.+?的)", text):
        level += 1
    # 矛盾描述
    if re.search(r"(厚厚的薄|薄如|五彩斑斓的)", text):
        level += 1
    # 废话古诗标记
    if any(kw in text for kw in ["曰", "若", "則", "不從", "子曰"]):
        level += 1
    # 引用 / 改写
    if "：" in text or re.search(r"[「」『』《》]", text):
        level += 1
    # 极短或极长降级
    if len(text) < 8:
        level -= 1
    if len(text) > 30:
        level -= 1
    return max(1, min(5, level))


def is_good(text):
    """质量过滤"""
    if not (4 <= len(text) <= 60):
        return False
    if not re.search(r"[\u4e00-\u9fff]", text):
        return False
    bad = ["转发", "微博", "链接", "http", "广告", "赞助"]
    for b in bad:
        if b in text:
            return False
    return True


def main():
    if not STAGING.exists():
        print("[filter] no staging file, nothing to do")
        return

    with open(STAGING, "r", encoding="utf-8") as f:
        candidates = json.load(f)
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    existing = {q["text"].strip() for q in data["quotes"]}
    max_id = max((q["id"] for q in data["quotes"]), default=0)

    accepted = []
    rejected = 0
    for c in candidates:
        text = c.get("text", "").strip()
        if text in existing:
            rejected += 1
            continue
        if not is_good(text):
            rejected += 1
            continue
        max_id += 1
        accepted.append({
            "id": max_id,
            "text": text,
            "level": heuristic_level(text),
            "category": c.get("category", "自動抓取"),
            "source": c.get("source", "auto"),
        })
        existing.add(text)

    if not accepted:
        print(f"[filter] no new quotes accepted (rejected {rejected})")
        STAGING.unlink()
        return

    # 追加
    data["quotes"].extend(accepted)
    data["count"] = len(data["quotes"])
    data["version"] = datetime.now().strftime("%Y-%m-%d")

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[filter] accepted {len(accepted)}, rejected {rejected}, total now {data['count']}")
    STAGING.unlink()
    print(f"[filter] updated {JSON_PATH}")


if __name__ == "__main__":
    main()
