"""
Media downloader — works WITHOUT ffmpeg.
.play  — download audio (mp3/m4a/best available)
.video — download video
.dl    — auto-detect
Auto-popup for supported URLs pasted in chat.
"""
import asyncio, shutil, time
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters,
)
from utils import dot_filter

DL_DIR = Path("./downloads")
DL_DIR.mkdir(parents=True, exist_ok=True)

TG_MAX = 50 * 1024 * 1024  # 50 MB

# Detect ffmpeg once at import time
_FFMPEG = bool(shutil.which("ffmpeg"))

try:
    import yt_dlp
    YT_OK = True
except ImportError:
    YT_OK = False

_DOMAINS = (
    "youtube.com", "youtu.be", "tiktok.com",
    "instagram.com", "twitter.com", "x.com",
    "soundcloud.com", "spotify.com", "open.spotify",
)


def _is_url(t: str) -> bool:
    return t.strip().startswith(("http://", "https://"))


def _audio_opts(out_dir: str) -> dict:
    base = {
        "outtmpl": f"{out_dir}/%(title)s.%(ext)s",
        "quiet": True, "no_warnings": True, "noplaylist": True,
    }
    if _FFMPEG:
        return {
            **base,
            "format": "bestaudio/best",
            "postprocessors": [{"key": "FFmpegExtractAudio",
                                 "preferredcodec": "mp3",
                                 "preferredquality": "192"}],
        }
    else:
        # No ffmpeg — download best native audio directly
        return {
            **base,
            "format": "bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio[ext=aac]/bestaudio/best",
        }


def _video_opts(out_dir: str) -> dict:
    base = {
        "outtmpl": f"{out_dir}/%(title)s.%(ext)s",
        "quiet": True, "no_warnings": True, "noplaylist": True,
    }
    if _FFMPEG:
        return {**base, "format": "best[height<=720][ext=mp4]/best[ext=mp4]/best"}
    else:
        return {**base, "format": "best[height<=720][ext=mp4]/mp4/best[ext=mp4]/best"}


def _run_ydl(url: str, opts: dict) -> dict | None:
    out_dir = str(DL_DIR / f"dl_{int(time.time()*1000)}")
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    try:
        with yt_dlp.YoutubeDL({**opts, "outtmpl": f"{out_dir}/%(title)s.%(ext)s"}) as ydl:
            info = ydl.extract_info(url, download=True)
            if info.get("_type") == "playlist" and info.get("entries"):
                info = info["entries"][0]
        files = list(Path(out_dir).glob("*"))
        if not files:
            shutil.rmtree(out_dir, ignore_errors=True)
            return None
        return {"file": str(files[0]), "info": info, "tmpdir": out_dir}
    except Exception as e:
        shutil.rmtree(out_dir, ignore_errors=True)
        return None


def _get_info(url: str) -> dict | None:
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            if info.get("_type") == "playlist" and info.get("entries"):
                info = info["entries"][0]
            return info
    except Exception:
        return None


# ─── PLAY ─────────────────────────────────────────────────────────────────────

async def play_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    if not YT_OK:
        return await msg.reply_text(
            "yt-dlp yuklu degil.\nKur: <code>pip install yt-dlp</code>",
            parse_mode="HTML",
        )

    query = " ".join(context.args).strip() if context.args else ""
    if not query:
        return await msg.reply_text(
            "Kullanim:\n"
            "• <code>.play sarki adi</code>\n"
            "• <code>.play https://youtube.com/...</code>\n"
            "• <code>.play https://open.spotify.com/...</code>",
            parse_mode="HTML",
        )

    url = query if _is_url(query) else f"ytsearch1:{query}"
    status = await msg.reply_text("🔍 Araniyor...")

    # Get info first (fast)
    info = await asyncio.get_event_loop().run_in_executor(None, _get_info, url)
    if not info:
        return await status.edit_text("❌ Bulunamadi veya desteklenmiyor.")

    title     = info.get("title", "Bilinmeyen")
    duration  = info.get("duration", 0)
    uploader  = info.get("uploader", "")
    thumbnail = info.get("thumbnail", "")
    real_url  = info.get("webpage_url") or url

    dur_str = f"{duration//60}:{duration%60:02d}" if duration else ""
    await status.edit_text(f"⬇️ İndiriliyor: <b>{title}</b>...", parse_mode="HTML")

    out_dir = str(DL_DIR / f"audio_{int(time.time()*1000)}")
    opts    = _audio_opts(out_dir)
    result  = await asyncio.get_event_loop().run_in_executor(
        None, _run_ydl, real_url, opts
    )

    if not result:
        return await status.edit_text("❌ İndirme basarisiz. Linki kontrol et.")

    fpath = Path(result["file"])
    size  = fpath.stat().st_size
    if size > TG_MAX:
        shutil.rmtree(result["tmpdir"], ignore_errors=True)
        return await status.edit_text(f"❌ Dosya cok buyuk ({size//1024//1024} MB). Max 50 MB.")

    await status.edit_text("📤 Yukleniyor...")
    try:
        # Try to get thumbnail
        thumb = None
        if thumbnail:
            try:
                import requests
                r = requests.get(thumbnail, timeout=5)
                if r.status_code == 200:
                    thumb = r.content
            except Exception:
                pass

        with open(fpath, "rb") as f:
            await context.bot.send_audio(
                update.effective_chat.id,
                audio=f,
                title=title[:64],
                performer=uploader[:64] if uploader else None,
                duration=int(duration) if duration else None,
                caption=f"🎵 <b>{title}</b>" + (f"\n👤 {uploader}" if uploader else "") + (f"\n⏱ {dur_str}" if dur_str else ""),
                parse_mode="HTML",
                thumbnail=thumb,
            )
        await status.delete()
    except Exception as e:
        await status.edit_text(f"❌ Gonderme basarisiz: {e}")
    finally:
        shutil.rmtree(result["tmpdir"], ignore_errors=True)


