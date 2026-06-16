#!/usr/bin/env python3
"""
generate_feihua.py — 用 LLM 生成繁體中文「廢話文學」候選，寫到 _staging.json，
之後交給 quality_filter.py 過濾 / 評分 / 去重 / 併入 quotes.json。

預設使用 GitHub Models：在 GitHub Actions 內可直接用內建的 GITHUB_TOKEN，
不需要任何額外的 API 金鑰（workflow 需 `permissions: models: read`）。

可用環境變數切換到任何 OpenAI 相容端點：
  LLM_BASE_URL  端點 (預設 https://models.github.ai/inference)
  LLM_MODEL     模型 (預設 openai/gpt-4.1；可改成目錄裡更新/更強的模型)
  LLM_API_KEY   金鑰 (預設讀 GITHUB_TOKEN)
  FEIHUA_COUNT  一次生成幾句 (預設 20)

例：用 Google Gemini 免費層
  LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai \
  LLM_MODEL=gemini-2.5-flash LLM_API_KEY=xxx python generate_feihua.py
"""
import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STAGING = ROOT / "_staging.json"
QUOTES = ROOT / "quotes.json"

BASE_URL = os.environ.get("LLM_BASE_URL", "https://models.github.ai/inference").rstrip("/")
MODEL = os.environ.get("LLM_MODEL", "openai/gpt-4.1")
API_KEY = os.environ.get("LLM_API_KEY") or os.environ.get("GITHUB_TOKEN")
COUNT = int(os.environ.get("FEIHUA_COUNT", "20"))

SYSTEM = (
    "你是「廢話文學」大師。廢話文學的精髓是同義反覆、繞圈子、把一句話用更長的方式"
    "說回它自己，看似有理、深刻，其實什麼都沒說，因而好笑。經典範例："
    "「聽君一席話，如聽一席話」「俗話說得好：俗話說得好」"
    "「但凡這句話有一點意義，也不至於一點意義都沒有」「三人行，必有三人」。"
)


def build_user(existing):
    avoid = "、".join(existing[:12])
    return (
        f"請生成 {COUNT} 句【全新】的繁體中文廢話文學。要求：\n"
        f"1. 每句 6～28 個字，必須是繁體中文。\n"
        f"2. 風格要同義反覆 / 繞口 / 似深實空，幽默為上。\n"
        f"3. 彼此不重複，也不要和這些重複：{avoid}\n"
        f"只輸出一個 JSON 字串陣列，例如 [\"句一\",\"句二\"]，"
        f"不要任何解釋、編號或 markdown 圍籬。"
    )


def call_llm(messages):
    body = json.dumps({"model": MODEL, "messages": messages, "temperature": 1.0}).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-GitHub-Api-Version": "2026-03-10",  # GitHub Models 用；其他端點會忽略
    }
    req = urllib.request.Request(f"{BASE_URL}/chat/completions", data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"[gen] HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:300]}")
    return data["choices"][0]["message"]["content"]


def parse_quotes(text):
    text = text.strip()
    m = re.search(r"\[.*\]", text, re.DOTALL)  # 容錯：抓出 JSON 陣列部分
    if m:
        text = m.group(0)
    try:
        arr = json.loads(text)
    except json.JSONDecodeError:
        sys.exit(f"[gen] 無法解析模型輸出為 JSON：{text[:200]}")
    return [s.strip() for s in arr if isinstance(s, str) and s.strip()]


def main():
    if not API_KEY:
        sys.exit("[gen] 缺少金鑰：請設定 GITHUB_TOKEN 或 LLM_API_KEY")
    existing = []
    if QUOTES.exists():
        existing = [q["text"] for q in json.load(open(QUOTES, encoding="utf-8")).get("quotes", [])]

    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": build_user(existing)},
    ]
    print(f"[gen] {MODEL} @ {BASE_URL} → 生成 {COUNT} 句...")
    quotes = parse_quotes(call_llm(messages))
    print(f"[gen] 收到 {len(quotes)} 句候選")

    staging = [{"text": q, "source": f"ai:{MODEL}", "category": "AI生成"} for q in quotes]
    json.dump(staging, open(STAGING, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[gen] 已寫入 {STAGING}（交給 quality_filter.py 處理）")


if __name__ == "__main__":
    main()
