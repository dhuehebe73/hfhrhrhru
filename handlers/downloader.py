import os, re, shutil, hashlib, tempfile, asyncio, base64
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler
from utils import dcmd, get_args

# ── URL / stream cache ────────────────────────────────────────────────────────
_url_cache: dict[str, str] = {}   # hash → url

def _hash(url: str) -> str:
    h = hashlib.md5(url.encode()).hexdigest()[:16]
    _url_cache[h] = url
    return h

def _has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None

def _cookies_path() -> str | None:
    p = Path(__file__).parent.parent / "cookies.txt"
    return str(p) if p.exists() else None

# ── M3U8 scraper (same logic as m3u8dl.py) ───────────────────────────────────
_M3U8_RE = re.compile(r'https?://[^\s\'"<>\)\]\\]+\.m3u8(?:[^\s\'"<>\)\]\\]*)?', re.I)
_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8",
}

def _find_m3u8_in(text: str, base: str = "") -> set[str]:
    from urllib.parse import urljoin
    found = set(_M3U8_RE.findall(text))
    # relative paths
    for m in re.finditer(r'''["'](/[^"'<>\s]+\.m3u8[^"'<>\s]*)''', text, re.I):
        found.add(urljoin(base, m.group(1)))
    # base64 blobs
    for m in re.finditer(r'''["']([A-Za-z0-9+/]{60,}={0,2})["']''', text):
        try:
            dec = base64.b64decode(m.group(1)).decode("utf-8", errors="ignore")
            found.update(_M3U8_RE.findall(dec))
        except Exception:
            pass
    # JS vars: file:"...", src:"...", url:"..."
    for m in re.finditer(r'''(?:file|src|url|stream|hls)\s*[=:]\s*["']([^"']+\.m3u8[^"']*)''', text, re.I):
        u = m.group(1)
        from urllib.parse import urljoin
        found.add(urljoin(base, u) if u.startswith("/") else u)
    return found

def _scrape_m3u8(page_url: str) -> list[str]:
    import requests
    sess = requests.Session()
    sess.headers.update(_HEADERS)
    resp = sess.get(page_url, timeout=20, allow_redirects=True)
    resp.raise_for_status()
    html = resp.text
    base = resp.url
    found = _find_m3u8_in(html, base)
    from urllib.parse import urljoin
    # iframes
    for m in re.finditer(r'''<iframe[^>]+src=["']([^"']+)["']''', html, re.I):
        try:
            ir = sess.get(urljoin(base, m.group(1)), timeout=12,
                          headers={**_HEADERS, "Referer": base})
            found.update(_find_m3u8_in(ir.text, ir.url))
        except Exception:
            pass
        if len(found) >= 20: break
    # external JS
    for m in re.finditer(r'''<script[^>]+src=["']([^"']+\.js[^"']*)["']''', html, re.I):
        try:
            jr = sess.get(urljoin(base, m.group(1)), timeout=10,
                          headers={**_HEADERS, "Referer": base})
            found.update(_find_m3u8_in(jr.text, jr.url))
        except Exception:
            pass
        if len(found) >= 20: break
    return list(found)

def _label(url: str) -> str:
    seg = url.split("?")[0].rstrip("/").split("/")[-1].lower().replace(".m3u8", "")
    if "audio" in seg:
        lang = re.search(r'[_-]([a-z]{2,4})\d*$', seg)
        return f"🔊 Audio [{lang.group(1).upper() if lang else '?'}]"
    for q in ("2160","1440","1080","720","480","360","240"):
        if q in seg or q in url:
            return f"🎬 {q}p"
    return f"📺 {seg or 'stream'}"


