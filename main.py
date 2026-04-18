"""
Telegram Grup Yönetim Botu
Kurulum: pip install -r requirements.txt
Çalıştır: python main.py
"""
import asyncio
import logging
from telegram.ext import Application
from config import TOKEN
from database import init_db

import handlers.info as info
import handlers.admin as admin
import handlers.warnings as warnings
import handlers.filters as flts
import handlers.welcome as welcome
import handlers.notes as notes
import handlers.translate as translate
import handlers.downloader as downloader
import handlers.giveaway as giveaway
import handlers.extras as extras
import handlers.moderation as moderation
import handlers.settings as settings

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)


async def _post_init(app: Application):
    await init_db()
    logging.info("Veritabanı hazır.")


async def _register_chat(update, ctx):
    """Track every chat the bot is active in."""
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup", "channel"):
        try:
            from database import register_chat
            await register_chat(chat.id, chat.type, chat.title or "")
        except Exception: pass


async def _register_bot_membership(update, ctx):
    """Register chats when bot is added as member/admin (including channels)."""
    result = update.my_chat_member
    if not result: return
    chat = result.chat
    new = result.new_chat_member
    from telegram.constants import ChatMemberStatus as CMS
    if new.status in (CMS.ADMINISTRATOR, CMS.MEMBER):
        if chat.type in ("group", "supergroup", "channel"):
            try:
                from database import register_chat
                await register_chat(chat.id, chat.type, chat.title or "")
            except Exception: pass


def build_app() -> Application:
    app = (
        Application.builder()
        .token(TOKEN)
        .job_queue(None)
        .post_init(_post_init)
        .build()
    )

    # Register chat tracker (lowest priority, all messages)
    from telegram.ext import MessageHandler, ChatMemberHandler, filters
    app.add_handler(MessageHandler(filters.ALL, _register_chat), group=100)
    app.add_handler(ChatMemberHandler(_register_bot_membership,
                                      ChatMemberHandler.MY_CHAT_MEMBER), group=100)

    # Register all feature modules
    info.register(app)
    admin.register(app)
    warnings.register(app)
    flts.register(app)
    welcome.register(app)
    notes.register(app)
    translate.register(app)
    downloader.register(app)
    giveaway.register(app)
    extras.register(app)
    moderation.register(app)
    settings.register(app)

    return app


def main():
    app = build_app()
    logging.info("Bot başlıyor...")
    app.run_polling(drop_pending_updates=True,
                    allowed_updates=["message","callback_query","chat_member",
                                     "my_chat_member","channel_post"])


if __name__ == "__main__":
    main()
