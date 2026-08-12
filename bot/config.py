"""Bot config — thin wrapper over shared core.config."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

# monorepo root on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import config as core_config  # noqa: E402

BOT_TOKEN = core_config.BOT_TOKEN
SUPER_ADMIN_ID = core_config.SUPER_ADMIN_ID
ADMIN_GROUP_ID = core_config.ADMIN_GROUP_ID
BOT_API_BASE_URL = core_config.BOT_API_BASE_URL

# FSM states
STATE_IDLE = core_config.STATE_IDLE
STATE_WAITING_MESSAGE = core_config.STATE_WAITING_MESSAGE
STATE_WAITING_DELAY = core_config.STATE_WAITING_DELAY
STATE_WAITING_CONTACT = core_config.STATE_WAITING_CONTACT
STATE_IMPORTING = core_config.STATE_IMPORTING

BOT_START_TIME = datetime.now()
