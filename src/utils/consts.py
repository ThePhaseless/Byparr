import logging
import os

LOG_LEVEL = os.getenv("LOG_LEVEL") or "INFO"
LOG_LEVEL = logging.getLevelNamesMapping()[LOG_LEVEL.upper()]

CHALLENGE_TITLES = [
    # Cloudflare
    "Just a moment...",
    # DDoS-GUARD
    "DDoS-Guard",
]
