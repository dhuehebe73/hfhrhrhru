"""
Admin commands: .ban .unban .kick .mute .unmute .promote .demote .pin .unpin
Supports both / and . prefix.
"""
import html
from datetime import datetime, timezone

from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from telegram.constants import ChatMemberStatus
from telegram.error import BadRequest

from utils import (
    resolve_user,
    is_admin,
    bot_is_admin,
    mention_html,
    parse_time,
    format_duration,
    MUTE_PERMISSIONS,
    FULL_PERMISSIONS,
)
from config import OWNER_ID, LOG_CHANNEL


# ─── Helpers ─────────────────────────────────────────────────────────────────

async def _log(context, text: str):
    if LOG_CHANNEL:
        try:
            await context.bot.send_message(LOG_CHANNEL, text, parse_mode="HTML")
        except Exception:
            pass


async def _check_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not await is_admin(update, context):
        await update.effective_message.reply_text("Bu komutu kullanmak icin admin olmalisin.")
        return False
    return True


async def _check_bot_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not await bot_is_admin(update, context):
        await update.effective_message.reply_text("Benim admin olmam gerekiyor!")
        return False
    return True


def _parse_dot_args(text: str, cmd: str) -> list[str]:
    """Extract args from '.ban user reason' style messages."""
    pattern = rf"^[./!]{re.escape(cmd)}\s*"
    import re
    stripped = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()
    return stripped.split() if stripped else []


# ─── BAN ─────────────────────────────────────────────────────────────────────

async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await _check_admin(update, context):
        return
    if not await _check_bot_admin(update, context):
        return

    uid, name, reason = await resolve_user(update, context)
    if not uid:
        await msg.reply_text("Kimi banlayayim? Birine reply at ya da ID/kullanici adi ver.")
        return

    chat = update.effective_chat
    try:
        await chat.ban_member(uid)
        reason_text = f" | Sebep: {html.escape(reason)}" if reason else ""
        await msg.reply_text(
            f"Banlandi: {mention_html(uid, name)}{reason_text}",
            parse_mode="HTML",
        )
        await _log(
            context,
            f"BAN | Chat: {chat.title} ({chat.id})\n"
            f"Kullanici: {mention_html(uid, name)} ({uid})\n"
            f"Admin: {mention_html(update.effective_user.id, update.effective_user.first_name)}\n"
            f"Sebep: {reason or 'Belirtilmedi'}",
        )
    except BadRequest as e:
        await msg.reply_text(f"Banlanamadi: {e}")


# ─── UNBAN ────────────────────────────────────────────────────────────────────

async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await _check_admin(update, context):
        return
    if not await _check_bot_admin(update, context):
        return

    uid, name, _ = await resolve_user(update, context)
    if not uid:
        await msg.reply_text("Kimin banini kaldirayayim?")
        return

    try:
        await update.effective_chat.unban_member(uid)
        await msg.reply_text(
            f"Bani kaldirildi: {mention_html(uid, name)}", parse_mode="HTML"
        )
    except BadRequest as e:
        await msg.reply_text(f"Ban kaldirilmadi: {e}")


# ─── KICK ─────────────────────────────────────────────────────────────────────

async def kick_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await _check_admin(update, context):
        return
    if not await _check_bot_admin(update, context):
        return

    uid, name, reason = await resolve_user(update, context)
    if not uid:
        await msg.reply_text("Kimi attayayim?")
        return

    chat = update.effective_chat
    try:
        await chat.ban_member(uid)
        await chat.unban_member(uid)  # kick = ban + unban
        reason_text = f" | Sebep: {html.escape(reason)}" if reason else ""
        await msg.reply_text(
            f"Gruptan atildi: {mention_html(uid, name)}{reason_text}",
            parse_mode="HTML",
        )
    except BadRequest as e:
        await msg.reply_text(f"Atilamadi: {e}")


# ─── MUTE ─────────────────────────────────────────────────────────────────────

async def mute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await _check_admin(update, context):
        return
    if not await _check_bot_admin(update, context):
        return

    uid, name, reason = await resolve_user(update, context)
    if not uid:
        await msg.reply_text("Kimi susturayim?")
        return

    # Check if first arg after user is a time
    until_date = None
    duration_text = ""
    args = context.args or []
    if not msg.reply_to_message and args:
        args = args[1:]  # skip username/id
    if args:
        secs = parse_time(args[0])
        if secs:
            until_date = datetime.now(tz=timezone.utc).timestamp() + secs
            duration_text = f" ({format_duration(secs)})"
            reason = " ".join(args[1:])

    try:
        await update.effective_chat.restrict_member(
            uid,
            MUTE_PERMISSIONS,
            until_date=datetime.fromtimestamp(until_date, tz=timezone.utc) if until_date else None,
        )
        reason_text = f" | Sebep: {html.escape(reason)}" if reason else ""
        await msg.reply_text(
            f"Susturuldu{duration_text}: {mention_html(uid, name)}{reason_text}",
            parse_mode="HTML",
        )
    except BadRequest as e:
        await msg.reply_text(f"Susturulamadi: {e}")


