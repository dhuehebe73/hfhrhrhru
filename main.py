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

import handlers.info        as info
import handlers.admin       as admin
import handlers.filters     as flts
import handlers.welcome     as welcome
import handlers.notes       as notes
import handlers.translate   as translate
import handlers.downloader  as downloader
import handlers.giveaway    as giveaway
import handlers.extras      as extras
import handlers.moderation  as moderation
import handlers.settings    as settings
import handlers.federation  as federation
import handlers.locks       as locks
import handlers.blacklist   as blacklist
import handlers.antispam    as antispam
import handlers.connection  as connection

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
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup", "channel"):
        try:
            from database import register_chat
            await register_chat(chat.id, chat.type, chat.title or "")
        except Exception:
            pass


async def _register_bot_membership(update, ctx):
    result = update.my_chat_member
    if not result:
        return
    chat = result.chat
    new  = result.new_chat_member
    from telegram.constants import ChatMemberStatus as CMS
    if new.status in (CMS.ADMINISTRATOR, CMS.MEMBER):
        if chat.type in ("group", "supergroup", "channel"):
            try:
                from database import register_chat
                await register_chat(chat.id, chat.type, chat.title or "")
            except Exception:
                pass


def build_app() -> Application:
    app = (
        Application.builder()
        .token(TOKEN)
        .job_queue(None)
        .post_init(_post_init)
        .build()
    )

    from telegram.ext import MessageHandler, ChatMemberHandler, filters

    # Lowest priority: track every chat the bot sees
    app.add_handler(MessageHandler(filters.ALL, _register_chat), group=100)
    app.add_handler(ChatMemberHandler(
        _register_bot_membership, ChatMemberHandler.MY_CHAT_MEMBER), group=100)

    # Priority order (lower group number = runs first):
    # 5  = welcome / captcha / member events
    # 6  = anti-flood
    # 7  = locks
    # 8  = blacklist
    # 10 = explicit commands
    # 15 = @herkes trigger
    # 20 = stats / afk tracking

    antispam.register(app)   # groups 6, 10
    locks.register(app)      # groups 7, 10
    blacklist.register(app)  # groups 8, 10
    welcome.register(app)    # groups 5, 10
    federation.register(app) # group 10
    connection.register(app) # group 10
    info.register(app)       # group 10
    admin.register(app)      # group 10
    flts.register(app)       # group 10
    notes.register(app)      # group 10
    translate.register(app)  # group 10
    downloader.register(app) # group 10
    giveaway.register(app)   # group 10
    extras.register(app)     # groups 10, 15, 20
    moderation.register(app) # group 10
    settings.register(app)   # group 10

    return app


def main():
    app = build_app()
    logging.info("Bot başlıyor...")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=[
            "message", "callback_query", "chat_member",
            "my_chat_member", "channel_post", "inline_query",
        ],
    )


if __name__ == "__main__":
    main()
