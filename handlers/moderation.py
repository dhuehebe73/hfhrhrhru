"""
Moderation: .purge .lock .unlock + anti-flood
"""
import time
from collections import defaultdict

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from telegram.error import BadRequest

from utils import is_admin, bot_is_admin, LOCKED_PERMISSIONS, FULL_PERMISSIONS
from database import get_chat_settings, update_chat_setting

import re as re_mod


def _dot_filter(cmd: str):
    return filters.Regex(rf"^[./!]{re_mod.escape(cmd)}(\s|$)")


# ─── Anti-flood (in-memory) ───────────────────────────────────────────────────

# {chat_id: {user_id: [timestamps]}}
_flood_tracker: dict[int, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))


async def flood_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not update.effective_user:
        return

    # Admins bypass flood check
    if await is_admin(update, context):
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    settings = await get_chat_settings(chat_id)

    if not settings["anti_flood"]:
        return

    limit = settings["flood_limit"]
    now = time.time()
    window = 5.0  # seconds

    # Clean old timestamps
    user_times = _flood_tracker[chat_id][user_id]
    user_times[:] = [t for t in user_times if now - t < window]
    user_times.append(now)

    if len(user_times) > limit:
        user_times.clear()
        user = update.effective_user
        try:
            from utils import MUTE_PERMISSIONS, mention_html
            await update.effective_chat.restrict_member(user_id, MUTE_PERMISSIONS)
            await msg.reply_text(
                f"{mention_html(user_id, user.first_name)} flood yaptigindan susturuldu!",
                parse_mode="HTML",
            )
        except BadRequest:
            pass


# ─── PURGE ────────────────────────────────────────────────────────────────────

async def purge_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await is_admin(update, context):
        await msg.reply_text("Bu komutu kullanmak icin admin olmalisin.")
        return
    if not await bot_is_admin(update, context):
        await msg.reply_text("Benim admin olmam gerekiyor!")
        return

    # .purge N — delete last N messages
    # Or reply to a message to delete from that point
    count = 0
    if msg.reply_to_message:
        start_id = msg.reply_to_message.message_id
        end_id = msg.message_id
        ids_to_delete = list(range(start_id, end_id + 1))
        count = len(ids_to_delete)
        # Telegram only allows bulk delete in chunks of 100
        for i in range(0, len(ids_to_delete), 100):
            chunk = ids_to_delete[i : i + 100]
            try:
                await context.bot.delete_messages(update.effective_chat.id, chunk)
            except BadRequest:
                # Try one by one
                for mid in chunk:
                    try:
                        await context.bot.delete_message(update.effective_chat.id, mid)
                    except Exception:
                        pass
    elif context.args:
        try:
            n = int(context.args[0])
        except ValueError:
            await msg.reply_text("Gecerli bir sayi gir. Ornek: .purge 10")
            return

        n = min(n, 200)  # safety cap
        ids_to_delete = list(range(msg.message_id - n, msg.message_id + 1))
        count = len(ids_to_delete)
        for i in range(0, len(ids_to_delete), 100):
            chunk = ids_to_delete[i : i + 100]
            try:
                await context.bot.delete_messages(update.effective_chat.id, chunk)
            except BadRequest:
                for mid in chunk:
                    try:
                        await context.bot.delete_message(update.effective_chat.id, mid)
                    except Exception:
                        pass
    else:
        await msg.reply_text(
            "Nasil kullanilir:\n"
            "• .purge 10 — son 10 mesaji sil\n"
            "• Bir mesaja reply at ve .purge yaz — o mesajdan itibaren sil"
        )
        return

    notice = await context.bot.send_message(
        update.effective_chat.id, f"{count} mesaj silindi."
    )
    context.job_queue.run_once(
        lambda ctx: ctx.bot.delete_message(update.effective_chat.id, notice.message_id),
        3,
    )


# ─── LOCK / UNLOCK ────────────────────────────────────────────────────────────

async def lock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await is_admin(update, context):
        await msg.reply_text("Bu komutu kullanmak icin admin olmalisin.")
        return
    if not await bot_is_admin(update, context):
        await msg.reply_text("Benim admin olmam gerekiyor!")
        return

    try:
        await update.effective_chat.set_permissions(LOCKED_PERMISSIONS)
        await update_chat_setting(update.effective_chat.id, "locked", 1)
        await msg.reply_text("Grup kilitlendi. Sadece adminler mesaj gonderebilir.")
    except BadRequest as e:
        await msg.reply_text(f"Kilitlenemedi: {e}")


async def unlock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await is_admin(update, context):
        await msg.reply_text("Bu komutu kullanmak icin admin olmalisin.")
        return
    if not await bot_is_admin(update, context):
        await msg.reply_text("Benim admin olmam gerekiyor!")
        return

    try:
        await update.effective_chat.set_permissions(FULL_PERMISSIONS)
        await update_chat_setting(update.effective_chat.id, "locked", 0)
        await msg.reply_text("Grup acildi. Herkes mesaj gonderebilir.")
    except BadRequest as e:
        await msg.reply_text(f"Acilamadi: {e}")


# ─── ANTIFLOOD CONFIG ─────────────────────────────────────────────────────────

async def antiflood_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await is_admin(update, context):
        await msg.reply_text("Bu komutu kullanmak icin admin olmalisin.")
        return

    args = context.args
    chat_id = update.effective_chat.id
    settings = await get_chat_settings(chat_id)

    if not args:
        status = "ACIK" if settings["anti_flood"] else "KAPALI"
        await msg.reply_text(
            f"Anti-flood: {status}\n"
            f"Limit: {settings['flood_limit']} mesaj / 5 saniye\n\n"
            "Degistirmek icin:\n"
            "  .antiflood on/off\n"
            "  .antiflood 5  (mesaj limiti)"
        )
        return

    arg = args[0].lower()
    if arg in ("on", "ac", "1"):
        await update_chat_setting(chat_id, "anti_flood", 1)
        await msg.reply_text("Anti-flood aktif!")
    elif arg in ("off", "kapat", "0"):
        await update_chat_setting(chat_id, "anti_flood", 0)
        await msg.reply_text("Anti-flood kapatildi.")
    elif arg.isdigit():
        limit = max(2, min(int(arg), 50))
        await update_chat_setting(chat_id, "flood_limit", limit)
        await msg.reply_text(f"Flood limiti {limit} mesaj/5sn olarak ayarlandi.")
    else:
        await msg.reply_text("Gecersiz arguman. Kullanim: .antiflood on/off/[sayi]")


def register_moderation_handlers(app):
    for cmd, handler in [
        ("purge", purge_cmd),
        ("lock", lock_cmd),
        ("unlock", unlock_cmd),
        ("antiflood", antiflood_cmd),
    ]:
        app.add_handler(CommandHandler(cmd, handler))
        app.add_handler(
            MessageHandler(filters.TEXT & _dot_filter(cmd), handler)
        )

    # Anti-flood check on every message
    app.add_handler(
        MessageHandler(filters.ALL & ~filters.COMMAND, flood_check),
        group=5,
    )