# ─── UNMUTE ───────────────────────────────────────────────────────────────────

async def unmute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await _check_admin(update, context):
        return
    if not await _check_bot_admin(update, context):
        return

    uid, name, _ = await resolve_user(update, context)
    if not uid:
        await msg.reply_text("Kimin sustugunu kaldirayayim?")
        return

    try:
        await update.effective_chat.restrict_member(uid, FULL_PERMISSIONS)
        await msg.reply_text(
            f"Sus kaldirildi: {mention_html(uid, name)}", parse_mode="HTML"
        )
    except BadRequest as e:
        await msg.reply_text(f"Sus kaldirilmadi: {e}")


# ─── PROMOTE ──────────────────────────────────────────────────────────────────

async def promote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await _check_admin(update, context):
        return
    if not await _check_bot_admin(update, context):
        return

    uid, name, _ = await resolve_user(update, context)
    if not uid:
        await msg.reply_text("Kimi admin yapayim?")
        return

    try:
        await update.effective_chat.promote_member(
            uid,
            can_delete_messages=True,
            can_restrict_members=True,
            can_pin_messages=True,
            can_invite_users=True,
        )
        await msg.reply_text(
            f"Admin yapildi: {mention_html(uid, name)}", parse_mode="HTML"
        )
    except BadRequest as e:
        await msg.reply_text(f"Admin yapilamadi: {e}")


# ─── DEMOTE ───────────────────────────────────────────────────────────────────

async def demote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await _check_admin(update, context):
        return
    if not await _check_bot_admin(update, context):
        return

    uid, name, _ = await resolve_user(update, context)
    if not uid:
        await msg.reply_text("Kimin adminligini alayim?")
        return

    try:
        await update.effective_chat.promote_member(
            uid,
            can_delete_messages=False,
            can_restrict_members=False,
            can_pin_messages=False,
            can_invite_users=False,
            can_manage_chat=False,
        )
        await msg.reply_text(
            f"Adminlik alindi: {mention_html(uid, name)}", parse_mode="HTML"
        )
    except BadRequest as e:
        await msg.reply_text(f"Adminlik alinamadi: {e}")


# ─── PIN ──────────────────────────────────────────────────────────────────────

async def pin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await _check_admin(update, context):
        return
    if not await _check_bot_admin(update, context):
        return

    if not msg.reply_to_message:
        await msg.reply_text("Hangi mesaji sabitleyeyim? Birine reply at.")
        return

    try:
        await msg.reply_to_message.pin()
        await msg.reply_text("Mesaj sabitlendi.")
    except BadRequest as e:
        await msg.reply_text(f"Sabitlenemedi: {e}")


# ─── UNPIN ────────────────────────────────────────────────────────────────────

async def unpin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await _check_admin(update, context):
        return
    if not await _check_bot_admin(update, context):
        return

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


# ─── DEL ──────────────────────────────────────────────────────────────────────

async def del_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await _check_admin(update, context):
        return

    if not msg.reply_to_message:
        await msg.reply_text("Hangi mesaji sileyim? Birine reply at.")
        return

    try:
        await msg.reply_to_message.delete()
        await msg.delete()
    except BadRequest:
        pass


# ─── Registration ─────────────────────────────────────────────────────────────

import re as re_mod

_DOT_CMD = re_mod.compile(r"^[./!](\w+)", re_mod.IGNORECASE)


def _dot_filter(cmd: str):
    return filters.Regex(rf"^[./!]{re_mod.escape(cmd)}(\s|$)")


def register_admin_handlers(app):
    for cmd, handler in [
        ("ban", ban_cmd),
        ("unban", unban_cmd),
        ("kick", kick_cmd),
        ("mute", mute_cmd),
        ("unmute", unmute_cmd),
        ("promote", promote_cmd),
        ("demote", demote_cmd),
        ("pin", pin_cmd),
        ("unpin", unpin_cmd),
        ("del", del_cmd),
    ]:
        app.add_handler(CommandHandler(cmd, handler))
        app.add_handler(
            MessageHandler(filters.TEXT & _dot_filter(cmd), handler)
        )
