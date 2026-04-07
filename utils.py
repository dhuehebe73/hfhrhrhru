import re
import html
from datetime import timedelta
from telegram import Update, ChatPermissions, Chat
from telegram.ext import ContextTypes
from telegram.constants import ChatMemberStatus


# ─── Time parser ─────────────────────────────────────────────────────────────

TIME_RE = re.compile(r"^(\d+)(s|m|h|d|w)$", re.IGNORECASE)
_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def parse_time(text: str) -> int | None:
    """'30m' -> seconds. Returns None if invalid."""
    m = TIME_RE.match(text.strip())
    if not m:
        return None
    return int(m.group(1)) * _UNITS[m.group(2).lower()]


def format_duration(seconds: int) -> str:
    td = timedelta(seconds=seconds)
    days = td.days
    hours, rem = divmod(td.seconds, 3600)
    mins, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins:
        parts.append(f"{mins}m")
    if secs and not days:
        parts.append(f"{secs}s")
    return " ".join(parts) or "0s"


# ─── User parsing ─────────────────────────────────────────────────────────────

async def resolve_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Returns (user_id, first_name, reason) from a command.
    Supports: reply, @username, user_id, or nothing (returns None).
    """
    msg = update.effective_message
    args = context.args or []

    # Reply to message
    if msg.reply_to_message:
        target = msg.reply_to_message.from_user
        reason = " ".join(args) if args else ""
        return target.id, target.first_name, reason

    # First arg is @username or numeric ID
    if args:
        arg0 = args[0]
        reason = " ".join(args[1:])
        if arg0.lstrip("-").isdigit():
            uid = int(arg0)
            try:
                member = await context.bot.get_chat(uid)
                return uid, member.first_name or str(uid), reason
            except Exception:
                return uid, str(uid), reason
        elif arg0.startswith("@"):
            username = arg0[1:]
            try:
                member = await context.bot.get_chat(f"@{username}")
                return member.id, member.first_name or username, reason
            except Exception:
                pass

    return None, None, None


# ─── Permission helpers ───────────────────────────────────────────────────────

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return False
    try:
        member = await chat.get_member(user.id)
        return member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except Exception:
        return False


async def bot_is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    if not chat:
        return False
    try:
        me = await context.bot.get_me()
        member = await chat.get_member(me.id)
        return member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except Exception:
        return False


MUTE_PERMISSIONS = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
)

FULL_PERMISSIONS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
)

LOCKED_PERMISSIONS = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
    can_change_info=False,
    can_invite_users=False,
    can_pin_messages=False,
)


# ─── Formatting ───────────────────────────────────────────────────────────────

def mention_html(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{html.escape(name)}</a>'
