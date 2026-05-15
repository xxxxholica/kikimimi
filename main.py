import os
import io
import re
import json
import tempfile
import asyncio
import datetime
import logging
import time
import shutil
import random
from collections import Counter
from urllib.parse import urlparse
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
UPDATE_INFO = os.getenv("UPDATE_INFO", "OSS版: 環境設定をロードしました。")
SYSTEM_FOOTER = os.getenv("SYSTEM_FOOTER", "Discord Bot System")
BOT_PRESENCE = os.getenv("BOT_PRESENCE", "Developed by xxxxholic")

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

def clean_text(text, guild):
    if not text:
        return ""
    
    if "```" in text:
        text = "ソースコード省略"
    
    text = re.sub(r'\|\|.*?\|\|', '伏せ字', text)
    
    mention_pattern = re.compile(r'<@!?(\d+)>')
    for match in mention_pattern.finditer(text):
        member = guild.get_member(int(match.group(1)))
        name = member.display_name if member else "ユーザー"
        text = text.replace(match.group(0), name)
    
    text = re.sub(r'<@&\d+>', '役職メンション', text)
    text = re.sub(r'<#\d+>', 'チャンネルリンク', text)
    
    url_pattern = re.compile(r'https?://[\w/:%#\$&\?\(\)~\.=\+\-]+')
    if url_pattern.search(text):
        parsed = urlparse(url_pattern.search(text).group())
        url_map = {
            "[www.youtube.com](https://www.youtube.com)": "ユーチューブ", "youtu.be": "ユーチューブ",
            "x.com": "エックス", "twitter.com": "エックス",
            "steampowered.com": "スチーム", "instagram.com": "インスタグラム"
        }
        text = url_map.get(parsed.netloc, "リンク") + "省略"

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
    if message.author.bot or message.channel.id != client.connected_channel_id:
        return
    
    vc = message.guild.voice_client
    if not vc or not vc.is_connected():
        return

    # 添付ファイル情報の取得
    attachment_notice = ""
    if message.attachments:
        has_image = any(att.content_type and att.content_type.startswith('image') for att in message.attachments)
        attachment_notice = "画像が送信されました。" if has_image else "ファイルが送信されました。"

    cleaned = clean_text(message.content, message.guild)
    
    # 最終的な読み上げテキストを構築
    final_text = (attachment_notice + " " + cleaned).strip()

    if not final_text:
        return

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
