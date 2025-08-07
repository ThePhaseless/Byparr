import logging
import os

from playwright_captcha import CaptchaType  # pyright: ignore[reportMissingTypeStubs]

LOG_LEVEL = logging.getLevelNamesMapping()[os.getenv("LOG_LEVEL", "INFO").upper()]

VERSION = os.getenv("VERSION", "unknown").removeprefix("v")

HEADLESS_MODE = os.getenv("HEADLESS_MODE", "virtual")

PROXY = os.getenv("PROXY")

CHALLENGE_TITLES_MAP: dict[CaptchaType, list[str]] = {
    # Cloudflare
    CaptchaType.CLOUDFLARE_INTERSTITIAL: ["Just a moment..."],
}

CHALLENGE_TITLES = [
    title for titles in CHALLENGE_TITLES_MAP.values() for title in titles
]
