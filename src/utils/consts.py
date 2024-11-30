import logging
import os


def get_version_from_env():
    """
    Retrieve the version from the environment variable 'VERSION'.

    This function checks the 'VERSION' environment variable for a value
    that starts with 'v' and returns the version without the prefix.

    Returns:
        str | None: The version string without the 'v' prefix, or None if
        the 'VERSION' environment variable is not set or does not start
        with 'v'.

    """
    version_env = os.getenv("VERSION")
    if not version_env or not version_env.startswith("v"):
        return None

    return version_env.removeprefix("v")


LOG_LEVEL = os.getenv("LOG_LEVEL") or "INFO"
LOG_LEVEL = logging.getLevelNamesMapping()[LOG_LEVEL.upper()]

VERSION = get_version_from_env() or "unknown"


CHALLENGE_TITLES = [
    # Cloudflare
    "Just a moment...",
    # DDoS-GUARD
    "DDoS-Guard",
]
