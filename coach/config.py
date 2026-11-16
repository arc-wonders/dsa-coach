import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


DATABASE_URL = env("DATABASE_URL") or env("POSTGRES_URL")
DB_PATH = Path(env("DB_PATH", str(ROOT / "coach.db")))
TZ = ZoneInfo(env("TIMEZONE", "Asia/Kolkata"))

LEETCODE_USERNAME = env("LEETCODE_USERNAME", "arkinkansra")
LEETCODE_SESSION = env("LEETCODE_SESSION")
LEETCODE_CSRF = env("LEETCODE_CSRFTOKEN")

GMAIL_ADDRESS = env("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = env("GMAIL_APP_PASSWORD").replace(" ", "")
MAIL_TO = env("MAIL_TO") or GMAIL_ADDRESS

GEMINI_API_KEY = env("GEMINI_API_KEY")
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-3.8-flash")

# Public URL of the web app; used for the buttons inside emails.
BASE_URL = env("BASE_URL", "http://localhost:8000").rstrip("/")
SECRET_KEY = env("SECRET_KEY", "change-me")
APP_PASSWORD = env("APP_PASSWORD")  # empty = no login (fine for localhost only)

DAILY_SEND_TIME = env("DAILY_SEND_TIME", "07:00")  # HH:MM in TIMEZONE
ENABLE_SCHEDULER = env("ENABLE_SCHEDULER", "true").lower() == "true" and not env("VERCEL")
CRON_SECRET = env("CRON_SECRET")
