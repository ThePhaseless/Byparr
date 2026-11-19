from playwright.async_api import Page, Request, Route

FORM_CONTENT_TYPE = "application/x-www-form-urlencoded"


class PostSubmitter:
    """
    Sends the target navigation as a form POST, like FlareSolverr's request.post.

    The browser, not an API client, makes the request, so the challenge and the
    cookies behave exactly as for a GET. Only the first main-frame navigation
    after arming is rewritten: redirects that follow the POST stay GETs.
    """

    def __init__(self, page: Page, url: str, body: str) -> None:
        """Remember the page, the target URL and the form body to send."""
        self.page = page
        self.url = url
        self.body = body
        self.posts_seen = 0
        self._armed = False

    async def install(self) -> None:
        """Install the request hooks; call before the first navigation."""
        self.page.on("request", self._count_post)
        await self.page.route("**/*", self._route)

    def _count_post(self, request: Request) -> None:
        """Count POST navigations, ours and any a challenge replays itself."""
        if (
            request.method == "POST"
            and request.is_navigation_request()
            and request.frame == self.page.main_frame
        ):
            self.posts_seen += 1

    async def goto(self, budget_ms: float) -> object:
        """Navigate to the URL with the body as the POST data."""
        self._armed = True
        try:
            return await self.page.goto(self.url, timeout=budget_ms)
        finally:
            self._armed = False

    async def _route(self, route: Route) -> None:
        request = route.request
        if (
            self._armed
            and request.is_navigation_request()
            and request.frame == self.page.main_frame
        ):
            self._armed = False
            await route.continue_(
                method="POST",
                post_data=self.body,
                headers={**request.headers, "content-type": FORM_CONTENT_TYPE},
            )
        else:
            await route.fallback()
