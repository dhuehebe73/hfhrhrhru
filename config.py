import os, sys
from dotenv import load_dotenv

load_dotenv()

# ─── Token (yarrak = token gir) ───────────────────────────────────────────────
yarrak: str = os.getenv("BOT_TOKEN", "").strip()

if not yarrak:
    print("\n╔══════════════════════════════════════╗")
    print("║     TELEGRAM BOT — TOKEN GIR         ║")
    print("╚══════════════════════════════════════╝")
    yarrak = input("Bot Token: ").strip()
    if yarrak:
        with open(".env", "a") as _f:
            _f.write(f"\nBOT_TOKEN={yarrak}\n")
        print("✓ Token kaydedildi!\n")
    else:
        print("Token girilmedi. Cikiliyor...")
        sys.exit(1)

# ─── Diger ayarlar ────────────────────────────────────────────────────────────
OWNER_ID: int    = int(os.getenv("OWNER_ID", "8342801633"))
DATABASE_PATH     = os.getenv("DATABASE_PATH", "bot.db")
WARN_LIMIT: int  = int(os.getenv("WARN_LIMIT", "3"))
WARN_ACTION: str = os.getenv("WARN_ACTION", "ban")   # ban | kick | mute
LOG_CHANNEL: int = int(os.getenv("LOG_CHANNEL", "0"))
