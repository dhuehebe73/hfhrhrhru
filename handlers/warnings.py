"""
Warning system: .warn .unwarn .resetwarns .warns
Auto-ban after WARN_LIMIT warnings.
"""
import html

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from telegram.error import BadRequest

from utils import resolve_user, is_admin, mention_html
from database import add_warning, remove_warning, reset_warnings, get_warnings
from config import WARN_LIMIT

import re as re_mod


def _dot_filter(cmd: str):
    return filters.Regex(rf"^[./!]{re_mod.escape(cmd)}(\s|$)")


async def warn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await is_admin(update, context):
        await msg.reply_text("Bu komutu kullanmak icin admin olmalisin.")
        return

    uid, name, reason = await resolve_user(update, context)
    if not uid:
        await msg.reply_text("Kimi uyarayayim?")
        return

    chat = update.effective_chat
    count = await add_warning(uid, chat.id, reason)
    reason_text = f"\nSebep: {html.escape(reason)}" if reason else ""

    if count >= WARN_LIMIT:
        try:
            await chat.ban_member(uid)
            await msg.reply_text(
                f"{mention_html(uid, name)} {count}. uyarisiyla banlandı! ({WARN_LIMIT}/{WARN_LIMIT}){reason_text}",
                parse_mode="HTML",
            )
            await reset_warnings(uid, chat.id)
        except BadRequest as e:
            await msg.reply_text(f"Banlanamadi: {e}")
    else:
        await msg.reply_text(
            f"{mention_html(uid, name)} uyarildi! ({count}/{WARN_LIMIT}){reason_text}",
            parse_mode="HTML",
        )


async def unwarn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await is_admin(update, context):
        await msg.reply_text("Bu komutu kullanmak icin admin olmalisin.")
        return

    uid, name, _ = await resolve_user(update, context)
    if not uid:
        await msg.reply_text("Kimin uyarisini kaldirayim?")
        return

    count = await remove_warning(uid, update.effective_chat.id)
    await msg.reply_text(
        f"{mention_html(uid, name)} icin 1 uyari kaldirildi. Kalan: {count}/{WARN_LIMIT}",
        parse_mode="HTML",
    )


async def resetwarns_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await is_admin(update, context):
        await msg.reply_text("Bu komutu kullanmak icin admin olmalisin.")
        return

    uid, name, _ = await resolve_user(update, context)
    if not uid:
        await msg.reply_text("Kimin uyarilari sifirlansin?")
        return

    await reset_warnings(uid, update.effective_chat.id)
    await msg.reply_text(
        f"{mention_html(uid, name)} icin tum uyarilar sifirlandi.",
        parse_mode="HTML",
    )


async def warns_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    uid, name, _ = await resolve_user(update, context)

    if not uid:
        # Check own warnings
        uid = update.effective_user.id
        name = update.effective_user.first_name

    count, reasons = await get_warnings(uid, update.effective_chat.id)

    if count == 0:
        await msg.reply_text(
            f"{mention_html(uid, name)} hic uyarilmamis.", parse_mode="HTML"
        )
        return

    reasons_text = ""
    if reasons:
        reasons_text = "\n" + "\n".join(
            f"  {i + 1}. {html.escape(r) if r else 'Sebep belirtilmedi'}"
            for i, r in enumerate(reasons)
        )

    await msg.reply_text(
        f"{mention_html(uid, name)} uyari durumu: {count}/{WARN_LIMIT}{reasons_text}",
        parse_mode="HTML",
    )


def register_warning_handlers(app):
    for cmd, handler in [
        ("warn", warn_cmd),
        ("unwarn", unwarn_cmd),
        ("resetwarns", resetwarns_cmd),
        ("warns", warns_cmd),
    ]:
        app.add_handler(CommandHandler(cmd, handler))
        app.add_handler(
            MessageHandler(filters.TEXT & _dot_filter(cmd), handler)
        )
