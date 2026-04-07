import aiosqlite
from config import DATABASE_PATH


async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS warnings (
                user_id   INTEGER,
                chat_id   INTEGER,
                count     INTEGER DEFAULT 0,
                reasons   TEXT    DEFAULT '',
                PRIMARY KEY (user_id, chat_id)
            );
            CREATE TABLE IF NOT EXISTS word_filters (
                chat_id INTEGER,
                word    TEXT,
                PRIMARY KEY (chat_id, word)
            );
            CREATE TABLE IF NOT EXISTS welcome (
                chat_id  INTEGER PRIMARY KEY,
                message  TEXT DEFAULT '',
                goodbye  TEXT DEFAULT '',
                enabled  INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS rules (
                chat_id INTEGER PRIMARY KEY,
                content TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS left_members (
                user_id INTEGER,
                chat_id INTEGER,
                PRIMARY KEY (user_id, chat_id)
            );
            CREATE TABLE IF NOT EXISTS chat_settings (
                chat_id          INTEGER PRIMARY KEY,
                auto_ban_leavers INTEGER DEFAULT 0,
                anti_flood       INTEGER DEFAULT 1,
                flood_limit      INTEGER DEFAULT 5,
                locked           INTEGER DEFAULT 0
            );
        """)
        await db.commit()


# ─── Warnings ────────────────────────────────────────────────────────────────

async def get_warnings(user_id: int, chat_id: int) -> tuple[int, list[str]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT count, reasons FROM warnings WHERE user_id=? AND chat_id=?",
            (user_id, chat_id),
        ) as cur:
            row = await cur.fetchone()
            if row:
                reasons = [r for r in row[1].split("|||") if r]
                return row[0], reasons
            return 0, []


async def add_warning(user_id: int, chat_id: int, reason: str = "") -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO warnings (user_id, chat_id, count, reasons)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(user_id, chat_id) DO UPDATE SET
                count   = count + 1,
                reasons = reasons || ?
            """,
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
        new_count = max(0, row[0] - 1)
        await db.execute(
            "UPDATE warnings SET count=?, reasons=? WHERE user_id=? AND chat_id=?",
            (new_count, "|||".join(reasons) + ("|||" if reasons else ""), user_id, chat_id),
        )
        await db.commit()
        return new_count


async def reset_warnings(user_id: int, chat_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM warnings WHERE user_id=? AND chat_id=?", (user_id, chat_id)
        )
        await db.commit()


# ─── Word Filters ─────────────────────────────────────────────────────────────

async def get_filters(chat_id: int) -> list[str]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT word FROM word_filters WHERE chat_id=?", (chat_id,)
        ) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def add_filter(chat_id: int, word: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO word_filters (chat_id, word) VALUES (?, ?)",
            (chat_id, word.lower()),
        )
        await db.commit()


async def remove_filter(chat_id: int, word: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM word_filters WHERE chat_id=? AND word=?",
            (chat_id, word.lower()),
        )
        await db.commit()


# ─── Welcome / Goodbye ───────────────────────────────────────────────────────

async def get_welcome(chat_id: int) -> tuple[str, str, bool]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT message, goodbye, enabled FROM welcome WHERE chat_id=?", (chat_id,)
        ) as cur:
            row = await cur.fetchone()
            if row:
                return row[0], row[1], bool(row[2])
            return "", "", True


async def set_welcome(chat_id: int, message: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO welcome (chat_id, message) VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET message=?
            """,
            (chat_id, message, message),
        )
        await db.commit()


async def set_goodbye(chat_id: int, message: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO welcome (chat_id, goodbye) VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET goodbye=?
            """,
            (chat_id, message, message),
        )
        await db.commit()


# ─── Rules ───────────────────────────────────────────────────────────────────

async def get_rules(chat_id: int) -> str:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT content FROM rules WHERE chat_id=?", (chat_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else ""


async def set_rules(chat_id: int, content: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO rules (chat_id, content) VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET content=?
            """,
            (chat_id, content, content),
        )
        await db.commit()


# ─── Left-Members (auto-ban rejoin) ──────────────────────────────────────────

async def mark_left(user_id: int, chat_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO left_members (user_id, chat_id) VALUES (?, ?)",
            (user_id, chat_id),
        )
        await db.commit()


async def has_left_before(user_id: int, chat_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM left_members WHERE user_id=? AND chat_id=?",
            (user_id, chat_id),
        ) as cur:
            return await cur.fetchone() is not None


async def clear_left(user_id: int, chat_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM left_members WHERE user_id=? AND chat_id=?",
            (user_id, chat_id),
        )
        await db.commit()


# ─── Chat Settings ────────────────────────────────────────────────────────────

_ALLOWED_SETTINGS = {"auto_ban_leavers", "anti_flood", "flood_limit", "locked"}


async def get_chat_settings(chat_id: int) -> dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT auto_ban_leavers, anti_flood, flood_limit, locked "
            "FROM chat_settings WHERE chat_id=?",
            (chat_id,),
        ) as cur:
            row = await cur.fetchone()
            if row:
                return {
                    "auto_ban_leavers": bool(row[0]),
                    "anti_flood": bool(row[1]),
                    "flood_limit": row[2],
                    "locked": bool(row[3]),
                }
            return {
                "auto_ban_leavers": False,
                "anti_flood": True,
                "flood_limit": 5,
                "locked": False,
            }


async def update_chat_setting(chat_id: int, key: str, value):
    if key not in _ALLOWED_SETTINGS:
        raise ValueError(f"Invalid setting key: {key}")
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            f"""
            INSERT INTO chat_settings (chat_id, {key}) VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET {key}=?
            """,
            (chat_id, value, value),
        )
        await db.commit()
