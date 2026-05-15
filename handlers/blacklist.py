import re
import aiosqlite
from config import DB_PATH
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from database import (
    get_warnings, add_warning, reset_warnings,
    get_settings, is_approved,
)
from utils import (
    require_admin, is_admin, dcmd, get_args,
    mention, MUTE_PERMS,
)


# ── Valid actions ─────────────────────────────────────────────────────────────

VALID_ACTIONS = ("warn", "mute", "kick", "ban", "delete")


# ── Database helpers ──────────────────────────────────────────────────────────

async def _ensure_tables(db):
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS chat_blacklist(
            chat_id INTEGER,
            word    TEXT,
            action  TEXT DEFAULT 'delete',
            PRIMARY KEY(chat_id, word));

        CREATE TABLE IF NOT EXISTS chat_blacklist_mode(
            chat_id INTEGER PRIMARY KEY,
            mode    TEXT DEFAULT 'delete');
    """)


async def get_blacklist(chat_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_tables(db)
        await db.commit()
        async with db.execute(
            "SELECT word, action FROM chat_blacklist WHERE chat_id=? ORDER BY word",
            (chat_id,)
        ) as c:
            return [{"word": r[0], "action": r[1]} for r in await c.fetchall()]


async def add_blacklist(chat_id: int, word: str, action: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_tables(db)
        await db.execute(
            "INSERT INTO chat_blacklist(chat_id, word, action) VALUES(?, ?, ?)"
            " ON CONFLICT(chat_id, word) DO UPDATE SET action=?",
            (chat_id, word.lower(), action, action)
        )
        await db.commit()


async def remove_blacklist(chat_id: int, word: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_tables(db)
        await db.execute(
            "DELETE FROM chat_blacklist WHERE chat_id=? AND word=?",
            (chat_id, word.lower())
        )
        await db.commit()


async def get_blacklist_mode(chat_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_tables(db)
        await db.commit()
        async with db.execute(
            "SELECT mode FROM chat_blacklist_mode WHERE chat_id=?", (chat_id,)
        ) as c:
            row = await c.fetchone()
    return row[0] if row else "delete"


async def _set_blacklist_mode(chat_id: int, mode: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_tables(db)
        await db.execute(
            "INSERT INTO chat_blacklist_mode(chat_id, mode) VALUES(?, ?)"
            " ON CONFLICT(chat_id) DO UPDATE SET mode=?",
            (chat_id, mode, mode)
        )
        await db.commit()


# ── Commands ──────────────────────────────────────────────────────────────────

async def addbl_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx):
        return

    args = get_args(update, ctx)
    if not args:
        await update.effective_message.reply_text(
            "❌ Kullanım: /addbl &lt;kelime&gt; [aksiyon]\n"
            f"Aksiyonlar: <code>{'  '.join(VALID_ACTIONS)}</code>",
            parse_mode="HTML"
        )
        return

    cid = update.effective_chat.id
    word = args[0].lower()

    if len(args) >= 2:
        action = args[1].lower()
        if action not in VALID_ACTIONS:
            await update.effective_message.reply_text(
                f"❌ Geçersiz aksiyon: <code>{action}</code>\n"
                f"Geçerli aksiyonlar: <code>{'  '.join(VALID_ACTIONS)}</code>",
                parse_mode="HTML"
            )
            return
    else:
        action = await get_blacklist_mode(cid)

    await add_blacklist(cid, word, action)
    await update.effective_message.reply_text(
        f"✅ <code>{word}</code> kara listeye eklendi. "
        f"Aksiyon: <b>{action}</b>",
        parse_mode="HTML"
    )


async def unbl_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx):
        return

    args = get_args(update, ctx)
    if not args:
        await update.effective_message.reply_text(
            "❌ Kullanım: /unbl &lt;kelime&gt;", parse_mode="HTML"
        )
        return

    cid = update.effective_chat.id
    word = args[0].lower()
    bl = await get_blacklist(cid)
    existing = [e["word"] for e in bl]

    if word not in existing:
        await update.effective_message.reply_text(
            f"❌ <code>{word}</code> kara listede yok.", parse_mode="HTML"
        )
        return

    await remove_blacklist(cid, word)
    await update.effective_message.reply_text(
        f"✅ <code>{word}</code> kara listeden çıkarıldı.", parse_mode="HTML"
    )


async def blacklist_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    bl = await get_blacklist(cid)
    mode = await get_blacklist_mode(cid)

    if not bl:
        await update.effective_message.reply_text(
            "ℹ️ Kara liste boş.", parse_mode="HTML"
        )
        return

    lines = []
    for entry in bl:
        lines.append(f"• <code>{entry['word']}</code> — <b>{entry['action']}</b>")

    await update.effective_message.reply_text(
        f"🚫 <b>Kara Liste</b>  (varsayılan mod: <b>{mode}</b>)\n\n"
        + "\n".join(lines),
        parse_mode="HTML"
    )


async def blmode_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, ctx):
        return

    args = get_args(update, ctx)
    if not args or args[0].lower() not in VALID_ACTIONS:
        mode = await get_blacklist_mode(update.effective_chat.id)
        await update.effective_message.reply_text(
            f"ℹ️ Mevcut varsayılan aksiyon: <b>{mode}</b>\n"
            f"Değiştirmek için: /blmode "
            f"<code>{'|'.join(VALID_ACTIONS)}</code>",
            parse_mode="HTML"
        )
        return

    mode = args[0].lower()
    await _set_blacklist_mode(update.effective_chat.id, mode)
    await update.effective_message.reply_text(
        f"✅ Kara liste varsayılan aksiyonu: <b>{mode}</b>",
        parse_mode="HTML"
    )


# ── Enforcement helpers ───────────────────────────────────────────────────────

async def _apply_action(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                        uid: int, name: str, action: str, word: str):
    msg = update.effective_message
    chat = update.effective_chat
    cid = chat.id

    # Always delete the triggering message first
    try:
        await msg.delete()
    except Exception:
        pass

    if action == "delete":
        # Silent delete — no notification
        return

    if action == "warn":
        s = await get_settings(cid)
        limit = s.get("warn_limit", 3)
        warn_action = s.get("warn_action", "ban")
        reason = f"Kara liste: {word}"
        count = await add_warning(uid, cid, reason)

        text = (
            f"⚠️ {mention(uid, name)} uyarıldı. ({count}/{limit})\n"
            f"📝 Sebep: kara liste — <code>{word}</code>"
        )

        if count >= limit:
            try:
                if warn_action == "ban":
                    await chat.ban_member(uid)
                    result = "banlandı 🚫"
                elif warn_action == "kick":
                    await chat.ban_member(uid)
                    await chat.unban_member(uid)
                    result = "atıldı 👢"
                elif warn_action == "mute":
                    await chat.restrict_member(uid, MUTE_PERMS)
                    result = "susturuldu 🔇"
                else:
                    result = "uyarılandı ⚠️"
            except Exception:
                result = "uyarılandı ⚠️"
            await reset_warnings(uid, cid)
            text += f"\n\n🔴 Limit aşıldı! Kullanıcı {result}"

        try:
            await ctx.bot.send_message(cid, text, parse_mode="HTML")
        except Exception:
            pass
        return

    if action == "mute":
        try:
            await chat.restrict_member(uid, MUTE_PERMS)
            await ctx.bot.send_message(
                cid,
                f"🔇 {mention(uid, name)} susturuldu.\n"
                f"📝 Sebep: kara liste — <code>{word}</code>",
                parse_mode="HTML"
            )
        except Exception:
            pass
        return

    if action == "kick":
        try:
            await chat.ban_member(uid)
            await chat.unban_member(uid)
            await ctx.bot.send_message(
                cid,
                f"👢 {mention(uid, name)} atıldı.\n"
                f"📝 Sebep: kara liste — <code>{word}</code>",
                parse_mode="HTML"
            )
        except Exception:
            pass
        return

    if action == "ban":
        try:
            await chat.ban_member(uid)
            await ctx.bot.send_message(
                cid,
                f"🚫 {mention(uid, name)} banlandı.\n"
                f"📝 Sebep: kara liste — <code>{word}</code>",
                parse_mode="HTML"
            )
        except Exception:
            pass
        return


# ── Message handler ───────────────────────────────────────────────────────────

async def _check_blacklist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return

    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    # Skip admins
    if await is_admin(update, ctx):
        return

    # Skip approved users
    if await is_approved(user.id, chat.id):
        return

    text = (msg.text or msg.caption or "").lower()
    if not text:
        return

    bl = await get_blacklist(chat.id)
    if not bl:
        return

    for entry in bl:
        word = entry["word"]
        # Use word-boundary-aware search: match if the blacklisted phrase
        # appears as a standalone word or substring (case-insensitive already lowered)
        pattern = re.compile(r"(?<![a-z0-9])" + re.escape(word) + r"(?![a-z0-9])", re.IGNORECASE)
        if pattern.search(text):
            await _apply_action(
                update, ctx,
                user.id, user.first_name,
                entry["action"], word
            )
            return  # One violation is enough — message already deleted


# ── Register ──────────────────────────────────────────────────────────────────

def register(app):
    # Message checker: group 8, runs before most handlers but after lock checker (7)
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & (filters.TEXT | filters.CAPTION),
            _check_blacklist
        ),
        group=8
    )
    for cmd, handler in [
        ("addbl", addbl_cmd),
        ("unbl", unbl_cmd),
        ("blacklist", blacklist_cmd),
        ("blmode", blmode_cmd),
    ]:
        app.add_handler(MessageHandler(dcmd(cmd), handler), group=10)
