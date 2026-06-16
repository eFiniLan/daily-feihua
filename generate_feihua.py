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
    "你是「廢話文學（nonsense logic humor）」大師。廢話文學的精髓是：句子看似有邏輯、"
    "有道理、甚至深刻，但實際上沒有新增任何資訊。常見技法："
    "同義反覆（用不同說法重複同一件事）、定義循環（用結果解釋原因、用原因解釋結果）、"
    "明顯但無意義的因果、自我重複的語意閉環、看似哲學實則空洞、偽科學／偽統計／偽論文語氣。"
    "經典範例：「聽君一席話，如聽一席話」「成功之所以成功，是因為它成功了」"
    "「根據研究顯示，研究本身顯示了研究」「當你看到這句話時，你正在看到這句話」。"
)


def build_user(existing):
    avoid = "、".join(existing[:12])
    return (
        f"請生成 {COUNT} 句【全新】的繁體中文廢話文學，每句獨立成立、不需要上下文。\n"
        f"硬性要求：\n"
        f"1. 必須是繁體中文，每句約 6～28 字（要能顯示在小螢幕上）。\n"
        f"2. 每句都要「看似有邏輯但實際沒有新增資訊」，禁止提供真正有用的知識。\n"
        f"3. 語氣可混搭：學術論文 / 公司會議報告 / 校長致詞 / 股市分析 / 健身教練 / "
        f"戀愛語錄 / 古文成語改寫 / AI 與程式設計術語。\n"
        f"4. 【重要】至少一半要帶「網路原生梗」——只有常上網的人才懂的笑點，例如："
        f"甲方需求梗（五彩斑斕的黑）、工程師梗（已 root 的手機已經被 root）、"
        f"流行語梗（內卷、躺平、45度人生、打工人、社畜、已讀不回）。\n"
        f"5. 避免老掉牙的「子曰／俗話說得好／三人行」這類最常見的繞口令，要新鮮。\n"
        f"6. 不要日常對話或語助詞（嗯／好的／收到／我先走了），每句都必須有明確的"
        f"廢話文學結構（同義反覆或循環論證），看完會心一笑。\n"
        f"7. 彼此不重複，也不要和這些重複：{avoid}\n"
        f"結構可參考：「如果A成立，那A就成立。」「X之所以X，是因為它X了。」\n"
        f"只輸出一個 JSON 字串陣列，例如 [\"句一\",\"句二\"]，"
        f"不要編號、不要解釋、不要 markdown 圍籬。"
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
        existing = json.load(open(QUOTES, encoding="utf-8")).get("quotes", [])

    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": build_user(existing)},
    ]
    print(f"[gen] {MODEL} @ {BASE_URL} → 生成 {COUNT} 句...")
    quotes = parse_quotes(call_llm(messages))
    print(f"[gen] 收到 {len(quotes)} 句候選")

    # 純字串陣列；去重/過濾交給 quality_filter.py
    json.dump(quotes, open(STAGING, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[gen] 已寫入 {STAGING}（交給 quality_filter.py 處理）")


if __name__ == "__main__":
    main()
