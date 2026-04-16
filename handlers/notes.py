"""
Notes system: save get notes clear
Also handles #notename shortcut in messages.
"""
import re

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters

from utils import require_admin, dot_filter
from database import get_note, save_note, delete_note, list_notes


async def _send_note(update: Update, context: ContextTypes.DEFAULT_TYPE, name: str):
    chat_id = update.effective_chat.id
    note = await get_note(chat_id, name.lower())
    if not note:
        return await update.effective_message.reply_text(
            f"Not bulunamadi: <code>{name}</code>", parse_mode="HTML"
        )

    content = note["content"]
    file_id = note["file_id"]
    ftype   = note["file_type"]

    if ftype == "photo":
        await update.effective_message.reply_photo(file_id, caption=content or None)
    elif ftype == "video":
        await update.effective_message.reply_video(file_id, caption=content or None)
    elif ftype == "document":
        await update.effective_message.reply_document(file_id, caption=content or None)
    elif ftype == "audio":
        await update.effective_message.reply_audio(file_id, caption=content or None)
    elif ftype == "sticker":
        await update.effective_message.reply_sticker(file_id)
    else:
        if content:
            await update.effective_message.reply_text(content, parse_mode="HTML")
        else:
            await update.effective_message.reply_text("(Bu not bos.)")


async def save_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await require_admin(update, context): return

    args = context.args
    if not args:
        return await msg.reply_text(
            "Kullanim:\n"
            "  .save <isim> <icerik>\n"
            "  .save <isim> (medyaya reply at)"
        )

    name = args[0].lower()
    content = " ".join(args[1:])
    file_id = ""
    file_type = ""

    if msg.reply_to_message:
        r = msg.reply_to_message
        if not content:
            content = r.text or r.caption or ""
        if r.photo:
            file_id   = r.photo[-1].file_id
            file_type = "photo"
        elif r.video:
            file_id   = r.video.file_id
            file_type = "video"
        elif r.document:
            file_id   = r.document.file_id
            file_type = "document"
        elif r.audio:
            file_id   = r.audio.file_id
            file_type = "audio"
        elif r.sticker:
            file_id   = r.sticker.file_id
            file_type = "sticker"

    await save_note(update.effective_chat.id, name, content, file_id, file_type)
    await msg.reply_text(f"Not kaydedildi: <code>{name}</code>", parse_mode="HTML")


async def get_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.effective_message.reply_text("Hangi notu getireyim? .get <isim>")
    await _send_note(update, context, context.args[0])


async def notes_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    names = await list_notes(update.effective_chat.id)
    if not names:
        return await update.effective_message.reply_text("Kayitli not yok.")
    text = "<b>Kayitli Notlar:</b>\n" + "\n".join(
        f"  • <code>{n}</code>" for n in names
    )
    await update.effective_message.reply_text(text, parse_mode="HTML")


async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context): return
    if not context.args:
        return await update.effective_message.reply_text("Hangi notu siliyim? .clear <isim>")
    name = context.args[0].lower()
    await delete_note(update.effective_chat.id, name)
    await update.effective_message.reply_text(f"Not silindi: <code>{name}</code>", parse_mode="HTML")


async def hashtag_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """#notename shortcut in messages."""
    msg = update.effective_message
    if not msg or not msg.text:
        return
    matches = re.findall(r"#(\w+)", msg.text)
    for name in matches:
        note = await get_note(update.effective_chat.id, name.lower())
        if note:
            await _send_note(update, context, name)
            break


def register_notes_handlers(app):
    for cmd, handler in [
        ("save", save_cmd), ("get", get_cmd),
        ("notes", notes_cmd), ("clear", clear_cmd),
    ]:
        app.add_handler(CommandHandler(cmd, handler))
        app.add_handler(MessageHandler(filters.TEXT & dot_filter(cmd), handler))

    # #notename trigger
    app.add_handler(
        MessageHandler(filters.TEXT & filters.Regex(r"#\w+"), hashtag_note),
        group=20,
    )
