from telegram import Update
from telegram.ext import ContextTypes, MessageHandler
from database import get_settings, set_setting
from utils import require_admin, dcmd, get_args


async def warnlimit_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    args = get_args(update, ctx)
    if not args or not args[0].isdigit():
        s = await get_settings(update.effective_chat.id)
        await update.effective_message.reply_text(
            f"⚠️ Mevcut uyarı limiti: {s.get('warn_limit',3)}\n"
            "Değiştirmek için: /warnlimit <sayı>"); return
    n = max(1, min(int(args[0]), 20))
    await set_setting(update.effective_chat.id, "warn_limit", n)
    await update.effective_message.reply_text(f"✅ Uyarı limiti {n} olarak ayarlandı.")

async def warnmode_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    args = get_args(update, ctx)
    valid = ("ban", "kick", "mute")
    if not args or args[0].lower() not in valid:
        s = await get_settings(update.effective_chat.id)
        await update.effective_message.reply_text(
            f"⚠️ Mevcut uyarı aksiyonu: {s.get('warn_action','ban')}\n"
            f"Değiştirmek için: /warnmode <{'|'.join(valid)}>"); return
    mode = args[0].lower()
    await set_setting(update.effective_chat.id, "warn_action", mode)
    await update.effective_message.reply_text(f"✅ Uyarı aksiyonu: {mode}")


def register(app):
    for cmd, h in [("warnlimit", warnlimit_cmd), ("warnmode", warnmode_cmd)]:
        app.add_handler(MessageHandler(dcmd(cmd), h), group=10)
