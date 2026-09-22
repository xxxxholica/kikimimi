import os
import io
import re
import json
import html
import socket
import ipaddress
import tempfile
import asyncio
import datetime
import logging
import time
import shutil
import random
from collections import Counter
from urllib.parse import urlparse, urljoin
from dotenv import load_dotenv

load_dotenv()

import psutil
import requests
from pydub import AudioSegment

import discord
from discord.ext import commands
from discord import app_commands
import discord.opus
from google.cloud import texttospeech

# --- 定数・設定 ---
START_TIME = time.time()
COLOR_SUCCESS = 0x2ecc71  # 緑
COLOR_NOTICE = 0x3498db   # 青
COLOR_ERROR = 0xe74c3c    # 赤

# カスタマイズ設定 (環境変数から取得)
UPDATE_INFO = os.getenv("UPDATE_INFO", "v1.1.0: 全チャンネル読み上げ・リンク先タイトル取得・ロール/絵文字読み上げに対応。")
SYSTEM_FOOTER = os.getenv("SYSTEM_FOOTER", "Discord Bot System")
BOT_PRESENCE = os.getenv("BOT_PRESENCE", "github.com/xxxxholica/kikimimi")

# システム案内用
SYSTEM_VOICE = "ja-JP-Chirp3-HD-Kore"

# ユーザー用ボイス (25種厳選)
USER_VOICE_OPTIONS = {
    "ja-JP-Chirp3-HD-Achird": "ja-JP-Chirp3-HD-Achird (男性)",
    "ja-JP-Chirp3-HD-Algenib": "ja-JP-Chirp3-HD-Algenib (男性)",
    "ja-JP-Chirp3-HD-Algieba": "ja-JP-Chirp3-HD-Algieba (男性)",
    "ja-JP-Chirp3-HD-Alnilam": "ja-JP-Chirp3-HD-Alnilam (男性)",
    "ja-JP-Chirp3-HD-Charon": "ja-JP-Chirp3-HD-Charon (男性)",
    "ja-JP-Chirp3-HD-Enceladus": "ja-JP-Chirp3-HD-Enceladus (男性)",
    "ja-JP-Chirp3-HD-Fenrir": "ja-JP-Chirp3-HD-Fenrir (男性)",
    "ja-JP-Chirp3-HD-Iapetus": "ja-JP-Chirp3-HD-Iapetus (男性)",
    "ja-JP-Chirp3-HD-Orus": "ja-JP-Chirp3-HD-Orus (男性)",
    "ja-JP-Chirp3-HD-Puck": "ja-JP-Chirp3-HD-Puck (男性)",
    "ja-JP-Chirp3-HD-Rasalgethi": "ja-JP-Chirp3-HD-Rasalgethi (男性)",
    "ja-JP-Chirp3-HD-Sadachbia": "ja-JP-Chirp3-HD-Sadachbia (男性)",
    "ja-JP-Chirp3-HD-Sadaltager": "ja-JP-Chirp3-HD-Sadaltager (男性)",
    "ja-JP-Chirp3-HD-Schedar": "ja-JP-Chirp3-HD-Schedar (男性)",
    "ja-JP-Chirp3-HD-Umbriel": "ja-JP-Chirp3-HD-Umbriel (男性)",
    "ja-JP-Chirp3-HD-Zubenelgenubi": "ja-JP-Chirp3-HD-Zubenelgenubi (男性)",
    "ja-JP-Chirp3-HD-Kore": "ja-JP-Chirp3-HD-Kore (女性)",
    "ja-JP-Chirp3-HD-Achernar": "ja-JP-Chirp3-HD-Achernar (女性)",
    "ja-JP-Chirp3-HD-Aoede": "ja-JP-Chirp3-HD-Aoede (女性)",
    "ja-JP-Chirp3-HD-Autonoe": "ja-JP-Chirp3-HD-Autonoe (女性)",
    "ja-JP-Chirp3-HD-Despina": "ja-JP-Chirp3-HD-Despina (女性)",
    "ja-JP-Chirp3-HD-Erinome": "ja-JP-Chirp3-HD-Erinome (女性)",
    "ja-JP-Chirp3-HD-Leda": "ja-JP-Chirp3-HD-Leda (女性)",
    "ja-JP-Chirp3-HD-Sulafat": "ja-JP-Chirp3-HD-Sulafat (女性)",
    "ja-JP-Chirp3-HD-Zephyr": "ja-JP-Chirp3-HD-Zephyr (女性)"
}
AVAILABLE_VOICE_NAMES = list(USER_VOICE_OPTIONS.keys())

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_PATH", os.path.join(BASE_DIR, "key", "google_credentials.json"))
WORD_COUNTER_FILE = os.path.join(BASE_DIR, "data", "word_counter.json")
USER_VOICES_FILE = os.path.join(BASE_DIR, "data", "user_voices.json")
CONFIG_FILE = os.path.join(BASE_DIR, "data", "config.json")
LOG_DIR = os.path.join(BASE_DIR, "logs")

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = KEY_PATH
FFMPEG_PATH = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"

