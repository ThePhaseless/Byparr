# https://github.com/ultrafunkamsterdam/undetected-chromedriver/issues/1954
# Fix for nodriver in .venv/lib/python3.11/site-packages/nodriver/core/browser.py
from __future__ import annotations

import logging
import os
from pathlib import Path

env_path = os.getenv("VIRTUAL_ENV")
if env_path is None:
    env_path = Path(os.__file__).parent.parent.parent.as_posix()
nodriver_path = Path(env_path + "/lib/python3.11/site-packages/nodriver/cdp/network.py")


new_cookie_partition_key = """\
        if isinstance(json, str):
            return cls(top_level_site=json, has_cross_site_ancestor=False)
        elif isinstance(json, dict):
            return cls(
                top_level_site=str(json["topLevelSite"]),
                has_cross_site_ancestor=bool(json["hasCrossSiteAncestor"]),
            )
"""

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.info(f"Fixing nodriver in {nodriver_path}")
# delete CookiePartitionKey declaration
with nodriver_path.open("r+") as f:
    lines = f.readlines()
    found_def = False
    found_body = False
    i = -1
    while i < len(lines):
        i += 1
        line = lines[i]
        strip_line = line.strip("\n")
        if not found_def and line.startswith("class CookiePartitionKey:"):
            logger.info(f"Found line {i}: {strip_line}")
            found_def = True
            continue
        if found_def:
            if line.startswith("    def from_json"):
                logger.info(f"Found line {i}: {strip_line}")
                found_body = True
                continue
            if found_body:
                if line.startswith(("\t\t", "        ")):
                    logger.info(f"Removing line {i}: {strip_line}")
                    lines.pop(i)
                    i -= 1
                    continue
                else:
                    lines = lines[:i] + [new_cookie_partition_key] + lines[i:]
                    break


with nodriver_path.open("w") as f:
    f.writelines(lines)
