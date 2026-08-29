import time
from collections import defaultdict
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from database import get_settings, set_setting, is_approved
from utils import require_admin, require_bot_admin, MUTE_PERMS, LOCKED_PERMS, FULL_PERMS, dcmd, mention, get_args

# flood tracker: {chat_id: {user_id: [timestamps]}}
_flood: dict[int, dict[int, list]] = defaultdict(lambda: defaultdict(list))


async def purge_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    if not await require_bot_admin(update, ctx): return
    msg = update.effective_message
    if not msg.reply_to_message:
        await msg.reply_text("Silmeye başlanacak mesajı yanıtlayın."); return
    from_id = msg.reply_to_message.message_id
    to_id   = msg.message_id
    deleted = 0
    for mid in range(from_id, to_id + 1):
        try:
            await ctx.bot.delete_message(update.effective_chat.id, mid)
            deleted += 1
        except Exception: pass
    m = await ctx.bot.send_message(update.effective_chat.id,
        f"🗑 {deleted} mesaj silindi.")
    from utils import later
    later(5, m.delete())


async def lock_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    if not await require_bot_admin(update, ctx): return
    try:
        await update.effective_chat.set_permissions(LOCKED_PERMS)
        await set_setting(update.effective_chat.id, "locked", 1)
        await update.effective_message.reply_text("🔒 Grup kilitlendi.")
    except Exception as e:
        await update.effective_message.reply_text(f"Hata: {e}")

async def unlock_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    if not await require_bot_admin(update, ctx): return
    try:
        await update.effective_chat.set_permissions(FULL_PERMS)
        await set_setting(update.effective_chat.id, "locked", 0)
        await update.effective_message.reply_text("🔓 Grup kilidi açıldı.")
    except Exception as e:
        await update.effective_message.reply_text(f"Hata: {e}")

async def slowmode_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    if not await require_bot_admin(update, ctx): return
    args = get_args(update, ctx)
    if not args or not args[0].isdigit():
        await update.effective_message.reply_text(
            "Kullanım: /slowmode <saniye> (0 = kapat)"); return
    sec = int(args[0])
    try:
        await update.effective_chat.set_slow_mode_delay(sec)
        await set_setting(update.effective_chat.id, "slowmode", sec)
        if sec:
            await update.effective_message.reply_text(f"🐢 Yavaş mod: {sec}sn")
        else:
            await update.effective_message.reply_text("✅ Yavaş mod kapatıldı.")
    except Exception as e:
        await update.effective_message.reply_text(f"Hata: {e}")

async def antiflood_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    args = get_args(update, ctx)
    cid = update.effective_chat.id
    s = await get_settings(cid)
    if not args:
        state = "açık" if s.get("anti_flood") else "kapalı"
        limit = s.get("flood_limit", 5)
        await update.effective_message.reply_text(
            f"ℹ️ Anti-flood: {state} (limit: {limit})\n"
            "Değiştir: /antiflood on|off [limit]"); return
    if args[0].lower() in ("on","ac","aç","1"):
        await set_setting(cid, "anti_flood", 1)
        if len(args) > 1 and args[1].isdigit():
            await set_setting(cid, "flood_limit", int(args[1]))
        await update.effective_message.reply_text("✅ Anti-flood açıldı.")
    elif args[0].lower() in ("off","kapat","0"):
        await set_setting(cid, "anti_flood", 0)
        await update.effective_message.reply_text("✅ Anti-flood kapatıldı.")
    elif args[0].isdigit():
        await set_setting(cid, "flood_limit", int(args[0]))
        await update.effective_message.reply_text(f"✅ Flood limiti: {args[0]}")


async def _flood_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.from_user: return
    chat = update.effective_chat
    if not chat or chat.type == "private": return

    uid = msg.from_user.id
    if await is_approved(uid, chat.id): return

    from utils import is_admin
    if await is_admin(update, ctx): return

    s = await get_settings(chat.id)
    if not s.get("anti_flood"): return

    limit = s.get("flood_limit", 5)
    now = time.time()
    window = 5.0

    msgs = _flood[chat.id][uid]
    msgs.append(now)
    _flood[chat.id][uid] = [t for t in msgs if now - t < window]

    if len(_flood[chat.id][uid]) >= limit:
        _flood[chat.id][uid] = []
        try:
            await chat.restrict_member(uid, MUTE_PERMS,
                until_date=int(now) + 60)
            m = await msg.reply_text(
                f"⚠️ {mention(uid, msg.from_user.first_name)} flood yaptı, 1 dakika susturuldu.",
                parse_mode="HTML")
            from utils import later
            later(10, m.delete())
        except Exception: pass


def register(app):
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & filters.ALL & ~filters.COMMAND,
        _flood_check), group=15)
    for cmd, h in [
        ("purge", purge_cmd), ("lock", lock_cmd), ("unlock", unlock_cmd),
        ("slowmode", slowmode_cmd), ("antiflood", antiflood_cmd),
    ]:
        app.add_handler(MessageHandler(dcmd(cmd), h), group=10)
