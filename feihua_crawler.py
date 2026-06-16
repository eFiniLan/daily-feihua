#!/usr/bin/env python3
"""
feihua_crawler.py — 每周从公开来源抓取新的废话文学

数据源（按优先级）：
  1. RSSHub 实例 (rsshub.app) → 微博「废话文学」超话 + 「废话」超话
  2. 网易云音乐「废话文学」相关歌单
  3. 公开博客合集 (知乎、公众号转载)

输出：append 到 data/quotes.json (注意去重)

注意：
  - 这是一个 stub，使用前需要根据 RSSHub 实例状况调整
  - 微信/小红书反爬严，初期不接入
  - 抓取后用 quality_filter.py 二次过滤
"""

import json
import os
import re
import sys
import time
import hashlib
from pathlib import Path
from datetime import datetime
import urllib.request
import urllib.parse
import urllib.error

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / "data" / "quotes.json"
RSSHUB = os.environ.get("RSSHUB_BASE", "https://rsshub.app")

# ---------------------------------------------------------------------------
# 来源定义
# ---------------------------------------------------------------------------
SOURCES = [
    {
        "name": "weibo-feihua-super-topic",
        "url": f"{RSSHUB}/weibo/super_topic/%E5%BA%9F%E8%AF%9D%E6%96%87%E5%AD%A6",
        "type": "rss",
        "min_length": 4,
        "max_length": 60,
    },
    {
        "name": "weibo-feihua-topic",
        "url": f"{RSSHUB}/weibo/search/%E5%BA%9F%E8%AF%9D",
        "type": "rss",
        "min_length": 4,
        "max_length": 60,
    },
    # 网易云音乐「废话文学」相关歌单评论
    {
        "name": "netease-feihua",
        "url": f"{RSSHUB}/163/playlist/123456789",  # TODO: 找到具体歌单 ID
        "type": "rss",
        "enabled": False,
    },
]


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def fetch(url, timeout=10):
    """简单 GET，返回 text"""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; feihua-bot/1.0)"
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        print(f"[fetch] {url} failed: {e}", file=sys.stderr)
        return ""


def parse_rss(xml):
    """从 RSS XML 抽出 <title> 列表"""
    titles = []
    # 简化解析（用 regex 够用）
    for m in re.finditer(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", xml, re.DOTALL):
        t = m.group(1).strip()
        if t and t != "微博超话":  # 跳过 RSS 标题
            titles.append(t)
    return titles


def is_garbage_quote(text):
    """基本过滤：长度 + 内容检查"""
    text = text.strip()
    if len(text) < 4 or len(text) > 60:
        return True
    # 跳过纯链接、广告、@、话题
    if text.startswith(("#", "@", "http", "【", "转发微博")):
        return True
    # 跳过纯标点
    if not re.search(r"[\u4e00-\u9fff]", text):
        return True
    return False


def hash_quote(text):
    """用归一化后的文本做 SHA1，方便去重"""
    # 去掉空白和标点
    norm = re.sub(r"[\s\W_]+", "", text)
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    # 读现有 JSON
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    existing_hashes = {hash_quote(q["text"]) for q in data["quotes"]}

    new_candidates = []
    for src in SOURCES:
        if not src.get("enabled", True):
            print(f"[skip] {src['name']} (disabled)")
            continue
        print(f"[fetch] {src['name']}: {src['url']}")
        xml = fetch(src["url"])
        if not xml:
            continue
        titles = parse_rss(xml)
        for t in titles:
            if is_garbage_quote(t):
                continue
            h = hash_quote(t)
            if h in existing_hashes:
                continue
            existing_hashes.add(h)
            new_candidates.append({
                "text": t,
                "level": 3,  # 默认中级，quality_filter 再调
                "category": "自動抓取",
                "source": src["name"],
            })
        time.sleep(1)  # 礼貌

    print(f"[crawl] found {len(new_candidates)} new candidates")

    # 写到 staging 區（quality_filter 再处理）
    STAGING = ROOT / "data" / "_staging.json"
    with open(STAGING, "w", encoding="utf-8") as f:
        json.dump(new_candidates, f, ensure_ascii=False, indent=2)
    print(f"[crawl] wrote staging to {STAGING}")


if __name__ == "__main__":
    main()
