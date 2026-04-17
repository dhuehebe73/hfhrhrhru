import time
import aiosqlite
from config import DATABASE_PATH


async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS warnings (
                user_id INTEGER, chat_id INTEGER,
                count   INTEGER DEFAULT 0,
                reasons TEXT    DEFAULT '',
                PRIMARY KEY (user_id, chat_id)
            );
            CREATE TABLE IF NOT EXISTS word_filters (
                chat_id INTEGER, word TEXT,
                PRIMARY KEY (chat_id, word)
            );
            CREATE TABLE IF NOT EXISTS welcome (
                chat_id         INTEGER PRIMARY KEY,
                welcome_msg     TEXT DEFAULT '',
                goodbye_msg     TEXT DEFAULT '',
                rules_text      TEXT DEFAULT '',
                enabled         INTEGER DEFAULT 1,
                captcha         INTEGER DEFAULT 0,
                captcha_timeout INTEGER DEFAULT 60
            );
            CREATE TABLE IF NOT EXISTS left_members (
                user_id INTEGER, chat_id INTEGER,
                PRIMARY KEY (user_id, chat_id)
            );
            CREATE TABLE IF NOT EXISTS chat_settings (
                chat_id          INTEGER PRIMARY KEY,
                auto_ban_leavers INTEGER DEFAULT 0,
                anti_flood       INTEGER DEFAULT 1,
                flood_limit      INTEGER DEFAULT 5,
                locked           INTEGER DEFAULT 0,
                link_filter      INTEGER DEFAULT 0,
                sticker_filter   INTEGER DEFAULT 0,
                media_filter     INTEGER DEFAULT 0,
                bot_filter       INTEGER DEFAULT 0,
                slowmode         INTEGER DEFAULT 0,
                warn_limit       INTEGER DEFAULT 3,
                warn_action      TEXT    DEFAULT 'ban'
            );
            CREATE TABLE IF NOT EXISTS notes (
                chat_id   INTEGER, name TEXT,
                content   TEXT DEFAULT '',
                file_id   TEXT DEFAULT '',
                file_type TEXT DEFAULT '',
                PRIMARY KEY (chat_id, name)
            );
            CREATE TABLE IF NOT EXISTS giveaways (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id       INTEGER,
                message_id    INTEGER,
                prize         TEXT,
                winners_count INTEGER DEFAULT 1,
                end_time      INTEGER,
                ended         INTEGER DEFAULT 0,
                created_by    INTEGER
            );
            CREATE TABLE IF NOT EXISTS giveaway_participants (
                giveaway_id INTEGER, user_id INTEGER, user_name TEXT,
                joined_at   INTEGER,
                PRIMARY KEY (giveaway_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS known_chats (
                chat_id  INTEGER PRIMARY KEY,
                chat_type TEXT, title TEXT,
                added_at INTEGER
            );
            CREATE TABLE IF NOT EXISTS afk_users (
                user_id INTEGER PRIMARY KEY,
                reason  TEXT DEFAULT '',
                since   INTEGER
            );
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id  INTEGER, chat_id INTEGER,
                messages INTEGER DEFAULT 0,
                last_seen INTEGER,
                PRIMARY KEY (user_id, chat_id)
            );
            CREATE TABLE IF NOT EXISTS approved_users (
                user_id INTEGER, chat_id INTEGER,
                PRIMARY KEY (user_id, chat_id)
            );
            CREATE TABLE IF NOT EXISTS captcha_pending (
                user_id  INTEGER, chat_id INTEGER,
                answer   INTEGER,
                expires  INTEGER,
                msg_id   INTEGER,
                PRIMARY KEY (user_id, chat_id)
            );
        """)
        await db.commit()


# ═══ WARNINGS ════════════════════════════════════════════════════════════════

async def get_warnings(user_id: int, chat_id: int) -> tuple[int, list[str]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT count, reasons FROM warnings WHERE user_id=? AND chat_id=?",
            (user_id, chat_id),
        ) as cur:
            row = await cur.fetchone()
            if row:
                return row[0], [r for r in row[1].split("|||") if r]
            return 0, []


async def add_warning(user_id: int, chat_id: int, reason: str = "") -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """INSERT INTO warnings (user_id,chat_id,count,reasons) VALUES(?,?,1,?)
               ON CONFLICT(user_id,chat_id) DO UPDATE SET
               count=count+1, reasons=reasons||?""",
            (user_id, chat_id, reason + "|||", reason + "|||"),
        )
        await db.commit()
        async with db.execute(
            "SELECT count FROM warnings WHERE user_id=? AND chat_id=?",
            (user_id, chat_id),
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def remove_warning(user_id: int, chat_id: int) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT count, reasons FROM warnings WHERE user_id=? AND chat_id=?",
            (user_id, chat_id),
        ) as cur:
            row = await cur.fetchone()
        if not row or row[0] == 0:
            return 0
        reasons = [r for r in row[1].split("|||") if r]
        if reasons:
            reasons.pop()
        new = max(0, row[0] - 1)
        await db.execute(
            "UPDATE warnings SET count=?,reasons=? WHERE user_id=? AND chat_id=?",
            (new, "|||".join(reasons) + ("|||" if reasons else ""), user_id, chat_id),
        )
        await db.commit()
        return new


async def reset_warnings(user_id: int, chat_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM warnings WHERE user_id=? AND chat_id=?", (user_id, chat_id)
        )
        await db.commit()


# ═══ WORD FILTERS ════════════════════════════════════════════════════════════

async def get_filters(chat_id: int) -> list[str]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT word FROM word_filters WHERE chat_id=?", (chat_id,)
        ) as cur:
            return [r[0] for r in await cur.fetchall()]


async def add_filter(chat_id: int, word: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO word_filters VALUES(?,?)", (chat_id, word.lower())
        )
        await db.commit()


async def remove_filter(chat_id: int, word: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM word_filters WHERE chat_id=? AND word=?", (chat_id, word.lower())
        )
        await db.commit()


# ═══ WELCOME ═════════════════════════════════════════════════════════════════

async def get_welcome_row(chat_id: int) -> dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT welcome_msg,goodbye_msg,rules_text,enabled,captcha,captcha_timeout "
            "FROM welcome WHERE chat_id=?",
            (chat_id,),
        ) as cur:
            row = await cur.fetchone()
            if row:
                return {
                    "welcome_msg": row[0], "goodbye_msg": row[1],
                    "rules_text": row[2], "enabled": bool(row[3]),
                    "captcha": bool(row[4]), "captcha_timeout": row[5],
                }
    return {"welcome_msg": "", "goodbye_msg": "", "rules_text": "",
            "enabled": True, "captcha": False, "captcha_timeout": 60}


async def set_welcome_field(chat_id: int, field: str, value):
    _ok = {"welcome_msg", "goodbye_msg", "rules_text", "enabled", "captcha", "captcha_timeout"}
    if field not in _ok:
        raise ValueError(f"bad field: {field}")
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            f"INSERT INTO welcome(chat_id,{field}) VALUES(?,?) "
            f"ON CONFLICT(chat_id) DO UPDATE SET {field}=?",
            (chat_id, value, value),
        )
        await db.commit()


# ═══ RULES (wrapper over welcome.rules_text) ══════════════════════════════════

async def get_rules(chat_id: int) -> str:
    row = await get_welcome_row(chat_id)
    return row.get("rules_text", "")


async def set_rules(chat_id: int, content: str):
    await set_welcome_field(chat_id, "rules_text", content)


# ═══ LEFT MEMBERS ════════════════════════════════════════════════════════════

async def mark_left(user_id: int, chat_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO left_members VALUES(?,?)", (user_id, chat_id)
        )
        await db.commit()


async def has_left_before(user_id: int, chat_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM left_members WHERE user_id=? AND chat_id=?", (user_id, chat_id)
        ) as cur:
            return await cur.fetchone() is not None


async def clear_left(user_id: int, chat_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM left_members WHERE user_id=? AND chat_id=?", (user_id, chat_id)
        )
        await db.commit()


# ═══ CHAT SETTINGS ═══════════════════════════════════════════════════════════

_CHAT_KEYS = {
    "auto_ban_leavers", "anti_flood", "flood_limit", "locked",
    "link_filter", "sticker_filter", "media_filter", "bot_filter",
    "slowmode", "warn_limit", "warn_action",
}


async def get_chat_settings(chat_id: int) -> dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT auto_ban_leavers,anti_flood,flood_limit,locked,"
            "link_filter,sticker_filter,media_filter,bot_filter,"
            "slowmode,warn_limit,warn_action FROM chat_settings WHERE chat_id=?",
            (chat_id,),
        ) as cur:
            row = await cur.fetchone()
    if row:
        keys = ["auto_ban_leavers","anti_flood","flood_limit","locked",
                "link_filter","sticker_filter","media_filter","bot_filter",
                "slowmode","warn_limit","warn_action"]
        d = dict(zip(keys, row))
        for k in ["auto_ban_leavers","anti_flood","locked","link_filter",
                  "sticker_filter","media_filter","bot_filter"]:
            d[k] = bool(d[k])
        return d
    return {
        "auto_ban_leavers": False, "anti_flood": True, "flood_limit": 5,
        "locked": False, "link_filter": False, "sticker_filter": False,
        "media_filter": False, "bot_filter": False, "slowmode": 0,
        "warn_limit": 3, "warn_action": "ban",
    }


async def update_chat_setting(chat_id: int, key: str, value):
    if key not in _CHAT_KEYS:
        raise ValueError(f"bad key: {key}")
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            f"INSERT INTO chat_settings(chat_id,{key}) VALUES(?,?) "
            f"ON CONFLICT(chat_id) DO UPDATE SET {key}=?",
            (chat_id, value, value),
        )
        await db.commit()


# ═══ NOTES ═══════════════════════════════════════════════════════════════════

async def get_note(chat_id: int, name: str) -> dict | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT content,file_id,file_type FROM notes WHERE chat_id=? AND name=?",
            (chat_id, name.lower()),
        ) as cur:
            row = await cur.fetchone()
            if row:
                return {"content": row[0], "file_id": row[1], "file_type": row[2]}
    return None


async def save_note(chat_id: int, name: str, content: str, file_id: str = "", file_type: str = ""):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO notes VALUES(?,?,?,?,?) "
            "ON CONFLICT(chat_id,name) DO UPDATE SET content=?,file_id=?,file_type=?",
            (chat_id, name.lower(), content, file_id, file_type,
             content, file_id, file_type),
        )
        await db.commit()


async def delete_note(chat_id: int, name: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM notes WHERE chat_id=? AND name=?", (chat_id, name.lower())
        )
        await db.commit()


async def list_notes(chat_id: int) -> list[str]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT name FROM notes WHERE chat_id=? ORDER BY name", (chat_id,)
        ) as cur:
            return [r[0] for r in await cur.fetchall()]


# ═══ GIVEAWAY ════════════════════════════════════════════════════════════════

async def create_giveaway(chat_id, message_id, prize, winners_count, end_time, created_by) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "INSERT INTO giveaways(chat_id,message_id,prize,winners_count,end_time,created_by) "
            "VALUES(?,?,?,?,?,?)",
            (chat_id, message_id, prize, winners_count, end_time, created_by),
        )
        await db.commit()
        return cur.lastrowid


async def get_giveaway(gid: int) -> dict | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT id,chat_id,message_id,prize,winners_count,end_time,ended,created_by "
            "FROM giveaways WHERE id=?", (gid,)
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0], "chat_id": row[1], "message_id": row[2],
        "prize": row[3], "winners_count": row[4], "end_time": row[5],
        "ended": bool(row[6]), "created_by": row[7],
    }


async def join_giveaway(gid: int, user_id: int, user_name: str) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO giveaway_participants VALUES(?,?,?,?)",
                (gid, user_id, user_name, int(time.time())),
            )
            await db.commit()
            return True
        except Exception:
            return False


async def get_giveaway_participants(gid: int) -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT user_id,user_name FROM giveaway_participants WHERE giveaway_id=?", (gid,)
        ) as cur:
            return [{"user_id": r[0], "user_name": r[1]} for r in await cur.fetchall()]


async def end_giveaway(gid: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE giveaways SET ended=1 WHERE id=?", (gid,))
        await db.commit()


async def get_active_giveaway(chat_id: int) -> dict | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT id,chat_id,message_id,prize,winners_count,end_time,ended,created_by "
            "FROM giveaways WHERE chat_id=? AND ended=0 ORDER BY id DESC LIMIT 1",
            (chat_id,),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0], "chat_id": row[1], "message_id": row[2],
        "prize": row[3], "winners_count": row[4], "end_time": row[5],
        "ended": bool(row[6]), "created_by": row[7],
    }


# ═══ KNOWN CHATS (broadcast) ════════════════════════════════════════════════

async def register_chat(chat_id: int, chat_type: str, title: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO known_chats VALUES(?,?,?,?) "
            "ON CONFLICT(chat_id) DO UPDATE SET title=?",
            (chat_id, chat_type, title, int(time.time()), title),
        )
        await db.commit()


async def get_all_chats() -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT chat_id, chat_type, title FROM known_chats"
        ) as cur:
            return [{"chat_id": r[0], "chat_type": r[1], "title": r[2]}
                    for r in await cur.fetchall()]


# ═══ AFK ═════════════════════════════════════════════════════════════════════

async def set_afk(user_id: int, reason: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO afk_users VALUES(?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET reason=?,since=?",
            (user_id, reason, int(time.time()), reason, int(time.time())),
        )
        await db.commit()


async def get_afk(user_id: int) -> dict | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT reason, since FROM afk_users WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
    return {"reason": row[0], "since": row[1]} if row else None


async def clear_afk(user_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM afk_users WHERE user_id=?", (user_id,))
        await db.commit()


# ═══ USER STATS ══════════════════════════════════════════════════════════════

async def increment_stats(user_id: int, chat_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO user_stats VALUES(?,?,1,?) "
            "ON CONFLICT(user_id,chat_id) DO UPDATE SET messages=messages+1,last_seen=?",
            (user_id, chat_id, int(time.time()), int(time.time())),
        )
        await db.commit()


async def get_top_users(chat_id: int, limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT user_id,messages FROM user_stats WHERE chat_id=? "
            "ORDER BY messages DESC LIMIT ?",
            (chat_id, limit),
        ) as cur:
            return [{"user_id": r[0], "messages": r[1]} for r in await cur.fetchall()]


# ═══ CAPTCHA PENDING ════════════════════════════════════════════════════════

async def set_captcha(user_id: int, chat_id: int, answer: int, expires: int, msg_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO captcha_pending VALUES(?,?,?,?,?)",
            (user_id, chat_id, answer, expires, msg_id),
        )
        await db.commit()


async def get_captcha(user_id: int, chat_id: int) -> dict | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT answer,expires,msg_id FROM captcha_pending WHERE user_id=? AND chat_id=?",
            (user_id, chat_id),
        ) as cur:
            row = await cur.fetchone()
    return {"answer": row[0], "expires": row[1], "msg_id": row[2]} if row else None


async def clear_captcha(user_id: int, chat_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM captcha_pending WHERE user_id=? AND chat_id=?", (user_id, chat_id)
        )
        await db.commit()


# ═══ APPROVED USERS ══════════════════════════════════════════════════════════

async def approve_user(user_id: int, chat_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO approved_users VALUES(?,?)", (user_id, chat_id)
        )
        await db.commit()


async def unapprove_user(user_id: int, chat_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM approved_users WHERE user_id=? AND chat_id=?", (user_id, chat_id)
        )
        await db.commit()


async def is_approved(user_id: int, chat_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM approved_users WHERE user_id=? AND chat_id=?", (user_id, chat_id)
        ) as cur:
            return await cur.fetchone() is not None
