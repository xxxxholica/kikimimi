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
import struct
import threading
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
COLOR_PLAYER = 0x1db954   # 音楽再生中 (Spotify Green)
COLOR_PAUSED = 0xf1c40f   # 音楽一時停止 (アンバーイエロー)
COLOR_IDLE = 0x2b2d31     # 音楽待機/停止 (スレートグレー)

# カスタマイズ設定 (環境変数から取得)
VERSION = os.getenv("VERSION", "v1.2.0")
UPDATE_INFO = os.getenv("UPDATE_INFO", "音楽再生機能を追加。読み上げと同時再生や/musicのプログレスバーUIに対応。")
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

# TTS制限設定 (Google Cloud無料枠 1,000,000文字 / 1発話上限)
TTS_MONTHLY_LIMIT = int(os.getenv("TTS_MONTHLY_LIMIT", "1000000"))
MAX_SPEAK_LENGTH = int(os.getenv("MAX_SPEAK_LENGTH", "150"))

# 音楽キャッシュ設定 (サーバー単位、直近N件・合計サイズ上限で管理)
MUSIC_CACHE_MAX_TRACKS = int(os.getenv("MUSIC_CACHE_MAX_TRACKS", "10"))
MUSIC_CACHE_MAX_MB = int(os.getenv("MUSIC_CACHE_MAX_MB", "200"))
MUSIC_VOLUME = float(os.getenv("MUSIC_VOLUME", "0.05"))  # TTS音量を1.0とした相対比
MUSIC_CACHE_DIR = os.path.join(BASE_DIR, "data", "music_cache")
MUSIC_CACHE_FILE = os.path.join(BASE_DIR, "data", "music_cache.json")
AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".opus", ".aac"}

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = KEY_PATH
FFMPEG_PATH = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
FFPROBE_PATH = shutil.which("ffprobe") or "/usr/bin/ffprobe"

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
    temp_path = f"{path}.tmp.{os.getpid()}"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        os.replace(temp_path, path)
    except Exception as e:
        print_log(f"JSON保存エラー ({path}): {e}")
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

