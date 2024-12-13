import logging
import time

import psutil

from src.utils.consts import LOG_LEVEL, MAX_CHROME_LIFETIME

logger = logging.getLogger("uvicorn.error")
logger.setLevel(LOG_LEVEL)
if len(logger.handlers) == 0:
    logger.addHandler(logging.StreamHandler())


def kill_chromium_processes():
    # Define the prefix and time threshold
    """
    Kill all chromium processes that have been running longer than the specified time threshold.

    This is used to clean up any rogue chromium processes that may be left behind.
    """
    prefix = "chromium"
    time_threshold = MAX_CHROME_LIFETIME

    # Get the current time
    current_time = time.time()

    # Iterate through all processes
    for proc in psutil.process_iter(["pid", "name", "create_time"]):
        try:
            # Extract process details
            pid = proc.info["pid"]
            name: str = proc.info["name"]
            create_time = proc.info["create_time"]

            # Check if the process name starts with the prefix and has been running longer than the threshold
            if (
                name
                and name.startswith(prefix)
                and (current_time - create_time > time_threshold)
            ):
                logger.info(
                    f"Terminating process {name} (PID: {pid}) running for {int(current_time - create_time)} seconds"
                )
                psutil.Process(pid).terminate()  # Terminate the process

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # Ignore processes that no longer exist or can't be accessed
            pass
