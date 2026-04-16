"""
Media downloader + music sender
.play [query/url]  — YouTube'dan sarki indir ve gonder
.video [url]       — Video indir ve gonder
.dl [url]          — Otomatik (ses/video)
Supports: YouTube, TikTok, Instagram, Twitter/X, SoundCloud, Spotify (via yt-dlp)
"""
import asyncio, time, shutil, os
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters,
)

from utils import dot_filter

DL_DIR = Path("./downloads")
for _d in ["audio", "video", "temp"]:
    (DL_DIR / _d).mkdir(parents=True, exist_ok=True)

TG_MAX_BYTES = 50 * 1024 * 1024  # 50 MB

try:
    import yt_dlp
    YT_OK = True
except ImportError:
    YT_OK = False


def _is_url(text: str) -> bool:
    return text.startswith(("http://", "https://"))


def _ydl_info(url: str, opts: dict) -> dict | None:
    try:
        with yt_dlp.YoutubeDL({**opts, "quiet": True, "no_warnings": True}) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception:
        return None


def _ydl_download(url: str, opts: dict) -> str | None:
    """Returns path of downloaded file or None."""
    out_dir = str(DL_DIR / "temp" / f"dl_{int(time.time()*1000)}")
    os.makedirs(out_dir, exist_ok=True)
    opts_full = {
        **opts,
        "outtmpl": f"{out_dir}/%(title)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts_full) as ydl:
            ydl.download([url])
        files = list(Path(out_dir).glob("*"))
        return str(files[0]) if files else None
    except Exception:
        shutil.rmtree(out_dir, ignore_errors=True)
        return None


async def _download_in_thread(url: str, opts: dict) -> str | None:
    return await asyncio.get_event_loop().run_in_executor(
        None, _ydl_download, url, opts
    )


async def _info_in_thread(url: str, opts: dict) -> dict | None:
    return await asyncio.get_event_loop().run_in_executor(
        None, _ydl_info, url, opts
    )


# ─── PLAY (audio) ────────────────────────────────────────────────────────────

async def play_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    if not YT_OK:
        return await msg.reply_text(
            "yt-dlp yuklu degil. Kur:\n`pip install yt-dlp`", parse_mode="Markdown"
        )

    query = " ".join(context.args) if context.args else ""
    if not query:
        return await msg.reply_text(
            "Kullanim:\n"
            "  .play <sarki adi>\n"
            "  .play <youtube/spotify/soundcloud linki>"
        )

    # Build URL or search
    if _is_url(query):
        url = query
    else:
        url = f"ytsearch1:{query}"

    status = await msg.reply_text("🎵 Araniyor / indiriliyor...")

    opts = {
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }

    # Get info first
    info = await _info_in_thread(url, {"format": "bestaudio/best"})
    if not info:
        return await status.edit_text("Bulunamadi veya indirilemedi.")

    # Pick first result if search
    if info.get("_type") == "playlist" and info.get("entries"):
        info = info["entries"][0]
        url  = info.get("webpage_url") or info.get("url") or url

    title     = info.get("title", "Bilinmeyen")
    duration  = info.get("duration", 0)
    thumbnail = info.get("thumbnail")
    uploader  = info.get("uploader", "")

    await status.edit_text(f"⬇️ İndiriliyor: <b>{title}</b>...", parse_mode="HTML")

    file_path = await _download_in_thread(url, opts)

    if not file_path or not Path(file_path).exists():
        return await status.edit_text("İndirme basarisiz.")

    size = Path(file_path).stat().st_size
    if size > TG_MAX_BYTES:
        shutil.rmtree(str(Path(file_path).parent), ignore_errors=True)
        return await status.edit_text(
            f"Dosya cok buyuk ({size//1024//1024} MB). Max 50 MB."
        )

    await status.edit_text("📤 Yukleniyor...")

    try:
        thumb_bytes = None
        if thumbnail:
            try:
                import requests
                r = requests.get(thumbnail, timeout=5)
                if r.status_code == 200:
                    thumb_bytes = r.content
            except Exception:
                pass

        dur_str = f"{duration//60}:{duration%60:02d}" if duration else ""
        caption = (
            f"🎵 <b>{title}</b>\n"
            f"👤 {uploader}\n"
            f"⏱ {dur_str}"
        )

        with open(file_path, "rb") as f:
            await context.bot.send_audio(
                update.effective_chat.id,
                audio=f,
                title=title,
                performer=uploader,
                duration=duration or None,
                caption=caption,
                parse_mode="HTML",
                thumbnail=thumb_bytes,
            )
        await status.delete()
    except Exception as e:
        await status.edit_text(f"Gonderme basarisiz: {e}")
    finally:
        shutil.rmtree(str(Path(file_path).parent), ignore_errors=True)


# ─── VIDEO ───────────────────────────────────────────────────────────────────

async def video_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    if not YT_OK:
        return await msg.reply_text("yt-dlp yuklu degil.")

    query = " ".join(context.args) if context.args else ""
    if not query:
        return await msg.reply_text(
            "Kullanim:\n"
            "  .video <url>\n"
            "  .video <arama>\n\n"
            "Desteklenen: YouTube, TikTok, Instagram, Twitter/X"
        )

    url = query if _is_url(query) else f"ytsearch1:{query}"
    status = await msg.reply_text("🎬 İndiriliyor...")

    opts = {"format": "best[height<=720][ext=mp4]/best[ext=mp4]/best"}

    info = await _info_in_thread(url, opts)
    if not info:
        return await status.edit_text("Bulunamadi.")

    if info.get("_type") == "playlist" and info.get("entries"):
        info = info["entries"][0]
        url  = info.get("webpage_url") or url

    title    = info.get("title", "Video")
    duration = info.get("duration", 0)
    width    = info.get("width", 0)
    height   = info.get("height", 0)

    file_path = await _download_in_thread(url, opts)
    if not file_path or not Path(file_path).exists():
        return await status.edit_text("İndirme basarisiz.")

    size = Path(file_path).stat().st_size
    if size > TG_MAX_BYTES:
        shutil.rmtree(str(Path(file_path).parent), ignore_errors=True)
        return await status.edit_text(f"Video cok buyuk ({size//1024//1024} MB). Max 50 MB.")

    await status.edit_text("📤 Yukleniyor...")

    try:
        with open(file_path, "rb") as f:
            await context.bot.send_video(
                update.effective_chat.id,
                video=f,
                caption=f"🎬 <b>{title}</b>",
                duration=duration or None,
                width=width or None,
                height=height or None,
                parse_mode="HTML",
                supports_streaming=True,
            )
        await status.delete()
    except Exception as e:
        await status.edit_text(f"Gonderme basarisiz: {e}")
    finally:
        shutil.rmtree(str(Path(file_path).parent), ignore_errors=True)


# ─── AUTO-DETECT URL HANDLER ─────────────────────────────────────────────────

_SUPPORTED_DOMAINS = (
    "youtube.com", "youtu.be", "tiktok.com",
    "instagram.com", "twitter.com", "x.com",
    "soundcloud.com", "spotify.com",
)


async def auto_dl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show download options when a supported URL is pasted."""
    msg = update.effective_message
    if not msg or not msg.text:
        return
    text = msg.text.strip()
    if not any(d in text.lower() for d in _SUPPORTED_DOMAINS):
        return

    url = text.split()[0]  # take first word as URL
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🎵 Ses", callback_data=f"autodl_audio_{url}"),
        InlineKeyboardButton("🎬 Video", callback_data=f"autodl_video_{url}"),
    ]])
    await msg.reply_text("Ne yapmak istersin?", reply_markup=kb)


async def auto_dl_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data  # autodl_audio_{url} or autodl_video_{url}
    await q.answer()

    parts   = data.split("_", 2)
    mode    = parts[1]   # audio or video
    url     = parts[2]

    # Inject URL as arg and call appropriate handler
    context.args = [url]
    if mode == "audio":
        await play_cmd(update, context)
    else:
        await video_cmd(update, context)

    try:
        await q.message.delete()
    except Exception:
        pass


def register_downloader_handlers(app):
    for cmd, handler in [
        ("play", play_cmd), ("music", play_cmd), ("sarki", play_cmd),
        ("video", video_cmd), ("dl", video_cmd),
    ]:
        app.add_handler(CommandHandler(cmd, handler))
        app.add_handler(MessageHandler(filters.TEXT & dot_filter(cmd), handler))

    app.add_handler(CallbackQueryHandler(auto_dl_callback, pattern=r"^autodl_"))

    # Auto-detect supported URLs (group=15)
    app.add_handler(
        MessageHandler(filters.TEXT & filters.Regex(r"https?://"), auto_dl),
        group=15,
    )
