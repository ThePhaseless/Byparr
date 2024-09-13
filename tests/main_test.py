import pytest

from main import read_item
from src.models.requests import LinkRequest

test_websites = [
    "https://ext.to/",
    "https://btmet.com/",
    "https://extratorrent.st/",
    "https://idope.se/",
]
pytest_plugins = ("pytest_asyncio",)


@pytest.mark.parametrize("website", test_websites)
@pytest.mark.asyncio
async def test_bypass(website: str):
    await read_item(LinkRequest(url=website, maxTimeout=5, cmd=""))
