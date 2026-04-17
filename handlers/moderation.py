"""
Moderation: purge lock unlock slowmode antiflood
"""
import time
from collections import defaultdict

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from telegram.error import BadRequest

from utils import (
    require_admin, require_bot_admin, is_admin,
    mention, LOCKED_PERMS, FULL_PERMS, MUTE_PERMS, dot_filter, later,
)
from database import get_chat_settings, update_chat_setting, increment_stats


# ─── Anti-flood (in-memory) ───────────────────────────────────────────────────

_flood: dict[int, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))


async def flood_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not update.effective_user:
        return

    if await is_admin(update, context):
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    settings = await get_chat_settings(chat_id)

    # Track stats
    await increment_stats(user_id, chat_id)

    if not settings["anti_flood"]:
        return

    limit  = settings["flood_limit"]
    now    = time.time()
    window = 5.0

    msgs = _flood[chat_id][user_id]
    msgs[:] = [t for t in msgs if now - t < window]
    msgs.append(now)

    if len(msgs) > limit:
        msgs.clear()
        user = update.effective_user
        try:
            await update.effective_chat.restrict_member(user_id, MUTE_PERMS)
            await msg.reply_text(
                f"{mention(user_id, user.first_name)} flood yaptigindan 5 dakika susturuldu!",
                parse_mode="HTML",
            )
            # Auto-unmute after 5 min
            later(300, context.bot.restrict_chat_member(chat_id, user_id, FULL_PERMS))
        except BadRequest:
            pass


# ─── PURGE ────────────────────────────────────────────────────────────────────

async def purge_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await require_admin(update, context): return
    if not await require_bot_admin(update, context): return

    ids = []
    if msg.reply_to_message:
        start = msg.reply_to_message.message_id
        end   = msg.message_id
        ids   = list(range(start, end + 1))
    elif context.args and context.args[0].isdigit():
        n   = min(int(context.args[0]), 200)
        ids = list(range(msg.message_id - n, msg.message_id + 1))
    else:
        return await msg.reply_text(
            "Kullanim:\n"
            "  .purge 10  — son 10 mesaji sil\n"
            "  Reply at + .purge — o mesajdan itibaren sil"
        )

    deleted = 0
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        try:
            await context.bot.delete_messages(update.effective_chat.id, chunk)
            deleted += len(chunk)
        except BadRequest:
            for mid in chunk:
                try:
                    await context.bot.delete_message(update.effective_chat.id, mid)
                    deleted += 1
                except Exception:
                    pass

    n = await context.bot.send_message(update.effective_chat.id, f"{deleted} mesaj silindi.")
    later(3, context.bot.delete_message(update.effective_chat.id, n.message_id))


# ─── LOCK / UNLOCK ────────────────────────────────────────────────────────────

async def lock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): return
    if not await require_bot_admin(update, context): return
    try:
        await update.effective_chat.set_permissions(LOCKED_PERMS)
        await update_chat_setting(update.effective_chat.id, "locked", 1)
        await update.effective_message.reply_text("Grup kilitlendi. Sadece adminler yazabilir.")
    except BadRequest as e:
        await update.effective_message.reply_text(f"Kilitlenemedi: {e}")


async def unlock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): return
    if not await require_bot_admin(update, context): return
    try:
        await update.effective_chat.set_permissions(FULL_PERMS)
        await update_chat_setting(update.effective_chat.id, "locked", 0)
        await update.effective_message.reply_text("Grup acildi.")
    except BadRequest as e:
        await update.effective_message.reply_text(f"Acilamadi: {e}")


# ─── SLOWMODE ────────────────────────────────────────────────────────────────

async def slowmode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): return
    if not await require_bot_admin(update, context): return
    args = context.args

    if not args:
        settings = await get_chat_settings(update.effective_chat.id)
        current = settings["slowmode"]
        return await update.effective_message.reply_text(
            f"Yavas mod: {current} saniye\n"
            ".slowmode 0 — kapat\n"
            ".slowmode 30 — 30 saniye"
        )

    try:
        secs = int(args[0])
    except ValueError:
        return await update.effective_message.reply_text("Saniye olarak rakam gir.")

    secs = max(0, min(secs, 3600))
    try:
        await context.bot.set_chat_slow_mode_delay(update.effective_chat.id, secs)
        await update_chat_setting(update.effective_chat.id, "slowmode", secs)
        if secs == 0:
            await update.effective_message.reply_text("Yavas mod kapatildi.")
        else:
            await update.effective_message.reply_text(f"Yavas mod: {secs} saniye")
    except BadRequest as e:
        await update.effective_message.reply_text(f"Ayarlanamadi: {e}")


# ─── ANTIFLOOD CONFIG ─────────────────────────────────────────────────────────

async def antiflood_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): return
    args = context.args
    chat_id = update.effective_chat.id
    settings = await get_chat_settings(chat_id)

    if not args:
        status = "ACIK" if settings["anti_flood"] else "KAPALI"
        return await update.effective_message.reply_text(
            f"Anti-flood: {status}\n"
            f"Limit: {settings['flood_limit']} mesaj/5sn\n\n"
            ".antiflood on/off\n"
            ".antiflood 5  (limit)"
        )

    arg = args[0].lower()
    if arg in ("on", "ac", "1"):
        await update_chat_setting(chat_id, "anti_flood", 1)
        await update.effective_message.reply_text("Anti-flood ACIK!")
    elif arg in ("off", "kapat", "0"):
        await update_chat_setting(chat_id, "anti_flood", 0)
        await update.effective_message.reply_text("Anti-flood KAPALI.")
    elif arg.isdigit():
        limit = max(2, min(int(arg), 50))
        await update_chat_setting(chat_id, "flood_limit", limit)
        await update.effective_message.reply_text(f"Flood limiti: {limit} mesaj/5sn")
    else:
        await update.effective_message.reply_text("Gecersiz arguman.")


def register_moderation_handlers(app):
    for cmd, handler in [
        ("purge", purge_cmd), ("lock", lock_cmd), ("unlock", unlock_cmd),
        ("slowmode", slowmode_cmd), ("antiflood", antiflood_cmd),
    ]:
        app.add_handler(CommandHandler(cmd, handler))
        app.add_handler(MessageHandler(filters.TEXT & dot_filter(cmd), handler))

    # Flood + stat tracking on every message
    app.add_handler(
        MessageHandler(filters.ALL & ~filters.COMMAND, flood_check),
        group=5,
    )
