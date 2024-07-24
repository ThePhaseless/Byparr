from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import httpx

from src.models.github import GithubResponse
from src.utils.consts import EXTENTION_REPOSITIORIES

downloaded_extentions: list[str] = []  # Do not modify, use download_extentions()


def get_latest_github_release(url: str):
    """Get the latest release from GitHub."""
    url = "https://api.github.com/repos/" + url
    url += "/releases/latest"
    response = GithubResponse.model_validate_json(httpx.get(url).text)

    for asset in response.assets:
        if "chrom" in asset.name:
            return asset

    raise ValueError("Couldn't find chrome verions of the release")


def download_extentions():
    """Download the extention."""
    for repository in EXTENTION_REPOSITIORIES:
        extention = get_latest_github_release(repository)
        extention_name = repository.split("/")[-1]
        response = httpx.get(extention.browser_download_url)
        Path("extentions").mkdir(exist_ok=True)
        if not Path(f"extentions/{extention.name}").exists():
            with Path(f"extentions/{extention.name}").open("wb") as f:
                f.write(response.content)

            with ZipFile(f"extentions/{extention.name}", "r") as zip_obj:
                zip_obj.extractall(f"extentions/{extention_name}")

        downloaded_extentions.append(f"extentions/{extention_name}")
