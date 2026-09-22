# kikimimi (聞き耳)

Google Cloud Text-to-Speech (Chirp3-HD) を使用した、Discord向けの高品質な日本語読み上げボット。

## 特徴
- Google「Chirp3-HD」による自然な読み上げ
- ボイスチャンネルへの入室を検知して自動接続・自動読み上げ開始、退室で自動切断
- サーバー内の全テキストチャンネルの発言を読み上げ、自動接続先以外のチャンネルでは「(チャンネル名)に投稿されました。(内容)」の形式で投稿元を案内
- 話者が変わった時だけ発言者名を読み上げ(Discordの連続投稿表示に倣い、同じ人の連続投稿では名前を省略)
- ユーザー・ロール・チャンネルメンションやカスタム絵文字を自然な名称に変換して読み上げ
- 本文中のリンク先ページにアクセスしてタイトルを取得し「リンク省略(タイトル)」のように読み上げ(プライベートIP等へのアクセスは自動的にブロックし、取得できない場合はドメイン名を使った「リンク省略。(ドメイン名)」にフォールバック)
- ユーザーごとに25種類のボイスから読み上げ声を選択可能
- 稼働時間・メモリ使用率・月間読み上げ文字数・直近のエラーログを確認できるステータス表示
- 絶対パスを排除したOSS設計(`.env`で設定完結、どの環境でもクローンしてすぐ動く)

## 必要環境
- Python 3.10以降(Apple Silicon環境ではvenv必須)
- ffmpeg / opus
- Discord Bot Token
- Google Cloud Text-to-Speech APIの認証情報(サービスアカウントJSON)

## セットアップ手順

### 1. システム依存ツールのインストール
**macOS (M4等のApple Silicon環境含む)**
```sh
brew install ffmpeg opus
```

**Linux**
```sh
sudo apt install ffmpeg libopus-dev
```

### 2. リポジトリのクローンと依存関係のインストール
```sh
git clone https://github.com/xxxxholica/kikimimi.git
cd kikimimi
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Discord Developer Portalの設定(重要)
- `Bot`タブの **Privileged Gateway Intents** で以下をONにする
  - SERVER MEMBERS INTENT
  - MESSAGE CONTENT INTENT
- `OAuth2`の URL Generator で以下を選択し、生成されたURLからボットをサーバーに招待する
  - Scopes: `bot`, `applications.commands`
  - Permissions: メッセージ送信 / リンク埋め込み / メッセージ履歴閲覧 / スラッシュコマンド使用 / 接続 / 発言

### 4. 環境設定
`.env.example` を `.env` にコピーし、トークンとGoogle Cloud認証JSONのパスを入力してください。
```sh
cp .env.example .env
```

クローン直後は `key/` ディレクトリが存在しないため、以下のコマンドで作成し、その中にGoogle Cloudの認証用JSONキーを配置してください。
```sh
mkdir key
```

## 起動方法
```sh
python3 main.py
```

## コマンド一覧
| コマンド | 説明 |
|---|---|
| `/join` | 実行者が参加しているボイスチャンネルに接続し、読み上げを開始します |
| `/leave` | ボイスチャンネルから切断します |
| `/voice` | 自分の読み上げボイスを25種類から選択して変更します |
| `/set_channel` | 自動接続時に読み上げ内容を送信するテキストチャンネルを設定します(要「チャンネルの管理」権限) |
| `/status` | 稼働時間・メモリ使用率・月間読み上げ文字数・直近のエラーログを表示します |

## ライセンス
本プロジェクトは [MIT License](./LICENSE) のもとで公開されています。
