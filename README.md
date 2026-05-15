# kikimimi (聞き耳) v1.0.1 👂
Google Cloud Text-to-Speech (Chirp3-HD) を使用した、Discord向けの高品質な日本語読み上げボット (v1.0.1)。

■ 特徴
- Googleの最新AI「Chirp3-HD」による自然な読み上げ
- ユーザー入退室による自動接続・切断機能
- ユーザーごとに25種類のボイスを選択可能（/voice）
- 絶対パスを排除したOSS設計（.envで設定完結）

■ セットアップ手順
1. システム依存ツールのインストール
   macOS (M4等のApple Silicon環境含む):
   ```sh
   brew install ffmpeg opus
   ```
   Linux:
   ```sh
   sudo apt install ffmpeg libopus-dev
   ```

2. インストール（Python 3.10以降推奨 / Mac M4環境などではvenv必須）
   ```sh
   git clone https://github.com/xxxxholica/kikimimi.git
   ```

   ```sh
   cd kikimimi
   ```

   ```sh
   python3 -m venv venv
   ```

   ```sh
   source venv/bin/activate
   ```

   ```sh
   pip install -r requirements.txt
   ```

3. Discord Portalの設定 (重要)
   - 「Bot」タブの「Privileged Gateway Intents」で以下をONにする：
     - SERVER MEMBERS INTENT
     - MESSAGE CONTENT INTENT
   - 「OAuth2」のURL Generatorで以下を許可：
     - Scopes: bot, applications.commands
     - Permissions: メッセージ送信, リンク埋め込み, メッセージ履歴閲覧, スラッシュコマンド使用, 接続, 発言

4. 環境設定
   `.env.example` を `.env` にコピーしてトークンとGoogle Cloud認証JSONのパスを入力してください。
   ```sh
   cp .env.example .env
   ```

   また、クローン直後は `key/` ディレクトリが存在しないため、以下のコマンドでディレクトリを作成し、その中にGoogle Cloudの認証用JSONキーを配置してください。
   ```sh
   mkdir key
   ```

■ 使い方
- 以下のコマンドで起動します：
  ```sh
  python3 main.py
  ```
- `/join` で接続、`/voice` で声の変更
