import re, html
from datetime import timedelta
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes
from telegram.constants import ChatMemberStatus
from config import OWNER_ID


# ═══ TIME ════════════════════════════════════════════════════════════════════

_TIME_RE = re.compile(r"^(\d+)(s|m|h|d|w)$", re.I)
_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def parse_time(text: str) -> int | None:
    m = _TIME_RE.match(text.strip())
    return int(m.group(1)) * _UNITS[m.group(2).lower()] if m else None


def fmt_time(seconds: int) -> str:
    td = timedelta(seconds=seconds)
    d, rem = td.days, td.seconds
    h, rem2 = divmod(rem, 3600)
    mins, secs = divmod(rem2, 60)
    parts = []
    if d:    parts.append(f"{d}g")
    if h:    parts.append(f"{h}s")
    if mins: parts.append(f"{mins}d")
    if secs and not d: parts.append(f"{secs}sn")
    return " ".join(parts) or "0sn"


def fmt_ago(ts: int) -> str:
    import time
    return fmt_time(int(time.time()) - ts)


# ═══ USER RESOLVE ════════════════════════════════════════════════════════════

async def resolve_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Returns (user_id, first_name, reason) or (None, None, None)."""
    msg = update.effective_message
    args = context.args or []

    if msg.reply_to_message:
        u = msg.reply_to_message.from_user
        return u.id, u.first_name, " ".join(args)

    if args:
        a0 = args[0]
        reason = " ".join(args[1:])
        if a0.lstrip("-").isdigit():
            uid = int(a0)
            try:
                chat_user = await context.bot.get_chat(uid)
                return uid, chat_user.first_name or str(uid), reason
            except Exception:
                return uid, str(uid), reason
        if a0.startswith("@"):
            try:
                chat_user = await context.bot.get_chat(a0)
                return chat_user.id, chat_user.first_name or a0[1:], reason
            except Exception:
                pass

    return None, None, None


# ═══ PERMISSIONS ═════════════════════════════════════════════════════════════

async def is_owner(update: Update) -> bool:
    return update.effective_user.id == OWNER_ID


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return False
    if user.id == OWNER_ID:
        return True
    try:
        m = await chat.get_member(user.id)
        return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False


async def bot_is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    if not chat:
        return False
    try:
        me = await context.bot.get_me()
        m = await chat.get_member(me.id)
        return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False


# ═══ PERMISSIONS PRESETS ══════════════════════════════════════════════════════

MUTE_PERMS = ChatPermissions(
    can_send_messages=False, can_send_audios=False, can_send_documents=False,
    can_send_photos=False, can_send_videos=False, can_send_video_notes=False,
    can_send_voice_notes=False, can_send_polls=False, can_send_other_messages=False,
    can_add_web_page_previews=False,
)
FULL_PERMS = ChatPermissions(
    can_send_messages=True, can_send_audios=True, can_send_documents=True,
    can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
    can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
    can_add_web_page_previews=True, can_invite_users=True,
)
LOCKED_PERMS = ChatPermissions(
    can_send_messages=False, can_send_audios=False, can_send_documents=False,
    can_send_photos=False, can_send_videos=False, can_send_video_notes=False,
    can_send_voice_notes=False, can_send_polls=False, can_send_other_messages=False,
    can_add_web_page_previews=False, can_change_info=False,
    can_invite_users=False, can_pin_messages=False,
)


# ═══ FORMATTING ══════════════════════════════════════════════════════════════

def mention(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{html.escape(str(name))}</a>'


def dot_filter(cmd: str):
    from telegram.ext import filters as F
    return F.Regex(rf"^[./!]{re.escape(cmd)}(\s|$)")


# ═══ ADMIN CHECK DECORATOR ═══════════════════════════════════════════════════

async def require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not await is_admin(update, context):
        await update.effective_message.reply_text(
            "Bu komutu kullanmak icin admin olmalisin."
        )
        return False
    return True


async def require_bot_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not await bot_is_admin(update, context):
        await update.effective_message.reply_text(
            "Bu komutu kullanmak icin benim admin olmam gerekiyor!"
        )
        return False
    return True
