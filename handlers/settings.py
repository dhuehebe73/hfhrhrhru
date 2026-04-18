from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler
from database import get_settings, set_setting
from utils import require_admin, dcmd

_TOGGLES = [
    ("anti_flood",       "Anti-Flood"),
    ("link_filter",      "Link Filtresi"),
    ("sticker_filter",   "Sticker Filtresi"),
    ("media_filter",     "Medya Filtresi"),
    ("bot_filter",       "Bot Filtresi"),
    ("auto_ban_leavers", "Çıkan = Ban"),
]


def _settings_kb(s: dict) -> InlineKeyboardMarkup:
    rows = []
    for key, label in _TOGGLES:
        state = "✅" if s.get(key) else "❌"
        rows.append([InlineKeyboardButton(
            f"{state} {label}", callback_data=f"stg_toggle|{key}")])
    rows.append([InlineKeyboardButton("🔄 Yenile", callback_data="stg_refresh"),
                 InlineKeyboardButton("❌ Kapat",  callback_data="stg_close")])
    return InlineKeyboardMarkup(rows)


def _settings_text(s: dict) -> str:
    lines = ["⚙️ <b>Grup Ayarları</b>\n"]
    for key, label in _TOGGLES:
        icon = "✅" if s.get(key) else "❌"
        lines.append(f"{icon} {label}")
    flood_limit = s.get("flood_limit", 5)
    warn_limit  = s.get("warn_limit", 3)
    warn_action = s.get("warn_action", "ban")
    lines.append(f"\n⚡ Flood limiti: {flood_limit}")
    lines.append(f"⚠️ Uyarı limiti: {warn_limit} → {warn_action}")
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
        await query.edit_message_text(_settings_text(s), parse_mode="HTML",
                                      reply_markup=_settings_kb(s))
        return

    if data.startswith("stg_toggle|"):
        key = data.split("|", 1)[1]
        from utils import is_admin
        if not await is_admin(update, ctx):
            await query.answer("❌ Admin değilsin.", show_alert=True); return
        s = await get_settings(chat_id)
        new_val = 0 if s.get(key) else 1
        await set_setting(chat_id, key, new_val)
        s = await get_settings(chat_id)
        await query.edit_message_text(_settings_text(s), parse_mode="HTML",
                                      reply_markup=_settings_kb(s))


def register(app):
    app.add_handler(MessageHandler(dcmd("settings"), settings_cmd), group=10)
    app.add_handler(CallbackQueryHandler(settings_callback, pattern=r"^stg_"), group=10)
