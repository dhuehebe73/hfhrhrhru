import time
import aiosqlite
from config import DB_PATH

# ══════════════════════════════════════════════════════════════════════════════
# SCHEMA
# ══════════════════════════════════════════════════════════════════════════════

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS warnings(
                user_id INTEGER, chat_id INTEGER,
                count INTEGER DEFAULT 0, reasons TEXT DEFAULT '',
                PRIMARY KEY(user_id, chat_id));

            CREATE TABLE IF NOT EXISTS word_filters(
                chat_id INTEGER, word TEXT,
                PRIMARY KEY(chat_id, word));

            CREATE TABLE IF NOT EXISTS welcome(
                chat_id INTEGER PRIMARY KEY,
                welcome_msg TEXT DEFAULT '',
                goodbye_msg TEXT DEFAULT '',
                rules_text  TEXT DEFAULT '',
                enabled     INTEGER DEFAULT 1,
                captcha     INTEGER DEFAULT 0,
                captcha_timeout INTEGER DEFAULT 60);

            CREATE TABLE IF NOT EXISTS left_members(
                user_id INTEGER, chat_id INTEGER,
                PRIMARY KEY(user_id, chat_id));

            CREATE TABLE IF NOT EXISTS chat_settings(
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
                warn_action      TEXT    DEFAULT 'ban');

            CREATE TABLE IF NOT EXISTS notes(
                chat_id INTEGER, name TEXT,
                content TEXT DEFAULT '',
                file_id TEXT DEFAULT '', file_type TEXT DEFAULT '',
                PRIMARY KEY(chat_id, name));

            CREATE TABLE IF NOT EXISTS giveaways(
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id       INTEGER, message_id INTEGER,
                prize         TEXT, winners_count INTEGER DEFAULT 1,
                end_time      INTEGER, ended INTEGER DEFAULT 0,
                created_by    INTEGER);

            CREATE TABLE IF NOT EXISTS giveaway_participants(
                giveaway_id INTEGER, user_id INTEGER, user_name TEXT,
                joined_at INTEGER,
                PRIMARY KEY(giveaway_id, user_id));

            CREATE TABLE IF NOT EXISTS known_chats(
                chat_id INTEGER PRIMARY KEY,
                chat_type TEXT, title TEXT, added_at INTEGER);

            CREATE TABLE IF NOT EXISTS afk_users(
                user_id INTEGER PRIMARY KEY,
                reason TEXT DEFAULT '', since INTEGER);

            CREATE TABLE IF NOT EXISTS user_stats(
                user_id INTEGER, chat_id INTEGER,
                messages INTEGER DEFAULT 0, last_seen INTEGER,
                PRIMARY KEY(user_id, chat_id));

            CREATE TABLE IF NOT EXISTS approved_users(
                user_id INTEGER, chat_id INTEGER,
                PRIMARY KEY(user_id, chat_id));

            CREATE TABLE IF NOT EXISTS captcha_pending(
                user_id INTEGER, chat_id INTEGER,
                answer INTEGER, expires INTEGER, msg_id INTEGER,
                PRIMARY KEY(user_id, chat_id));

            CREATE TABLE IF NOT EXISTS bot_users(
                user_id    INTEGER PRIMARY KEY,
                username   TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                lang       TEXT DEFAULT 'en',
                started_at INTEGER);
        """)
        await db.commit()


# ══════════════════════════════════════════════════════════════════════════════
# WARNINGS
# ══════════════════════════════════════════════════════════════════════════════

async def get_warnings(uid: int, cid: int) -> tuple[int, list[str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT count, reasons FROM warnings WHERE user_id=? AND chat_id=?", (uid, cid)
        ) as c:
            row = await c.fetchone()
    if row:
        return row[0], [r for r in row[1].split("|||") if r]
    return 0, []

async def add_warning(uid: int, cid: int, reason: str = "") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO warnings(user_id,chat_id,count,reasons) VALUES(?,?,1,?)"
            " ON CONFLICT(user_id,chat_id) DO UPDATE SET count=count+1, reasons=reasons||?",
            (uid, cid, reason+"|||", reason+"|||"))
        await db.commit()
        async with db.execute(
            "SELECT count FROM warnings WHERE user_id=? AND chat_id=?", (uid, cid)
        ) as c:
            row = await c.fetchone()
    return row[0] if row else 0

async def remove_warning(uid: int, cid: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT count, reasons FROM warnings WHERE user_id=? AND chat_id=?", (uid, cid)
        ) as c:
            row = await c.fetchone()
        if not row or row[0] == 0:
            return 0
        reasons = [r for r in row[1].split("|||") if r]
        if reasons: reasons.pop()
        new = max(0, row[0] - 1)
        await db.execute(
            "UPDATE warnings SET count=?,reasons=? WHERE user_id=? AND chat_id=?",
            (new, "|||".join(reasons)+("|||" if reasons else ""), uid, cid))
        await db.commit()
    return new

async def reset_warnings(uid: int, cid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM warnings WHERE user_id=? AND chat_id=?", (uid, cid))
        await db.commit()


# ══════════════════════════════════════════════════════════════════════════════
# WORD FILTERS
# ══════════════════════════════════════════════════════════════════════════════

async def get_filters(cid: int) -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT word FROM word_filters WHERE chat_id=?", (cid,)) as c:
            return [r[0] for r in await c.fetchall()]

async def add_filter(cid: int, word: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO word_filters VALUES(?,?)", (cid, word.lower()))
        await db.commit()

async def remove_filter(cid: int, word: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM word_filters WHERE chat_id=? AND word=?", (cid, word.lower()))
        await db.commit()


# ══════════════════════════════════════════════════════════════════════════════
# WELCOME / RULES
# ══════════════════════════════════════════════════════════════════════════════

_WELCOME_FIELDS = {"welcome_msg","goodbye_msg","rules_text","enabled","captcha","captcha_timeout"}

async def get_welcome(cid: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT welcome_msg,goodbye_msg,rules_text,enabled,captcha,captcha_timeout"
            " FROM welcome WHERE chat_id=?", (cid,)
        ) as c:
            row = await c.fetchone()
    if row:
        return dict(zip(
            ["welcome_msg","goodbye_msg","rules_text","enabled","captcha","captcha_timeout"],
            row))
    return {"welcome_msg":"","goodbye_msg":"","rules_text":"",
            "enabled":True,"captcha":False,"captcha_timeout":60}

async def set_welcome_field(cid: int, field: str, value):
    if field not in _WELCOME_FIELDS: raise ValueError(f"bad field: {field}")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"INSERT INTO welcome(chat_id,{field}) VALUES(?,?)"
            f" ON CONFLICT(chat_id) DO UPDATE SET {field}=?",
            (cid, value, value))
        await db.commit()

async def get_rules(cid: int) -> str:
    w = await get_welcome(cid)
    return w.get("rules_text", "")

async def set_rules(cid: int, text: str):
    await set_welcome_field(cid, "rules_text", text)


# ══════════════════════════════════════════════════════════════════════════════
# LEFT MEMBERS
# ══════════════════════════════════════════════════════════════════════════════

async def mark_left(uid: int, cid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO left_members VALUES(?,?)", (uid, cid))
        await db.commit()

async def has_left(uid: int, cid: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM left_members WHERE user_id=? AND chat_id=?", (uid, cid)
        ) as c:
            return await c.fetchone() is not None

async def clear_left(uid: int, cid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM left_members WHERE user_id=? AND chat_id=?", (uid, cid))
        await db.commit()


# ══════════════════════════════════════════════════════════════════════════════
# CHAT SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

_SETTING_KEYS = {
    "auto_ban_leavers","anti_flood","flood_limit","locked",
    "link_filter","sticker_filter","media_filter","bot_filter",
    "slowmode","warn_limit","warn_action",
}
_BOOL_SETTINGS = {
    "auto_ban_leavers","anti_flood","locked",
    "link_filter","sticker_filter","media_filter","bot_filter",
}

async def get_settings(cid: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT auto_ban_leavers,anti_flood,flood_limit,locked,"
            "link_filter,sticker_filter,media_filter,bot_filter,"
            "slowmode,warn_limit,warn_action FROM chat_settings WHERE chat_id=?", (cid,)
        ) as c:
            row = await c.fetchone()
    keys = ["auto_ban_leavers","anti_flood","flood_limit","locked",
            "link_filter","sticker_filter","media_filter","bot_filter",
            "slowmode","warn_limit","warn_action"]
    if row:
        d = dict(zip(keys, row))
        for k in _BOOL_SETTINGS: d[k] = bool(d[k])
        return d
    return {"auto_ban_leavers":False,"anti_flood":True,"flood_limit":5,"locked":False,
            "link_filter":False,"sticker_filter":False,"media_filter":False,"bot_filter":False,
            "slowmode":0,"warn_limit":3,"warn_action":"ban"}

async def set_setting(cid: int, key: str, value):
    if key not in _SETTING_KEYS: raise ValueError(f"bad key: {key}")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"INSERT INTO chat_settings(chat_id,{key}) VALUES(?,?)"
            f" ON CONFLICT(chat_id) DO UPDATE SET {key}=?",
            (cid, value, value))
        await db.commit()


# ══════════════════════════════════════════════════════════════════════════════
# NOTES
# ══════════════════════════════════════════════════════════════════════════════

async def get_note(cid: int, name: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT content,file_id,file_type FROM notes WHERE chat_id=? AND name=?",
            (cid, name.lower())
        ) as c:
            row = await c.fetchone()
    return {"content":row[0],"file_id":row[1],"file_type":row[2]} if row else None

async def save_note(cid: int, name: str, content: str, file_id: str = "", file_type: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO notes VALUES(?,?,?,?,?)"
            " ON CONFLICT(chat_id,name) DO UPDATE SET content=?,file_id=?,file_type=?",
            (cid, name.lower(), content, file_id, file_type, content, file_id, file_type))
        await db.commit()

async def delete_note(cid: int, name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM notes WHERE chat_id=? AND name=?", (cid, name.lower()))
        await db.commit()

async def list_notes(cid: int) -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT name FROM notes WHERE chat_id=? ORDER BY name", (cid,)
        ) as c:
            return [r[0] for r in await c.fetchall()]


# ══════════════════════════════════════════════════════════════════════════════
# GIVEAWAY
# ══════════════════════════════════════════════════════════════════════════════

async def create_giveaway(cid, msg_id, prize, winners, end_time, creator) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO giveaways(chat_id,message_id,prize,winners_count,end_time,created_by)"
            " VALUES(?,?,?,?,?,?)", (cid, msg_id, prize, winners, end_time, creator))
        await db.commit()
        return cur.lastrowid

async def get_giveaway(gid: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id,chat_id,message_id,prize,winners_count,end_time,ended,created_by"
            " FROM giveaways WHERE id=?", (gid,)
        ) as c:
            row = await c.fetchone()
    if not row: return None
    return dict(zip(
        ["id","chat_id","message_id","prize","winners_count","end_time","ended","created_by"],
        row))

async def get_active_giveaway(cid: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id,chat_id,message_id,prize,winners_count,end_time,ended,created_by"
            " FROM giveaways WHERE chat_id=? AND ended=0 ORDER BY id DESC LIMIT 1", (cid,)
        ) as c:
            row = await c.fetchone()
    if not row: return None
    return dict(zip(
        ["id","chat_id","message_id","prize","winners_count","end_time","ended","created_by"],
        row))

async def join_giveaway(gid: int, uid: int, name: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO giveaway_participants VALUES(?,?,?,?)",
                (gid, uid, name, int(time.time())))
            await db.commit()
            return True
        except Exception:
            return False

async def get_participants(gid: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id,user_name FROM giveaway_participants WHERE giveaway_id=?", (gid,)
        ) as c:
            return [{"user_id":r[0],"user_name":r[1]} for r in await c.fetchall()]

async def end_giveaway(gid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE giveaways SET ended=1 WHERE id=?", (gid,))
        await db.commit()


# ══════════════════════════════════════════════════════════════════════════════
# KNOWN CHATS / AFK / STATS / CAPTCHA / APPROVED
# ══════════════════════════════════════════════════════════════════════════════

async def register_chat(cid: int, ctype: str, title: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO known_chats VALUES(?,?,?,?)"
            " ON CONFLICT(chat_id) DO UPDATE SET title=?",
            (cid, ctype, title, int(time.time()), title))
        await db.commit()

async def get_all_chats() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT chat_id,chat_type,title FROM known_chats") as c:
            return [{"chat_id":r[0],"chat_type":r[1],"title":r[2]} for r in await c.fetchall()]

async def set_afk(uid: int, reason: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO afk_users VALUES(?,?,?)"
            " ON CONFLICT(user_id) DO UPDATE SET reason=?,since=?",
            (uid, reason, int(time.time()), reason, int(time.time())))
        await db.commit()

async def get_afk(uid: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT reason,since FROM afk_users WHERE user_id=?", (uid,)
        ) as c:
            row = await c.fetchone()
    return {"reason":row[0],"since":row[1]} if row else None

async def clear_afk(uid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM afk_users WHERE user_id=?", (uid,))
        await db.commit()

async def bump_stats(uid: int, cid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO user_stats VALUES(?,?,1,?)"
            " ON CONFLICT(user_id,chat_id) DO UPDATE SET messages=messages+1,last_seen=?",
            (uid, cid, int(time.time()), int(time.time())))
        await db.commit()

async def top_users(cid: int, n: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id,messages FROM user_stats WHERE chat_id=?"
            " ORDER BY messages DESC LIMIT ?", (cid, n)
        ) as c:
            return [{"user_id":r[0],"messages":r[1]} for r in await c.fetchall()]

async def set_captcha_pending(uid: int, cid: int, answer: int, expires: int, msg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO captcha_pending VALUES(?,?,?,?,?)",
            (uid, cid, answer, expires, msg_id))
        await db.commit()

async def get_captcha_pending(uid: int, cid: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT answer,expires,msg_id FROM captcha_pending WHERE user_id=? AND chat_id=?",
            (uid, cid)
        ) as c:
            row = await c.fetchone()
    return {"answer":row[0],"expires":row[1],"msg_id":row[2]} if row else None

async def clear_captcha_pending(uid: int, cid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM captcha_pending WHERE user_id=? AND chat_id=?", (uid, cid))
        await db.commit()

async def register_user(uid: int, username: str, first_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO bot_users(user_id,username,first_name,started_at) VALUES(?,?,?,?)"
            " ON CONFLICT(user_id) DO UPDATE SET username=?,first_name=?",
            (uid, username, first_name, int(time.time()), username, first_name))
        await db.commit()

async def get_user_lang(uid: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT lang FROM bot_users WHERE user_id=?", (uid,)
        ) as c:
            row = await c.fetchone()
    return row[0] if row else "en"

async def set_user_lang(uid: int, lang: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO bot_users(user_id,lang,started_at) VALUES(?,?,?)"
            " ON CONFLICT(user_id) DO UPDATE SET lang=?",
            (uid, lang, int(time.time()), lang))
        await db.commit()

async def get_all_users() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id,username,first_name,started_at FROM bot_users ORDER BY started_at DESC"
        ) as c:
            return [{"user_id": r[0], "username": r[1], "first_name": r[2], "started_at": r[3]}
                    for r in await c.fetchall()]


async def get_chat_member_ids(cid: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, messages, last_seen FROM user_stats WHERE chat_id=? ORDER BY messages DESC",
            (cid,)
        ) as c:
            return [{"user_id": r[0], "messages": r[1], "last_seen": r[2]}
                    for r in await c.fetchall()]


async def get_user_stats(uid: int, cid: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT messages, last_seen FROM user_stats WHERE user_id=? AND chat_id=?",
            (uid, cid)
        ) as c:
            row = await c.fetchone()
    return {"messages": row[0], "last_seen": row[1]} if row else None


async def approve(uid: int, cid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO approved_users VALUES(?,?)", (uid, cid))
        await db.commit()

async def unapprove(uid: int, cid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM approved_users WHERE user_id=? AND chat_id=?", (uid, cid))
        await db.commit()

async def is_approved(uid: int, cid: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM approved_users WHERE user_id=? AND chat_id=?", (uid, cid)
        ) as c:
            return await c.fetchone() is not None
