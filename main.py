"""
Main entry point for the Telegram group management bot.
Usage:
    1. Copy .env.example to .env and fill in your BOT_TOKEN and OWNER_ID
    2. pip install -r requirements.txt
    3. python main.py
"""
import logging

from telegram.ext import Application

from config import BOT_TOKEN
from database import init_db
from handlers.admin import register_admin_handlers
from handlers.warnings import register_warning_handlers
from handlers.word_filters import register_filter_handlers
from handlers.welcome import register_welcome_handlers
from handlers.translate import register_translate_handlers
from handlers.info import register_info_handlers
from handlers.moderation import register_moderation_handlers

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(app: Application):
    await init_db()
    me = await app.bot.get_me()
    logger.info(f"Bot baslatildi: @{me.username} ({me.id})")


def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    register_info_handlers(app)       # /start /help .info .id .rules .stats .report
    register_admin_handlers(app)      # .ban .unban .kick .mute .unmute .promote .demote .pin .unpin .del
    register_warning_handlers(app)    # .warn .unwarn .resetwarns .warns
    register_filter_handlers(app)     # .filter .unfilter .filters + auto-delete
    register_welcome_handlers(app)    # .setwelcome .setgoodbye .welcome .autoban + join/leave events
    register_translate_handlers(app)  # .tr .translate .cevir
    register_moderation_handlers(app) # .purge .lock .unlock .antiflood + anti-flood

    logger.info("Polling baslatiliyor...")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "chat_member", "callback_query"],
    )


if __name__ == "__main__":
    main()
