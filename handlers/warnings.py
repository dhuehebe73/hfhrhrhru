"""
Warn system: warn dwarn unwarn resetwarns warns
Auto-action (ban/kick/mute) when limit is reached.
"""
import html
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler
from telegram.constants import ChatMemberStatus
from telegram.error import BadRequest

from utils import resolve_user, require_admin, require_bot_admin, mention, MUTE_PERMS, dot_filter
from database import (
    add_warning, remove_warning, reset_warnings,
    get_warnings, get_chat_settings,
)


async def _do_warn(update: Update, context: ContextTypes.DEFAULT_TYPE,
                   uid: int, name: str, reason: str) -> str:
    """Core warn logic. Returns result string."""
    chat = update.effective_chat
    settings = await get_chat_settings(chat.id)
    limit  = settings["warn_limit"]
    action = settings["warn_action"]

    count = await add_warning(uid, chat.id, reason)
    r = f"\nSebep: {html.escape(reason)}" if reason else ""

    if count >= limit:
        await reset_warnings(uid, chat.id)
        if action == "ban":
            try:
                await chat.ban_member(uid)
                return (f"{mention(uid, name)} {limit}. uyarisiyla <b>BANLANDI!</b>"
                        f" ({count}/{limit}){r}")
            except BadRequest as e:
                return f"Uyarildi ama banlanamadi: {e}"
        elif action == "kick":
            try:
                await chat.ban_member(uid)
                await chat.unban_member(uid)
                return (f"{mention(uid, name)} {limit}. uyarisiyla <b>ATILDI!</b>"
                        f" ({count}/{limit}){r}")
            except BadRequest as e:
                return f"Uyarildi ama atilamadi: {e}"
        elif action == "mute":
            try:
                await chat.restrict_member(uid, MUTE_PERMS)
                return (f"{mention(uid, name)} {limit}. uyarisiyla <b>SUSTURULDU!</b>"
                        f" ({count}/{limit}){r}")
            except BadRequest as e:
                return f"Uyarildi ama susturulamadi: {e}"

    return f"{mention(uid, name)} uyarildi ({count}/{limit}){r}"


async def warn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): return
    if not await require_bot_admin(update, context): return
    uid, name, reason = await resolve_user(update, context)
    if not uid:
        return await update.effective_message.reply_text(
            "Kimi uyarayayim? Reply at ya da @user/ID yaz."
        )
    result = await _do_warn(update, context, uid, name, reason)
    await update.effective_message.reply_text(result, parse_mode="HTML")


async def unwarn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): return
    uid, name, _ = await resolve_user(update, context)
    if not uid:
        return await update.effective_message.reply_text("Kimin uyarisini kaldirayim?")
    settings = await get_chat_settings(update.effective_chat.id)
    count = await remove_warning(uid, update.effective_chat.id)
    await update.effective_message.reply_text(
        f"{mention(uid, name)} icin 1 uyari kaldirildi. Kalan: {count}/{settings['warn_limit']}",
        parse_mode="HTML",
    )


async def resetwarns_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): return
    uid, name, _ = await resolve_user(update, context)
    if not uid:
        return await update.effective_message.reply_text("Kim?")
    await reset_warnings(uid, update.effective_chat.id)
    await update.effective_message.reply_text(
        f"{mention(uid, name)} icin tum uyarilar sifirlandi.", parse_mode="HTML"
    )


async def warns_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name, _ = await resolve_user(update, context)
    if not uid:
        uid  = update.effective_user.id
        name = update.effective_user.first_name

    settings = await get_chat_settings(update.effective_chat.id)
    count, reasons = await get_warnings(uid, update.effective_chat.id)

    if count == 0:
        return await update.effective_message.reply_text(
            f"{mention(uid, name)} hic uyarilmamis.", parse_mode="HTML"
        )

    reasons_text = ""
    if reasons:
        reasons_text = "\n" + "\n".join(
            f"  {i+1}. {html.escape(r) if r else '(sebep yok)'}"
            for i, r in enumerate(reasons)
        )
    await update.effective_message.reply_text(
        f"{mention(uid, name)}: {count}/{settings['warn_limit']} uyari{reasons_text}",
        parse_mode="HTML",
    )


async def warnmode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set warn action: ban/kick/mute"""
    if not await require_admin(update, context): return
    args = context.args
    if not args or args[0].lower() not in ("ban", "kick", "mute"):
        settings = await get_chat_settings(update.effective_chat.id)
        return await update.effective_message.reply_text(
            f"Mevcut mod: {settings['warn_action']}\n"
            "Degistir: .warnmode ban | .warnmode kick | .warnmode mute"
        )
    from database import update_chat_setting
    await update_chat_setting(update.effective_chat.id, "warn_action", args[0].lower())
    await update.effective_message.reply_text(f"Uyari modu: {args[0].lower()}")


async def warnlimit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set warn limit"""
    if not await require_admin(update, context): return
    args = context.args
    if not args or not args[0].isdigit():
        settings = await get_chat_settings(update.effective_chat.id)
        return await update.effective_message.reply_text(
            f"Mevcut limit: {settings['warn_limit']}\n"
            "Degistir: .warnlimit 3"
        )
    limit = max(1, min(int(args[0]), 10))
    from database import update_chat_setting
    await update_chat_setting(update.effective_chat.id, "warn_limit", limit)
    await update.effective_message.reply_text(f"Uyari limiti: {limit}")


def register_warning_handlers(app):
    from telegram.ext import filters
    cmds = [
        ("warn", warn_cmd), ("unwarn", unwarn_cmd),
        ("resetwarns", resetwarns_cmd), ("warns", warns_cmd),
        ("warnmode", warnmode_cmd), ("warnlimit", warnlimit_cmd),
    ]
    for cmd, handler in cmds:
        app.add_handler(CommandHandler(cmd, handler))
        app.add_handler(MessageHandler(filters.TEXT & dot_filter(cmd), handler))
