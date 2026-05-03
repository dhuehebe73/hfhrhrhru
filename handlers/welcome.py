import html, random, time
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes, MessageHandler, ChatMemberHandler, filters
from database import (get_welcome, set_welcome_field, get_settings, set_setting,
                      mark_left, has_left, clear_left,
                      set_captcha_pending, get_captcha_pending, clear_captcha_pending,
                      upsert_user_cache)
from utils import require_admin, MUTE_PERMS, FULL_PERMS, mention, dcmd, later, get_args


def _fmt(template: str, user, chat) -> str:
    return (template
        .replace("{first}", html.escape(user.first_name or ""))
        .replace("{last}",  html.escape(user.last_name or ""))
        .replace("{name}",  html.escape(user.full_name or ""))
        .replace("{username}", f"@{user.username}" if user.username else user.first_name)
        .replace("{chat}",  html.escape(chat.title or ""))
        .replace("{count}", "?"))


async def _on_member_update(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if not result: return
    chat = result.chat
    old, new = result.old_chat_member, result.new_chat_member
    user = new.user
    if user and user.username:
        await upsert_user_cache(user.id, user.username, user.first_name or "")

    from telegram.constants import ChatMemberStatus as CMS

    joined = (old.status in (CMS.LEFT, CMS.BANNED) and
              new.status in (CMS.MEMBER, CMS.RESTRICTED))
    left   = (old.status in (CMS.MEMBER, CMS.ADMINISTRATOR, CMS.OWNER, CMS.RESTRICTED) and
              new.status in (CMS.LEFT, CMS.BANNED))

    if left:
        s = await get_settings(chat.id)
        if s.get("auto_ban_leavers"):
            await mark_left(user.id, chat.id)
            try: await chat.ban_member(user.id)
            except Exception: pass
            return

        w = await get_welcome(chat.id)
        if w.get("goodbye_msg"):
            try:
                msg = await ctx.bot.send_message(chat.id,
                    _fmt(w["goodbye_msg"], user, chat), parse_mode="HTML")
                later(30, msg.delete())
            except Exception: pass
        return

    if not joined: return

    # Re-join check
    if await has_left(user.id, chat.id):
        s = await get_settings(chat.id)
        if s.get("auto_ban_leavers"):
            try: await chat.ban_member(user.id)
            except Exception: pass
            return
        await clear_left(user.id, chat.id)

    w = await get_welcome(chat.id)

    if w.get("captcha"):
        a = random.randint(1, 9)
        b = random.randint(1, 9)
        answer = a + b
        try:
            await chat.restrict_member(user.id, MUTE_PERMS)
        except Exception: pass
        try:
            q = await ctx.bot.send_message(chat.id,
                f"👋 {mention(user.id, user.first_name)}, lütfen doğrula:\n\n"
                f"<b>{a} + {b} = ?</b>\n\n"
                f"Cevabı yaz (sadece rakam). ({w.get('captcha_timeout',60)}sn)",
                parse_mode="HTML")
            expires = int(time.time()) + w.get("captcha_timeout", 60)
            await set_captcha_pending(user.id, chat.id, answer, expires, q.message_id)
            later(w.get("captcha_timeout", 60) + 5, _captcha_timeout(ctx, user.id, chat.id))
        except Exception: pass
        return

    if w.get("welcome_msg") and w.get("enabled", True):
        try:
            msg = await ctx.bot.send_message(chat.id,
                _fmt(w["welcome_msg"], user, chat), parse_mode="HTML")
            later(120, msg.delete())
        except Exception: pass


async def _captcha_timeout(ctx, uid: int, cid: int):
    pending = await get_captcha_pending(uid, cid)
    if not pending: return
    try:
        await ctx.bot.ban_chat_member(cid, uid)
    except Exception: pass
    try:
        await ctx.bot.delete_message(cid, pending["msg_id"])
    except Exception: pass
    await clear_captcha_pending(uid, cid)


async def _captcha_answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.from_user: return
    chat = update.effective_chat
    if not chat or chat.type == "private": return
    text = (msg.text or "").strip()
    if not text.isdigit(): return
    pending = await get_captcha_pending(msg.from_user.id, chat.id)
    if not pending: return
    try:
        guess = int(text)
    except ValueError:
        return
    try: await msg.delete()
    except Exception: pass
    if int(time.time()) > pending["expires"]:
        try: await chat.ban_member(msg.from_user.id)
        except Exception: pass
        await clear_captcha_pending(msg.from_user.id, chat.id)
        return
    if guess == pending["answer"]:
        try: await chat.restrict_member(msg.from_user.id, FULL_PERMS)
        except Exception: pass
        try: await ctx.bot.delete_message(chat.id, pending["msg_id"])
        except Exception: pass
        await clear_captcha_pending(msg.from_user.id, chat.id)
        m = await ctx.bot.send_message(chat.id,
            f"✅ {mention(msg.from_user.id, msg.from_user.first_name)} doğrulandı!",
            parse_mode="HTML")
        later(10, m.delete())
    else:
        try:
            m = await ctx.bot.send_message(chat.id, "❌ Yanlış cevap, tekrar dene.")
            later(5, m.delete())
        except Exception: pass


# ── Admin commands ─────────────────────────────────────────────────────────────

async def setwelcome_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    msg = update.effective_message
    _a = get_args(update, ctx)
    text = " ".join(_a) if _a else (
        msg.reply_to_message.text if msg.reply_to_message else "")
    if not text:
        await msg.reply_text("Kullanım: /setwelcome <metin>\nDeğişkenler: {name} {chat}"); return
    await set_welcome_field(update.effective_chat.id, "welcome_msg", text)
    await msg.reply_text("✅ Karşılama mesajı ayarlandı.")

async def setgoodbye_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    msg = update.effective_message
    _a = get_args(update, ctx)
    text = " ".join(_a) if _a else (
        msg.reply_to_message.text if msg.reply_to_message else "")
    if not text:
        await msg.reply_text("Kullanım: /setgoodbye <metin>"); return
    await set_welcome_field(update.effective_chat.id, "goodbye_msg", text)
    await msg.reply_text("✅ Veda mesajı ayarlandı.")

async def welcome_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    args = get_args(update, ctx)
    cid = update.effective_chat.id
    w = await get_welcome(cid)
    if not args:
        state = "açık" if w.get("enabled", True) else "kapalı"
        await update.effective_message.reply_text(
            f"ℹ️ Karşılama: {state}\n"
            f"Metin: {w.get('welcome_msg') or '(yok)'}\n"
            "Aç/kapat: /welcome on|off"); return
    if args[0].lower() in ("on","ac","aç","1"):
        await set_welcome_field(cid, "enabled", 1)
        await update.effective_message.reply_text("✅ Karşılama açıldı.")
    elif args[0].lower() in ("off","kapat","0"):
        await set_welcome_field(cid, "enabled", 0)
        await update.effective_message.reply_text("✅ Karşılama kapatıldı.")

async def captcha_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    args = get_args(update, ctx)
    cid = update.effective_chat.id
    w = await get_welcome(cid)
    if not args:
        state = "açık" if w.get("captcha") else "kapalı"
        await update.effective_message.reply_text(f"ℹ️ Captcha: {state}"); return
    if args[0].lower() in ("on","ac","aç","1"):
        await set_welcome_field(cid, "captcha", 1)
        await update.effective_message.reply_text("✅ Captcha açıldı.")
    elif args[0].lower() in ("off","kapat","0"):
        await set_welcome_field(cid, "captcha", 0)
        await update.effective_message.reply_text("✅ Captcha kapatıldı.")

async def autoban_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    args = get_args(update, ctx)
    cid = update.effective_chat.id
    s = await get_settings(cid)
    if not args:
        state = "açık" if s.get("auto_ban_leavers") else "kapalı"
        await update.effective_message.reply_text(
            f"ℹ️ Çıkan üye otomatik ban: {state}"); return
    if args[0].lower() in ("on","ac","aç","1"):
        await set_setting(cid, "auto_ban_leavers", 1)
        await update.effective_message.reply_text("✅ Çıkan üye otomatik ban açıldı.")
    elif args[0].lower() in ("off","kapat","0"):
        await set_setting(cid, "auto_ban_leavers", 0)
        await update.effective_message.reply_text("✅ Çıkan üye otomatik ban kapatıldı.")


def register(app):
    app.add_handler(ChatMemberHandler(_on_member_update, ChatMemberHandler.CHAT_MEMBER), group=5)
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND, _captcha_answer), group=5)
    for cmd, h in [
        ("setwelcome", setwelcome_cmd), ("setgoodbye", setgoodbye_cmd),
        ("welcome", welcome_cmd), ("captcha", captcha_cmd), ("autoban", autoban_cmd),
    ]:
        app.add_handler(MessageHandler(dcmd(cmd), h), group=10)
