import logging
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict

from playwright_captcha import CaptchaType


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    log_level: str = "INFO"
    version: str = "unknown"

    max_attempts: int = sys.maxsize

    proxy_server: str | None = None
    proxy_username: str | None = None
    proxy_password: str | None = None

    host: str = "0.0.0.0"  # noqa: S104
    port: int = 8191

    block_media: bool = False
    return_only_cookies: bool = False


settings = Settings()

LOG_LEVEL = logging.getLevelNamesMapping()[settings.log_level.upper()]
VERSION = settings.version.removeprefix("v")

MAX_ATTEMPTS = settings.max_attempts

PROXY_SERVER = settings.proxy_server
PROXY_USERNAME = settings.proxy_username
PROXY_PASSWORD = settings.proxy_password

HOST = settings.host
PORT = settings.port

BLOCK_MEDIA = settings.block_media
RETURN_ONLY_COOKIES = settings.return_only_cookies

CHALLENGE_TITLES_MAP: dict[CaptchaType, list[str]] = {
    # Cloudflare
    CaptchaType.CLOUDFLARE_INTERSTITIAL: ["Just a moment..."],
}

CHALLENGE_TITLES = [
    title for titles in CHALLENGE_TITLES_MAP.values() for title in titles
]
