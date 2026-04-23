# GitHub セットアップ手順

このファイルを読みながら順番に進めてください。所要時間: 約15〜20分

---

## STEP 1: ローカルでテスト実行（動作確認）

ターミナルを開いて以下を順番に実行します。

```bash
# 1. プロジェクトフォルダに移動
cd ~/Library/CloudStorage/OneDrive-個人用/Claude/wbbg/agri-news

# 2. feedparser をインストール（初回のみ）
pip install feedparser

# 3. スクリプトを実行
python scripts/fetch_news.py
```

完了すると `docs/index.html` が生成されます。
ブラウザで開いて記事が表示されることを確認してください。

---

## STEP 2: GitHub にリポジトリを作成

1. https://github.com にログイン
2. 右上の「+」ボタン → **New repository** をクリック
3. 以下の設定で作成:
   - **Repository name**: `agri-news`
   - **Public** を選択（GitHub Pagesの無料公開に必要）
   - **Initialize this repository** のチェックは **外す**
4. 「Create repository」をクリック

---

## STEP 3: ファイルをGitHubにアップロード

ターミナルで以下を順番に実行します（`your-username` を自分のGitHubユーザー名に書き換えてください）。

```bash
# agri-news フォルダに移動
cd ~/Library/CloudStorage/OneDrive-個人用/Claude/wbbg/agri-news

# Git を初期化
git init

# 全ファイルをステージング
git add .

# 最初のコミット
git commit -m "🌾 農業ニュースサイト 初期構築"

# main ブランチに設定
git branch -M main

# GitHub リポジトリと接続（your-username を書き換える）
git remote add origin https://github.com/your-username/agri-news.git

# プッシュ（アップロード）
git push -u origin main
```

※ 途中でGitHubのユーザー名・パスワード（またはPersonal Access Token）を求められたら入力してください。

---

## STEP 4: GitHub Pages を有効化

1. GitHubの `agri-news` リポジトリページを開く
2. 上部タブの **Settings** をクリック
3. 左メニューの **Pages** をクリック
4. 「Source」の設定を以下に変更:
   - Branch: `main`
   - Folder: `/docs`
5. **Save** をクリック

数分後、以下のURLでサイトが公開されます:
```
https://your-username.github.io/agri-news/
```

---

## STEP 5: 動作確認（手動でActionsを実行）

1. GitHubの `agri-news` リポジトリページを開く
2. 上部タブの **Actions** をクリック
3. 左メニューの「農業ニュース 毎日自動更新」をクリック
4. 右側の **Run workflow** → **Run workflow** をクリック
5. 緑色のチェックマークが出れば成功

以降は毎日 AM 8:00 に自動でニュースが更新されます。

---

## よくある質問

**Q: git push で認証エラーが出る**
A: GitHubにPersonal Access Tokenが必要な場合があります。
   GitHub → Settings → Developer settings → Personal access tokens → Generate new token
   権限は「repo」にチェックを入れてください。

**Q: GitHub Pages のURLが表示されない**
A: Settings → Pages でSourceが `/docs` になっているか確認してください。
   反映まで最大10分かかることがあります。
