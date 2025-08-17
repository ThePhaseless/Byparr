import logging
import os
from pathlib import Path

from playwright_captcha import CaptchaType
from playwright_captcha.utils.camoufox_add_init_script.add_init_script import (
    get_addon_path,
)

LOG_LEVEL = logging.getLevelNamesMapping()[os.getenv("LOG_LEVEL", "INFO").upper()]

VERSION = os.getenv("VERSION", "unknown").removeprefix("v")

HEADLESS_MODE = os.getenv("HEADLESS_MODE") or True

ADDON_PATH = str(Path(get_addon_path()).absolute())

PROXY = os.getenv("PROXY")

CHALLENGE_TITLES_MAP: dict[CaptchaType, list[str]] = {
    # Cloudflare
    CaptchaType.CLOUDFLARE_INTERSTITIAL: ["Just a moment..."],
}

CHALLENGE_TITLES = [
    title for titles in CHALLENGE_TITLES_MAP.values() for title in titles
]
