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
    if not version_env:
        return None

    return version_env.removeprefix("v")


def parse_bool_env(env_name, default=None):
    """
    Parse boolean environment variables.

    Accepts various formats: 1, 0, true, false, yes, no in any capit.

    Args:
        env_name (str): The name of the environment variable
        default (bool | None): Default value if env var doesn't exist or can't be parsed

    Returns:
        bool | None: The parsed boolean value or default

    """
    env_value = os.getenv(env_name)
    if env_value is None:
        return default

    true_values = ["1", "true", "yes"]
    false_values = ["0", "false", "no"]

    if env_value.lower() in true_values:
        return True
    if env_value.lower() in false_values:
        return False
    return default


LOG_LEVEL = os.getenv("LOG_LEVEL") or "INFO"

VERSION = get_version_from_env()

USE_XVFB = parse_bool_env("USE_XVFB")

USE_HEADLESS = parse_bool_env("USE_HEADLESS")

PROXY = os.getenv("PROXY")

CHALLENGE_TITLES = [
    # Cloudflare
    "Just a moment...",
    # DDoS-GUARD
    "DDoS-Guard",
]
