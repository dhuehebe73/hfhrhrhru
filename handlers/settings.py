from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler
from telegram.error import BadRequest
from database import get_settings, set_setting
from utils import require_admin, dcmd

_TOGGLES = [
    ("anti_flood",       "Anti-Flood"),
    ("link_filter",      "Link Filter"),
    ("sticker_filter",   "Sticker Filter"),
    ("media_filter",     "Media Filter"),
    ("bot_filter",       "Bot Filter"),
    ("auto_ban_leavers", "Auto-ban on leave"),
]


def _settings_kb(s: dict) -> InlineKeyboardMarkup:
    rows = []
    for key, label in _TOGGLES:
        state = "✅" if s.get(key) else "❌"
        rows.append([InlineKeyboardButton(
            f"{state} {label}", callback_data=f"stg_toggle|{key}")])
    rows.append([InlineKeyboardButton("🔄 Refresh", callback_data="stg_refresh"),
                 InlineKeyboardButton("❌ Close",   callback_data="stg_close")])
    return InlineKeyboardMarkup(rows)


def _settings_text(s: dict) -> str:
    lines = ["⚙️ <b>Group Settings</b>\n"]
    for key, label in _TOGGLES:
        icon = "✅" if s.get(key) else "❌"
        lines.append(f"{icon} {label}")
    lines.append(f"\n⚡ Flood limit: {s.get('flood_limit', 5)}")
    lines.append(f"⚠️ Warn limit: {s.get('warn_limit', 3)} → {s.get('warn_action', 'ban')}")
    return "\n".join(lines)


async def settings_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    s = await get_settings(update.effective_chat.id)
    await update.effective_message.reply_text(
        _settings_text(s), parse_mode="HTML", reply_markup=_settings_kb(s))


async def settings_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data = query.data

    if data == "stg_close":
        try: await query.message.delete()
        except Exception: pass
        return

    if data == "stg_refresh":
        s = await get_settings(chat_id)
        try:
            await query.edit_message_text(_settings_text(s), parse_mode="HTML",
                                          reply_markup=_settings_kb(s))
        except BadRequest as e:
            if "not modified" not in str(e).lower(): raise
        return

    if data.startswith("stg_toggle|"):
        key = data.split("|", 1)[1]
        from utils import is_admin
        if not await is_admin(update, ctx):
            await query.answer("❌ You must be an admin.", show_alert=True); return
        s = await get_settings(chat_id)
        new_val = 0 if s.get(key) else 1
        await set_setting(chat_id, key, new_val)
        s = await get_settings(chat_id)
        try:
            await query.edit_message_text(_settings_text(s), parse_mode="HTML",
                                          reply_markup=_settings_kb(s))
        except BadRequest as e:
            if "not modified" not in str(e).lower(): raise


def register(app):
    app.add_handler(MessageHandler(dcmd("settings"), settings_cmd), group=10)
    app.add_handler(CallbackQueryHandler(settings_callback, pattern=r"^stg_"), group=10)
