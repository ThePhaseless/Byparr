import logging
import os
import sys
from pathlib import Path

from playwright_captcha import CaptchaType
from playwright_captcha.utils.camoufox_add_init_script.add_init_script import (
    get_addon_path,
)

LOG_LEVEL = logging.getLevelNamesMapping()[os.getenv("LOG_LEVEL", "INFO").upper()]

VERSION = os.getenv("VERSION", "unknown").removeprefix("v")

ADDON_PATH = str(Path(get_addon_path()).absolute())
MAX_ATTEMPTS = sys.maxsize

PROXY_SERVER = os.getenv("PROXY_SERVER")
PROXY_USERNAME = os.getenv("PROXY_USERNAME")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD")

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8191"))

CHALLENGE_TITLES_MAP: dict[CaptchaType, list[str]] = {
    # Cloudflare
    CaptchaType.CLOUDFLARE_INTERSTITIAL: ["Just a moment..."],
}

CHALLENGE_TITLES = [
    title for titles in CHALLENGE_TITLES_MAP.values() for title in titles
]
