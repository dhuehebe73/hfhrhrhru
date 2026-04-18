import os, shutil, hashlib, tempfile, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler
from utils import dcmd

# URL cache: md5_hash -> url
_url_cache: dict[str, str] = {}


def _hash_url(url: str) -> str:
    h = hashlib.md5(url.encode()).hexdigest()[:16]
    _url_cache[h] = url
    return h


def _has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


async def _download(url: str, audio_only: bool) -> tuple[str | None, str | None]:
    """Returns (filepath, error). Runs yt-dlp in executor."""
    import yt_dlp

    tmpdir = tempfile.mkdtemp()
    ffmpeg = _has_ffmpeg()

    if audio_only:
        if ffmpeg:
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(tmpdir, "%(title)s.%(ext)s"),
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
                "quiet": True, "no_warnings": True,
            }
        else:
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(tmpdir, "%(title)s.%(ext)s"),
                "quiet": True, "no_warnings": True,
            }
    else:
        ydl_opts = {
            "format": "best[ext=mp4]/best[height<=720]/best",
            "outtmpl": os.path.join(tmpdir, "%(title)s.%(ext)s"),
            "quiet": True, "no_warnings": True,
        }

    def _run():
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            files = os.listdir(tmpdir)
            return os.path.join(tmpdir, files[0]) if files else None
        except Exception as e:
            return str(e)

    result = await asyncio.get_event_loop().run_in_executor(None, _run)
    if result and os.path.isfile(result):
        return result, None
    return None, str(result) if result else "İndirme başarısız"


async def _send_media(update_or_query, ctx, url: str, audio_only: bool):
    if hasattr(update_or_query, "edit_message_text"):
        await update_or_query.edit_message_text("⏳ İndiriliyor...")
        chat_id = update_or_query.message.chat_id
    else:
        msg = await update_or_query.effective_message.reply_text("⏳ İndiriliyor...")
        chat_id = update_or_query.effective_chat.id

    filepath, err = await _download(url, audio_only)
    if err or not filepath:
        try:
            if hasattr(update_or_query, "edit_message_text"):
                await update_or_query.edit_message_text(f"❌ Hata: {err}")
            else:
                await msg.edit_text(f"❌ Hata: {err}")
        except Exception: pass
        return

    try:
        size = os.path.getsize(filepath)
        if size > 50 * 1024 * 1024:
            text = "❌ Dosya çok büyük (50MB üzeri gönderilemez)."
            if hasattr(update_or_query, "edit_message_text"):
                await update_or_query.edit_message_text(text)
            else:
                await msg.edit_text(text)
            return

        with open(filepath, "rb") as f:
            if audio_only:
                await ctx.bot.send_audio(chat_id, f)
            else:
                await ctx.bot.send_video(chat_id, f)

        if hasattr(update_or_query, "edit_message_text"):
            try: await update_or_query.message.delete()
            except Exception: pass
        else:
            try: await msg.delete()
            except Exception: pass
    except Exception as e:
        try:
            if hasattr(update_or_query, "edit_message_text"):
                await update_or_query.edit_message_text(f"❌ Gönderilemedi: {e}")
            else:
                await msg.edit_text(f"❌ Gönderilemedi: {e}")
        except Exception: pass
    finally:
        try:
            import shutil as sh
            sh.rmtree(os.path.dirname(filepath), ignore_errors=True)
        except Exception: pass


async def play_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args or []
    if not args:
        await update.effective_message.reply_text(
            "Kullanım: /play <url>\nDesteklenen: YouTube, SoundCloud, Spotify vb."); return
    url = args[0]
    h = _hash_url(url)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🎵 Ses İndir", callback_data=f"dl_a|{h}"),
        InlineKeyboardButton("🎬 Video İndir", callback_data=f"dl_v|{h}"),
    ]])
    await update.effective_message.reply_text(
        f"🔗 <code>{url[:60]}</code>\n\nNe indireyim?",
        parse_mode="HTML", reply_markup=kb)

async def video_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args or []
    if not args:
        await update.effective_message.reply_text("Kullanım: /video <url>"); return
    url = args[0]
    h = _hash_url(url)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🎵 Ses", callback_data=f"dl_a|{h}"),
        InlineKeyboardButton("🎬 Video", callback_data=f"dl_v|{h}"),
    ]])
    await update.effective_message.reply_text(
        f"🔗 <code>{url[:60]}</code>\n\nNe indireyim?",
        parse_mode="HTML", reply_markup=kb)

async def dl_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await play_cmd(update, ctx)


async def dl_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith(("dl_a|", "dl_v|")): return
    mode, h = data.split("|", 1)
    url = _url_cache.get(h)
    if not url:
        await query.edit_message_text("❌ URL süresi doldu, komutu tekrar çalıştır."); return
    audio_only = (mode == "dl_a")
    await _send_media(query, ctx, url, audio_only)


def register(app):
    for cmd, h in [("play", play_cmd), ("video", video_cmd), ("dl", dl_cmd)]:
        app.add_handler(MessageHandler(dcmd(cmd), h), group=10)
    app.add_handler(CallbackQueryHandler(dl_callback, pattern=r"^dl_[av]\|"), group=10)
