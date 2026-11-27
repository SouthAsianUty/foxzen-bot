import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory
BASE_DIR = Path(__file__).resolve().parent

# Load .env file
load_dotenv(BASE_DIR / ".env")

# App configurations
BOT_TOKEN = os.getenv("BOT_TOKEN", "8444936570:AAHPhqLVDQuhTYohxasvJoXHLBguMrEGecY").strip()
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "9088050558:AAEpzubiyrQWFUMOGiHGc1iJD1JqdV21G5A").strip()
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID", "6443134339").strip()

BINANCE_PAY_ID = os.getenv("BINANCE_PAY_ID", "").strip()
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "").strip()
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "").strip()

WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("PORT", os.getenv("WEB_PORT", "8000")))
SECRET_KEY = os.getenv("SECRET_KEY", "foxzen_default_secret_key_change_me")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# Database Path (supports persistent volume e.g. /data in Railway / Docker)
DATA_DIR = os.getenv("DATA_DIR", "").strip()
if DATA_DIR:
    data_dir_path = Path(DATA_DIR)
    data_dir_path.mkdir(parents=True, exist_ok=True)
    target_db = data_dir_path / "bot_database.db"
    source_db = BASE_DIR / "bot_database.db"
    if not target_db.exists() and source_db.exists():
        import shutil
        shutil.copy2(source_db, target_db)
    DB_PATH = target_db
else:
    DB_PATH = BASE_DIR / "bot_database.db"
