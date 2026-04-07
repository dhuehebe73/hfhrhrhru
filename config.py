import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
OWNER_ID: int = int(os.getenv("OWNER_ID", "0"))
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "bot.db")
WARN_LIMIT: int = int(os.getenv("WARN_LIMIT", "3"))
LOG_CHANNEL: int = int(os.getenv("LOG_CHANNEL", "0"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN ayarlanmamis! .env dosyasini kontrol et.")
