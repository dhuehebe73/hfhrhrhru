import os, sys
from dotenv import load_dotenv

load_dotenv()

# ── Token ─────────────────────────────────────────────────────────────────────
TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
if not TOKEN:
    print("\n╔═══════════════════════════════╗")
    print("║   BOT TOKEN GIR               ║")
    print("╚═══════════════════════════════╝")
    TOKEN = input("Token: ").strip()
    if TOKEN:
        with open(".env", "a") as f:
            f.write(f"\nBOT_TOKEN={TOKEN}\n")
        print("✓ Token kaydedildi.\n")
    else:
        print("Token girilmedi. Cikiliyor.")
        sys.exit(1)

# ── Diger ─────────────────────────────────────────────────────────────────────
OWNER_ID: int    = int(os.getenv("OWNER_ID", "8342801633"))
DB_PATH: str     = os.getenv("DATABASE_PATH", "bot.db")
WARN_LIMIT: int  = int(os.getenv("WARN_LIMIT", "3"))
WARN_ACTION: str = os.getenv("WARN_ACTION", "ban")
LOG_CHANNEL: int = int(os.getenv("LOG_CHANNEL", "0"))
