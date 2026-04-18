import re
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from database import get_note, save_note, delete_note, list_notes
from utils import require_admin, dcmd

_HASHTAG_RE = re.compile(r"#(\w+)")


async def save_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    msg = update.effective_message
    args = ctx.args or []
    if not args:
        await msg.reply_text("Kullanım: /save <isim> [içerik]"); return
    name = args[0].lower()
    content = " ".join(args[1:])
    file_id = file_type = ""

    reply = msg.reply_to_message
    if reply:
        if not content: content = reply.text or reply.caption or ""
        if reply.photo:
            file_id = reply.photo[-1].file_id; file_type = "photo"
        elif reply.video:
            file_id = reply.video.file_id; file_type = "video"
        elif reply.document:
            file_id = reply.document.file_id; file_type = "document"
        elif reply.audio:
            file_id = reply.audio.file_id; file_type = "audio"
        elif reply.sticker:
            file_id = reply.sticker.file_id; file_type = "sticker"

    await save_note(update.effective_chat.id, name, content, file_id, file_type)
    await msg.reply_text(f"✅ Not «{name}» kaydedildi.")

async def get_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args or []
    if not args:
        await update.effective_message.reply_text("Kullanım: /get <isim>"); return
    await _send_note(update, ctx, args[0].lower())

async def notes_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    names = await list_notes(update.effective_chat.id)
    if not names:
        await update.effective_message.reply_text("Kayıtlı not yok."); return
    await update.effective_message.reply_text(
        "📝 Notlar:\n" + "\n".join(f"• #{n}" for n in names))

async def clear_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx): return
    args = ctx.args or []
    if not args:
        await update.effective_message.reply_text("Kullanım: /clear <isim>"); return
    name = args[0].lower()
    note = await get_note(update.effective_chat.id, name)
    if not note:
        await update.effective_message.reply_text(f"«{name}» notu bulunamadı."); return
    await delete_note(update.effective_chat.id, name)
    await update.effective_message.reply_text(f"✅ «{name}» notu silindi.")


async def _send_note(update: Update, ctx: ContextTypes.DEFAULT_TYPE, name: str):
    note = await get_note(update.effective_chat.id, name)
    if not note:
        await update.effective_message.reply_text(f"«{name}» notu bulunamadı."); return
    content = note["content"]
    fid = note["file_id"]
    ftype = note["file_type"]
    if ftype == "photo":
        await update.effective_message.reply_photo(fid, caption=content or None, parse_mode="HTML")
    elif ftype == "video":
        await update.effective_message.reply_video(fid, caption=content or None, parse_mode="HTML")
    elif ftype == "document":
        await update.effective_message.reply_document(fid, caption=content or None, parse_mode="HTML")
    elif ftype == "audio":
        await update.effective_message.reply_audio(fid, caption=content or None, parse_mode="HTML")
    elif ftype == "sticker":
        await update.effective_message.reply_sticker(fid)
    else:
        await update.effective_message.reply_text(content or "(boş)", parse_mode="HTML")


async def _hashtag_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not (msg.text or msg.caption): return
    text = msg.text or msg.caption
    matches = _HASHTAG_RE.findall(text)
    if not matches: return
    names = await list_notes(update.effective_chat.id)
    for match in matches:
        if match.lower() in names:
            await _send_note(update, ctx, match.lower())
            return


def register(app):
    for cmd, h in [
        ("save", save_cmd), ("get", get_cmd),
        ("notes", notes_cmd), ("clear", clear_cmd),
    ]:
        app.add_handler(MessageHandler(dcmd(cmd), h), group=10)
    app.add_handler(
        MessageHandler(filters.ChatType.GROUPS & (filters.TEXT | filters.CAPTION),
                       _hashtag_handler), group=20)
