#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
農業ニュース投稿下書き生成スクリプト
毎日自動実行: 今日のニュースからX投稿の下書きを生成してNotionに保存する
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
import anthropic
from notion_client import Client as NotionClient

# 同ディレクトリのfetch_news.pyからfetch_articles関数をインポート
sys.path.insert(0, str(Path(__file__).parent))
from fetch_news import fetch_articles

# .env を読み込む（GitHub Actions では環境変数として注入されるため無視される）
load_dotenv(Path(__file__).parent.parent / ".env")

# 環境変数から設定を読み込む
ANTHROPIC_API_KEY     = os.environ["ANTHROPIC_API_KEY"]
NOTION_API_KEY        = os.environ["NOTION_API_KEY"]
NOTION_DB_ID          = os.environ["NOTION_DB_ID"]
NOTION_DATA_SOURCE_ID = os.environ["NOTION_DATA_SOURCE_ID"]

JST = timezone(timedelta(hours=9))

# Notionに登録できるカテゴリ（fetch_news.pyのFLAGSと同じ）
VALID_CATEGORIES = [
    "畜産", "水産", "果樹", "野菜", "米・穀物", "農業DX",
    "補助金・政策", "輸出", "食料安保", "害虫・病害", "価格・相場", "新技術",
]


def get_recent_posts(notion: NotionClient, days: int = 14) -> list:
    """直近N日間の投稿済み・下書き・承認済みレコードを取得（重複防止用）"""
    cutoff = (datetime.now(JST) - timedelta(days=days)).date().isoformat()

    # notion-client 2.7.0 以降は data_sources.query() を使用
    results = notion.data_sources.query(
        NOTION_DATA_SOURCE_ID,
        filter={
            "and": [
                {
                    "property": "ステータス",
                    "select": {"does_not_equal": "スキップ"},
                },
                {
                    "property": "投稿日",
                    "date": {"on_or_after": cutoff},
                },
            ]
        },
    )

    posts = []
    for page in results["results"]:
        props = page["properties"]
        theme_rt = props["テーマ"]["title"]
        angle_rt = props["切り口"]["rich_text"]
        posts.append({
            "テーマ": theme_rt[0]["plain_text"] if theme_rt else "",
            "切り口": angle_rt[0]["plain_text"] if angle_rt else "",
        })
    return posts


def generate_draft(articles: list, recent_posts: list) -> dict:
    """Claude APIを使って投稿下書きを生成する"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # 記事リストをテキストに変換（上位20件）
    articles_text = "\n".join(
        "- [{date}] {title} ({source}) フラグ:{flags}".format(
            date=a["date"],
            title=a["title"],
            source=a["source"],
            flags=",".join(f["name"] for f in a["flags"]) or "なし",
        )
        for a in articles[:20]
    )

    # 過去の投稿・切り口
    recent_text = "\n".join(
        f"- テーマ:{p['テーマ']} / 切り口:{p['切り口']}"
        for p in recent_posts
    ) or "（なし）"

    prompt = f"""あなたはagrifoodというブランドのSNS担当です。
農業関連ニュースから今日のX（Twitter）投稿を1本作成してください。

## 今日の農業ニュース（最新順）
{articles_text}

## 直近2週間の投稿済みテーマ・切り口（これと重複しないこと）
{recent_text}

## カテゴリの選択肢（enumから選ぶこと）
畜産 / 水産 / 果樹 / 野菜 / 米・穀物 / 農業DX / 補助金・政策 / 輸出 / 食料安保 / 害虫・病害 / 価格・相場 / 新技術

## 投稿者の過去ポスト（この口調・文体を真似ること）
---
発想がやばすぎるw
最初言われても、どういうこと？ってなったわw
---
生成AIにポスト考えさせてるな
ってアカウントめちゃ増えたな
---
信頼度検定も何もしてない結果を大々的に発表されても、、、
とりあえず、この会社に仕事を頼むことはない。
---
BIの導入とかそのへんはどちらかというとデータアナリティクスとかの領域だから、餅は餅屋という考え方からすると当然だと思ってたけど、違うのか、、、？
私は広告代理店に答えを求めてる時点でズレてる気がするが、、、
---
だめだ！アホすぎる！お前はもう作業要員だ！(某生成AIに対して)
---

