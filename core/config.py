"""Shared configuration loaded from environment / .env files."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("TG_SENDER_DATA_DIR", ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_DB_PATH = DATA_DIR / "sender.db"


def _load_dotenv() -> None:
    candidates = [
        ROOT / ".env",
        ROOT / "bot" / ".env",
    ]
    for env_path in candidates:
        if not env_path.is_file():
            continue
        try:
            text = env_path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip("\"'"))


_load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SUPER_ADMIN_ID = int(os.environ.get("SUPER_ADMIN_ID", "0") or "0")
ADMIN_GROUP_ID_STR = os.environ.get("ADMIN_GROUP_ID", "").strip()
ADMIN_GROUP_ID = (
    int(ADMIN_GROUP_ID_STR) if ADMIN_GROUP_ID_STR.lstrip("-").isdigit() else None
)

DB_PATH = Path(os.environ.get("TG_SENDER_DB_PATH", str(DEFAULT_DB_PATH)))

# FSM states
STATE_IDLE = 0
STATE_WAITING_MESSAGE = 1
STATE_WAITING_DELAY = 2
STATE_WAITING_CONTACT = 3
STATE_IMPORTING = 4
