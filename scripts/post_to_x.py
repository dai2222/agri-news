#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X（Twitter）投稿スクリプト
Notionで「承認」済み・投稿予定日時を過ぎたレコードをXに投稿する
実行タイミング: 投稿したいときに手動で実行
"""

import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
import tweepy
from notion_client import Client as NotionClient

# .env を読み込む
load_dotenv(Path(__file__).parent.parent / ".env")

# 環境変数から設定を読み込む
X_API_KEY             = os.environ["X_API_KEY"]
X_API_KEY_SECRET      = os.environ["X_API_KEY_SECRET"]
X_ACCESS_TOKEN        = os.environ["X_ACCESS_TOKEN"]
X_ACCESS_TOKEN_SECRET = os.environ["X_ACCESS_TOKEN_SECRET"]
NOTION_API_KEY        = os.environ["NOTION_API_KEY"]
NOTION_DB_ID          = os.environ["NOTION_DB_ID"]
NOTION_DATA_SOURCE_ID = os.environ["NOTION_DATA_SOURCE_ID"]

JST = timezone(timedelta(hours=9))


def get_approved_posts(notion: NotionClient) -> list:
    """Notionから「承認」済みで投稿予定日時を過ぎたレコードを取得する"""
    # notion-client 2.7.0 以降は data_sources.query() を使用
    results = notion.data_sources.query(
        NOTION_DATA_SOURCE_ID,
        filter={
            "property": "ステータス",
            "select": {"equals": "承認"},
        },
    )

    now = datetime.now(JST)
    posts = []

    for page in results["results"]:
        props = page["properties"]

        # 投稿予定日時チェック（設定されている場合のみ）
        scheduled = props["投稿予定日時"]["date"]
        if scheduled and scheduled["start"]:
            scheduled_dt = datetime.fromisoformat(scheduled["start"])
            # タイムゾーン情報がない場合はJSTとして扱う
            if scheduled_dt.tzinfo is None:
                scheduled_dt = scheduled_dt.replace(tzinfo=JST)
            if scheduled_dt > now:
                theme = props["テーマ"]["title"]
                theme_str = theme[0]["plain_text"] if theme else "（不明）"
                print(f"  スキップ（予約時刻未到達: {scheduled['start']}）: {theme_str}")
                continue

        # ページ本文から投稿文を取得
        blocks = notion.blocks.children.list(block_id=page["id"])
        post_text = ""
        for block in blocks["results"]:
            if block["type"] == "paragraph":
                for rt in block["paragraph"]["rich_text"]:
                    post_text += rt["plain_text"]

        if not post_text.strip():
            print(f"  スキップ（投稿文なし）: {page['id']}")
            continue

        theme = props["テーマ"]["title"]
        posts.append({
            "page_id": page["id"],
            "テーマ": theme[0]["plain_text"] if theme else "",
            "投稿文": post_text.strip(),
        })

    return posts


def post_to_x(post_text: str) -> str:
    """Xに投稿してツイートIDを返す"""
    client = tweepy.Client(
        consumer_key=X_API_KEY,
        consumer_secret=X_API_KEY_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_TOKEN_SECRET,
    )
    response = client.create_tweet(text=post_text)
    return str(response.data["id"])


def mark_as_posted(notion: NotionClient, page_id: str):
    """Notionのレコードをステータス「投稿済み」・投稿日=今に更新する"""
    now_jst = datetime.now(JST).isoformat()
    notion.pages.update(
        page_id=page_id,
        properties={
            "ステータス": {"select": {"name": "投稿済み"}},
            "投稿日": {"date": {"start": now_jst}},
        },
    )


def main():
    print("=== X投稿スクリプト 開始 ===")

    notion = NotionClient(auth=NOTION_API_KEY)

    # 1. 承認済みレコードを取得
    print("\n承認済みの投稿を確認中...")
    posts = get_approved_posts(notion)

    if not posts:
        print("投稿対象なし（承認済み・投稿予定時刻到達済みのレコードがありません）。")
        return

    print(f"\n{len(posts)}件の投稿対象が見つかりました。\n")

    # 2. 各レコードを投稿
    for i, post in enumerate(posts, 1):
        print(f"[{i}/{len(posts)}] テーマ: {post['テーマ']}")
        print(f"投稿文:\n{post['投稿文']}")
        print("-" * 50)

        # 投稿実行
        tweet_id = post_to_x(post["投稿文"])
        tweet_url = f"https://x.com/i/web/status/{tweet_id}"
        print(f"投稿完了: {tweet_url}")

        # Notionを更新
        mark_as_posted(notion, post["page_id"])
        print("Notionを「投稿済み」に更新しました。\n")

    print("=== 完了 ===")


if __name__ == "__main__":
    main()