# --- ログ設定 ---
os.makedirs(LOG_DIR, exist_ok=True)
current_log_file = os.path.join(LOG_DIR, datetime.datetime.now().strftime("%Y-%m-%d.log"))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s 聞き耳 %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(current_log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def print_log(message):
    logging.info(message)

# --- データ管理 ---
def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print_log(f"JSON読み込みエラー ({path}): {e}")
    return default

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- ユーティリティ ---
async def send_embed(interaction, title, description, color=COLOR_NOTICE, ephemeral=False):
    embed = discord.Embed(title=title, description=description, color=color)
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, ephemeral=ephemeral)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

MENTION_PATTERN = re.compile(r'<@!?(\d+)>')
ROLE_MENTION_PATTERN = re.compile(r'<@&(\d+)>')
CHANNEL_MENTION_PATTERN = re.compile(r'<#(\d+)>')
CUSTOM_EMOJI_PATTERN = re.compile(r'<a?:(\w+):\d+>')
URL_PATTERN = re.compile(r'https?://[\w/:%#\$&\?\(\)~\.=\+\-]+')
TITLE_TAG_PATTERN = re.compile(r'<title[^>]*>(.*?)</title>', re.IGNORECASE | re.DOTALL)

MAX_TITLE_LENGTH = 20
LINK_FETCH_TIMEOUT = 4
LINK_MAX_REDIRECTS = 3
LINK_MAX_BYTES = 65536

KNOWN_SITE_LABELS = {
    "www.youtube.com": "ユーチューブ", "youtu.be": "ユーチューブ",
    "x.com": "エックス", "twitter.com": "エックス",
    "store.steampowered.com": "スチーム", "steampowered.com": "スチーム",
    "www.instagram.com": "インスタグラム", "instagram.com": "インスタグラム",
    "netmall.hardoff.co.jp": "オフモール",
    "drive.google.com": "Google Drive",
}

# サブドメインを問わずマッチさせるドメイン(先頭にwww.等が付いていても一致させる)
KNOWN_SITE_LABEL_SUFFIXES = {
    "amzn.asia": "アマゾン",
    "rakuten.co.jp": "楽天市場",
    "aliexpress.com": "アリエスプレス",
}

# ドメイン名フォールバック時に「co.jp」等を1階層としてまとめて扱うための例外リスト
MULTI_PART_TLDS = {"co.jp", "ne.jp", "or.jp", "ac.jp", "go.jp", "co.uk", "org.uk", "com.au"}

def lookup_known_label(netloc):
    netloc = netloc.lower()
    if netloc in KNOWN_SITE_LABELS:
        return KNOWN_SITE_LABELS[netloc]
    for domain, label in KNOWN_SITE_LABEL_SUFFIXES.items():
        if netloc == domain or netloc.endswith("." + domain):
            return label
    return None

def extract_base_domain(netloc):
    """サブドメインを省いたドメイン名を返す(例: www.hinata.works -> hinata.works)"""
    netloc = netloc.lower().split(":")[0]
    labels = netloc.split(".")
    if len(labels) <= 2:
        return netloc
    if ".".join(labels[-2:]) in MULTI_PART_TLDS and len(labels) >= 3:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])

