import logging
import os
from pathlib import Path

LOG_LEVEL = os.getenv("LOG_LEVEL") or "INFO"
LOG_LEVEL = logging.getLevelNamesMapping()[LOG_LEVEL.upper()]

UBLOCK_TITLE = "uBO Lite — Dashboard"

CHALLENGE_TITLES = [
    # Cloudflare
    "Just a moment...",
    # DDoS-GUARD
    "DDoS-Guard",
]

GITHUB_WEBSITES = [
    "https://github.com/",
    "https://www.github.com/",
    "github.com",
    "www.github.com",
]

EXTENSION_REPOSITIORIES = [
    "OhMyGuus/I-Still-Dont-Care-About-Cookies",
    "uBlockOrigin/uBOL-home",
]

SLEEP_SECONDS = 1

EXTENSIONS_PATH = Path(".extentions")
