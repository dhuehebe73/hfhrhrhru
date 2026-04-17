"""
Telegram Grup Yonetim Botu
Rose'dan daha kapsamli — tam ozellikli.

Kurulum:
  1. pip install -r requirements.txt
  2. cp .env.example .env  (token gir)
  3. python main.py
"""
import logging

from telegram.ext import Application

from config import yarrak          # bot token
from database import init_db
from handlers.info        import register_info_handlers
from handlers.admin       import register_admin_handlers
from handlers.warnings    import register_warning_handlers
from handlers.filters     import register_filter_handlers
from handlers.welcome     import register_welcome_handlers
from handlers.translate   import register_translate_handlers
from handlers.moderation  import register_moderation_handlers
from handlers.notes       import register_notes_handlers
from handlers.downloader  import register_downloader_handlers
from handlers.giveaway    import register_giveaway_handlers
from handlers.extras      import register_extras_handlers

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def post_init(app: Application):
    await init_db()
    me = await app.bot.get_me()
    logger.info(f"Bot baslatildi: @{me.username} (ID: {me.id})")
    print(f"\n✓ Bot aktif: @{me.username}\n")


def main():
    app = (
        Application.builder()
        .token(yarrak)
        .post_init(post_init)
        .job_queue(None)   # disable job_queue (Python 3.13 compat)
        .build()
    )

    # Handlers — priority order matters
    register_info_handlers(app)        # /start /help .rules .id .info .stats .admins .members
    register_admin_handlers(app)       # .ban .dban .sban .kick .dkick .mute .dmute .unmute .promote .demote .pin .del .approve
    register_warning_handlers(app)     # .warn .dwarn .unwarn .resetwarns .warns .warnmode .warnlimit
    register_filter_handlers(app)      # .filter .unfilter .filters .linkfilter .stickerfilter .mediafilter
    register_welcome_handlers(app)     # .setwelcome .setgoodbye .welcome .autoban .captcha + join/leave events
    register_translate_handlers(app)   # .tr .translate .cevir .langs
    register_moderation_handlers(app)  # .purge .lock .unlock .slowmode .antiflood + flood check
    register_notes_handlers(app)       # .save .get .notes .clear + #notismi
    register_downloader_handlers(app)  # .play .video .dl + auto-detect URLs
    register_giveaway_handlers(app)    # .giveaway .gend .greroll
    register_extras_handlers(app)      # .broadcast .afk .back .dice .flip .calc .weather .poll .report

    logger.info("Polling baslatiliyor...")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=[
            "message", "edited_message",
            "chat_member", "callback_query",
            "poll", "poll_answer",
        ],
    )


if __name__ == "__main__":
    main()