# SSRF対策: 取得先IPがこれらのレンジに解決される場合はアクセスしない
PRIVATE_IP_NETWORKS = [ipaddress.ip_network(n) for n in (
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8",
    "169.254.0.0/16", "172.16.0.0/12", "192.0.0.0/24", "192.168.0.0/16",
    "198.18.0.0/15", "224.0.0.0/4", "240.0.0.0/4",
    "::1/128", "fc00::/7", "fe80::/10",
)]

def _is_public_hostname(hostname):
    try:
        infos = socket.getaddrinfo(hostname, None)
    except Exception:
        return False
    if not infos:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            return False
        if any(ip in net for net in PRIVATE_IP_NETWORKS):
            return False
    return True

def _decode_html(raw_bytes, header_encoding):
    for enc in filter(None, [header_encoding, "utf-8", "shift_jis", "euc-jp", "cp932"]):
        try:
            return raw_bytes.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw_bytes.decode("utf-8", errors="ignore")

def fetch_page_title(url):
    """URL先のページタイトルを取得する。プライベートIP・非HTML・取得失敗時はNoneを返す。"""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; KikimimiBot/1.0)"}
    for _ in range(LINK_MAX_REDIRECTS + 1):
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return None
        if not _is_public_hostname(parsed.hostname):
            return None
        try:
            resp = requests.get(url, headers=headers, timeout=LINK_FETCH_TIMEOUT, stream=True, allow_redirects=False)
        except Exception:
            return None
        try:
            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location")
                if not location:
                    return None
                url = urljoin(url, location)
                continue
            if resp.status_code != 200:
                return None
            content_type = resp.headers.get("Content-Type", "")
            if "html" not in content_type.lower():
                return None
            raw = resp.raw.read(LINK_MAX_BYTES, decode_content=True)
        except Exception:
            return None
        finally:
            resp.close()

        decoded = _decode_html(raw, resp.encoding)
        match = TITLE_TAG_PATTERN.search(decoded)
        if not match:
            return None
        title = html.unescape(match.group(1))
        title = re.sub(r'\s+', ' ', title).strip()
        return title[:MAX_TITLE_LENGTH] if title else None
    return None

async def resolve_link_label(url, loop):
    netloc = urlparse(url).netloc
    known = lookup_known_label(netloc)
    if known:
        return f"{known}省略"
    title = await loop.run_in_executor(None, fetch_page_title, url)
    if title:
        return f"リンク省略({title})"
    return f"リンク省略。{extract_base_domain(netloc)}"

async def resolve_links(text):
    urls = list(dict.fromkeys(URL_PATTERN.findall(text)))
    if not urls:
        return text
    loop = asyncio.get_running_loop()
    labels = await asyncio.gather(*(resolve_link_label(url, loop) for url in urls))
    for url, label in zip(urls, labels):
        text = text.replace(url, label)
    return text

def preprocess_text(text, guild):
    if not text:
        return ""

    if "```" in text:
        text = "ソースコード省略"

    text = re.sub(r'\|\|.*?\|\|', '伏せ字', text)

    for match in MENTION_PATTERN.finditer(text):
        member = guild.get_member(int(match.group(1)))
        text = text.replace(match.group(0), member.display_name if member else "ユーザー")

    for match in ROLE_MENTION_PATTERN.finditer(text):
        role = guild.get_role(int(match.group(1)))
        text = text.replace(match.group(0), role.name if role else "役職")

    for match in CHANNEL_MENTION_PATTERN.finditer(text):
        channel = guild.get_channel(int(match.group(1)))
        text = text.replace(match.group(0), channel.name if channel else "チャンネル")

    text = CUSTOM_EMOJI_PATTERN.sub(lambda m: f":{m.group(1)}:", text)

    return text

async def clean_text(text, guild):
    text = preprocess_text(text, guild)
    text = await resolve_links(text)
    text = re.sub(r'[a-zA-Z]+', lambda x: x.group(0).lower(), text)
    return text[:55]

