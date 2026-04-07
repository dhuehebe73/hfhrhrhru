"""
Word filter system: .filter .unfilter .filters
Auto-deletes messages containing blacklisted words.
"""
import re

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from telegram.error import BadRequest

from utils import is_admin
from database import add_filter, remove_filter, get_filters

import re as re_mod


def _dot_filter_cmd(cmd: str):
    return filters.Regex(rf"^[./!]{re_mod.escape(cmd)}(\s|$)")


async def filter_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await is_admin(update, context):
        await msg.reply_text("Bu komutu kullanmak icin admin olmalisin.")
        return

    if not context.args:
        await msg.reply_text("Hangi kelimeyi filtreleyelim? Ornek: .filter kelime")
        return

    word = context.args[0].lower()
    await add_filter(update.effective_chat.id, word)
    await msg.reply_text(f"Filtrelendi: <code>{word}</code>", parse_mode="HTML")


async def unfilter_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not await is_admin(update, context):
        await msg.reply_text("Bu komutu kullanmak icin admin olmalisin.")
        return

    if not context.args:
        await msg.reply_text("Hangi filtreyi kaldirayim? Ornek: .unfilter kelime")
        return

    word = context.args[0].lower()
    await remove_filter(update.effective_chat.id, word)
    await msg.reply_text(f"Filtre kaldirildi: <code>{word}</code>", parse_mode="HTML")


async def list_filters_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    word_list = await get_filters(update.effective_chat.id)

    if not word_list:
        await msg.reply_text("Bu grupta aktif filtre yok.")
        return

    text = "Aktif filtreler:\n" + "\n".join(f"  • <code>{w}</code>" for w in word_list)
    await msg.reply_text(text, parse_mode="HTML")


async def check_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-delete messages containing filtered words."""
    msg = update.effective_message
    if not msg or not msg.text:
        return

    # Admins bypass filters
    if await is_admin(update, context):
        return

    chat_id = update.effective_chat.id
    word_list = await get_filters(chat_id)
    if not word_list:
        return

    text_lower = msg.text.lower()
    for word in word_list:
        if re.search(rf"\b{re.escape(word)}\b", text_lower):
            try:
                await msg.delete()
                notice = await context.bot.send_message(
                    chat_id,
                    f"Yasak kelime iceren mesaj silindi.",
                )
                # Auto-delete the notice after 5 seconds
                context.job_queue.run_once(
                    lambda ctx: ctx.bot.delete_message(chat_id, notice.message_id),
                    5,
                )
            except BadRequest:
                pass
            break


def register_filter_handlers(app):
    for cmd, handler in [
        ("filter", filter_cmd),
        ("unfilter", unfilter_cmd),
        ("filters", list_filters_cmd),
    ]:
        app.add_handler(CommandHandler(cmd, handler))
        app.add_handler(
            MessageHandler(filters.TEXT & _dot_filter_cmd(cmd), handler)
        )

    # Auto-filter check on every text message
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, check_filters),
        group=10,
    )
