"""
Admin commands: ban unban kick mute unmute promote demote pin unpin del
D-variants: dban dkick dmute dwarn  (sil + islem)
S-variants: sban (sessiz ban)
"""
import html
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler
from telegram.error import BadRequest

from utils import (
    resolve_user, require_admin, require_bot_admin,
    mention, parse_time, fmt_time,
    MUTE_PERMS, FULL_PERMS, dot_filter,
    is_admin,
)
from config import LOG_CHANNEL


async def _log(context, text: str):
    if LOG_CHANNEL:
        try:
            await context.bot.send_message(LOG_CHANNEL, text, parse_mode="HTML")
        except Exception:
            pass


# ─── BAN ─────────────────────────────────────────────────────────────────────

async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): return
    if not await require_bot_admin(update, context): return
    uid, name, reason = await resolve_user(update, context)
    if not uid:
        return await update.effective_message.reply_text("Kimi banlayayim? Reply at veya @user/ID yaz.")
    try:
        await update.effective_chat.ban_member(uid)
        r = f" | Sebep: {html.escape(reason)}" if reason else ""
        await update.effective_message.reply_text(
            f"Banlandi: {mention(uid, name)}{r}", parse_mode="HTML"
        )
        await _log(context,
            f"🔨 BAN | {update.effective_chat.title}\n"
            f"Kullanici: {mention(uid, name)} ({uid})\n"
            f"Admin: {mention(update.effective_user.id, update.effective_user.first_name)}\n"
            f"Sebep: {reason or '-'}"
        )
    except BadRequest as e:
        await update.effective_message.reply_text(f"Banlanamadi: {e}")


async def dban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mesaji sil + Banla"""
    msg = update.effective_message
    if not await require_admin(update, context): return
    if not await require_bot_admin(update, context): return
    if msg.reply_to_message:
        try: await msg.reply_to_message.delete()
        except Exception: pass
    await ban_cmd(update, context)
    try: await msg.delete()
    except Exception: pass


async def sban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sessiz ban (mesaj yok)"""
    msg = update.effective_message
    if not await require_admin(update, context): return
    if not await require_bot_admin(update, context): return
    uid, name, reason = await resolve_user(update, context)
    if not uid: return
    try:
        await update.effective_chat.ban_member(uid)
        await msg.delete()
    except Exception: pass


# ─── UNBAN ────────────────────────────────────────────────────────────────────

async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): return
    if not await require_bot_admin(update, context): return
    uid, name, _ = await resolve_user(update, context)
    if not uid:
        return await update.effective_message.reply_text("Kimin banini kaldirayayim?")
    try:
        await update.effective_chat.unban_member(uid)
        await update.effective_message.reply_text(
            f"Ban kaldirildi: {mention(uid, name)}", parse_mode="HTML"
        )
    except BadRequest as e:
        await update.effective_message.reply_text(f"Kaldirilamadi: {e}")


# ─── KICK ─────────────────────────────────────────────────────────────────────

async def kick_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): return
    if not await require_bot_admin(update, context): return
    uid, name, reason = await resolve_user(update, context)
    if not uid:
        return await update.effective_message.reply_text("Kimi attayayim?")
    chat = update.effective_chat
    try:
        await chat.ban_member(uid)
        await chat.unban_member(uid)
        r = f" | Sebep: {html.escape(reason)}" if reason else ""
        await update.effective_message.reply_text(
            f"Atildi: {mention(uid, name)}{r}", parse_mode="HTML"
        )
    except BadRequest as e:
        await update.effective_message.reply_text(f"Atilamadi: {e}")


async def dkick_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mesaji sil + At"""
    msg = update.effective_message
    if not await require_admin(update, context): return
    if not await require_bot_admin(update, context): return
    if msg.reply_to_message:
        try: await msg.reply_to_message.delete()
        except Exception: pass
    await kick_cmd(update, context)
    try: await msg.delete()
    except Exception: pass


# ─── MUTE ─────────────────────────────────────────────────────────────────────

async def mute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): return
    if not await require_bot_admin(update, context): return
    uid, name, reason = await resolve_user(update, context)
    if not uid:
        return await update.effective_message.reply_text(
            "Kullanim: .mute @user [sure] [sebep]\nOrnek: .mute @user 1h spam")

    args = list(context.args or [])
    if not update.effective_message.reply_to_message and args:
        args = args[1:]

    until_date = None
    dur_text = ""
    if args:
        secs = parse_time(args[0])
        if secs:
            until_date = datetime.now(tz=timezone.utc).timestamp() + secs
            dur_text = f" ({fmt_time(secs)})"
            reason = " ".join(args[1:])

    try:
        await update.effective_chat.restrict_member(
            uid, MUTE_PERMS,
            until_date=datetime.fromtimestamp(until_date, tz=timezone.utc) if until_date else None,
        )
        r = f" | Sebep: {html.escape(reason)}" if reason else ""
        await update.effective_message.reply_text(
            f"Susturuldu{dur_text}: {mention(uid, name)}{r}", parse_mode="HTML"
        )
    except BadRequest as e:
        await update.effective_message.reply_text(f"Susturulamadi: {e}")


async def dmute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mesaji sil + Sustur"""
    msg = update.effective_message
    if not await require_admin(update, context): return
    if not await require_bot_admin(update, context): return
    if msg.reply_to_message:
        try: await msg.reply_to_message.delete()
        except Exception: pass
    await mute_cmd(update, context)
    try: await msg.delete()
    except Exception: pass


# ─── UNMUTE ───────────────────────────────────────────────────────────────────