# --- TTS エンジン ---
async def generate_audio_google(text, voice_name):
    loop = asyncio.get_running_loop()
    
    def tts_process():
        current_month = datetime.datetime.now().strftime("%Y-%m")
        data = load_json(WORD_COUNTER_FILE, {"count": 0, "last_reset": current_month})
        
        if data.get("last_reset") != current_month:
            print_log(f"月次リセット: {data.get('last_reset')} -> {current_month}")
            data["count"] = 0
            data["last_reset"] = current_month
            
        data["count"] += len(text)
        save_json(WORD_COUNTER_FILE, data)
        
        client_tts = texttospeech.TextToSpeechClient()
        s_input = texttospeech.SynthesisInput(text=text)
        v_params = texttospeech.VoiceSelectionParams(language_code="ja-JP", name=voice_name)
        a_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
        response = client_tts.synthesize_speech(input=s_input, voice=v_params, audio_config=a_config)
        return AudioSegment.from_file(io.BytesIO(response.audio_content), format="mp3")
        
    return await loop.run_in_executor(None, tts_process)

# --- Bot クラス ---
class KikimimiBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.all())
        self.tree = app_commands.CommandTree(self)
        self.connected_channel_id = None
        self.last_channel_speaker = {}

    async def setup_hook(self):
        try:
            discord.opus.load_opus('libopus.so.0')
        except:
            pass
        await self.tree.sync()

client = KikimimiBot()

# --- 再生ロジック ---
async def speak(vc, text, voice_name):
    if not vc or not vc.is_connected():
        return
    try:
        audio = await generate_audio_google(text, voice_name)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            audio.export(f.name, format="mp3")
            temp_path = f.name
        
        while vc.is_playing():
            await asyncio.sleep(0.1)
            
        vc.play(
            discord.FFmpegPCMAudio(temp_path, executable=FFMPEG_PATH), 
            after=lambda e: os.remove(temp_path) if os.path.exists(temp_path) else None
        )
    except Exception as e:
        print_log(f"再生エラー: {e}")

# --- 通知ロジック ---
async def voice_channel_activity(vc, member, activity_type, before_channel=None, after_channel=None):
    display_name = member.display_name
    display_name = re.sub(r'[a-zA-Z]+', lambda x: x.group(0).lower(), display_name)
    
    message = ""
    if activity_type == "入室" and after_channel:
        message = f"{display_name}が{after_channel.name}に入室しました。"
    elif activity_type == "退室" and before_channel:
        message = f"{display_name}が{before_channel.name}から退室しました。"
    elif activity_type == "移動" and before_channel and after_channel:
        message = f"{display_name}が{before_channel.name}から{after_channel.name}に移動しました。"

    if message:
        await speak(vc, message, SYSTEM_VOICE)

def get_connection_embed(text_channel_mention):
    """接続時の共通リッチEmbedオブジェクトを生成"""
    embed = discord.Embed(title="ボイスチャンネル接続", color=COLOR_SUCCESS)
    embed.description = (
        f"{text_channel_mention}に接続しました。 \n\n"
        "**使用可能なコマンド:**\n"
        "- **/leave** - ボットを切断\n"
        "- **/voice** - 読み上げボイスの変更\n"
        "- **/set_channel** - 自動接続の設定\n"
        "- **/status** - システム状況表示\n\n"
        f"**更新情報:**\n`{UPDATE_INFO}`"
    )
    return embed

def get_disconnect_embed(text_channel_mention):
    """切断時の共通リッチEmbedオブジェクトを生成"""
    embed = discord.Embed(title="ボイスチャンネル切断", color=COLOR_NOTICE)
    embed.description = (
        f"**{text_channel_mention}** での読み上げを終了しました。\n\n"
        "**利用可能なコマンド:**\n"
        "- **/join** - ボットを接続\n"
        "- **/voice** - 読み上げボイスの変更\n"
        "- **/set_channel** - 自動接続の設定\n"
        "- **/status** - システム状況表示\n\n"
        f"**更新情報:**\n`{UPDATE_INFO}`"
    )
    return embed