## 投稿スタイルのルール
- 話し言葉・ゆるい文体（「〜だな」「〜わ」「〜けど」「w」「、、、」など）
- 自分の感想・反応を先に書いて、理由や背景は後に添える
- 【タイトル】のような形式的な見出しは使わない
- 短文・体言止めを活かしてテンポよく
- 単なるニュース転載ではなく「なぜ重要か」「自分はどう思うか」を入れる
- ハッシュタグは #農業 を1〜2個だけ（多用しない）
- 投稿文は200文字以内に収める
"""

    # tool_choice で構造化出力を強制（JSONパースエラーを防ぐ）
    # ※ Anthropic API のプロパティ名は英数字のみ必須のため英語キーを使用
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        tools=[{
            "name": "create_post_draft",
            "description": "農業ニュースの投稿下書きを作成する",
            "input_schema": {
                "type": "object",
                "properties": {
                    "theme":       {"type": "string", "description": "投稿のテーマ（20字以内）"},
                    "categories":  {"type": "array", "items": {"type": "string"}, "description": "該当カテゴリ"},
                    "angle":       {"type": "string", "description": "使った視点・論点（50字以内）"},
                    "news_title":  {"type": "string", "description": "引用した記事のタイトル"},
                    "news_url":    {"type": "string", "description": "引用した記事のURL"},
                    "post_text":   {"type": "string", "description": "X投稿本文（200文字以内・ハッシュタグ含む）"},
                },
                "required": ["theme", "categories", "angle", "news_title", "news_url", "post_text"],
            },
        }],
        tool_choice={"type": "tool", "name": "create_post_draft"},
        messages=[{"role": "user", "content": prompt}],
    )

    # tool_use ブロックの input を日本語キーに変換して返す
    inp = message.content[0].input
    return {
        "テーマ":            inp["theme"],
        "カテゴリ":          inp["categories"],
        "切り口":            inp["angle"],
        "引用ニュース見出し": inp["news_title"],
        "引用ニュースURL":   inp["news_url"],
        "投稿文":            inp["post_text"],
    }


def save_to_notion(notion: NotionClient, draft: dict) -> str:
    """下書きをNotionに保存してページIDを返す"""
    # カテゴリは有効値のみ
    categories = [c for c in draft.get("カテゴリ", []) if c in VALID_CATEGORIES]

    page = notion.pages.create(
        parent={"database_id": NOTION_DB_ID},
        properties={
            "テーマ": {
                "title": [{"text": {"content": draft["テーマ"]}}]
            },
            "ステータス": {"select": {"name": "下書き"}},
            "プラットフォーム": {"multi_select": [{"name": "X"}]},
            "カテゴリ": {"multi_select": [{"name": c} for c in categories]},
            "切り口": {
                "rich_text": [{"text": {"content": draft["切り口"]}}]
            },
            "引用ニュース見出し": {
                "rich_text": [{"text": {"content": draft["引用ニュース見出し"]}}]
            },
            "引用ニュースURL": {"url": draft["引用ニュースURL"]},
        },
        # 投稿文はページ本文に保存（プロパティは文字数制限があるため）
        children=[
            {
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": "X投稿文"}}]
                },
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": draft["投稿文"]}}]
                },
            },
        ],
    )
    return page["id"]


NUM_DRAFTS = 3  # 1回の実行で生成する下書きの本数


def main():
    print("=== 農業ニュース投稿下書き生成 開始 ===")

    # 1. ニュース収集
    print("\n[1/3] ニュースを取得中...")
    articles = fetch_articles()

    # 2. Notionから過去の投稿を取得
    print("\n[2/3] 過去の投稿を確認中...")
    notion = NotionClient(auth=NOTION_API_KEY)
    recent_posts = get_recent_posts(notion)
    print(f"  直近の投稿: {len(recent_posts)}件")

    # 3. NUM_DRAFTS 本分を生成・保存
    print(f"\n[3/3] 下書きを{NUM_DRAFTS}本生成中...")
    # 今回のセッションで生成済みのものも重複防止リストに追加していく
    generated_today = []

    for i in range(NUM_DRAFTS):
        print(f"\n  --- {i + 1}本目 ---")
        draft = generate_draft(articles, recent_posts + generated_today)
        print(f"  テーマ  : {draft['テーマ']}")
        print(f"  切り口  : {draft['切り口']}")
        print(f"  投稿文  :\n{draft['投稿文']}")

        page_id = save_to_notion(notion, draft)
        print(f"  保存完了 → https://notion.so/{page_id.replace('-', '')}")

        # 次の生成時に重複しないよう追加
        generated_today.append({
            "テーマ": draft["テーマ"],
            "切り口": draft["切り口"],
        })

    print("\n=== 完了 ===")
    print(f"{NUM_DRAFTS}本の下書きをNotionに保存しました。確認してください。")


if __name__ == "__main__":
    main()
