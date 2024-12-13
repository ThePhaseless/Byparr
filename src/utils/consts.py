import logging
import os
import time

import psutil

from src.utils import logger


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

def kill_chromium_processes():
    # Define the prefix and time threshold
    prefix = "chromium"
    time_threshold = 300  # 5 minutes in seconds

    # Get the current time
    current_time = time.time()

    # Iterate through all processes
    for proc in psutil.process_iter(['pid', 'name', 'create_time']):
        try:
            # Extract process details
            pid = proc.info['pid']
            name:str = proc.info['name']
            create_time = proc.info['create_time']

            # Check if the process name starts with the prefix and has been running longer than the threshold
            if name and name.startswith(prefix) and (current_time - create_time > time_threshold):
                logger.info(f"Terminating process {name} (PID: {pid}) running for {int(current_time - create_time)} seconds")
                psutil.Process(pid).terminate()  # Terminate the process

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # Ignore processes that no longer exist or can't be accessed
            pass

LOG_LEVEL = os.getenv("LOG_LEVEL") or "INFO"
LOG_LEVEL = logging.getLevelNamesMapping()[LOG_LEVEL.upper()]

VERSION = get_version_from_env() or "unknown"

MAX_CHROME_LIFETIME= int(os.getenv("MAX_CHROME_LIFETIME", 300))


CHALLENGE_TITLES = [
    # Cloudflare
    "Just a moment...",
    # DDoS-GUARD
    "DDoS-Guard",
]