# --- コマンド ---
@client.tree.command(name='join', description='ボイスチャンネルに接続して読み上げを開始します')
async def join(interaction: discord.Interaction):
    if not interaction.user.voice:
        await send_embed(interaction, "エラー", "ボイスチャンネルに参加してから実行してください", COLOR_ERROR, True)
        return
    
    await interaction.response.defer()
    channel = interaction.user.voice.channel
    try:
        vc = await channel.connect(timeout=10)
        client.connected_channel_id = interaction.channel_id
        
        embed = get_connection_embed(interaction.channel.mention)
        await interaction.followup.send(embed=embed)
        await speak(vc, "ボイスチャンネルに接続しました。読み上げを開始します。", SYSTEM_VOICE)
    except Exception as e:
        await send_embed(interaction, "エラー", f"接続に失敗しました: {e}", COLOR_ERROR)

@client.tree.command(name='leave', description='ボイスチャンネルから切断します')
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        mention = interaction.channel.mention
        await interaction.guild.voice_client.disconnect()
        embed = get_disconnect_embed(mention)
        await interaction.response.send_message(embed=embed)
        client.connected_channel_id = None
    else:
        await send_embed(interaction, "エラー", "接続していません。", COLOR_ERROR, True)

@client.tree.command(name='set_channel', description='自動入室時の読み上げテキストチャンネルをここに設定します')
@app_commands.checks.has_permissions(manage_channels=True)
async def set_channel(interaction: discord.Interaction):
    config = load_json(CONFIG_FILE, {})
    config[str(interaction.guild.id)] = interaction.channel_id
    save_json(CONFIG_FILE, config)
    
    # 全体公開（ephemeral=False）で設定完了を通知
    await send_embed(
        interaction, 
        "設定完了", 
        f"今後、自動接続時は {interaction.channel.mention} で読み上げを開始します。", 
        COLOR_SUCCESS, 
        False
    )

@client.tree.command(name='voice', description='Google TTS 読み上げボイスを変更します')
@app_commands.choices(voice=[
    app_commands.Choice(name=label, value=name) for name, label in USER_VOICE_OPTIONS.items()
])
async def set_voice(interaction: discord.Interaction, voice: app_commands.Choice[str]):
    voices = load_json(USER_VOICES_FILE, {})
    voices[str(interaction.user.id)] = voice.value
    save_json(USER_VOICES_FILE, voices)
    await send_embed(interaction, "設定変更", f"声を **{voice.name}** に設定しました。", COLOR_SUCCESS, True)

