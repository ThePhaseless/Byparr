"""Find a click Cloudflare's checkbox actually accepts.

The widget is reachable now, but `Checkbox clicked successfully` leaves it
`checked=False`, so the click is not registering as a user gesture. This tries
each candidate in turn against a fresh page and reports which one ticks the box
and which one clears the challenge.

    docker run --rm -e PYTHONPATH=/app -e TRACE_URL=https://extratorrent.st/ \\
      -v "$PWD/out:/out" byparr-test uv run python debug/click_modes.py

MODES defaults to every strategy; set MODES=force,label to narrow it.
"""

import asyncio
import os
import pathlib
import time

from src.utils import get_browser

URL = os.environ.get("TRACE_URL", "https://extratorrent.st/")
MODES = os.environ.get(
    "MODES", "locator,force,check,label,mouse,widget_centre"
).split(",")
SETTLE = int(os.environ.get("SETTLE", "45"))
OUT = pathlib.Path(os.environ.get("DIAG_OUT", "/out"))


def log(*a: object) -> None:
    """Print immediately."""
    print(*a, flush=True)


def cf_frame(page):
    """The turnstile widget frame."""
    for frame in page.frames:
        if "challenges.cloudflare.com" in frame.url and not frame.is_detached():
            return frame
    return None


async def wait_for_widget(page, seconds: int = 30):
    """Wait until the checkbox is visible, returning (frame, locator)."""
    for _ in range(seconds * 2):
        frame = cf_frame(page)
        if frame is not None:
            try:
                box = frame.locator('input[type="checkbox"]')
                if await box.count() and await box.first.is_visible():
                    return frame, box.first
            except Exception:  # noqa: BLE001
                pass
        await asyncio.sleep(0.5)
    return None, None


async def do_click(page, frame, box, mode: str) -> str:
    """Perform one click strategy."""
    if mode == "locator":
        await box.click(timeout=10_000)
        return "locator.click()"
    if mode == "force":
        await box.click(timeout=10_000, force=True)
        return "locator.click(force=True)"
    if mode == "check":
        await box.check(timeout=10_000)
        return "locator.check()"
    if mode == "label":
        label = frame.locator("label")
        if await label.count():
            await label.first.click(timeout=10_000)
            return "label.click()"
        return "no label present"
    if mode in {"mouse", "widget_centre"}:
        rect = await box.bounding_box()
        if rect is None:
            return "no bounding box"
        x = rect["x"] + rect["width"] / 2
        y = rect["y"] + rect["height"] / 2
        # Approach first: a cursor that teleports is itself a signal.
        await page.mouse.move(x - 180, y - 120)
        await asyncio.sleep(0.3)
        await page.mouse.move(x - 40, y - 20, steps=18)
        await asyncio.sleep(0.2)
        await page.mouse.move(x, y, steps=10)
        await asyncio.sleep(0.35)
        await page.mouse.down()
        await asyncio.sleep(0.07)
        await page.mouse.up()
        return f"page.mouse at ({x:.0f}, {y:.0f})"
    return f"unknown mode {mode}"


async def try_mode(mode: str) -> None:
    """One fresh browser, one strategy, one verdict."""
    log(f"\n===== mode={mode} =====")
    async for dep in get_browser():
        page = dep.page
        await page.goto(URL, timeout=60_000)
        await page.wait_for_load_state("domcontentloaded", timeout=30_000)

        # Is our shadow-root patch even surviving the page's CSP?
        try:
            src = await page.evaluate("() => Element.prototype.attachShadow.toString()")
            flag = await page.evaluate("() => '_shadowRootPatched' in window")
            log(f"  on challenge page: native={'[native code]' in src} flag={flag}")
        except Exception as exc:  # noqa: BLE001
            log(f"  tamper probe blocked: {str(exc)[:70]}")

        frame, box = await wait_for_widget(page)
        if box is None:
            log("  checkbox never became visible")
            return

        log(f"  before: checked={await box.is_checked()}")
        try:
            what = await do_click(page, frame, box, mode)
            log(f"  clicked via {what}")
        except Exception as exc:  # noqa: BLE001
            log(f"  click raised: {str(exc)[:120]}")
            return

        start = time.perf_counter()
        for _ in range(SETTLE // 3):
            await asyncio.sleep(3)
            elapsed = time.perf_counter() - start
            title = await page.title()
            checked = None
            frame_now = cf_frame(page)
            if frame_now is not None:
                try:
                    b = frame_now.locator('input[type="checkbox"]')
                    checked = await b.first.is_checked() if await b.count() else None
                except Exception:  # noqa: BLE001
                    checked = "unreadable"
            log(f"    +{elapsed:3.0f}s checked={checked} title={title!r}")
            if "oment" not in title and "ierpliwo" not in title:
                log(f"  >>> CLEARED by {mode}")
                await page.screenshot(path=str(OUT / f"cleared-{mode}.png"))
                return
        await page.screenshot(path=str(OUT / f"stuck-{mode}.png"))
        log(f"  {mode}: still challenged")


async def main() -> None:
    """Try each strategy on its own fresh browser."""
    OUT.mkdir(parents=True, exist_ok=True)
    log(f"### {URL} modes={MODES}")
    for mode in MODES:
        try:
            await try_mode(mode.strip())
        except Exception as exc:  # noqa: BLE001
            log(f"  mode {mode} blew up: {str(exc)[:150]}")


if __name__ == "__main__":
    asyncio.run(main())
