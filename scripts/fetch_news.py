#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
農業ニュース収集スクリプト
Google News RSS から農業関連記事を取得し、docs/index.html を生成する
"""

import feedparser
import re
import json
from datetime import datetime, timezone, timedelta
from html import unescape
from pathlib import Path

# ============================================================
# 設定
# ============================================================

# RSSフィードURL（Google News 農業検索）
RSS_FEEDS = [
    "https://news.google.com/rss/search?q=農業&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=農業+技術&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=農業+政策&hl=ja&gl=JP&ceid=JP:ja",
]

# 出力先（このスクリプトの親ディレクトリの docs/ 以下）
OUTPUT_DIR = Path(__file__).parent.parent / "docs"
OUTPUT_HTML = OUTPUT_DIR / "index.html"

# JST タイムゾーン
JST = timezone(timedelta(hours=9))

# ============================================================
# フラグ定義（キーワード → フラグ名 + 色）
# ジャンル系と トピック系の2種
# ============================================================

FLAGS = [
    # --- ジャンル系 ---
    {"name": "畜産",      "color": "#c0654a", "keywords": ["畜産", "牛", "豚", "鶏", "乳牛", "肉牛", "養豚", "養鶏", "酪農", "ブロイラー"]},
    {"name": "水産",      "color": "#2e86c1", "keywords": ["水産", "魚", "養殖", "漁業", "漁", "水産物", "サーモン", "ホタテ", "海面"]},
    {"name": "果樹",      "color": "#d4ac0d", "keywords": ["果樹", "りんご", "みかん", "ぶどう", "もも", "梨", "柑橘", "果物", "果実", "ブドウ"]},
    {"name": "野菜",      "color": "#28a745", "keywords": ["野菜", "トマト", "レタス", "キャベツ", "大根", "ほうれん草", "ネギ", "ジャガイモ", "ピーマン", "白菜"]},
    {"name": "米・穀物",  "color": "#b07d2a", "keywords": ["米", "水稲", "稲作", "稲", "小麦", "大豆", "穀物", "コメ", "もち米", "飼料用米"]},
    {"name": "農業DX",    "color": "#6f42c1", "keywords": ["DX", "デジタル", "IoT", "AI", "ドローン", "スマート農業", "自動化", "ロボット", "精密農業", "センサー"]},
    # --- トピック系 ---
    {"name": "補助金・政策", "color": "#dc3545", "keywords": ["補助金", "助成", "補助", "政策", "農林水産省", "農水省", "法律", "制度", "予算", "交付金"]},
    {"name": "輸出",         "color": "#17a2b8", "keywords": ["輸出", "海外", "国際", "グローバル", "輸出額", "海外展開"]},
    {"name": "食料安保",     "color": "#fd7e14", "keywords": ["食料安保", "食料安全保障", "食糧", "食料自給率", "食料危機"]},
    {"name": "害虫・病害",   "color": "#795548", "keywords": ["害虫", "病害", "防除", "農薬", "病虫害", "カメムシ", "ウンカ", "疫病"]},
    {"name": "価格・相場",   "color": "#e63946", "keywords": ["価格", "高騰", "値上がり", "相場", "市場価格", "卸値", "騰落"]},
    {"name": "新技術",       "color": "#5a67d8", "keywords": ["新技術", "開発", "研究", "イノベーション", "特許", "実証", "新品種", "育種"]},
]

# ============================================================
# 関数
# ============================================================

def detect_flags(text):
    """テキストからフラグを自動判定して返す"""
    detected = []
    for flag in FLAGS:
        for kw in flag["keywords"]:
            if kw in text:
                detected.append({"name": flag["name"], "color": flag["color"]})
                break  # 同一フラグの重複追加を防ぐ
    return detected


def extract_thumbnail(entry):
    """RSSエントリからサムネイルURLを取得する（複数パターンに対応）"""
    # パターン1: media:content
    if hasattr(entry, "media_content") and entry.media_content:
        for m in entry.media_content:
            if "url" in m:
                return m["url"]
    # パターン2: enclosure（添付ファイル）
    if hasattr(entry, "enclosures") and entry.enclosures:
        for e in entry.enclosures:
            if e.get("type", "").startswith("image"):
                return e.get("href") or e.get("url")
    # パターン3: description内の <img> タグを抽出
    desc = getattr(entry, "description", "") or getattr(entry, "summary", "") or ""
    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
    if img_match:
        return img_match.group(1)
    return None


def parse_date(entry) -> datetime:
    """エントリの公開日を datetime (JST) で返す"""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).astimezone(JST)
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc).astimezone(JST)
    return datetime.now(JST)


def fetch_articles():
    """全RSSフィードから記事を収集して返す（重複排除・日付降順）"""
    articles = []
    seen_links = set()

    for url in RSS_FEEDS:
        print(f"  取得中: {url}")
        feed = feedparser.parse(url)

        for entry in feed.entries:
            link = entry.get("link", "")
            if not link or link in seen_links:
                continue
            seen_links.add(link)

            title = unescape(entry.get("title", "タイトルなし"))
            source = entry.get("source", {}).get("title", "") or feed.feed.get("title", "")
            pub_date = parse_date(entry)
            thumbnail = extract_thumbnail(entry)

            # フラグ判定はタイトル＋概要テキストで行う
            summary = unescape(re.sub(r"<[^>]+>", "", entry.get("summary", "") or ""))
            flags = detect_flags(title + " " + summary)

            articles.append({
                "title": title,
                "link": link,
                "source": source,
                "date": pub_date.strftime("%Y-%m-%d %H:%M"),
                "date_iso": pub_date.isoformat(),
                "thumbnail": thumbnail,
                "flags": flags,
            })

    # 日付の新しい順でソート
    articles.sort(key=lambda x: x["date_iso"], reverse=True)
    print(f"  合計 {len(articles)} 件取得（重複排除済み）")
    return articles


def render_html(articles):
    """記事リストから index.html を生成する"""
    now_str = datetime.now(JST).strftime("%Y年%m月%d日 %H:%M")
    articles_json = json.dumps(articles, ensure_ascii=False, indent=None)

    # フィルターボタン用のフラグ一覧（記事に登場したものだけ）
    seen_flag_names = []
    all_flags = []
    for a in articles:
        for f in a["flags"]:
            if f["name"] not in seen_flag_names:
                seen_flag_names.append(f["name"])
                all_flags.append(f)

    filter_buttons = "\n".join(
        f'<button class="filter-btn" data-flag="{f["name"]}" '
        f'style="--fc:{f["color"]}">{f["name"]}</button>'
        for f in all_flags
    )

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>農業ニュース まとめ</title>
<style>
:root {{
  --bg: #f4f7f2;
  --card: #ffffff;
  --text: #2d3a2e;
  --sub: #6b7c6d;
  --accent: #3d7a4f;
  --border: #dce5dd;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Helvetica Neue', 'Hiragino Sans', 'Noto Sans JP', sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
}}
header {{
  background: var(--accent);
  color: #fff;
  padding: 18px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 6px;
}}
header h1 {{ font-size: 1.35rem; font-weight: 700; letter-spacing: 0.02em; }}
.updated {{ font-size: 0.78rem; opacity: 0.82; }}
.container {{ max-width: 1200px; margin: 0 auto; padding: 20px 16px; }}
.filter-bar {{
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-bottom: 20px;
  align-items: center;
}}
.filter-label {{ font-size: 0.82rem; color: var(--sub); }}
.filter-btn {{
  border: 1.5px solid var(--border);
  background: var(--card);
  color: var(--text);
  border-radius: 20px;
  padding: 4px 13px;
  font-size: 0.78rem;
  cursor: pointer;
  transition: all 0.15s;
}}
.filter-btn:hover {{ border-color: var(--fc, var(--accent)); color: var(--fc, var(--accent)); }}
.filter-btn.active {{
  background: var(--fc, var(--accent));
  color: #fff;
  border-color: var(--fc, var(--accent));
}}
.count {{ font-size: 0.82rem; color: var(--sub); margin-left: auto; }}
.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
  gap: 16px;
}}
.card {{
  background: var(--card);
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  transition: box-shadow 0.15s, transform 0.15s;
}}
.card:hover {{ box-shadow: 0 6px 20px rgba(0,0,0,.09); transform: translateY(-2px); }}
.thumb {{
  width: 100%;
  height: 155px;
  background: #e2ece4;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2.2rem;
  overflow: hidden;
  flex-shrink: 0;
}}
.thumb img {{ width: 100%; height: 155px; object-fit: cover; display: block; }}
.card-body {{ padding: 13px; flex: 1; display: flex; flex-direction: column; gap: 7px; }}
.flags {{ display: flex; flex-wrap: wrap; gap: 4px; min-height: 20px; }}
.flag {{
  font-size: 0.68rem;
  padding: 2px 8px;
  border-radius: 12px;
  color: #fff;
  font-weight: 700;
  letter-spacing: 0.03em;
}}
.card-title {{
  font-size: 0.92rem;
  font-weight: 600;
  line-height: 1.45;
  color: var(--text);
  text-decoration: none;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}}
.card-title:hover {{ color: var(--accent); text-decoration: underline; }}
.card-meta {{
  font-size: 0.75rem;
  color: var(--sub);
  margin-top: auto;
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 3px;
}}
.no-result {{
  grid-column: 1 / -1;
  text-align: center;
  padding: 60px 0;
  color: var(--sub);
  font-size: 0.95rem;
}}
@media (max-width: 480px) {{
  .grid {{ grid-template-columns: 1fr; }}
  header h1 {{ font-size: 1.1rem; }}
}}
</style>
</head>
<body>
<header>
  <h1>🌾 農業ニュース まとめ</h1>
  <div class="updated">最終更新: {now_str}</div>
</header>

<div class="container">
  <div class="filter-bar" id="filterBar">
    <span class="filter-label">フィルター:</span>
    <button class="filter-btn active" data-flag="all" style="--fc:var(--accent)">すべて</button>
    {filter_buttons}
    <span class="count" id="countLabel">{len(articles)} 件</span>
  </div>
  <div class="grid" id="grid"></div>
</div>

<script>
const ARTICLES = {articles_json};

function renderCards(filter) {{
  const grid = document.getElementById('grid');
  const countEl = document.getElementById('countLabel');
  const list = filter === 'all'
    ? ARTICLES
    : ARTICLES.filter(a => a.flags.some(f => f.name === filter));

  countEl.textContent = list.length + ' 件';

  if (list.length === 0) {{
    grid.innerHTML = '<div class="no-result">該当する記事がありません</div>';
    return;
  }}

  grid.innerHTML = list.map(a => {{
    const thumb = a.thumbnail
      ? `<div class="thumb"><img src="${{a.thumbnail}}" alt="" loading="lazy"
           onerror="this.parentElement.innerHTML='🌾'"></div>`
      : `<div class="thumb">🌾</div>`;

    const flagsHtml = a.flags.length
      ? a.flags.map(f =>
          `<span class="flag" style="background:${{f.color}}">${{f.name}}</span>`
        ).join('')
      : '';

    return `
<div class="card">
  ${{thumb}}
  <div class="card-body">
    <div class="flags">${{flagsHtml}}</div>
    <a class="card-title" href="${{a.link}}" target="_blank" rel="noopener noreferrer">${{a.title}}</a>
    <div class="card-meta">
      <span>${{a.source}}</span>
      <span>${{a.date}}</span>
    </div>
  </div>
</div>`;
  }}).join('');
}}

document.getElementById('filterBar').addEventListener('click', e => {{
  const btn = e.target.closest('.filter-btn');
  if (!btn) return;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderCards(btn.dataset.flag);
}});

renderCards('all');
</script>
</body>
</html>"""


# ============================================================
# メイン処理
# ============================================================

def main():
    print("=== 農業ニュース収集 開始 ===")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    articles = fetch_articles()
    html = render_html(articles)

    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"HTMLを生成しました → {OUTPUT_HTML}")
    print("=== 完了 ===")


if __name__ == "__main__":
    main()
