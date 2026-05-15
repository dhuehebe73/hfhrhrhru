import re
import aiosqlite
from config import DB_PATH
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from database import is_approved
from utils import require_admin, is_admin, dcmd, get_args


# ── Lock types ────────────────────────────────────────────────────────────────

LOCK_TYPES = [
    "sticker", "gif", "media", "game", "inline", "forward",
    "bot", "url", "button", "phone", "location", "contact",
    "audio", "video", "document", "voice", "videonote", "poll",
    "rtl", "spoiler",
]

_RTL_RE = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿ"
                     r"֐-׿ﭐ-﷿ﹰ-﻿]")
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


# ── Database helpers ──────────────────────────────────────────────────────────

async def _ensure_row(db, chat_id: int):
    await db.execute(
        "INSERT OR IGNORE INTO chat_locks(chat_id) VALUES(?)", (chat_id,)
    )


async def _ensure_table(db):
    cols = ", ".join(f"{t} INTEGER DEFAULT 0" for t in LOCK_TYPES)
    await db.executescript(
        f"CREATE TABLE IF NOT EXISTS chat_locks(chat_id INTEGER PRIMARY KEY, {cols});"
    )
    # Add any missing columns (idempotent migrations)
    async with db.execute("PRAGMA table_info(chat_locks)") as c:
        existing = {row[1] for row in await c.fetchall()}
    for t in LOCK_TYPES:
        if t not in existing:
            await db.execute(
                f"ALTER TABLE chat_locks ADD COLUMN {t} INTEGER DEFAULT 0"
            )


async def get_locks(chat_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_table(db)
        await _ensure_row(db, chat_id)
        await db.commit()
        cols = ", ".join(LOCK_TYPES)
        async with db.execute(
            f"SELECT {cols} FROM chat_locks WHERE chat_id=?", (chat_id,)
        ) as c:
            row = await c.fetchone()
    if row:
        return dict(zip(LOCK_TYPES, row))
    return {t: 0 for t in LOCK_TYPES}


async def set_lock(chat_id: int, lock_type: str, state: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_table(db)
        await db.execute(
            f"INSERT INTO chat_locks(chat_id, {lock_type}) VALUES(?, ?)"
            f" ON CONFLICT(chat_id) DO UPDATE SET {lock_type}=?",
            (chat_id, state, state)
        )
        await db.commit()


# ── Commands ──────────────────────────────────────────────────────────────────

async def lock_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx):
        return
    args = get_args(update, ctx)
    if not args:
        await update.effective_message.reply_text(
            f"❌ Kullanım: /lock &lt;tür&gt;\n"
            f"Türler: <code>{'  '.join(LOCK_TYPES)}</code>\n"
            f"Hepsini kilitlemek için: /lock all",
            parse_mode="HTML"
        )
        return

    lock_type = args[0].lower()
    cid = update.effective_chat.id

    if lock_type == "all":
        for t in LOCK_TYPES:
            await set_lock(cid, t, 1)
        await update.effective_message.reply_text(
            "🔒 Tüm mesaj türleri kilitlendi.", parse_mode="HTML"
        )
        return

    if lock_type not in LOCK_TYPES:
        await update.effective_message.reply_text(
            f"❌ Geçersiz tür: <code>{lock_type}</code>\n"
            f"Geçerli türler: <code>{'  '.join(LOCK_TYPES)}</code>",
            parse_mode="HTML"
        )
        return

    await set_lock(cid, lock_type, 1)
    await update.effective_message.reply_text(
        f"🔒 <b>{lock_type}</b> kilitlendi.", parse_mode="HTML"
    )


async def unlock_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx):
        return
    args = get_args(update, ctx)
    if not args:
        await update.effective_message.reply_text(
            f"❌ Kullanım: /unlock &lt;tür&gt;\n"
            f"Türler: <code>{'  '.join(LOCK_TYPES)}</code>\n"
            f"Hepsini açmak için: /unlock all",
            parse_mode="HTML"
        )
        return

    lock_type = args[0].lower()
    cid = update.effective_chat.id

    if lock_type == "all":
        for t in LOCK_TYPES:
            await set_lock(cid, t, 0)
        await update.effective_message.reply_text(
            "🔓 Tüm kilitler açıldı.", parse_mode="HTML"
        )
        return

    if lock_type not in LOCK_TYPES:
        await update.effective_message.reply_text(
            f"❌ Geçersiz tür: <code>{lock_type}</code>\n"
            f"Geçerli türler: <code>{'  '.join(LOCK_TYPES)}</code>",
            parse_mode="HTML"
        )
        return

    await set_lock(cid, lock_type, 0)
    await update.effective_message.reply_text(
        f"🔓 <b>{lock_type}</b> kilidi açıldı.", parse_mode="HTML"
    )


