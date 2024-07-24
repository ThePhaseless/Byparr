from __future__ import annotations

from pydantic import BaseModel


class Author(BaseModel):
    login: str
    id: int
    node_id: str
    avatar_url: str
    gravatar_id: str
    url: str
    html_url: str
    followers_url: str
    following_url: str
    gists_url: str
    starred_url: str
    subscriptions_url: str
    organizations_url: str
    repos_url: str
    events_url: str
    received_events_url: str
    type: str
    site_admin: bool


class Uploader(BaseModel):
    login: str
    id: int
    node_id: str
    avatar_url: str
    gravatar_id: str
    url: str
    html_url: str
    followers_url: str
    following_url: str
    gists_url: str
    starred_url: str
    subscriptions_url: str
    organizations_url: str
    repos_url: str
    events_url: str
    received_events_url: str
    type: str
    site_admin: bool


class Asset(BaseModel):
    url: str
    id: int
    node_id: str
    name: str
    label: str | None
    uploader: Uploader
    content_type: str
    state: str
    size: int
    download_count: int
    created_at: str
    updated_at: str
    browser_download_url: str


class Reactions(BaseModel):
    url: str
    total_count: int

    laugh: int
    hooray: int
    confused: int
    heart: int
    rocket: int
    eyes: int


class GithubResponse(BaseModel):
    url: str
    assets_url: str
    upload_url: str
    html_url: str
    id: int
    author: Author
    node_id: str
    tag_name: str
    target_commitish: str
    name: str
    draft: bool
    prerelease: bool
    created_at: str
    published_at: str
    assets: list[Asset]
    tarball_url: str
    zipball_url: str
    body: str
    reactions: Reactions
