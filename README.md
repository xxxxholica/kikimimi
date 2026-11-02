# kikimimi｜入室するだけで始まる、自然な声のDiscord読み上げボット

Google Cloud Text-to-Speech の Chirp 3: HD ボイスを使用した、Discord 向けの日本語読み上げボットです。

## 特徴

### 1. 自然な音声と聞き取りやすい読み上げ整形

Google Cloud の Chirp 3: HD による自然な音声を採用し、ユーザーごとに25種類の声から選択できます。メンションやカスタム絵文字は名前に変換し、URLはリンク先のページタイトルを取得して読み上げます。また、別チャンネルへの投稿時は投稿元チャンネル名を案内し、同じ人の連続投稿では発言者名を省略します。

### 2. 入退室に連動する自動接続と自動切断

ボイスチャンネルへの参加を検知して自動で接続し、全員が退室すると自動で切断します。通話のたびにコマンドを実行する必要がありません。

### 3. 読み上げと音楽再生の同時利用

サーバーに投稿された音声ファイルを直近25件まで自動でキャッシュし、スラッシュコマンドの音楽プレイヤーから再生・一時停止・停止を操作できます。BGMを流しながらでも発言の読み上げが同時に行われます。

### 4. 安全な外部通信と無料利用枠ガード

URLのタイトル取得では Discord が生成した埋め込み情報を優先して参照し、直接取得する場合もプライベートIPアドレスへの通信を遮断して安全性を確保しています。あわせて、Google Cloud の月間100万文字の無料利用枠を超えない自動停止ガードと長文の省略機能を備えています。

## 必要環境

- Python 3.10 以降
- ffmpeg および opus
- Discord Bot Token
- Google Cloud Text-to-Speech API のサービスアカウント認証情報

## セットアップ手順

### 1. システム依存ツールのインストール

**macOS**
```sh
brew install ffmpeg opus
```

**Linux**
```sh
sudo apt install ffmpeg libopus-dev
```

### 2. リポジトリのクローンとパッケージのインストール

Apple Silicon 環境を含め、仮想環境を作成してパッケージを導入します。

```sh
git clone https://github.com/xxxxholica/kikimimi.git
cd kikimimi
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Discord Developer Portal の設定

- Bot 設定画面の Privileged Gateway Intents で以下の2つを有効にします。
  - SERVER MEMBERS INTENT
  - MESSAGE CONTENT INTENT
- OAuth2 の URL Generator で以下のスコープと権限を選択し、生成されたURLからボットをサーバーへ招待します。
  - Scopes: `bot`, `applications.commands`
  - Permissions: メッセージ送信 / リンク埋め込み / メッセージ履歴閲覧 / スラッシュコマンド使用 / 接続 / 発言

### 4. 環境変数の設定

`.env.example` を `.env` にコピーし、Discord Bot Token と Google Cloud 認証情報ファイルのパスを設定します。

```sh
cp .env.example .env
mkdir key
```

作成した `key` ディレクトリに Google Cloud のサービスアカウント JSON キーを配置してください。

## 起動方法

```sh
python3 main.py
```

## コマンド一覧

| コマンド | 説明 |
| :--- | :--- |
| `/join` | 実行者が参加しているボイスチャンネルに接続し、読み上げを開始します |
| `/leave` | ボイスチャンネルから切断します |
| `/music` | キャッシュされた音声ファイルの音楽プレイヤーを表示し、読み上げと並行して再生や停止を操作します |
| `/voice` | 自分の読み上げボイスを25種類から選択して変更します |
| `/set_channel` | 自動接続時に案内メッセージを送信するテキストチャンネルを設定します。チャンネルの管理権限が必要です |
| `/status` | 稼働時間・メモリ使用率・月間読み上げ文字数を表示します |

## ライセンス

本プロジェクトは [MIT License](./LICENSE) のもとで公開されています。
