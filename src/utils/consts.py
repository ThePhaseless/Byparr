import logging
import os
from pathlib import Path

LOG_LEVEL = os.getenv("LOG_LEVEL") or "INFO"
LOG_LEVEL = logging.getLevelName(LOG_LEVEL.upper())

CHALLENGE_TITLES = [
    # Cloudflare
    "Just a moment...",
    # DDoS-GUARD
    "DDoS-Guard",
]

EXTENTION_REPOSITIORIES = [
    "OhMyGuus/I-Still-Dont-Care-About-Cookies",
    "uBlockOrigin/uBOL-home",
]

SLEEP_SECONDS = 1

EXTENTIONS_PATH = Path(".extentions")
