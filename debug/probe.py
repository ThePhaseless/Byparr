"""Watch Byparr work a Cloudflare challenge, with screenshots.

Runs the real /v1 handler against one URL and narrates the page every few
seconds: what Cloudflare is showing, whether the challenge markers are still
there, whether the widget frame is reachable, and whether the checkbox is
clickable. Screenshots land in /out.

    docker run --rm -e PYTHONPATH=/app -e TRACE_URL=https://extratorrent.st/ \\
      -e BUDGET=240 -v "$PWD/out:/out" byparr-test \\
      uv run python debug/probe.py

Set FRAMEWORK=patchright to launch the solver the other way for comparison.
"""

import asyncio
import logging
import os
import pathlib
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(relativeCreated)8.0fms %(name)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
for noisy in ("asyncio", "httpx", "httpcore", "urllib3"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

from src.endpoints import CHALLENGE_MARKERS, read_item  # noqa: E402
from src.models import LinkRequest  # noqa: E402
from src.utils import get_browser  # noqa: E402

URL = os.environ.get("TRACE_URL", "https://extratorrent.st/")
BUDGET = int(os.environ.get("BUDGET", "240"))
OUT = pathlib.Path(os.environ.get("DIAG_OUT", "/out"))


def log(*a: object) -> None:
    """Print immediately so a hung step is still visible."""
    print(*a, flush=True)


def cf_frame(page):
    """The turnstile widget frame, if the browser exposes it."""
    for frame in page.frames:
        if "challenges.cloudflare.com" in frame.url and not frame.is_detached():
            return frame
    return None


async def watch(page, seconds: int) -> None:
    """Narrate the page while the handler works."""
    start = time.perf_counter()
    for i in range(seconds // 5):
        await asyncio.sleep(5)
        elapsed = time.perf_counter() - start
        try:
            title = await page.title()
            markers = await page.locator(CHALLENGE_MARKERS).count()
            body = (await page.locator("body").inner_text())[:70]
            body = body.replace("\n", " | ")

            frame = cf_frame(page)
            widget = "no frame"
            if frame is not None:
                try:
                    box = frame.locator('input[type="checkbox"]')
                    count = await box.count()
                    visible = count and await box.first.is_visible()
                    checked = await box.first.is_checked() if count else None
                    widget = f"checkbox={count} visible={bool(visible)} checked={checked}"
                except Exception as exc:  # noqa: BLE001
                    widget = f"frame unreadable: {str(exc)[:50]}"

            log(f"  +{elapsed:5.0f}s markers={markers} {widget} | {title!r} {body!r}")
            if i % 3 == 0:
                await page.screenshot(path=str(OUT / f"probe-{elapsed:04.0f}s.png"))
        except Exception as exc:  # noqa: BLE001
            log(f"  +{elapsed:5.0f}s <{str(exc)[:80]}>")


async def main() -> None:
    """Call read_item and report what came back."""
    OUT.mkdir(parents=True, exist_ok=True)
    log(f"### {URL} budget={BUDGET}s")
    async for dep in get_browser():
        try:
            native = await dep.page.evaluate(
                "() => Element.prototype.attachShadow.toString()"
            )
            flagged = await dep.page.evaluate("() => '_shadowRootPatched' in window")
            log(f"  attachShadow native: {'[native code]' in native}")
            log(f"  _shadowRootPatched flag on window: {flagged}")
        except Exception as exc:  # noqa: BLE001
            log(f"  tamper probe failed: {str(exc)[:80]}")

        watcher = asyncio.create_task(watch(dep.page, BUDGET))
        started = time.perf_counter()
        try:
            response = await read_item(LinkRequest(url=URL, max_timeout=BUDGET), dep)
            took = time.perf_counter() - started
            cookies = [c["name"] for c in response.solution.cookies]
            log(f"\nRESULT ok in {took:.0f}s")
            log(f"  solution.status = {response.solution.status}")
            log(f"  bytes           = {len(response.solution.response)}")
            log(f"  cf_clearance    = {'cf_clearance' in cookies}")
        except Exception as exc:  # noqa: BLE001
            log(f"\nRESULT failed in {time.perf_counter() - started:.0f}s: {exc!r}"[:250])
        watcher.cancel()
        try:
            await dep.page.screenshot(path=str(OUT / "probe-final.png"))
            log(f"final title = {await dep.page.title()!r}")
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    asyncio.run(main())
