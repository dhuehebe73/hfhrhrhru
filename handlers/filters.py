"""
Filters: word, link, sticker, media, bot
Commands: filter unfilter filters
"""
import re
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from telegram.error import BadRequest

from utils import require_admin, is_admin, dot_filter
from database import add_filter, remove_filter, get_filters, get_chat_settings, is_approved


_LINK_RE = re.compile(
    r"(https?://|t\.me/|@\w{5,}|telegram\.me/)", re.IGNORECASE
)


async def filter_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await require_admin(update, context): return
    if not context.args:
        return await msg.reply_text(
            "Kullanim: .filter <kelime>\n"
            "Birden fazla: .filter kotu kelime"
        )
    word = " ".join(context.args).lower()
    await add_filter(update.effective_chat.id, word)
    await msg.reply_text(f"Filtre eklendi: <code>{word}</code>", parse_mode="HTML")


async def unfilter_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await require_admin(update, context): return
    if not context.args:
        return await msg.reply_text("Hangi filtreyi kaldirayim?")
    word = " ".join(context.args).lower()
    await remove_filter(update.effective_chat.id, word)
    await msg.reply_text(f"Filtre kaldirildi: <code>{word}</code>", parse_mode="HTML")


async def list_filters_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    words = await get_filters(update.effective_chat.id)
    if not words:
        return await update.effective_message.reply_text("Aktif kelime filtresi yok.")
    text = "<b>Kelime Filtreleri:</b>\n" + "\n".join(f"  • <code>{w}</code>" for w in words)
    await update.effective_message.reply_text(text, parse_mode="HTML")


async def _auto_delete(update: Update, context: ContextTypes.DEFAULT_TYPE, reason: str):
    msg = update.effective_message
    chat_id = update.effective_chat.id
    try:
        await msg.delete()
    except BadRequest:
        pass
    try:
        notice = await context.bot.send_message(
            chat_id, f"Mesaj silindi ({reason})."
        )
        context.job_queue.run_once(
            lambda ctx: ctx.bot.delete_message(chat_id, notice.message_id),
            5,
        )
    except Exception:
        pass


async def check_all_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Master auto-filter handler."""
    msg = update.effective_message
    if not msg or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Admins and approved users bypass everything
    if await is_admin(update, context):
        return
    if await is_approved(user_id, chat_id):
        return

    settings = await get_chat_settings(chat_id)

    # ── Sticker filter
    if settings["sticker_filter"] and msg.sticker:
        return await _auto_delete(update, context, "sticker yasak")

    # ── Media filter
    if settings["media_filter"] and (
        msg.photo or msg.video or msg.document or msg.audio or msg.voice
    ):
        return await _auto_delete(update, context, "medya yasak")

    # ── Bot filter
    if settings["bot_filter"] and update.effective_user.is_bot:
        return await _auto_delete(update, context, "bot mesaji yasak")

    text = msg.text or msg.caption or ""
    if not text:
        return

    # ── Link filter
    if settings["link_filter"] and _LINK_RE.search(text):
        return await _auto_delete(update, context, "link yasak")

    # ── Word filter
    words = await get_filters(chat_id)
    text_lower = text.lower()
    for word in words:
        if re.search(rf"\b{re.escape(word)}\b", text_lower):
            return await _auto_delete(update, context, f"yasak kelime: {word}")


# ─── Filter toggle commands ───────────────────────────────────────────────────

async def _toggle(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str, label: str):
    if not await require_admin(update, context): return
    from database import update_chat_setting
    settings = await get_chat_settings(update.effective_chat.id)
    new_val = not settings[key]
    await update_chat_setting(update.effective_chat.id, key, int(new_val))
    state = "ACIK" if new_val else "KAPALI"
    await update.effective_message.reply_text(f"{label}: {state}")


async def linkfilter_cmd(u, c): await _toggle(u, c, "link_filter", "Link filtresi")
async def stickerfilter_cmd(u, c): await _toggle(u, c, "sticker_filter", "Sticker filtresi")
async def mediafilter_cmd(u, c): await _toggle(u, c, "media_filter", "Medya filtresi")
async def botfilter_cmd(u, c): await _toggle(u, c, "bot_filter", "Bot mesaj filtresi")


def register_filter_handlers(app):
    for cmd, handler in [
        ("filter", filter_cmd), ("unfilter", unfilter_cmd), ("filters", list_filters_cmd),
        ("linkfilter", linkfilter_cmd), ("stickerfilter", stickerfilter_cmd),
        ("mediafilter", mediafilter_cmd), ("botfilter", botfilter_cmd),
    ]:
        app.add_handler(CommandHandler(cmd, handler))
        app.add_handler(MessageHandler(filters.TEXT & dot_filter(cmd), handler))

    # Auto-filter on every message (group=10 = low priority)
    app.add_handler(
        MessageHandler(filters.ALL & ~filters.COMMAND, check_all_filters),
        group=10,
    )