# ── yt-dlp download ───────────────────────────────────────────────────────────
async def _ytdlp_download(url: str, audio_only: bool) -> tuple[str | None, str | None]:
    import yt_dlp
    tmpdir  = tempfile.mkdtemp()
    ffmpeg  = _has_ffmpeg()
    cookies = _cookies_path()

    common = {
        "quiet": True, "no_warnings": True,
        "outtmpl": os.path.join(tmpdir, "%(title).80s.%(ext)s"),
    }
    if cookies:
        common["cookiefile"] = cookies

    if audio_only:
        opts = {**common, "format": "bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio/best"}
    else:
        opts = {**common, "format": "best[ext=mp4]/best[height<=720]/best"}

    def _run():
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            files = os.listdir(tmpdir)
            if not files:
                return None
            fp = os.path.join(tmpdir, files[0])
            if audio_only and not fp.endswith(".mp3"):
                new_fp = os.path.splitext(fp)[0] + ".mp3"
                os.rename(fp, new_fp)
                fp = new_fp
            return fp
        except Exception as e:
            return str(e)

    result = await asyncio.get_event_loop().run_in_executor(None, _run)
    if result and os.path.isfile(result):
        return result, None
    return None, str(result) if result else "Download failed"


# ── ffmpeg HLS download ───────────────────────────────────────────────────────
async def _hls_download(video_url: str, audio_url: str | None,
                        referer: str = "") -> tuple[str | None, str | None]:
    if not _has_ffmpeg():
        return None, "ffmpeg not installed"

    tmpdir = tempfile.mkdtemp()
    output = os.path.join(tmpdir, "stream.mp4")
    hdrs   = (f"Referer: {referer}\r\nUser-Agent: {_HEADERS['User-Agent']}\r\n"
              if referer else "")

    cmd = ["ffmpeg", "-y",
           "-protocol_whitelist", "https,http,tls,tcp,crypto,file,m3u8,hls"]
    if hdrs:
        cmd += ["-headers", hdrs]
    cmd += ["-i", video_url]
    if audio_url:
        if hdrs:
            cmd += ["-headers", hdrs]
        cmd += ["-i", audio_url]
    if audio_url:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-c", "copy", output]

    def _run():
        try:
            r = __import__("subprocess").run(
                cmd, capture_output=True, timeout=600)
            if r.returncode == 0 and os.path.exists(output):
                return output
            return r.stderr.decode(errors="ignore")[-300:]
        except Exception as e:
            return str(e)

    result = await asyncio.get_event_loop().run_in_executor(None, _run)
    if result and os.path.isfile(result):
        return result, None
    return None, str(result) if result else "HLS download failed"


# ── Send helper ───────────────────────────────────────────────────────────────
async def _send(query_or_update, ctx, filepath: str, audio_only: bool):
    chat_id = (query_or_update.message.chat_id
               if hasattr(query_or_update, "edit_message_text")
               else query_or_update.effective_chat.id)

    async def _edit(text):
        try:
            if hasattr(query_or_update, "edit_message_text"):
                await query_or_update.edit_message_text(text)
            else:
                await _msg.edit_text(text)
        except Exception: pass

    size = os.path.getsize(filepath)
    if size > 50 * 1024 * 1024:
        await _edit("❌ File too large (>50 MB — Telegram limit).")
        return

    try:
        with open(filepath, "rb") as f:
            if audio_only:
                await ctx.bot.send_audio(chat_id, f)
            else:
                await ctx.bot.send_video(chat_id, f)
        try:
            if hasattr(query_or_update, "edit_message_text"):
                await query_or_update.message.delete()
            else:
                await _msg.delete()
        except Exception: pass
    except Exception as e:
        await _edit(f"❌ Could not send: {e}")
    finally:
        try: shutil.rmtree(os.path.dirname(filepath), ignore_errors=True)
        except Exception: pass


# ── Commands ──────────────────────────────────────────────────────────────────
def _make_url(args: list[str]) -> tuple[str, str]:
    q = " ".join(args)
    if q.startswith(("http://", "https://")):
        return q, q[:60]
    return f"ytsearch1:{q}", f"🔎 {q[:55]}"