# ─── VIDEO ────────────────────────────────────────────────────────────────────

async def video_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    if not YT_OK:
        return await msg.reply_text("yt-dlp yuklu degil. Kur: pip install yt-dlp")

    query = " ".join(context.args).strip() if context.args else ""
    if not query:
        return await msg.reply_text(
            "Kullanim:\n"
            "• <code>.video https://youtube.com/...</code>\n"
            "• <code>.video https://tiktok.com/...</code>\n"
            "• <code>.video sarki adi</code>",
            parse_mode="HTML",
        )

    url = query if _is_url(query) else f"ytsearch1:{query}"
    status = await msg.reply_text("🎬 İndiriliyor...")

    info = await asyncio.get_event_loop().run_in_executor(None, _get_info, url)
    if not info:
        return await status.edit_text("❌ Bulunamadi.")

    title    = info.get("title", "Video")
    duration = info.get("duration", 0)
    width    = info.get("width") or 0
    height   = info.get("height") or 0
    real_url = info.get("webpage_url") or url

    out_dir = str(DL_DIR / f"video_{int(time.time()*1000)}")
    opts    = _video_opts(out_dir)
    result  = await asyncio.get_event_loop().run_in_executor(
        None, _run_ydl, real_url, opts
    )

    if not result:
        return await status.edit_text("❌ İndirme basarisiz.")

    fpath = Path(result["file"])
    size  = fpath.stat().st_size
    if size > TG_MAX:
        shutil.rmtree(result["tmpdir"], ignore_errors=True)
        return await status.edit_text(f"❌ Video cok buyuk ({size//1024//1024} MB). Max 50 MB.")

    await status.edit_text("📤 Yukleniyor...")
    try:
        with open(fpath, "rb") as f:
            await context.bot.send_video(
                update.effective_chat.id,
                video=f,
                caption=f"🎬 <b>{title}</b>",
                duration=int(duration) if duration else None,
                width=width or None,
                height=height or None,
                parse_mode="HTML",
                supports_streaming=True,
            )
        await status.delete()
    except Exception as e:
        await status.edit_text(f"❌ Gonderme basarisiz: {e}")
    finally:
        shutil.rmtree(result["tmpdir"], ignore_errors=True)


# ─── AUTO-DETECT URL ─────────────────────────────────────────────────────────

async def auto_dl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return
    text = msg.text.strip()
    if not any(d in text.lower() for d in _DOMAINS):
        return
    if not _is_url(text.split()[0]):
        return

    url = text.split()[0]
    kb  = InlineKeyboardMarkup([[
        InlineKeyboardButton("🎵 Ses", callback_data=f"adl_a|{url}"),
        InlineKeyboardButton("🎬 Video", callback_data=f"adl_v|{url}"),
        InlineKeyboardButton("❌", callback_data="adl_x"),
    ]])
    await msg.reply_text("📥 Ne yapmak istersin?", reply_markup=kb)


async def auto_dl_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data
    await q.answer()

    if data == "adl_x":
        try: await q.message.delete()
        except Exception: pass
        return

    mode, url = data.split("|", 1)
    try: await q.message.delete()
    except Exception: pass

    context.args = [url]
    if mode == "adl_a":
        await play_cmd(update, context)
    else:
        await video_cmd(update, context)


def register_downloader_handlers(app):
    for cmd, handler in [
        ("play", play_cmd), ("music", play_cmd), ("sarki", play_cmd), ("mp3", play_cmd),
        ("video", video_cmd), ("dl", video_cmd), ("indir", video_cmd),
    ]:
        app.add_handler(CommandHandler(cmd, handler))
        app.add_handler(MessageHandler(filters.TEXT & dot_filter(cmd), handler))

    app.add_handler(CallbackQueryHandler(auto_dl_cb, pattern=r"^adl_"))
    app.add_handler(
        MessageHandler(filters.TEXT & filters.Regex(r"https?://"), auto_dl),
        group=15,
    )
