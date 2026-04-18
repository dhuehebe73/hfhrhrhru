import time
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler
from database import (get_warnings, add_warning, reset_warnings, remove_warning,
                      get_settings, approve, unapprove)
from utils import (resolve_user, require_admin, require_bot_admin,
                   MUTE_PERMS, FULL_PERMS, mention, dcmd, parse_time, fmt_duration, later)
from config import LOG_CHANNEL


async def _log(ctx, text):
    if LOG_CHANNEL:
        try: await ctx.bot.send_message(LOG_CHANNEL, text, parse_mode="HTML")
        except Exception: pass


# ── Ban ────────────────────────────────────────────────────────────────────────

async def ban_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    if not await require_bot_admin(update, ctx): return
    uid, name, reason = await resolve_user(update, ctx)
    if not uid:
        await update.effective_message.reply_text("Kullanıcı belirtin."); return
    try:
        await update.effective_chat.ban_member(uid)
        text = f"🚫 {mention(uid, name)} banlandı."
        if reason: text += f"\n📝 {reason}"
        await update.effective_message.reply_text(text, parse_mode="HTML")
        await _log(ctx, f"BAN | {mention(uid,name)} | {update.effective_chat.title}\n{reason}")
    except Exception as e:
        await update.effective_message.reply_text(f"Hata: {e}")

async def dban_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    if not await require_bot_admin(update, ctx): return
    uid, name, reason = await resolve_user(update, ctx)
    if not uid:
        await update.effective_message.reply_text("Kullanıcı belirtin."); return
    if update.effective_message.reply_to_message:
        try: await update.effective_message.reply_to_message.delete()
        except Exception: pass
    try: await update.effective_message.delete()
    except Exception: pass
    try:
        await update.effective_chat.ban_member(uid)
        msg = await ctx.bot.send_message(update.effective_chat.id,
            f"🚫 {mention(uid,name)} banlandı.", parse_mode="HTML")
        later(5, msg.delete())
    except Exception as e:
        await ctx.bot.send_message(update.effective_chat.id, f"Hata: {e}")

async def sban_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    if not await require_bot_admin(update, ctx): return
    uid, name, _ = await resolve_user(update, ctx)
    if not uid: return
    if update.effective_message.reply_to_message:
        try: await update.effective_message.reply_to_message.delete()
        except Exception: pass
    try: await update.effective_message.delete()
    except Exception: pass
    try: await update.effective_chat.ban_member(uid)
    except Exception: pass

async def unban_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    if not await require_bot_admin(update, ctx): return
    uid, name, _ = await resolve_user(update, ctx)
    if not uid:
        await update.effective_message.reply_text("Kullanıcı belirtin."); return
    try:
        await update.effective_chat.unban_member(uid, only_if_banned=True)
        await update.effective_message.reply_text(
            f"✅ {mention(uid,name)} unban edildi.", parse_mode="HTML")
    except Exception as e:
        await update.effective_message.reply_text(f"Hata: {e}")


# ── Kick ───────────────────────────────────────────────────────────────────────

async def kick_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    if not await require_bot_admin(update, ctx): return
    uid, name, reason = await resolve_user(update, ctx)
    if not uid:
        await update.effective_message.reply_text("Kullanıcı belirtin."); return
    try:
        await update.effective_chat.ban_member(uid)
        await update.effective_chat.unban_member(uid)
        text = f"👢 {mention(uid,name)} atıldı."
        if reason: text += f"\n📝 {reason}"
        await update.effective_message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        await update.effective_message.reply_text(f"Hata: {e}")

async def dkick_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    if not await require_bot_admin(update, ctx): return
    uid, name, _ = await resolve_user(update, ctx)
    if not uid:
        await update.effective_message.reply_text("Kullanıcı belirtin."); return
    if update.effective_message.reply_to_message:
        try: await update.effective_message.reply_to_message.delete()
        except Exception: pass
    try: await update.effective_message.delete()
    except Exception: pass
    try:
        await update.effective_chat.ban_member(uid)
        await update.effective_chat.unban_member(uid)
        msg = await ctx.bot.send_message(update.effective_chat.id,
            f"👢 {mention(uid,name)} atıldı.", parse_mode="HTML")
        later(5, msg.delete())
    except Exception as e:
        await ctx.bot.send_message(update.effective_chat.id, f"Hata: {e}")


# ── Mute ───────────────────────────────────────────────────────────────────────

