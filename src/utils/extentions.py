from __future__ import annotations

import io
import json
from pathlib import Path
from zipfile import ZipFile

import httpx
import requests

from src.models.github import GithubResponse
from src.models.requests import NoChromeExtentionError
from src.utils import logger
from src.utils.consts import EXTENTION_REPOSITIORIES, EXTENTIONS_PATH, GITHUB_WEBSITES


def get_latest_github_chrome_release(url: str):
    """
    Get the latest release for chrome from GitHub for a given repository URL.

    Args:
    ----
        url (str): The URL of the GitHub repository.

    Returns:
    -------
        GithubResponse: The latest release asset with 'chrom' in its name.

    Raises:
    ------
        httpx.NetworkError: If the request to GitHub API returns a 403 Forbidden status code.
        NoChromeExtentionError: If no release asset with 'chrom' in its name is found.

    """
    if url.startswith(tuple(GITHUB_WEBSITES)):
        url = "/".join(url.split("/")[-2:])
    url = "https://api.github.com/repos/" + url + "/releases/latest"

    response = httpx.get(url)
    if response.status_code == httpx.codes.FORBIDDEN:
        error = json.loads(response.text)["message"]
        logger.error(error)
        raise httpx.NetworkError(error)
    response = GithubResponse(**response.json())

    for asset in response.assets:
        if "chrom" in asset.name:
            return asset

    raise NoChromeExtentionError


def download_extentions():
    """
    Download extensions from the specified repositories and saves them locally.

    Returns
    -------
        list[str]: A list of paths to the downloaded extensions.

    Raises
    ------
        httpx.NetworkError: If there is an error downloading an extension.

    """
    downloaded_extentions: list[str] = []
    for repository in EXTENTION_REPOSITIORIES:
        extention_name = repository.split("/")[-1]
        path = Path(f"{EXTENTIONS_PATH}/{extention_name}")
        try:
            extention = get_latest_github_chrome_release(repository)
            logger.info(
                f"Downloading {extention_name} from {extention.browser_download_url}"
            )
        except httpx.NetworkError:
            if path.is_dir():
                logger.error(f"Error downloading {extention_name}, using local copy")
                downloaded_extentions.append(path.as_posix())
                continue
        try:
            zip_file = requests.get(extention.browser_download_url, timeout=10)
        except UnboundLocalError as e:
            logger.error(f"Error downloading {extention_name}, skipping")
            logger.error(e)
            continue
        Path(EXTENTIONS_PATH).mkdir(exist_ok=True)
        with ZipFile(io.BytesIO(zip_file.content)) as zip_obj:
            if not path.joinpath(extention_name).exists():
                zip_obj.extractall(f"{EXTENTIONS_PATH}/{extention_name}")
                logger.debug(f"Extracted {extention_name} to {path}")

        logger.info(f"Successfully downloaded {extention_name} to {path}")
        downloaded_extentions.append(path.as_posix())
    return downloaded_extentions
