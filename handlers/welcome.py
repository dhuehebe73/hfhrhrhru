"""
Welcome / goodbye messages + auto-ban leavers.
Commands: .setwelcome .setgoodbye .welcome .autoban
"""
import html

from telegram import Update, ChatMemberUpdated
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    filters,
)
from telegram.constants import ChatMemberStatus

from utils import is_admin, mention_html
from database import (
    get_welcome,
    set_welcome,
    set_goodbye,
    mark_left,
    has_left_before,
    clear_left,
    get_chat_settings,
    update_chat_setting,
)

import re as re_mod


def _dot_filter(cmd: str):
    return filters.Regex(rf"^[./!]{re_mod.escape(cmd)}(\s|$)")


# ─── Welcome/goodbye config commands ─────────────────────────────────────────

async def setwelcome_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await is_admin(update, context):
        await msg.reply_text("Bu komutu kullanmak icin admin olmalisin.")
        return

    text = " ".join(context.args) if context.args else ""
    if not text:
        await msg.reply_text(
            "Karsilama mesajini yaz. Kullanilabilir degiskenler:\n"
            "  {name} - kullanici adi\n"
            "  {chat} - grup adi\n"
            "  {count} - uye sayisi\n\n"
            "Ornek: .setwelcome Hos geldin {name}!"
        )
        return

    await set_welcome(update.effective_chat.id, text)
    await msg.reply_text("Karsilama mesaji ayarlandi!")


async def setgoodbye_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await is_admin(update, context):
        await msg.reply_text("Bu komutu kullanmak icin admin olmalisin.")
        return

    text = " ".join(context.args) if context.args else ""
    if not text:
        await msg.reply_text(
            "Veda mesajini yaz. Kullanilabilir degiskenler:\n"
            "  {name} - kullanici adi\n"
            "  {chat} - grup adi\n\n"
            "Ornek: .setgoodbye Gule gule {name}!"
        )
        return

    await set_goodbye(update.effective_chat.id, text)
    await msg.reply_text("Veda mesaji ayarlandi!")


async def welcome_preview_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    welcome_text, goodbye_text, enabled = await get_welcome(update.effective_chat.id)

    user = update.effective_user
    chat = update.effective_chat

    preview = (welcome_text or "Henuz karsilama mesaji ayarlanmamis.").format(
        name=html.escape(user.first_name),
        chat=html.escape(chat.title or ""),
        count="?",
    )
    await msg.reply_text(
        f"Karsilama on izleme:\n\n{preview}", parse_mode="HTML"
    )


async def autoban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle auto-ban for members who leave."""
    msg = update.effective_message
    if not await is_admin(update, context):
        await msg.reply_text("Bu komutu kullanmak icin admin olmalisin.")
        return

    args = context.args
    chat_id = update.effective_chat.id
    settings = await get_chat_settings(chat_id)

    if args and args[0].lower() in ("on", "ac", "aktif", "1"):
        await update_chat_setting(chat_id, "auto_ban_leavers", 1)
        await msg.reply_text("Oto-ban aktif! Gruptan ayrilanlar banlanacak.")
    elif args and args[0].lower() in ("off", "kapat", "pasif", "0"):
        await update_chat_setting(chat_id, "auto_ban_leavers", 0)
        await msg.reply_text("Oto-ban kapatildi.")
    else:
        current = "ACIK" if settings["auto_ban_leavers"] else "KAPALI"
        await msg.reply_text(
            f"Oto-ban su anda: {current}\n"
            "Degistirmek icin: .autoban on / .autoban off"
        )


# ─── Chat member update handler ───────────────────────────────────────────────

def _extract_status_change(update: ChatMemberUpdated):
    old = update.old_chat_member.status
    new = update.new_chat_member.status
    return old, new


async def chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if not result:
        return

    chat = result.chat
    user = result.new_chat_member.user
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status

    # Member JOINED
    if new_status == ChatMemberStatus.MEMBER and old_status in (
        ChatMemberStatus.LEFT,
        ChatMemberStatus.BANNED,
    ):
        settings = await get_chat_settings(chat.id)

        # Auto-ban if they previously left voluntarily
        if settings["auto_ban_leavers"] and await has_left_before(user.id, chat.id):
            try:
                await context.bot.ban_chat_member(chat.id, user.id)
                await context.bot.send_message(
                    chat.id,
                    f"{mention_html(user.id, user.first_name)} daha once gruptan ayrilmisti, otomatik banlandı.",
                    parse_mode="HTML",
                )
                await clear_left(user.id, chat.id)
                return
            except Exception:
                pass

        # Welcome message
        welcome_text, _, enabled = await get_welcome(chat.id)
        if enabled:
            try:
                member_count = await context.bot.get_chat_member_count(chat.id)
            except Exception:
                member_count = "?"

            text = (welcome_text or "Hos geldin, {name}!").format(
                name=html.escape(user.first_name),
                chat=html.escape(chat.title or ""),
                count=member_count,
            )
            try:
                await context.bot.send_message(chat.id, text, parse_mode="HTML")
            except Exception:
                pass

    # Member LEFT voluntarily
    elif new_status == ChatMemberStatus.LEFT and old_status == ChatMemberStatus.MEMBER:
        settings = await get_chat_settings(chat.id)

        if settings["auto_ban_leavers"]:
            # Ban them immediately
            try:
                await context.bot.ban_chat_member(chat.id, user.id)
                await context.bot.send_message(
                    chat.id,
                    f"{mention_html(user.id, user.first_name)} gruptan ayrildi ve otomatik banlandı.",
                    parse_mode="HTML",
                )
                return
            except Exception:
                pass
        else:
            # Just mark them as having left (for future rejoin detection)
            await mark_left(user.id, chat.id)

        # Goodbye message
        _, goodbye_text, enabled = await get_welcome(chat.id)
        if enabled and goodbye_text:
            text = goodbye_text.format(
                name=html.escape(user.first_name),
                chat=html.escape(chat.title or ""),
                count="?",
            )
            try:
                await context.bot.send_message(chat.id, text, parse_mode="HTML")
            except Exception:
                pass


def register_welcome_handlers(app):
    for cmd, handler in [
        ("setwelcome", setwelcome_cmd),
        ("setgoodbye", setgoodbye_cmd),
        ("welcome", welcome_preview_cmd),
        ("autoban", autoban_cmd),
    ]:
        app.add_handler(CommandHandler(cmd, handler))
        app.add_handler(
            MessageHandler(filters.TEXT & _dot_filter(cmd), handler)
        )

    app.add_handler(ChatMemberHandler(chat_member_update, ChatMemberHandler.CHAT_MEMBER))
