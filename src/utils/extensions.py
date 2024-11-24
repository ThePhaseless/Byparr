from __future__ import annotations

import io
import json
from pathlib import Path
from zipfile import ZipFile

import httpx
import requests

from src.models.github import GithubResponse
from src.models.requests import NoChromeExtensionError
from src.utils import logger
from src.utils.consts import EXTENSION_REPOSITIORIES, EXTENSIONS_PATH, GITHUB_WEBSITES


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
        NoChromeExtensionError: If no release asset with 'chrom' in its name is found.

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

    raise NoChromeExtensionError


def download_extensions():
    """
    Download extensions from the specified repositories and saves them locally.

    Returns
    -------
        list[str]: A list of paths to the downloaded extensions.

    Raises
    ------
        httpx.NetworkError: If there is an error downloading an extension.

    """
    downloaded_extensions: list[str] = []
    for repository in EXTENSION_REPOSITIORIES:
        extension_name = repository.split("/")[-1]
        path = Path(f"{EXTENSIONS_PATH}/{extension_name}")
        try:
            extension = get_latest_github_chrome_release(repository)
            logger.info(
                f"Downloading {extension_name} from {extension.browser_download_url}"
            )
        except httpx.NetworkError:
            if path.is_dir():
                logger.error(f"Error downloading {extension_name}, using local copy")
                downloaded_extensions.append(path.as_posix())
                continue
        try:
            zip_file = requests.get(extension.browser_download_url, timeout=10)
        except UnboundLocalError as e:
            logger.error(f"Error downloading {extension_name}, skipping")
            logger.error(e)
            continue
        Path(EXTENSIONS_PATH).mkdir(exist_ok=True)
        with ZipFile(io.BytesIO(zip_file.content)) as zip_obj:
            if not path.joinpath(extension_name).exists():
                zip_obj.extractall(f"{EXTENSIONS_PATH}/{extension_name}")
                logger.debug(f"Extracted {extension_name} to {path}")

        logger.info(f"Successfully downloaded {extension_name} to {path}")
        downloaded_extensions.append(path.as_posix())
    return downloaded_extensions