async def locks_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    lock_states = await get_locks(cid)

    lines = []
    for t in LOCK_TYPES:
        icon = "✅" if lock_states.get(t) else "❌"
        lines.append(f"{icon} <code>{t}</code>")

    await update.effective_message.reply_text(
        "🔐 <b>Kilit Durumları</b>\n\n" + "\n".join(lines),
        parse_mode="HTML"
    )


# ── Message type detection helpers ────────────────────────────────────────────

def _is_gif(msg) -> bool:
    """Animated GIF (document with mime video/mp4 from inline share, or animation)."""
    if msg.animation:
        return True
    if msg.document and msg.document.mime_type in ("video/mp4", "image/gif"):
        return True
    return False


def _has_spoiler(msg) -> bool:
    """Check if message contains spoiler-formatted text."""
    text = msg.text or msg.caption or ""
    if not text:
        return False
    # Check MessageEntities for spoiler type
    entities = list(msg.entities or []) + list(msg.caption_entities or [])
    return any(e.type == "spoiler" for e in entities)


def _has_url(msg) -> bool:
    """Check for http/https URLs in text or caption."""
    text = msg.text or msg.caption or ""
    if _URL_RE.search(text):
        return True
    # Also check URL entities
    entities = list(msg.entities or []) + list(msg.caption_entities or [])
    return any(e.type in ("url", "text_link") for e in entities)


def _has_rtl(msg) -> bool:
    """Detect right-to-left Unicode characters."""
    text = msg.text or msg.caption or ""
    return bool(_RTL_RE.search(text))


def _has_phone(msg) -> bool:
    """Phone number entity in message."""
    entities = list(msg.entities or []) + list(msg.caption_entities or [])
    return any(e.type == "phone_number" for e in entities)


def _has_button(msg) -> bool:
    """Inline keyboard buttons attached to message."""
    return bool(msg.reply_markup)


# ── Lock enforcement handler ──────────────────────────────────────────────────

async def _check_locks(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return

    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    # Admins bypass all locks
    if await is_admin(update, ctx):
        return

    # Approved users bypass all locks
    if await is_approved(user.id, chat.id):
        return

    lock_states = await get_locks(chat.id)

    # Build list of triggered locks
    violated = []

    if lock_states.get("sticker") and msg.sticker:
        violated.append("sticker")

    if lock_states.get("gif") and _is_gif(msg):
        violated.append("gif")

    if lock_states.get("media") and (msg.photo or msg.video or msg.audio
                                     or msg.document or msg.animation
                                     or msg.video_note or msg.voice):
        violated.append("media")

    if lock_states.get("game") and msg.game:
        violated.append("game")

    if lock_states.get("inline") and msg.via_bot:
        violated.append("inline")

    if lock_states.get("forward") and (msg.forward_date is not None
                                        or msg.forward_from is not None
                                        or msg.forward_from_chat is not None
                                        or msg.forward_sender_name is not None):
        violated.append("forward")

    if lock_states.get("bot") and user.is_bot:
        violated.append("bot")

    if lock_states.get("url") and _has_url(msg):
        violated.append("url")

    if lock_states.get("button") and _has_button(msg):
        violated.append("button")

    if lock_states.get("phone") and _has_phone(msg):
        violated.append("phone")

    if lock_states.get("location") and msg.location:
        violated.append("location")

    if lock_states.get("contact") and msg.contact:
        violated.append("contact")

    if lock_states.get("audio") and msg.audio:
        violated.append("audio")

    if lock_states.get("video") and msg.video:
        violated.append("video")

    if lock_states.get("document") and msg.document and not _is_gif(msg):
        violated.append("document")

    if lock_states.get("voice") and msg.voice:
        violated.append("voice")

    if lock_states.get("videonote") and msg.video_note:
        violated.append("videonote")

    if lock_states.get("poll") and msg.poll:
        violated.append("poll")

    if lock_states.get("rtl") and _has_rtl(msg):
        violated.append("rtl")

    if lock_states.get("spoiler") and _has_spoiler(msg):
        violated.append("spoiler")

    if violated:
        try:
            await msg.delete()
        except Exception:
            pass


# ── Register ──────────────────────────────────────────────────────────────────

def register(app):
    app.add_handler(
        MessageHandler(filters.ChatType.GROUPS & filters.ALL, _check_locks),
        group=7
    )
    for cmd, handler in [
        ("lock", lock_cmd),
        ("unlock", unlock_cmd),
        ("locks", locks_cmd),
    ]:
        app.add_handler(MessageHandler(dcmd(cmd), handler), group=10)