@client.tree.command(name='status', description='システムの稼働状況を表示します')
async def status(interaction: discord.Interaction):
    uptime = str(datetime.timedelta(seconds=int(time.time() - START_TIME)))
    mem = psutil.virtual_memory()
    tts_data = load_json(WORD_COUNTER_FILE, {"count": 0})
    
    try:
        with open(current_log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            error_logs = [l for l in lines if "error" in l.lower() or "エラー" in l][-5:]
            last_logs = "".join(error_logs) if error_logs else "現在、記録されたエラーはありません。"
    except:
        last_logs = "ログを取得できませんでした。"

    embed = discord.Embed(title="ステータス", color=COLOR_NOTICE)
    embed.add_field(name="稼働時間", value=f"`{uptime}`", inline=True)
    embed.add_field(name="メモリ使用率", value=f"`{mem.percent}%`", inline=True)
    embed.add_field(name="TTS (今月)", value=f"`{tts_data['count']:,} / 1,000,000` 文字", inline=True)
    embed.add_field(name="更新情報", value=f"`{UPDATE_INFO}`", inline=False)
    embed.add_field(name="GitHub", value="[github.com/xxxxholica/kikimimi](https://github.com/xxxxholica/kikimimi)", inline=False)
    embed.add_field(name="エラーログ", value=f"```\n{last_logs}\n```", inline=False)
    embed.set_footer(text=f"{SYSTEM_FOOTER} | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    await interaction.response.send_message(embed=embed)

# --- イベント ---
@client.event
async def on_ready():
    print_log(f'ログイン: {client.user}')
    await client.change_presence(activity=discord.Game(BOT_PRESENCE))

@client.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    vc = message.guild.voice_client
    if not vc or not vc.is_connected():
        return

    # 添付ファイル情報の取得
    attachment_notice = ""
    if message.attachments:
        has_image = any(att.content_type and att.content_type.startswith('image') for att in message.attachments)
        attachment_notice = "画像が送信されました。" if has_image else "ファイルが送信されました。"

    cleaned = await clean_text(message.content, message.guild)

    # 最終的な読み上げテキストを構築
    body = (attachment_notice + " " + cleaned).strip()

    if not body:
        return

    channel_id = message.channel.id
    author_id = message.author.id
    is_consecutive = client.last_channel_speaker.get(channel_id) == author_id
    client.last_channel_speaker[channel_id] = author_id
    is_home_channel = channel_id == client.connected_channel_id

    if is_consecutive:
        final_text = body if is_home_channel else f"{message.channel.name}に投稿されました。{body}"
    else:
        display_name = re.sub(r'[a-zA-Z]+', lambda x: x.group(0).lower(), message.author.display_name)
        final_text = f"{display_name}　{body}" if is_home_channel else f"{message.channel.name}に{display_name}が投稿しました。{body}"

    user_voices = load_json(USER_VOICES_FILE, {})
    user_id_str = str(message.author.id)

    if user_id_str not in user_voices:
        used_counts = Counter(user_voices.values())
        shuffled_voices = AVAILABLE_VOICE_NAMES.copy()
        random.shuffle(shuffled_voices)
        unused_voices = [v for v in shuffled_voices if v not in used_counts]
        voice_name = unused_voices[0] if unused_voices else min(used_counts, key=used_counts.get)
        user_voices[user_id_str] = voice_name
        save_json(USER_VOICES_FILE, user_voices)
        print_log(f"新規ボイス割当: {message.author.display_name} -> {voice_name}")
    else:
        voice_name = user_voices[user_id_str]

    print_log(f"発言: {message.author.display_name} ({voice_name}) -> {final_text}")
    await speak(vc, final_text, voice_name)

@client.event
async def on_voice_state_update(member, before, after):
    if member.bot or before.channel == after.channel:
        return
    
    vc = member.guild.voice_client

    # --- 自動接続ロジック ---
    if vc is None and after.channel is not None:
        try:
            vc = await after.channel.connect(timeout=10)
            
            config = load_json(CONFIG_FILE, {})
            target_id = config.get(str(member.guild.id))
            
            text_ch = client.get_channel(target_id) if target_id else \
                      discord.utils.get(member.guild.text_channels, name="読み上げ") or \
                      member.guild.system_channel or \
                      member.guild.text_channels[0]
            
            client.connected_channel_id = text_ch.id
            
            embed = get_connection_embed(text_ch.mention)
            await text_ch.send(embed=embed)
            
            await speak(vc, "ボイスチャンネルに自動で接続しました。読み上げを開始します。", SYSTEM_VOICE)
            print_log(f"自動接続: {after.channel.name} (Text: {text_ch.name})")
        except Exception as e:
            print_log(f"自動接続エラー: {e}")
        return

    if not vc:
        return

    is_event_in_current_vc = (before.channel == vc.channel) or (after.channel == vc.channel)
    if not is_event_in_current_vc:
        return

    if before.channel is None and after.channel:
        await voice_channel_activity(vc, member, "入室", after_channel=after.channel)
    elif after.channel is None and before.channel:
        await voice_channel_activity(vc, member, "退室", before_channel=before.channel)
        
        if len(vc.channel.members) == 1:
            text_channel = client.get_channel(client.connected_channel_id)
            mention = text_channel.mention if text_channel else "テキストチャンネル"
            await vc.disconnect()
            if text_channel:
                embed = get_disconnect_embed(mention)
                await text_channel.send(embed=embed)
            client.connected_channel_id = None
            print_log(f"自動切断: {before.channel.name}")

    elif before.channel and after.channel:
        await voice_channel_activity(vc, member, "移動", before_channel=before.channel, after_channel=after.channel)

client.run(os.environ.get("KIKIMIMI_BOT_TOKEN"))