async def mute_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    if not await require_bot_admin(update, ctx): return
    uid, name, reason = await resolve_user(update, ctx)
    if not uid:
        await update.effective_message.reply_text("Kullanıcı belirtin."); return
    args = ctx.args or []
    duration = None
    if args:
        t = parse_time(args[-1])
        if t:
            duration = t
            reason = " ".join(args[:-1]) if len(args) > 1 else ""
    until = int(time.time()) + duration if duration else None
    try:
        await update.effective_chat.restrict_member(uid, MUTE_PERMS, until_date=until)
        text = f"🔇 {mention(uid,name)} susturuldu."
        if duration: text += f" ({fmt_duration(duration)})"
        if reason: text += f"\n📝 {reason}"
        await update.effective_message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        await update.effective_message.reply_text(f"Hata: {e}")

async def dmute_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    if not await require_bot_admin(update, ctx): return
    uid, name, _ = await resolve_user(update, ctx)
    if not uid:
        await update.effective_message.reply_text("Kullanıcı belirtin."); return
    if update.effective_message.reply_to_message:
        try: await update.effective_message.reply_to_message.delete()
        except Exception: pass
    try: await update.effective_message.delete()
    except Exception: pass
    try:
        await update.effective_chat.restrict_member(uid, MUTE_PERMS)
        msg = await ctx.bot.send_message(update.effective_chat.id,
            f"🔇 {mention(uid,name)} susturuldu.", parse_mode="HTML")
        later(5, msg.delete())
    except Exception as e:
        await ctx.bot.send_message(update.effective_chat.id, f"Hata: {e}")

async def unmute_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    if not await require_bot_admin(update, ctx): return
    uid, name, _ = await resolve_user(update, ctx)
    if not uid:
        await update.effective_message.reply_text("Kullanıcı belirtin."); return
    try:
        await update.effective_chat.restrict_member(uid, FULL_PERMS)
        await update.effective_message.reply_text(
            f"🔊 {mention(uid,name)} susturması kaldırıldı.", parse_mode="HTML")
    except Exception as e:
        await update.effective_message.reply_text(f"Hata: {e}")


# ── Warn ───────────────────────────────────────────────────────────────────────

async def _do_action(update: Update, ctx: ContextTypes.DEFAULT_TYPE, uid: int, action: str) -> str:
    chat = update.effective_chat
    if action == "ban":
        await chat.ban_member(uid); return "banlandı 🚫"
    if action == "kick":
        await chat.ban_member(uid); await chat.unban_member(uid); return "atıldı 👢"
    if action == "mute":
        await chat.restrict_member(uid, MUTE_PERMS); return "susturuldu 🔇"
    return "uyarılandı ⚠️"

async def warn_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    uid, name, reason = await resolve_user(update, ctx)
    if not uid:
        await update.effective_message.reply_text("Kullanıcı belirtin."); return
    cid = update.effective_chat.id
    s = await get_settings(cid)
    limit, action = s.get("warn_limit", 3), s.get("warn_action", "ban")
    count = await add_warning(uid, cid, reason)
    text = f"⚠️ {mention(uid,name)} uyarıldı. ({count}/{limit})"
    if reason: text += f"\n📝 {reason}"
    if count >= limit:
        result = await _do_action(update, ctx, uid, action)
        text += f"\n\n🔴 Limit aşıldı! Kullanıcı {result}"
        await reset_warnings(uid, cid)
    await update.effective_message.reply_text(text, parse_mode="HTML")

async def dwarn_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    uid, name, reason = await resolve_user(update, ctx)
    if not uid:
        await update.effective_message.reply_text("Kullanıcı belirtin."); return
    if update.effective_message.reply_to_message:
        try: await update.effective_message.reply_to_message.delete()
        except Exception: pass
    try: await update.effective_message.delete()
    except Exception: pass
    cid = update.effective_chat.id
    s = await get_settings(cid)
    limit, action = s.get("warn_limit", 3), s.get("warn_action", "ban")
    count = await add_warning(uid, cid, reason)
    text = f"⚠️ {mention(uid,name)} uyarıldı. ({count}/{limit})"
    if count >= limit:
        result = await _do_action(update, ctx, uid, action)
        text += f"\n🔴 {result}"
        await reset_warnings(uid, cid)
    msg = await ctx.bot.send_message(cid, text, parse_mode="HTML")
    later(8, msg.delete())

async def unwarn_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    uid, name, _ = await resolve_user(update, ctx)
    if not uid:
        await update.effective_message.reply_text("Kullanıcı belirtin."); return
    new = await remove_warning(uid, update.effective_chat.id)
    await update.effective_message.reply_text(
        f"✅ {mention(uid,name)} bir uyarısı silindi. Toplam: {new}", parse_mode="HTML")

async def resetwarns_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    uid, name, _ = await resolve_user(update, ctx)
    if not uid:
        await update.effective_message.reply_text("Kullanıcı belirtin."); return
    await reset_warnings(uid, update.effective_chat.id)
    await update.effective_message.reply_text(
        f"✅ {mention(uid,name)} uyarıları sıfırlandı.", parse_mode="HTML")

