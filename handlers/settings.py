"""
Settings panel with inline keyboard toggles (Rose-style).
/settings — open panel
Callback: set_toggle_<key>
"""
import html

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from utils import require_admin, dot_filter
from database import get_chat_settings, update_chat_setting


def _settings_kb(s: dict) -> InlineKeyboardMarkup:
    def btn(icon_on, icon_off, label, key):
        icon = icon_on if s.get(key) else icon_off
        return InlineKeyboardButton(
            f"{icon} {label}", callback_data=f"set_toggle_{key}"
        )

    return InlineKeyboardMarkup([
        [
            btn("✅", "❌", "Anti-Flood",  "anti_flood"),
            btn("✅", "❌", "Link Filtre", "link_filter"),
        ],
        [
            btn("✅", "❌", "Sticker Filtre", "sticker_filter"),
            btn("✅", "❌", "Medya Filtre",   "media_filter"),
        ],
        [
            btn("✅", "❌", "Bot Filtre",  "bot_filter"),
            btn("✅", "❌", "Oto-Ban",     "auto_ban_leavers"),
        ],
        [
            InlineKeyboardButton("🔒 Kilitle",  callback_data="set_lock_1"),
            InlineKeyboardButton("🔓 Ac",        callback_data="set_lock_0"),
        ],
        [InlineKeyboardButton("❌ Kapat", callback_data="set_close")],
    ])


def _settings_text(s: dict, title: str) -> str:
    def st(val): return "✅ Acik" if val else "❌ Kapali"
    return (
        f"⚙️ <b>{html.escape(title)} — Ayarlar</b>\n\n"
        f"Anti-Flood:    {st(s['anti_flood'])}\n"
        f"Link Filtre:   {st(s['link_filter'])}\n"
        f"Sticker Filtre:{st(s['sticker_filter'])}\n"
        f"Medya Filtre:  {st(s['media_filter'])}\n"
        f"Bot Filtre:    {st(s['bot_filter'])}\n"
        f"Oto-Ban:       {st(s['auto_ban_leavers'])}\n"
        f"Kilitli:       {st(s['locked'])}\n\n"
        f"Flood Limiti:  {s['flood_limit']} mesaj/5sn\n"
        f"Uyari Limiti:  {s['warn_limit']} uyari\n"
        f"Uyari Aksiyonu:{s['warn_action']}"
    )


async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg  = update.effective_message
    chat = update.effective_chat

    if chat.type == "private":
        return await msg.reply_text(
            "Bu komutu grupta kullan.",
        )
    if not await require_admin(update, context):
        return

    s    = await get_chat_settings(chat.id)
    text = _settings_text(s, chat.title or "Grup")
    kb   = _settings_kb(s)
    await msg.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data
    chat = update.effective_chat
    user = update.effective_user

    await q.answer()

    # Permission check
    try:
        member = await chat.get_member(user.id)
        from telegram.constants import ChatMemberStatus
        from config import OWNER_ID
        is_adm = member.status in (
            ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER
        ) or user.id == OWNER_ID
    except Exception:
        is_adm = False

    if not is_adm:
        return await q.answer("Sadece adminler degistirebilir!", show_alert=True)

    if data == "set_close":
        try:
            await q.message.delete()
        except Exception:
            pass
        return

    _BOOL_KEYS = {
        "anti_flood", "link_filter", "sticker_filter",
        "media_filter", "bot_filter", "auto_ban_leavers",
    }

    if data.startswith("set_toggle_"):
        key = data[len("set_toggle_"):]
        if key not in _BOOL_KEYS:
            return
        s = await get_chat_settings(chat.id)
        new_val = not s[key]
        await update_chat_setting(chat.id, key, int(new_val))

    elif data == "set_lock_1":
        from utils import LOCKED_PERMS
        try:
            await chat.set_permissions(LOCKED_PERMS)
            await update_chat_setting(chat.id, "locked", 1)
        except Exception:
            pass

    elif data == "set_lock_0":
        from utils import FULL_PERMS
        try:
            await chat.set_permissions(FULL_PERMS)
            await update_chat_setting(chat.id, "locked", 0)
        except Exception:
            pass

    # Refresh panel
    s    = await get_chat_settings(chat.id)
    text = _settings_text(s, chat.title or "Grup")
    kb   = _settings_kb(s)
    try:
        await q.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass


def register_settings_handlers(app):
    app.add_handler(CommandHandler("settings", settings_cmd))
    app.add_handler(CommandHandler("ayarlar",  settings_cmd))
    app.add_handler(MessageHandler(filters.TEXT & dot_filter("settings"), settings_cmd))
    app.add_handler(MessageHandler(filters.TEXT & dot_filter("ayarlar"),  settings_cmd))
    app.add_handler(CallbackQueryHandler(settings_callback, pattern=r"^set_"))
