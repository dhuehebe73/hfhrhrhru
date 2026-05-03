import re, html, asyncio
from datetime import timedelta
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes
from telegram.constants import ChatMemberStatus
from config import OWNER_ID


# ── Time ──────────────────────────────────────────────────────────────────────

_TIME_RE = re.compile(r"^(\d+)(s|m|h|d|w)$", re.I)
_UNITS = {"s":1,"m":60,"h":3600,"d":86400,"w":604800}

def parse_time(s: str) -> int | None:
    m = _TIME_RE.match(s.strip())
    return int(m.group(1)) * _UNITS[m.group(2).lower()] if m else None

def fmt_duration(sec: int) -> str:
    d = timedelta(seconds=sec)
    days, rem = d.days, d.seconds
    h, rem2 = divmod(rem, 3600)
    mins, secs = divmod(rem2, 60)
    parts = []
    if days:  parts.append(f"{days}g")
    if h:     parts.append(f"{h}s")
    if mins:  parts.append(f"{mins}d")
    if secs and not days: parts.append(f"{secs}sn")
    return " ".join(parts) or "0sn"

def fmt_ago(ts: int) -> str:
    import time
    return fmt_duration(max(0, int(time.time()) - ts))


# ── User resolve ──────────────────────────────────────────────────────────────

async def resolve_user(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Returns (user_id, first_name, reason) or (None, None, None)."""
    msg  = update.effective_message
    args = get_args(update, ctx)

    if msg.reply_to_message and msg.reply_to_message.from_user:
        u = msg.reply_to_message.from_user
        return u.id, u.first_name, " ".join(args)

    if args:
        a0, reason = args[0], " ".join(args[1:])
        if a0.lstrip("-").isdigit():
            uid = int(a0)
            try:
                u = await ctx.bot.get_chat(uid)
                return uid, u.first_name or str(uid), reason
            except Exception:
                return uid, str(uid), reason
        if a0.startswith("@"):
            chat = update.effective_chat
            if chat and chat.type != "private":
                try:
                    member = await ctx.bot.get_chat_member(chat.id, a0)
                    u = member.user
                    return u.id, u.first_name or a0[1:], reason
                except Exception:
                    pass
            try:
                u = await ctx.bot.get_chat(a0)
                return u.id, u.first_name or a0[1:], reason
            except Exception:
                pass
    return None, None, None


# ── Permission helpers ────────────────────────────────────────────────────────

async def is_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat: return False
    if user.id == OWNER_ID:  return True
    try:
        m = await chat.get_member(user.id)
        return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False

async def bot_is_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    if not chat: return False
    try:
        me = await ctx.bot.get_me()
        m  = await chat.get_member(me.id)
        return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False

async def require_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    if not await is_admin(update, ctx):
        await update.effective_message.reply_text("❌ Admin olmalisin.")
        return False
    return True

async def require_bot_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    if not await bot_is_admin(update, ctx):
        await update.effective_message.reply_text("❌ Benim admin olmam gerekiyor!")
        return False
    return True


# ── Permissions presets ───────────────────────────────────────────────────────

MUTE_PERMS = ChatPermissions(
    can_send_messages=False, can_send_audios=False, can_send_documents=False,
    can_send_photos=False, can_send_videos=False, can_send_video_notes=False,
    can_send_voice_notes=False, can_send_polls=False, can_send_other_messages=False,
    can_add_web_page_previews=False)

FULL_PERMS = ChatPermissions(
    can_send_messages=True, can_send_audios=True, can_send_documents=True,
    can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
    can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
    can_add_web_page_previews=True, can_invite_users=True)

LOCKED_PERMS = ChatPermissions(
    can_send_messages=False, can_send_audios=False, can_send_documents=False,
    can_send_photos=False, can_send_videos=False, can_send_video_notes=False,
    can_send_voice_notes=False, can_send_polls=False, can_send_other_messages=False,
    can_add_web_page_previews=False, can_change_info=False,
    can_invite_users=False, can_pin_messages=False)


# ── Formatting ────────────────────────────────────────────────────────────────

def mention(uid: int, name: str) -> str:
    return f'<a href="tg://user?id={uid}">{html.escape(str(name))}</a>'


# ── Dot-command filter helper ─────────────────────────────────────────────────

def dcmd(cmd: str):
    from telegram.ext import filters
    return filters.Regex(rf"^[./!]{re.escape(cmd)}(\s|$)")


def get_args(update, ctx) -> list[str]:
    """Works for both /command (ctx.args set) and .command (parse manually)."""
    if ctx.args:
        return ctx.args
    msg = update.effective_message
    if msg:
        text = (msg.text or msg.caption or "").strip()
        parts = text.split()
        return parts[1:] if len(parts) > 1 else []
    return []


# ── Async delay helper (replaces job_queue) ───────────────────────────────────

async def _later(delay: float, coro):
    await asyncio.sleep(delay)
    try: await coro
    except Exception: pass

def later(delay: float, coro):
    asyncio.create_task(_later(delay, coro))