async def warns_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid, name, _ = await resolve_user(update, ctx)
    if not uid:
        u = update.effective_user; uid, name = u.id, u.first_name
    count, reasons = await get_warnings(uid, update.effective_chat.id)
    if not count:
        await update.effective_message.reply_text(
            f"ℹ️ {mention(uid,name)} hiç uyarısı yok.", parse_mode="HTML"); return
    lines = "\n".join(f"  {i+1}. {r or '(sebep yok)'}" for i, r in enumerate(reasons))
    await update.effective_message.reply_text(
        f"⚠️ {mention(uid,name)} — {count} uyarı:\n{lines}", parse_mode="HTML")


# ── Promote / Demote ───────────────────────────────────────────────────────────

async def promote_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    if not await require_bot_admin(update, ctx): return
    uid, name, _ = await resolve_user(update, ctx)
    if not uid:
        await update.effective_message.reply_text("Kullanıcı belirtin."); return
    try:
        await update.effective_chat.promote_member(uid,
            can_delete_messages=True, can_restrict_members=True,
            can_pin_messages=True, can_invite_users=True, can_manage_chat=True)
        await update.effective_message.reply_text(
            f"⬆️ {mention(uid,name)} admin yapıldı.", parse_mode="HTML")
    except Exception as e:
        await update.effective_message.reply_text(f"Hata: {e}")

async def demote_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    if not await require_bot_admin(update, ctx): return
    uid, name, _ = await resolve_user(update, ctx)
    if not uid:
        await update.effective_message.reply_text("Kullanıcı belirtin."); return
    try:
        await update.effective_chat.promote_member(uid,
            can_delete_messages=False, can_restrict_members=False,
            can_pin_messages=False, can_invite_users=False, can_manage_chat=False)
        await update.effective_message.reply_text(
            f"⬇️ {mention(uid,name)} admin'den indirildi.", parse_mode="HTML")
    except Exception as e:
        await update.effective_message.reply_text(f"Hata: {e}")


# ── Approve ────────────────────────────────────────────────────────────────────

async def approve_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    uid, name, _ = await resolve_user(update, ctx)
    if not uid:
        await update.effective_message.reply_text("Kullanıcı belirtin."); return
    await approve(uid, update.effective_chat.id)
    await update.effective_message.reply_text(
        f"✅ {mention(uid,name)} onaylandı (filtrelerden muaf).", parse_mode="HTML")

async def unapprove_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    uid, name, _ = await resolve_user(update, ctx)
    if not uid:
        await update.effective_message.reply_text("Kullanıcı belirtin."); return
    await unapprove(uid, update.effective_chat.id)
    await update.effective_message.reply_text(
        f"❎ {mention(uid,name)} onayı kaldırıldı.", parse_mode="HTML")


# ── Pin ────────────────────────────────────────────────────────────────────────

async def pin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    if not await require_bot_admin(update, ctx): return
    if not update.effective_message.reply_to_message:
        await update.effective_message.reply_text("Sabitlenecek mesajı yanıtlayın."); return
    try:
        await update.effective_message.reply_to_message.pin()
        await update.effective_message.reply_text("📌 Sabitlendi.")
    except Exception as e:
        await update.effective_message.reply_text(f"Hata: {e}")

async def unpin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    if not await require_bot_admin(update, ctx): return
    try:
        if update.effective_message.reply_to_message:
            await update.effective_message.reply_to_message.unpin()
        else:
            await update.effective_chat.unpin_all_messages()
        await update.effective_message.reply_text("📌 Sabitleme kaldırıldı.")
    except Exception as e:
        await update.effective_message.reply_text(f"Hata: {e}")


# ── Delete message ─────────────────────────────────────────────────────────────

async def del_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    if update.effective_message.reply_to_message:
        try: await update.effective_message.reply_to_message.delete()
        except Exception: pass
    try: await update.effective_message.delete()
    except Exception: pass


# ── Register ───────────────────────────────────────────────────────────────────

def register(app):
    f = dcmd
    for cmd, handler in [
        ("ban", ban_cmd), ("dban", dban_cmd), ("sban", sban_cmd), ("unban", unban_cmd),
        ("kick", kick_cmd), ("dkick", dkick_cmd),
        ("mute", mute_cmd), ("dmute", dmute_cmd), ("unmute", unmute_cmd),
        ("warn", warn_cmd), ("dwarn", dwarn_cmd), ("unwarn", unwarn_cmd),
        ("resetwarns", resetwarns_cmd), ("warns", warns_cmd),
        ("promote", promote_cmd), ("demote", demote_cmd),
        ("approve", approve_cmd), ("unapprove", unapprove_cmd),
        ("pin", pin_cmd), ("unpin", unpin_cmd),
        ("del", del_cmd),
    ]:
        app.add_handler(MessageHandler(f(cmd), handler), group=10)
