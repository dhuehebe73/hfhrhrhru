import re
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from database import get_filters, add_filter, remove_filter, list_notes, get_settings, is_approved
from utils import require_admin, dcmd

_URL_RE = re.compile(r"(https?://|t\.me/|@\w{5,})", re.I)


async def filter_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    args = ctx.args or []
    if not args:
        words = await get_filters(update.effective_chat.id)
        if not words:
            await update.effective_message.reply_text("Filtre yok."); return
        await update.effective_message.reply_text(
            "🔍 Filtreler:\n" + "\n".join(f"• {w}" for w in words)); return
    word = " ".join(args).lower()
    await add_filter(update.effective_chat.id, word)
    await update.effective_message.reply_text(f"✅ «{word}» filtreye eklendi.")

async def unfilter_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    args = ctx.args or []
    if not args:
        await update.effective_message.reply_text("Hangi kelimeyi kaldırayım?"); return
    word = " ".join(args).lower()
    await remove_filter(update.effective_chat.id, word)
    await update.effective_message.reply_text(f"✅ «{word}» filtreden kaldırıldı.")

async def filters_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    words = await get_filters(update.effective_chat.id)
    if not words:
        await update.effective_message.reply_text("Aktif filtre yok."); return
    await update.effective_message.reply_text(
        "🔍 Aktif kelime filtreleri:\n" + "\n".join(f"• {w}" for w in words))


async def _check_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.from_user: return
    chat = update.effective_chat
    if not chat or chat.type == "private": return

    uid = msg.from_user.id
    if await is_approved(uid, chat.id): return

    from utils import is_admin
    if await is_admin(update, ctx): return

    s = await get_settings(chat.id)
    text = (msg.text or msg.caption or "").lower()

    # Word filter
    banned = await get_filters(chat.id)
    if banned:
        for w in banned:
            if w in text:
                try: await msg.delete()
                except Exception: pass
                try:
                    m = await msg.reply_text(f"🚫 Yasaklı kelime: {w}")
                    from utils import later
                    later(5, m.delete())
                except Exception: pass
                return

    # Link filter
    if s.get("link_filter") and _URL_RE.search(text):
        try: await msg.delete()
        except Exception: pass
        return

    # Sticker filter
    if s.get("sticker_filter") and msg.sticker:
        try: await msg.delete()
        except Exception: pass
        return

    # Media filter
    if s.get("media_filter") and (msg.photo or msg.video or msg.document or msg.audio):
        try: await msg.delete()
        except Exception: pass
        return

    # Bot filter
    if s.get("bot_filter") and msg.from_user.is_bot:
        try: await msg.delete()
        except Exception: pass
        return


def register(app):
    for cmd, h in [
        ("filter", filter_cmd), ("unfilter", unfilter_cmd), ("filters", filters_cmd)
    ]:
        app.add_handler(MessageHandler(dcmd(cmd), h), group=10)
    app.add_handler(
        MessageHandler(filters.ChatType.GROUPS & filters.ALL, _check_message), group=15)