async def unmute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): return
    if not await require_bot_admin(update, context): return
    uid, name, _ = await resolve_user(update, context)
    if not uid:
        return await update.effective_message.reply_text("Kimin susturmasini kaldirayayim?")
    try:
        await update.effective_chat.restrict_member(uid, FULL_PERMS)
        await update.effective_message.reply_text(
            f"Sus kaldirildi: {mention(uid, name)}", parse_mode="HTML"
        )
    except BadRequest as e:
        await update.effective_message.reply_text(f"Kaldirilamadi: {e}")


# ─── DWARN ────────────────────────────────────────────────────────────────────

async def dwarn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mesaji sil + Uyar"""
    msg = update.effective_message
    if not await require_admin(update, context): return
    if not await require_bot_admin(update, context): return
    if msg.reply_to_message:
        try: await msg.reply_to_message.delete()
        except Exception: pass
    # Import here to avoid circular
    from handlers.warnings import warn_cmd
    await warn_cmd(update, context)
    try: await msg.delete()
    except Exception: pass


# ─── PROMOTE / DEMOTE ─────────────────────────────────────────────────────────

async def promote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): return
    if not await require_bot_admin(update, context): return
    uid, name, _ = await resolve_user(update, context)
    if not uid:
        return await update.effective_message.reply_text("Kimi admin yapayim?")
    try:
        await update.effective_chat.promote_member(
            uid,
            can_delete_messages=True, can_restrict_members=True,
            can_pin_messages=True, can_invite_users=True,
            can_manage_chat=True,
        )
        await update.effective_message.reply_text(
            f"Admin yapildi: {mention(uid, name)}", parse_mode="HTML"
        )
    except BadRequest as e:
        await update.effective_message.reply_text(f"Admin yapilamadi: {e}")


async def demote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): return
    if not await require_bot_admin(update, context): return
    uid, name, _ = await resolve_user(update, context)
    if not uid:
        return await update.effective_message.reply_text("Kimin adminligini alayim?")
    try:
        await update.effective_chat.promote_member(
            uid,
            can_delete_messages=False, can_restrict_members=False,
            can_pin_messages=False, can_invite_users=False,
            can_manage_chat=False,
        )
        await update.effective_message.reply_text(
            f"Adminlik alindi: {mention(uid, name)}", parse_mode="HTML"
        )
    except BadRequest as e:
        await update.effective_message.reply_text(f"Kaldirilamadi: {e}")


# ─── PIN / UNPIN ─────────────────────────────────────────────────────────────

async def pin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await require_admin(update, context): return
    if not await require_bot_admin(update, context): return
    if not msg.reply_to_message:
        return await msg.reply_text("Hangi mesaji sabitleyeyim? Birine reply at.")
    try:
        await msg.reply_to_message.pin()
        await msg.reply_text("Mesaj sabitlendi.")
    except BadRequest as e:
        await msg.reply_text(f"Sabitlenemedi: {e}")


async def unpin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await require_admin(update, context): return
    if not await require_bot_admin(update, context): return
    try:
        if msg.reply_to_message:
            await context.bot.unpin_chat_message(
                update.effective_chat.id, msg.reply_to_message.message_id
            )
        else:
            await context.bot.unpin_chat_message(update.effective_chat.id)
        await msg.reply_text("Sabit mesaj kaldirildi.")
    except BadRequest as e:
        await msg.reply_text(f"Kaldirilamadi: {e}")


async def unpinall_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): return
    if not await require_bot_admin(update, context): return
    try:
        await context.bot.unpin_all_chat_messages(update.effective_chat.id)
        await update.effective_message.reply_text("Tum sabit mesajlar kaldirildi.")
    except BadRequest as e:
        await update.effective_message.reply_text(f"Kaldirilamadi: {e}")


# ─── DEL ──────────────────────────────────────────────────────────────────────

async def del_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await require_admin(update, context): return
    if not msg.reply_to_message:
        return await msg.reply_text("Hangi mesaji sileyim? Reply at.")
    try:
        await msg.reply_to_message.delete()
        await msg.delete()
    except BadRequest:
        pass


# ─── APPROVE / UNAPPROVE ─────────────────────────────────────────────────────

async def approve_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): return
    uid, name, _ = await resolve_user(update, context)
    if not uid:
        return await update.effective_message.reply_text("Kimi onayla?")
    from database import approve_user
    await approve_user(uid, update.effective_chat.id)
    await update.effective_message.reply_text(
        f"{mention(uid, name)} onaylandi. Filtreleri atlayabilir.", parse_mode="HTML"
    )


async def unapprove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): return
    uid, name, _ = await resolve_user(update, context)
    if not uid:
        return await update.effective_message.reply_text("Kim?")
    from database import unapprove_user
    await unapprove_user(uid, update.effective_chat.id)
    await update.effective_message.reply_text(
        f"{mention(uid, name)} onay kaldirildi.", parse_mode="HTML"
    )


# ─── REGISTER ─────────────────────────────────────────────────────────────────

def register_admin_handlers(app):
    cmds = [
        ("ban", ban_cmd), ("dban", dban_cmd), ("sban", sban_cmd),
        ("unban", unban_cmd),
        ("kick", kick_cmd), ("dkick", dkick_cmd),
        ("mute", mute_cmd), ("dmute", dmute_cmd),
        ("unmute", unmute_cmd),
        ("dwarn", dwarn_cmd),
        ("promote", promote_cmd), ("demote", demote_cmd),
        ("pin", pin_cmd), ("unpin", unpin_cmd), ("unpinall", unpinall_cmd),
        ("del", del_cmd),
        ("approve", approve_cmd), ("unapprove", unapprove_cmd),
    ]
    from telegram.ext import filters
    for cmd, handler in cmds:
        app.add_handler(CommandHandler(cmd, handler))
        app.add_handler(MessageHandler(filters.TEXT & dot_filter(cmd), handler))