async def play_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = get_args(update, ctx)
    if not args:
        await update.effective_message.reply_text(
            "Usage: /play <song name or URL>\nExample: /play Tarkan Şımarık")
        return
    url, lbl = _make_url(args)
    h = _hash(url)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🎵 Audio", callback_data=f"dl_a|{h}"),
        InlineKeyboardButton("🎬 Video", callback_data=f"dl_v|{h}"),
    ]])
    await update.effective_message.reply_text(
        f"<code>{lbl}</code>\n\nWhat to download?",
        parse_mode="HTML", reply_markup=kb)

async def video_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = get_args(update, ctx)
    if not args:
        await update.effective_message.reply_text("Usage: /video <name or URL>")
        return
    url, lbl = _make_url(args)
    h = _hash(url)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🎵 Audio", callback_data=f"dl_a|{h}"),
        InlineKeyboardButton("🎬 Video", callback_data=f"dl_v|{h}"),
    ]])
    await update.effective_message.reply_text(
        f"<code>{lbl}</code>\n\nWhat to download?",
        parse_mode="HTML", reply_markup=kb)

async def dl_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await play_cmd(update, ctx)


# ── Callback: handles both yt-dlp and m3u8 ───────────────────────────────────
async def dl_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data

    # ── yt-dlp mode ─────────────────────────────────────────────────────────
    if data.startswith(("dl_a|", "dl_v|")):
        mode, h = data.split("|", 1)
        url = _url_cache.get(h)
        if not url:
            await query.edit_message_text("❌ Link expired — run the command again.")
            return
        audio_only = (mode == "dl_a")
        await query.edit_message_text("⏳ Downloading…")

        filepath, err = await _ytdlp_download(url, audio_only)

        if filepath:
            await _send(query, ctx, filepath, audio_only)
            return

        # yt-dlp failed — try m3u8 scraping if it was a webpage URL
        if url.startswith("http") and "ytsearch" not in url:
            await query.edit_message_text("⏳ Trying stream scraper…")
            try:
                def _scrape():
                    return _scrape_m3u8(url)
                streams = await asyncio.get_event_loop().run_in_executor(None, _scrape)
            except Exception:
                streams = []

            if streams:
                # Build quality keyboard
                videos = [s for s in streams if "audio" not in s.split("/")[-1].lower()]
                audios = [s for s in streams if "audio" in s.split("/")[-1].lower()]
                rows = []
                for s in videos[:6]:
                    sh = _hash(s)
                    # Store referer alongside url
                    _url_cache[sh + "_ref"] = url
                    rows.append([InlineKeyboardButton(
                        _label(s), callback_data=f"hls_v|{sh}")])
                for s in audios[:3]:
                    sh = _hash(s)
                    _url_cache[sh + "_ref"] = url
                    rows.append([InlineKeyboardButton(
                        _label(s), callback_data=f"hls_a|{sh}")])
                if rows:
                    await query.edit_message_text(
                        "🎬 <b>Streams found — pick one:</b>",
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(rows))
                    return

        await query.edit_message_text(f"❌ Error: {err[:300]}")
        return

    # ── HLS / m3u8 mode ─────────────────────────────────────────────────────
    if data.startswith(("hls_v|", "hls_a|")):
        mode, h = data.split("|", 1)
        url     = _url_cache.get(h)
        referer = _url_cache.get(h + "_ref", "")
        if not url:
            await query.edit_message_text("❌ Link expired — run the command again.")
            return
        audio_only = (mode == "hls_a")
        await query.edit_message_text("⏳ Downloading stream…")

        filepath, err = await _hls_download(
            url if not audio_only else url,
            None,
            referer)

        if filepath:
            await _send(query, ctx, filepath, audio_only)
        else:
            await query.edit_message_text(f"❌ HLS error: {err[:300]}")
        return


def register(app):
    for cmd, h in [("play", play_cmd), ("video", video_cmd), ("dl", dl_cmd)]:
        app.add_handler(MessageHandler(dcmd(cmd), h), group=10)
    app.add_handler(CallbackQueryHandler(
        dl_callback, pattern=r"^(dl_[av]|hls_[va])\|"), group=10)
