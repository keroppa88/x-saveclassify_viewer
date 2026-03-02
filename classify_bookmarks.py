"""
X ブックマーク分類スクリプト

x_bookmark_url.csv のツイートURLを Gemini API で以下のカテゴリに分類します:
  - 経済
  - 移民
  - AIプログラム
  - その他

使い方:
  1. GEMINI_API_KEY 環境変数を設定（または .env ファイルに記載）
  2. x_bookmark_url.csv を同じディレクトリに配置
  3. python classify_bookmarks.py を実行
  4. x_bookmark_classified.csv が出力されます

必要パッケージ:
  pip install google-generativeai requests
"""

import csv
import json
import os
import sys
import time
import requests
import google.generativeai as genai

# === 設定 ===
INPUT_CSV = "x_bookmark_url.csv"
OUTPUT_CSV = "x_bookmark_classified.csv"
CATEGORIES = ["経済", "移民", "AIプログラム", "その他"]
BATCH_SIZE = 5  # 一度にGeminiに送るURL数
RATE_LIMIT_DELAY = 2  # API呼び出し間隔（秒）


def load_api_key():
    """環境変数または .env ファイルから API キーを取得"""
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key

    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("GEMINI_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")

    print("エラー: GEMINI_API_KEY が設定されていません。")
    print("以下のいずれかで設定してください:")
    print("  export GEMINI_API_KEY='your-api-key'")
    print("  または .env ファイルに GEMINI_API_KEY=your-api-key を記載")
    sys.exit(1)


def read_urls(csv_path):
    """CSVからURLリストを読み込む"""
    urls = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get("url", "").strip()
            if url:
                urls.append(url)
    return urls


def fetch_tweet_text(url):
    """Twitter oEmbed API でツイートのテキストを取得（無料・認証不要）"""
    oembed_url = "https://publish.twitter.com/oembed"
    try:
        resp = requests.get(oembed_url, params={"url": url}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            # HTMLタグを簡易除去してテキスト抽出
            html = data.get("html", "")
            # <blockquote>内のテキストを取得
            import re
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:500]  # 長すぎる場合は切り詰め
    except Exception as e:
        print(f"  oEmbed取得失敗 ({url}): {e}")
    return None


def classify_batch(model, urls_with_text):
    """Gemini API でバッチ分類"""
    prompt_parts = []
    for i, (url, text) in enumerate(urls_with_text):
        content = text if text else f"(テキスト取得不可。URLから推測してください: {url})"
        prompt_parts.append(f"[{i+1}] URL: {url}\n内容: {content}")

    tweets_text = "\n\n".join(prompt_parts)

    prompt = f"""以下のツイート（X投稿）を、それぞれ下記の4カテゴリのいずれかに分類してください。

カテゴリ:
- 経済: 経済政策、金融、株式、為替、財政、景気、貿易、税制など
- 移民: 移民政策、外国人労働者、難民、ビザ、入管、多文化共生など
- AIプログラム: AI、機械学習、プログラミング、テクノロジー、ソフトウェア開発など
- その他: 上記に該当しないもの

回答は必ず以下のJSON配列形式のみで返してください（説明不要）:
[
  {{"index": 1, "category": "カテゴリ名"}},
  {{"index": 2, "category": "カテゴリ名"}}
]

ツイート:
{tweets_text}"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()

        # JSONブロックを抽出
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        results = json.loads(text)
        return results
    except json.JSONDecodeError as e:
        print(f"  JSON解析エラー: {e}")
        print(f"  レスポンス: {text[:200]}")
        return None
    except Exception as e:
        print(f"  Gemini API エラー: {e}")
        return None


def main():
    # APIキー読み込み
    api_key = load_api_key()
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    # URL読み込み
    if not os.path.exists(INPUT_CSV):
        print(f"エラー: {INPUT_CSV} が見つかりません。")
        print("先に collect_bookmarks.js でブックマークURLを収集してください。")
        sys.exit(1)

    urls = read_urls(INPUT_CSV)
    print(f"読み込み: {len(urls)} 件のURL")

    if not urls:
        print("URLが0件です。終了します。")
        sys.exit(0)

    # ツイートテキスト取得
    print("\nツイートテキストを取得中...")
    urls_with_text = []
    for i, url in enumerate(urls):
        print(f"  [{i+1}/{len(urls)}] {url}")
        text = fetch_tweet_text(url)
        urls_with_text.append((url, text))
        if (i + 1) % 10 == 0:
            time.sleep(1)  # oEmbed APIのレート制限対策

    # バッチ分類
    print(f"\nGemini API で分類中（{BATCH_SIZE}件ずつ）...")
    results = []

    for batch_start in range(0, len(urls_with_text), BATCH_SIZE):
        batch = urls_with_text[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(urls_with_text) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  バッチ {batch_num}/{total_batches} ({len(batch)}件)")

        classified = classify_batch(model, batch)

        if classified:
            for item in classified:
                idx = item["index"] - 1
                actual_idx = batch_start + idx
                if 0 <= actual_idx < len(urls_with_text):
                    category = item.get("category", "その他")
                    if category not in CATEGORIES:
                        category = "その他"
                    results.append({
                        "url": urls_with_text[actual_idx][0],
                        "category": category
                    })
        else:
            # 分類失敗時は「その他」に割り当て
            for url, _ in batch:
                results.append({"url": url, "category": "その他"})

        time.sleep(RATE_LIMIT_DELAY)

    # CSV出力
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["url", "category"])
        writer.writeheader()
        writer.writerows(results)

    # サマリー表示
    print(f"\n=== 分類完了 ===")
    print(f"出力: {OUTPUT_CSV}")
    print(f"合計: {len(results)} 件\n")

    summary = {}
    for r in results:
        cat = r["category"]
        summary[cat] = summary.get(cat, 0) + 1

    for cat in CATEGORIES:
        count = summary.get(cat, 0)
        print(f"  {cat}: {count} 件")


if __name__ == "__main__":
    main()
