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

# カスタマイズ設定 (環境変数から取得)
VERSION = os.getenv("VERSION", "v1.1.0")
UPDATE_INFO = os.getenv("UPDATE_INFO", "全チャンネル読み上げ・リンク先タイトル取得・ロール/絵文字読み上げに対応。")
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

# 音楽キャッシュ設定 (サーバー単位、直近N件・合計サイズ上限で管理)
MUSIC_CACHE_MAX_TRACKS = int(os.getenv("MUSIC_CACHE_MAX_TRACKS", "10"))
MUSIC_CACHE_MAX_MB = int(os.getenv("MUSIC_CACHE_MAX_MB", "200"))
MUSIC_CACHE_DIR = os.path.join(BASE_DIR, "data", "music_cache")
MUSIC_CACHE_FILE = os.path.join(BASE_DIR, "data", "music_cache.json")
AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".opus", ".aac"}

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

# --- 音楽キャッシュ ---
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

    cache = load_json(MUSIC_CACHE_FILE, {})
    tracks = cache.setdefault(str(guild_id), [])
    tracks.insert(0, {
        "id": str(attachment.id),
        "filename": attachment.filename,
        "uploader": uploader_name,
        "uploaded_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "size": attachment.size,
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
    print_log(f"音楽キャッシュ追加: {attachment.filename} (guild={guild_id})")

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
    def __init__(self):
        self._sources = []  # list[tuple[AudioSource, Optional[Callable]]]
        self._lock = threading.Lock()

    def add(self, source, on_finished=None):
        with self._lock:
            self._sources.append((source, on_finished))

    def remove(self, source):
        with self._lock:
            self._sources = [(s, cb) for (s, cb) in self._sources if s is not source]
        try:
            source.cleanup()
        except Exception:
            pass

    def read(self):
        with self._lock:
            entries = list(self._sources)

        frames = []
        finished = []
        for source, on_finished in entries:
            try:
                data = source.read()
            except Exception:
                data = b""
            if not data:
                finished.append((source, on_finished))
                continue
            if len(data) < FRAME_SIZE:
                data = data + b"\x00" * (FRAME_SIZE - len(data))
            frames.append(data)

        if finished:
            with self._lock:
                self._sources = [(s, cb) for (s, cb) in self._sources if (s, cb) not in finished]
            for source, on_finished in finished:
                try:
                    source.cleanup()
                except Exception:
                    pass
                if on_finished:
                    on_finished()

        if not frames:
            return SILENCE_FRAME
        if len(frames) == 1:
            return frames[0]
        return self._mix(frames)

    def _mix(self, frames):
        mixed = [0] * SAMPLE_COUNT
        for frame in frames:
            for i, s in enumerate(struct.unpack(SAMPLE_FORMAT, frame)):
                mixed[i] += s
        clipped = [max(-32768, min(32767, v)) for v in mixed]
        return struct.pack(SAMPLE_FORMAT, *clipped)

    def is_opus(self):
        return False

    def cleanup(self):
        with self._lock:
            entries, self._sources = self._sources, []
        for source, _ in entries:
            try:
                source.cleanup()
            except Exception:
                pass

# ギルドID -> 状態 (Botは単一プロセスでの単一/少数サーバー運用を想定しているが、
# 音楽キャッシュ・再生まわりはサーバー単位で独立させる)
guild_mixers = {}       # guild_id -> MixingAudioSource
guild_music_slot = {}   # guild_id -> 現在再生中の音楽AudioSource ( /stop用 )
guild_tts_queue = {}    # guild_id -> asyncio.Queue (TTSは従来通り逐次再生)
guild_tts_tasks = {}    # guild_id -> asyncio.Task (TTSキューの消費タスク)

def attach_mixer(vc):
    """ボイス接続時にミキサーを起動し、そのギルドの再生ハブとして登録する"""
    mixer = MixingAudioSource()
    vc.play(mixer)
    guild_mixers[vc.guild.id] = mixer
    return mixer

def detach_mixer(guild_id):
    """切断時にそのギルドの再生関連状態を破棄する"""
    mixer = guild_mixers.pop(guild_id, None)
    if mixer:
        mixer.cleanup()
    guild_music_slot.pop(guild_id, None)
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
                audio = await generate_audio_google(text, voice_name)
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

async def play_track(guild, track):
    """指定トラックをそのギルドの音楽スロットで再生する(既存の再生中トラックは差し替え)"""
    mixer = guild_mixers.get(guild.id)
    if mixer is None:
        return False

    old_source = guild_music_slot.pop(guild.id, None)
    if old_source is not None:
        mixer.remove(old_source)

    loop = asyncio.get_running_loop()
    source = discord.FFmpegPCMAudio(track["path"], executable=FFMPEG_PATH)

    def on_finished():
        def clear():
            if guild_music_slot.get(guild.id) is source:
                guild_music_slot.pop(guild.id, None)
        loop.call_soon_threadsafe(clear)

    guild_music_slot[guild.id] = source
    mixer.add(source, on_finished=on_finished)
    return True

async def stop_track(guild):
    """再生中の音楽を停止する。何も再生していなければFalseを返す"""
    source = guild_music_slot.pop(guild.id, None)
    if source is None:
        return False
    mixer = guild_mixers.get(guild.id)
    if mixer:
        mixer.remove(source)
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
        f"- {cmd_mention('play')} - キャッシュされた音楽を再生\n"
        f"- {cmd_mention('stop')} - 音楽の再生を停止\n"
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

class MusicSelect(discord.ui.Select):
    def __init__(self, tracks):
        options = [
            discord.SelectOption(
                label=track["filename"][:100],
                description=f'{track["uploader"]} ・ {track["uploaded_at"][:16].replace("T", " ")}'[:100],
                value=track["id"],
            )
            for track in tracks
        ]
        super().__init__(placeholder="再生する曲を選択", options=options)
        self.tracks_by_id = {track["id"]: track for track in tracks}

    async def callback(self, interaction: discord.Interaction):
        track = self.tracks_by_id.get(self.values[0])
        vc = interaction.guild.voice_client
        if not track or not vc or not vc.is_connected():
            await interaction.response.send_message("再生できませんでした。", ephemeral=True)
            return
        await play_track(interaction.guild, track)
        await interaction.response.send_message(f"再生します: {track['filename']}", ephemeral=True)

class MusicView(discord.ui.View):
    def __init__(self, tracks):
        super().__init__(timeout=60)
        self.add_item(MusicSelect(tracks))

@client.tree.command(name='play', description='サーバーにキャッシュされた音楽を選んで再生します')
async def play(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if not vc or not vc.is_connected():
        await send_embed(interaction, "エラー", "ボイスチャンネルに接続していません。", COLOR_ERROR, True)
        return

    cache = load_json(MUSIC_CACHE_FILE, {})
    tracks = [t for t in cache.get(str(interaction.guild.id), []) if os.path.exists(t["path"])]

    if not tracks:
        await send_embed(interaction, "案内", "キャッシュされた音楽がありません。音楽ファイルをチャンネルに投稿するとキャッシュされます。", COLOR_NOTICE, True)
        return

    await interaction.response.send_message("再生する曲を選択してください。", view=MusicView(tracks), ephemeral=True)

@client.tree.command(name='stop', description='再生中の音楽を停止します')
async def stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if not vc or not vc.is_connected():
        await send_embed(interaction, "エラー", "ボイスチャンネルに接続していません。", COLOR_ERROR, True)
        return

    stopped = await stop_track(interaction.guild)
    if stopped:
        await send_embed(interaction, "停止", "音楽の再生を停止しました。", COLOR_SUCCESS)
    else:
        await send_embed(interaction, "案内", "再生中の音楽はありません。", COLOR_NOTICE, True)

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
    embed.add_field(name="更新情報", value=f"`{VERSION}: {UPDATE_INFO}`", inline=False)
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