# --- 音楽キャッシュ ---
async def get_audio_duration(file_path):
    """ffprobeを使用して音声ファイルの総再生時間(秒)を取得する"""
    try:
        proc = await asyncio.create_subprocess_exec(
            FFPROBE_PATH,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0 and stdout:
            val = float(stdout.decode().strip())
            return max(0.0, val)
    except Exception as e:
        print_log(f"ffprobe再生時間取得エラー ({file_path}): {e}")
    return 0.0

async def ensure_track_duration(track):
    """トラック情報にdurationがない場合、ffprobeで取得してキャッシュを更新する"""
    duration = track.get("duration")
    if duration is None or duration <= 0:
        if os.path.exists(track.get("path", "")):
            duration = await get_audio_duration(track["path"])
            track["duration"] = duration
            try:
                cache = load_json(MUSIC_CACHE_FILE, {})
                for guild_tracks in cache.values():
                    for t in guild_tracks:
                        if t.get("id") == track.get("id"):
                            t["duration"] = duration
                            break
                save_json(MUSIC_CACHE_FILE, cache)
            except Exception:
                pass
    return duration or 0.0

def is_audio_attachment(attachment):
    if attachment.content_type and attachment.content_type.startswith("audio/"):
        return True
    ext = os.path.splitext(attachment.filename)[1].lower()
    return ext in AUDIO_EXTENSIONS

async def cache_music_attachment(guild_id, attachment, uploader_name):
    """音楽添付ファイルをサーバー単位でキャッシュする。件数・合計サイズの上限を超えたら古い順に削除する。"""
    max_bytes = MUSIC_CACHE_MAX_MB * 1024 * 1024
    if attachment.size > max_bytes:
        print_log(f"音楽キャッシュ: {attachment.filename} はサイズ上限({MUSIC_CACHE_MAX_MB}MB)を超えるためキャッシュしません")
        return

    guild_dir = os.path.join(MUSIC_CACHE_DIR, str(guild_id))
    os.makedirs(guild_dir, exist_ok=True)
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', attachment.filename)
    local_path = os.path.join(guild_dir, f"{attachment.id}_{safe_name}")

    try:
        await attachment.save(local_path)
    except Exception as e:
        print_log(f"音楽キャッシュ保存エラー: {e}")
        return

    duration = await get_audio_duration(local_path)

    cache = load_json(MUSIC_CACHE_FILE, {})
    tracks = cache.setdefault(str(guild_id), [])
    tracks.insert(0, {
        "id": str(attachment.id),
        "filename": attachment.filename,
        "uploader": uploader_name,
        "uploaded_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "size": attachment.size,
        "duration": duration,
        "path": local_path,
    })

    while len(tracks) > MUSIC_CACHE_MAX_TRACKS or sum(t["size"] for t in tracks) > max_bytes:
        removed = tracks.pop()
        if os.path.exists(removed["path"]):
            try:
                os.remove(removed["path"])
            except OSError:
                pass

    save_json(MUSIC_CACHE_FILE, cache)
    print_log(f"音楽キャッシュ追加: {attachment.filename} (guild={guild_id}, duration={duration:.1f}s)")

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

MAX_TITLE_LENGTH = 50
LINK_FETCH_TIMEOUT = 4
LINK_MAX_REDIRECTS = 3
LINK_MAX_BYTES = 262144

KNOWN_SITE_LABELS = {
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

def extract_base_domain(hostname):
    """サブドメインを省いたドメイン名を返す(例: www.hinata.works -> hinata.works)。IPアドレスはそのまま返す。"""
    hostname = hostname.lower()
    try:
        ipaddress.ip_address(hostname)
        return hostname
    except ValueError:
        pass
    labels = hostname.split(".")
    if len(labels) <= 2:
        return hostname
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

DISCORD_EMBED_WAIT_TIMEOUT = 3.0

def _find_embed_title(message, url, solo_link):
    """メッセージ内のembedからurlに対応するタイトルを探す。
    Discordはyoutu.be等の短縮URLを正規化したURLでembed化することがあり文字列が完全一致しないため、
    メッセージ内のリンクが1つだけ(solo_link)の場合はURL不一致でもタイトルがあれば採用する。"""
    for embed in message.embeds:
        if embed.url == url and embed.title:
            return embed.title
    if solo_link:
        for embed in message.embeds:
            if embed.title:
                return embed.title
    return None

async def wait_for_discord_embed_title(message, url, solo_link):
    """Discordが自動生成するリンク埋め込み(embed)のタイトルを待つ。
    多くのサイトはDiscordの公式クローラーには情報を渡すため、自前のfetchより成功率が高い。"""
    title = _find_embed_title(message, url, solo_link)
    if title:
        return title

    def check(before, after):
        return after.id == message.id and _find_embed_title(after, url, solo_link)

    try:
        _, after = await client.wait_for('message_edit', check=check, timeout=DISCORD_EMBED_WAIT_TIMEOUT)
        return _find_embed_title(after, url, solo_link)
    except asyncio.TimeoutError:
        return None

async def resolve_link_label(url, loop, message, solo_link):
    parsed_url = urlparse(url)
    known = lookup_known_label(parsed_url.netloc)
    if known:
        return f"{known}省略"

    title = await wait_for_discord_embed_title(message, url, solo_link)
    if not title:
        title = await loop.run_in_executor(None, fetch_page_title, url)
    if title:
        title = re.sub(r'\s+', ' ', title).strip()[:MAX_TITLE_LENGTH]
        return f"リンク省略({title})"
    return f"リンク省略。{extract_base_domain(parsed_url.hostname or parsed_url.netloc)}"

async def resolve_links(text, message):
    urls = list(dict.fromkeys(URL_PATTERN.findall(text)))
    if not urls:
        return text
    loop = asyncio.get_running_loop()
    solo_link = len(urls) == 1
    labels = await asyncio.gather(*(resolve_link_label(url, loop, message, solo_link) for url in urls))
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

async def clean_text(text, guild, message):
    text = preprocess_text(text, guild)
    text = await resolve_links(text, message)
    text = re.sub(r'[a-zA-Z]+', lambda x: x.group(0).lower(), text)
    return text

# --- TTS エンジン ---
_tts_client = None

def _get_tts_client():
    global _tts_client
    if _tts_client is None:
        _tts_client = texttospeech.TextToSpeechClient()
    return _tts_client

def get_next_reset_timestamp():
    """翌月1日 00:00:00 (JST) の Unix タイムスタンプを返す"""
    now = datetime.datetime.now()
    if now.month == 12:
        next_month = datetime.datetime(now.year + 1, 1, 1, 0, 0, 0)
    else:
        next_month = datetime.datetime(now.year, now.month + 1, 1, 0, 0, 0)
    return int(next_month.timestamp())

def get_tts_status():
    """現在の月間TTS状態を取得・更新する。
    戻り値: (is_limited: bool, count: int, reset_ts: int)
    """
    current_month = datetime.datetime.now().strftime("%Y-%m")
    data = load_json(WORD_COUNTER_FILE, {"count": 0, "last_reset": current_month, "notified_limit": False, "last_vc_notice": 0})
    if data.get("last_reset") != current_month:
        print_log(f"月次リセット: {data.get('last_reset')} -> {current_month}")
        data["count"] = 0
        data["last_reset"] = current_month
        data["notified_limit"] = False
        data["last_vc_notice"] = 0
        save_json(WORD_COUNTER_FILE, data)

    is_limited = data.get("count", 0) >= TTS_MONTHLY_LIMIT
    return is_limited, data.get("count", 0), get_next_reset_timestamp()

def get_tts_limit_embed(reset_ts):
    """月間TTS上限到達時の共通Embedを生成"""
    return discord.Embed(
        title="接続できません",
        description=(
            f"今月の無料使用量上限（`{TTS_MONTHLY_LIMIT:,}文字`）に達しているため、ボイスチャンネルに接続できません。\n\n"
            f"**次回のリセット予定**\n<t:{reset_ts}:F>"
        ),
        color=COLOR_ERROR
    )

def check_and_update_tts_count(char_count):
    """月間TTS文字数を更新する。
    戻り値: (allowed: bool, just_reached: bool, current_count: int)
    - allowed: 今回の生成が許可されるか (上限未到達)
    - just_reached: 今回の生成で初めて月間上限に達したか (通知用)
    - current_count: 更新後の月間文字数
    """
    current_month = datetime.datetime.now().strftime("%Y-%m")
    data = load_json(WORD_COUNTER_FILE, {"count": 0, "last_reset": current_month, "notified_limit": False, "last_vc_notice": 0})

    if data.get("last_reset") != current_month:
        print_log(f"月次リセット: {data.get('last_reset')} -> {current_month}")
        data["count"] = 0
        data["last_reset"] = current_month
        data["notified_limit"] = False
        data["last_vc_notice"] = 0

    current_count = data.get("count", 0)
    if current_count >= TTS_MONTHLY_LIMIT:
        return False, False, current_count

    data["count"] = current_count + char_count
    just_reached = False
    if data["count"] >= TTS_MONTHLY_LIMIT and not data.get("notified_limit", False):
        data["notified_limit"] = True
        just_reached = True

    save_json(WORD_COUNTER_FILE, data)
    return True, just_reached, data["count"]

async def generate_audio_google(text, voice_name):
    """Google Cloud TTSで音声を合成する。月間上限到達時は (None, just_reached) を返す。"""
    loop = asyncio.get_running_loop()

    def tts_process():
        allowed, just_reached, current_count = check_and_update_tts_count(len(text))
        if not allowed:
            print_log(f"TTS月間上限到達中 ({current_count:,} / {TTS_MONTHLY_LIMIT:,}文字): 音声生成をスキップします")
            return None, False

        try:
            client_tts = _get_tts_client()
            s_input = texttospeech.SynthesisInput(text=text)
            v_params = texttospeech.VoiceSelectionParams(language_code="ja-JP", name=voice_name)
            a_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
            response = client_tts.synthesize_speech(input=s_input, voice=v_params, audio_config=a_config)
            audio = AudioSegment.from_file(io.BytesIO(response.audio_content), format="mp3")
            return audio, just_reached
        except Exception as e:
            print_log(f"Google TTS API エラー: {e}")
            return None, False

    return await loop.run_in_executor(None, tts_process)

# --- Bot クラス ---
class KikimimiBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.all())
        self.tree = app_commands.CommandTree(self)
        self.connected_channel_id = None
        self.last_channel_speaker = {}
        self.command_ids = {}

    async def setup_hook(self):
        try:
            discord.opus.load_opus('libopus.so.0')
        except:
            pass
        synced = await self.tree.sync()
        self.command_ids = {cmd.name: cmd.id for cmd in synced}

client = KikimimiBot()

def cmd_mention(name):
    """スラッシュコマンドをタップ可能なチップとして表示するためのメンション文字列を生成する"""
    command_id = client.command_ids.get(name)
    return f"</{name}:{command_id}>" if command_id else f"`/{name}`"

# --- 再生ロジック ---
# discord.pyのVoiceClientは同時に1つのAudioSourceしか再生できないため、
# ギルドごとにこのミキサーを1つだけvc.play()し続け、TTS発話と音楽再生を
# ここに出し入れすることで両者の同時再生(重ね聞き)を実現する。
FRAME_SIZE = 3840  # 48kHz * 16bit(2byte) * ステレオ(2ch) * 20ms
SAMPLE_COUNT = FRAME_SIZE // 2
SAMPLE_FORMAT = f"<{SAMPLE_COUNT}h"
SILENCE_FRAME = b"\x00" * FRAME_SIZE

class MixingAudioSource(discord.AudioSource):
    def __init__(self, vc):
        self._sources = []  # list[tuple[AudioSource, Optional[Callable], float]]
        self._lock = threading.Lock()
        self._vc = vc
        # このミキサーは常時再生し続けるため、discord.pyが再生開始時に1度だけ
        # SpeakingState.voiceにした状態を初期値として引き継ぎ、無音区間でnoneに戻す
        self._speaking = True

    def _set_speaking(self, speaking):
        try:
            asyncio.run_coroutine_threadsafe(self._vc.ws.speak(speaking), self._vc.loop)
        except Exception:
            pass

    def add(self, source, on_finished=None, volume=1.0):
        with self._lock:
            self._sources.append((source, on_finished, volume))

    def remove(self, source):
        with self._lock:
            self._sources = [e for e in self._sources if e[0] is not source]
        try:
            source.cleanup()
        except Exception:
            pass

    def read(self):
        with self._lock:
            entries = list(self._sources)

        frames = []
        finished = []
        for source, on_finished, volume in entries:
            try:
                data = source.read()
            except Exception:
                data = b""
            if not data:
                finished.append((source, on_finished, volume))
                continue
            if len(data) < FRAME_SIZE:
                data = data + b"\x00" * (FRAME_SIZE - len(data))
            frames.append((data, volume))

        if finished:
            with self._lock:
                self._sources = [e for e in self._sources if e not in finished]
            for source, on_finished, _ in finished:
                try:
                    source.cleanup()
                except Exception:
                    pass
                if on_finished:
                    on_finished()

        if not frames:
            if self._speaking:
                self._speaking = False
                self._set_speaking(discord.SpeakingState.none)
            return SILENCE_FRAME

        if not self._speaking:
            self._speaking = True
            self._set_speaking(discord.SpeakingState.voice)

        if len(frames) == 1 and frames[0][1] == 1.0:
            return frames[0][0]
        return self._mix(frames)

    def _mix(self, frames):
        mixed = [0] * SAMPLE_COUNT
        for data, volume in frames:
            for i, s in enumerate(struct.unpack(SAMPLE_FORMAT, data)):
                mixed[i] += s * volume
        clipped = [max(-32768, min(32767, int(v))) for v in mixed]
        return struct.pack(SAMPLE_FORMAT, *clipped)

    def is_opus(self):
        return False

    def cleanup(self):
        with self._lock:
            entries, self._sources = self._sources, []
        for source, _, _ in entries:
            try:
                source.cleanup()
            except Exception:
                pass

class PausableAudioSource(discord.AudioSource):
    """一時停止に対応したAudioSourceラッパー。一時停止中は無音フレームを返すことでミキサーのfinished判定を回避し、内部ソースの読み進めを停止する"""
    def __init__(self, source):
        self._source = source
        self._is_paused = False
        self._lock = threading.Lock()

    def pause(self):
        with self._lock:
            self._is_paused = True

    def resume(self):
        with self._lock:
            self._is_paused = False

    @property
    def is_paused(self):
        with self._lock:
            return self._is_paused

    def read(self):
        with self._lock:
            if self._is_paused:
                return SILENCE_FRAME
        return self._source.read()

    def cleanup(self):
        with self._lock:
            try:
                self._source.cleanup()
            except Exception:
                pass

    def is_opus(self):
        return self._source.is_opus()

# ギルドID -> 状態 (Botは単一プロセスでの単一/少数サーバー運用を想定しているが、
# 音楽キャッシュ・再生まわりはサーバー単位で独立させる)
guild_mixers = {}       # guild_id -> MixingAudioSource
guild_music_states = {} # guild_id -> MusicPlayerState
guild_tts_queue = {}    # guild_id -> asyncio.Queue (TTSは従来通り逐次再生)
guild_tts_tasks = {}    # guild_id -> asyncio.Task (TTSキューの消費タスク)

class MusicPlayerState:
    """各ギルドの音楽再生状況を保持・管理するクラス"""
    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.track = None
        self.source = None              # PausableAudioSource
        self.start_time = 0.0           # monotonic
        self.total_paused_duration = 0.0
        self.pause_start_time = 0.0
        self.is_paused = False
        self.auto_stop_task = None      # 3分放置タイムアウトタスク
        self.progress_task = None       # 15秒おきプログレス更新タスク
        self.message = None             # コントローラーの discord.Message
        self.last_status = "idle"       # "idle", "playing", "paused", "stopped", "ended"

    def get_elapsed_seconds(self):
        if not self.track or self.start_time == 0.0:
            return 0.0
        if self.is_paused:
            elapsed = self.pause_start_time - self.start_time - self.total_paused_duration
        else:
            elapsed = time.monotonic() - self.start_time - self.total_paused_duration
        duration = self.track.get("duration", 0.0)
        if duration > 0:
            elapsed = min(elapsed, duration)
        return max(0.0, elapsed)

    def pause(self):
        if not self.is_paused and self.source:
            self.is_paused = True
            self.pause_start_time = time.monotonic()
            self.source.pause()
            self.last_status = "paused"

    def resume(self):
        if self.is_paused and self.source:
            self.is_paused = False
            self.total_paused_duration += (time.monotonic() - self.pause_start_time)
            self.source.resume()
            self.last_status = "playing"
            if self.auto_stop_task and not self.auto_stop_task.done():
                self.auto_stop_task.cancel()
                self.auto_stop_task = None

    def cleanup_tasks(self):
        if self.progress_task and not self.progress_task.done():
            self.progress_task.cancel()
            self.progress_task = None
        if self.auto_stop_task and not self.auto_stop_task.done():
            self.auto_stop_task.cancel()
            self.auto_stop_task = None

def get_cached_tracks(guild_id):
    """サーバーにキャッシュされた音楽トラックリスト(存在確認済み)を取得"""
    cache = load_json(MUSIC_CACHE_FILE, {})
    return [t for t in cache.get(str(guild_id), []) if os.path.exists(t.get("path", ""))]

def format_duration(seconds: float) -> str:
    secs = int(max(0, seconds))
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def render_progress_bar(current: float, total: float, bar_length: int = 16) -> str:
    """ミニマル角括弧プログレスバー [████░░░░]"""
    if total <= 0:
        return f"[{'░' * bar_length}]"
    ratio = max(0.0, min(1.0, current / total))
    filled = int(round(bar_length * ratio))
    empty = bar_length - filled
    return f"[{'█' * filled}{'░' * empty}]"

def build_music_embed(state=None, track=None, status=None):
    """音楽プレイヤーのリッチEmbedを生成"""
    if status is None:
        status = state.last_status if state else "idle"
    if track is None and state:
        track = state.track

    if status == "playing" and track:
        curr = state.get_elapsed_seconds() if state else 0.0
        total = track.get("duration", 0.0)
        curr_str = format_duration(curr)
        total_str = format_duration(total) if total > 0 else "--:--"
        bar = render_progress_bar(curr, total, bar_length=16)

        embed = discord.Embed(title="🎵  NOW PLAYING", color=COLOR_PLAYER)
        embed.description = (
            f"### **{track['filename']}**\n\n"
            f"`▶`  `{curr_str}`  `{bar}`  `{total_str}`\n\n"
            f"👤 **投稿者**: {track.get('uploader', '不明')}\n\n"
            "🔄 15秒おきに自動更新"
        )
        return embed

    elif status == "paused" and track:
        curr = state.get_elapsed_seconds() if state else 0.0
        total = track.get("duration", 0.0)
        curr_str = format_duration(curr)
        total_str = format_duration(total) if total > 0 else "--:--"
        bar = render_progress_bar(curr, total, bar_length=16)

        embed = discord.Embed(title="⏸️  PAUSED", color=COLOR_PAUSED)
        embed.description = (
            f"### **{track['filename']}**\n\n"
            f"`⏸`  `{curr_str}`  `{bar}`  `{total_str}`\n\n"
            f"👤 **投稿者**: {track.get('uploader', '不明')}\n\n"
            "⚠️３分間の無操作で自動停止します"
        )
        return embed

    elif status == "stopped":
        embed = discord.Embed(title="⏹️  STOPPED", color=COLOR_IDLE)
        embed.description = (
            "再生を停止しました。\n"
            "下のメニューから曲を選択すると再生を開始します。"
        )
        return embed

    elif status == "ended":
        embed = discord.Embed(title="🏁  TRACK FINISHED", color=COLOR_IDLE)
        filename = track['filename'] if track else '曲'
        embed.description = (
            f"**{filename}** の再生が終了しました。\n"
            "下のメニューから曲を選択すると再生を開始します。"
        )
        return embed

    else:  # idle
        embed = discord.Embed(title="🎵  MUSIC PLAYER", color=COLOR_IDLE)
        embed.description = (
            "キャッシュされた音楽をボイスチャンネルで再生します。\n"
            "下のメニューから曲を選択してください。"
        )
        return embed

def attach_mixer(vc):
    """ボイス接続時にミキサーを起動し、そのギルドの再生ハブとして登録する"""
    mixer = MixingAudioSource(vc)
    vc.play(mixer)
    guild_mixers[vc.guild.id] = mixer
    return mixer

def detach_mixer(guild_id):
    """切断時にそのギルドの再生関連状態を破棄する"""
    mixer = guild_mixers.pop(guild_id, None)
    if mixer:
        mixer.cleanup()
    state = guild_music_states.pop(guild_id, None)
    if state:
        state.cleanup_tasks()
        if state.source:
            state.source.cleanup()
    task = guild_tts_tasks.pop(guild_id, None)
    if task:
        task.cancel()
    guild_tts_queue.pop(guild_id, None)

async def process_tts_queue(guild_id):
    queue = guild_tts_queue[guild_id]
    try:
        while True:
            text, voice_name = await queue.get()
            mixer = guild_mixers.get(guild_id)
            if mixer is None:
                continue
            temp_path = None
            try:
                audio, just_reached = await generate_audio_google(text, voice_name)

                if just_reached:
                    channel_id = client.connected_channel_id
                    if channel_id:
                        channel = client.get_channel(channel_id)
                        if channel:
                            reset_ts = get_next_reset_timestamp()
                            embed = get_tts_limit_embed(reset_ts)
                            asyncio.create_task(channel.send(embed=embed))

                    guild = client.get_guild(guild_id)
                    if guild and guild.voice_client:
                        detach_mixer(guild_id)
                        asyncio.create_task(guild.voice_client.disconnect())
                        client.connected_channel_id = None
                    continue

                if audio is None:
                    continue

                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    audio.export(f.name, format="mp3")
                    temp_path = f.name

                source = discord.FFmpegPCMAudio(temp_path, executable=FFMPEG_PATH)
                finished = asyncio.Event()
                loop = asyncio.get_running_loop()

                def on_finished(path=temp_path):
                    if os.path.exists(path):
                        try:
                            os.remove(path)
                        except OSError:
                            pass
                    loop.call_soon_threadsafe(finished.set)

                mixer.add(source, on_finished=on_finished)
                await finished.wait()
            except Exception as e:
                print_log(f"再生エラー: {e}")
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
    except asyncio.CancelledError:
        pass

async def speak(vc, text, voice_name):
    if not vc or not vc.is_connected():
        return
    guild_id = vc.guild.id
    if guild_id not in guild_mixers:
        return
    queue = guild_tts_queue.setdefault(guild_id, asyncio.Queue())
    await queue.put((text, voice_name))
    if guild_id not in guild_tts_tasks or guild_tts_tasks[guild_id].done():
        guild_tts_tasks[guild_id] = asyncio.create_task(process_tts_queue(guild_id))

class MusicSelect(discord.ui.Select):
    def __init__(self, guild_id, tracks):
        options = [
            discord.SelectOption(
                label=track["filename"][:100],
                description=f'{track["uploader"]} ・ {track["uploaded_at"][:16].replace("T", " ")}'[:100],
                value=track["id"],
            )
            for track in tracks[:25]
        ]
        super().__init__(placeholder="🎵 再生する曲を選択", options=options, row=0)
        self.guild_id = guild_id
        self.tracks_by_id = {track["id"]: track for track in tracks}

    async def callback(self, interaction: discord.Interaction):
        track = self.tracks_by_id.get(self.values[0])
        vc = interaction.guild.voice_client
        if not track or not vc or not vc.is_connected():
            await interaction.response.send_message("ボイスチャンネルに接続していないため再生できません。", ephemeral=True)
            return

        await interaction.response.defer()
        await ensure_track_duration(track)

        msg = interaction.message
        await play_track(interaction.guild, track, message=msg)

        state = guild_music_states.get(interaction.guild.id)
        tracks = get_cached_tracks(interaction.guild.id)
        embed = build_music_embed(state, track=track, status="playing")
        view = MusicPlayerView(interaction.guild.id, tracks)
        await interaction.edit_original_response(embed=embed, view=view)

class MusicPlayerView(discord.ui.View):
    def __init__(self, guild_id, tracks):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.tracks = tracks

        state = guild_music_states.get(guild_id)
        is_playing = state and state.source is not None and not state.is_paused
        is_paused = state and state.is_paused
        has_active_track = is_playing or is_paused

        # Row 0: 曲選択セレクト
        if tracks:
            self.add_item(MusicSelect(guild_id, tracks))

        # Row 1: ボタン群
        if is_paused:
            self.pause_resume_btn = discord.ui.Button(
                label="再開", emoji="▶️", style=discord.ButtonStyle.success, row=1, disabled=False
            )
            self.pause_resume_btn.callback = self.resume_callback
        else:
            self.pause_resume_btn = discord.ui.Button(
                label="一時停止", emoji="⏸️", style=discord.ButtonStyle.secondary, row=1, disabled=not is_playing
            )
            self.pause_resume_btn.callback = self.pause_callback
        self.add_item(self.pause_resume_btn)

        self.stop_btn = discord.ui.Button(
            label="停止", emoji="⏹️", style=discord.ButtonStyle.danger, row=1, disabled=not has_active_track
        )
        self.stop_btn.callback = self.stop_callback
        self.add_item(self.stop_btn)

    async def pause_callback(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            await interaction.response.send_message("ボイスチャンネルに接続されていません。", ephemeral=True)
            return
        await interaction.response.defer()
        await pause_track(interaction.guild)
        state = guild_music_states.get(self.guild_id)
        embed = build_music_embed(state, status="paused")
        view = MusicPlayerView(self.guild_id, self.tracks)
        await interaction.edit_original_response(embed=embed, view=view)

    async def resume_callback(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            await interaction.response.send_message("ボイスチャンネルに接続されていないため再開できません。", ephemeral=True)
            return
        await interaction.response.defer()
        resumed = await resume_track(interaction.guild)
        if not resumed:
            await interaction.followup.send("再開できませんでした。再度曲を選択してください。", ephemeral=True)
            return
        state = guild_music_states.get(self.guild_id)
        embed = build_music_embed(state, status="playing")
        view = MusicPlayerView(self.guild_id, self.tracks)
        await interaction.edit_original_response(embed=embed, view=view)

    async def stop_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await stop_track(interaction.guild, status="stopped")
        state = guild_music_states.get(self.guild_id)
        embed = build_music_embed(state, status="stopped")
        view = MusicPlayerView(self.guild_id, self.tracks)
        await interaction.edit_original_response(embed=embed, view=view)

def start_music_progress_loop(guild_id):
    """15秒おきにプレイヤーEmbedのプログレスバーを更新するバックグラウンドタスク"""
    state = guild_music_states.get(guild_id)
    if not state:
        return
    if state.progress_task and not state.progress_task.done():
        state.progress_task.cancel()

    async def loop_coro():
        try:
            while True:
                await asyncio.sleep(15)
                curr_state = guild_music_states.get(guild_id)
                if not curr_state or not curr_state.source or curr_state.is_paused:
                    continue
                if not curr_state.message:
                    break

                guild = client.get_guild(guild_id)
                vc = guild.voice_client if guild else None
                if not vc or not vc.is_connected():
                    break

                tracks = get_cached_tracks(guild_id)
                embed = build_music_embed(curr_state, status="playing")
                view = MusicPlayerView(guild_id, tracks)
                try:
                    await curr_state.message.edit(embed=embed, view=view)
                except discord.NotFound:
                    break
                except discord.HTTPException as e:
                    print_log(f"プログレス更新エラー (HTTP): {e}")
                    pass
        except asyncio.CancelledError:
            pass

    state.progress_task = asyncio.create_task(loop_coro())

async def play_track(guild, track, message=None):
    """指定トラックをそのギルドの音楽スロットで再生する(既存の再生中トラックは差し替え)"""
    mixer = guild_mixers.get(guild.id)
    if mixer is None:
        return False

    state = guild_music_states.setdefault(guild.id, MusicPlayerState(guild.id))
    state.cleanup_tasks()

    if state.source is not None:
        mixer.remove(state.source)
        state.source = None

    loop = asyncio.get_running_loop()
    raw_source = discord.FFmpegPCMAudio(track["path"], executable=FFMPEG_PATH)
    source = PausableAudioSource(raw_source)

    def on_finished():
        async def finish_coro():
            curr_state = guild_music_states.get(guild.id)
            if curr_state and curr_state.source is source:
                curr_state.cleanup_tasks()
                curr_state.last_status = "ended"
                curr_state.source = None
                if curr_state.message:
                    try:
                        tracks = get_cached_tracks(guild.id)
                        embed = build_music_embed(curr_state, track=curr_state.track, status="ended")
                        view = MusicPlayerView(guild.id, tracks)
                        await curr_state.message.edit(embed=embed, view=view)
                    except Exception:
                        pass
        asyncio.run_coroutine_threadsafe(finish_coro(), loop)

    state.track = track
    state.source = source
    state.start_time = time.monotonic()
    state.total_paused_duration = 0.0
    state.is_paused = False
    state.last_status = "playing"
    if message:
        state.message = message

    mixer.add(source, on_finished=on_finished, volume=MUSIC_VOLUME)
    start_music_progress_loop(guild.id)
    return True

async def pause_track(guild):
    """再生中の音楽を一時停止する。3分放置タイマーをセット"""
    state = guild_music_states.get(guild.id)
    if not state or not state.source or state.is_paused:
        return False

    state.pause()

    # 3分放置で自動停止するタイマー
    async def auto_stop_coro():
        try:
            await asyncio.sleep(180)
            curr = guild_music_states.get(guild.id)
            if curr and curr.is_paused and curr.source is state.source:
                print_log(f"音楽再生: 一時停止タイムアウト(3分)のため自動停止 (guild={guild.id})")
                await stop_track(guild, status="stopped")
        except asyncio.CancelledError:
            pass

    state.auto_stop_task = asyncio.create_task(auto_stop_coro())
    return True

async def resume_track(guild):
    """一時停止中の音楽を再開する"""
    state = guild_music_states.get(guild.id)
    if not state or not state.source or not state.is_paused:
        return False

    vc = guild.voice_client
    if not vc or not vc.is_connected():
        return False

    state.resume()
    start_music_progress_loop(guild.id)
    return True

async def stop_track(guild, status="stopped"):
    """再生中または一時停止中の音楽を停止する"""
    state = guild_music_states.get(guild.id)
    if not state:
        return False

    state.cleanup_tasks()
    mixer = guild_mixers.get(guild.id)
    if state.source and mixer:
        mixer.remove(state.source)
    state.source = None
    state.is_paused = False
    state.last_status = status

    if state.message:
        try:
            tracks = get_cached_tracks(guild.id)
            embed = build_music_embed(state, status=status)
            view = MusicPlayerView(guild.id, tracks)
            await state.message.edit(embed=embed, view=view)
        except Exception:
            pass
    return True

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
        f"- {cmd_mention('leave')} - ボットを切断\n"
        f"- {cmd_mention('music')} - 音楽プレイヤーを表示・操作\n"
        f"- {cmd_mention('voice')} - 読み上げボイスの変更\n"
        f"- {cmd_mention('set_channel')} - 自動接続の設定\n"
        f"- {cmd_mention('status')} - システム状況表示\n\n"
        f"**更新情報:**\n`{VERSION}: {UPDATE_INFO}`"
    )
    return embed

def get_disconnect_embed(text_channel_mention):
    """切断時の共通リッチEmbedオブジェクトを生成"""
    embed = discord.Embed(title="ボイスチャンネル切断", color=COLOR_NOTICE)
    embed.description = (
        f"**{text_channel_mention}** での読み上げを終了しました。\n\n"
        "**利用可能なコマンド:**\n"
        f"- {cmd_mention('join')} - ボットを接続\n"
        f"- {cmd_mention('voice')} - 読み上げボイスの変更\n"
        f"- {cmd_mention('set_channel')} - 自動接続の設定\n"
        f"- {cmd_mention('status')} - システム状況表示\n\n"
        f"**更新情報:**\n`{VERSION}: {UPDATE_INFO}`"
    )
    return embed

AUTO_DISCONNECT_GRACE_SECONDS = 3

async def schedule_auto_disconnect(guild, channel_id):
    """退室検知後、一定時間待ってから本当に誰もいなくなったか再確認して切断する(通信瞬断による誤切断を防止)"""
    await asyncio.sleep(AUTO_DISCONNECT_GRACE_SECONDS)

    vc = guild.voice_client
    if not vc or not vc.is_connected() or vc.channel.id != channel_id:
        return
    if len(vc.channel.members) > 1:
        return

    channel_name = vc.channel.name
    text_channel = client.get_channel(client.connected_channel_id)
    mention = text_channel.mention if text_channel else "テキストチャンネル"
    detach_mixer(guild.id)
    await vc.disconnect()
    if text_channel:
        embed = get_disconnect_embed(mention)
        await text_channel.send(embed=embed)
    client.connected_channel_id = None
    print_log(f"自動切断: {channel_name}")

# --- コマンド ---
@client.tree.command(name='join', description='ボイスチャンネルに接続して読み上げを開始します')
async def join(interaction: discord.Interaction):
    if not interaction.user.voice:
        await send_embed(interaction, "エラー", "ボイスチャンネルに参加してから実行してください", COLOR_ERROR, True)
        return

    is_limited, _, reset_ts = get_tts_status()
    if is_limited:
        embed = get_tts_limit_embed(reset_ts)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    await interaction.response.defer()
    channel = interaction.user.voice.channel
    try:
        vc = await channel.connect(timeout=10)
        attach_mixer(vc)
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
        detach_mixer(interaction.guild.id)
        await interaction.guild.voice_client.disconnect()
        embed = get_disconnect_embed(mention)
        await interaction.response.send_message(embed=embed)
        client.connected_channel_id = None
    else:
        await send_embed(interaction, "エラー", "接続していません。", COLOR_ERROR, True)

@client.tree.command(name='music', description='音楽プレイヤーを表示し、曲の再生・一時停止・停止を操作します')
async def music(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if not vc or not vc.is_connected():
        await send_embed(interaction, "エラー", "ボイスチャンネルに接続していません。先にボイスチャンネルへ参加してください。", COLOR_ERROR, True)
        return

    tracks = get_cached_tracks(interaction.guild.id)
    if not tracks:
        await send_embed(interaction, "案内", "キャッシュされた音楽がありません。音楽ファイルをチャンネルに投稿すると自動的にキャッシュされます。", COLOR_NOTICE, True)
        return

    state = guild_music_states.setdefault(interaction.guild.id, MusicPlayerState(interaction.guild.id))
    embed = build_music_embed(state)
    view = MusicPlayerView(interaction.guild.id, tracks)

    await interaction.response.send_message(embed=embed, view=view)
    msg = await interaction.original_response()
    state.message = msg

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
    tts_count = tts_data.get("count", 0)
    limit_suffix = " (上限到達)" if tts_count >= TTS_MONTHLY_LIMIT else ""

    embed = discord.Embed(title="ステータス", color=COLOR_NOTICE)
    embed.add_field(name="稼働時間", value=f"`{uptime}`", inline=False)
    embed.add_field(name="メモリ使用率", value=f"`{mem.percent}%`", inline=False)
    embed.add_field(name="無料使用量上限", value=f"`{tts_count:,} / {TTS_MONTHLY_LIMIT:,}` 文字{limit_suffix}", inline=False)
    embed.add_field(name="更新情報", value=f"`{VERSION}: {UPDATE_INFO}`", inline=False)
    embed.set_footer(text="https://github.com/xxxxholica/kikimimi")
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

    # 音楽添付ファイルのキャッシュは、ボイスチャンネル未接続時でも行う
    audio_attachments = [att for att in message.attachments if is_audio_attachment(att)]
    for att in audio_attachments:
        await cache_music_attachment(message.guild.id, att, message.author.display_name)

    vc = message.guild.voice_client
    if not vc or not vc.is_connected():
        return

    # 添付ファイル情報の取得
    attachment_notice = ""
    if message.attachments:
        if audio_attachments:
            attachment_notice = "音楽ファイルが送信されました。"
        elif any(att.content_type and att.content_type.startswith('image') for att in message.attachments):
            attachment_notice = "画像が送信されました。"
        else:
            attachment_notice = "ファイルが送信されました。"

    cleaned = await clean_text(message.content, message.guild, message)

    # 最終的な読み上げテキストを構築
    body = (attachment_notice + " " + cleaned).strip()

    if not body:
        return

    # 1メッセージあたりの文字数上限 (長文スパム・無料枠急激消費防止)
    if len(body) > MAX_SPEAK_LENGTH:
        body = body[:MAX_SPEAK_LENGTH] + "、以下略"

    channel_id = message.channel.id
    is_home_channel = channel_id == client.connected_channel_id

    if is_home_channel:
        final_text = body
    else:
        author_id = message.author.id
        is_consecutive = client.last_channel_speaker.get(channel_id) == author_id
        client.last_channel_speaker[channel_id] = author_id
        if is_consecutive:
            final_text = f"{message.channel.name}に投稿されました。{body}"
        else:
            display_name = re.sub(r'[a-zA-Z]+', lambda x: x.group(0).lower(), message.author.display_name)
            final_text = f"{message.channel.name}に{display_name}が投稿しました。{body}"

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
        is_limited, _, reset_ts = get_tts_status()
        if is_limited:
            config = load_json(CONFIG_FILE, {})
            target_id = config.get(str(member.guild.id))
            text_ch = client.get_channel(target_id) if target_id else \
                      discord.utils.get(member.guild.text_channels, name="読み上げ") or \
                      member.guild.system_channel or \
                      member.guild.text_channels[0]

            counter_data = load_json(WORD_COUNTER_FILE, {})
            last_notice = counter_data.get("last_vc_notice", 0)
            now_ts = int(time.time())
            if now_ts - last_notice >= 86400:
                counter_data["last_vc_notice"] = now_ts
                save_json(WORD_COUNTER_FILE, counter_data)
                if text_ch:
                    embed = get_tts_limit_embed(reset_ts)
                    try:
                        await text_ch.send(embed=embed)
                    except Exception as e:
                        print_log(f"上限通知送信エラー: {e}")
            return

        try:
            vc = await after.channel.connect(timeout=10)
            attach_mixer(vc)

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
            asyncio.create_task(schedule_auto_disconnect(member.guild, vc.channel.id))

    elif before.channel and after.channel:
        await voice_channel_activity(vc, member, "移動", before_channel=before.channel, after_channel=after.channel)

client.run(os.environ.get("KIKIMIMI_BOT_TOKEN"))
