"""Two variables at once: hide the patch, and click where a human would.

Findings this is built on, both measured on a residential connection:

  * On the challenge page the library's unlockShadowRoot.js has run --
    `_shadowRootPatched` is a global and attachShadow is visibly patched. Any
    anti-bot script can read that in one line.
  * Turnstile's <input type="checkbox"> is invisible. Playwright reports a
    successful click on it and `checked` never flips, because the real target
    is the overlay drawn on top.

So: MODE=stealth patches shadow roots without leaving a global or a
non-native toString; MODE=library keeps the current behaviour. Either way the
click is a real mouse press at the widget's visible position, not a synthetic
click on a hidden input.

    docker run --rm -e PYTHONPATH=/app -e MODE=stealth \\
      -e TRACE_URL=https://extratorrent.st/ -v "$PWD/out:/out" \\
      byparr-test uv run python debug/stealth_click.py
"""

import asyncio
import os
import pathlib

from invisible_playwright.async_api import InvisiblePlaywright
from playwright_captcha import ClickSolver, FrameworkType

URL = os.environ.get("TRACE_URL", "https://extratorrent.st/")
MODE = os.environ.get("MODE", "stealth")
WATCH = int(os.environ.get("WATCH", "60"))
OUT = pathlib.Path(os.environ.get("DIAG_OUT", "/out"))

PREFS = {
    "devtools.jsonview.enabled": False,
    "browser.tabs.remote.useCrossOriginOpenerPolicy": False,
    "browser.tabs.remote.useCrossOriginEmbedderPolicy": False,
}

STEALTH_UNLOCK = """
(() => {
  const nativeToString = Function.prototype.toString;
  const spoofed = new WeakMap();
  const asNative = (fake, real) => { spoofed.set(fake, real); return fake; };

  Function.prototype.toString = asNative(function toString() {
    const real = spoofed.get(this);
    return nativeToString.call(real === undefined ? this : real);
  }, nativeToString);

  const hidden = new WeakMap();
  const realAttach = Element.prototype.attachShadow;
  Element.prototype.attachShadow = asNative(function attachShadow(init) {
    const root = realAttach.call(this, Object.assign({}, init, {mode: 'open'}));
    hidden.set(this, root);
    return root;
  }, realAttach);

  const desc = Object.getOwnPropertyDescriptor(Element.prototype, 'shadowRoot');
  if (desc && desc.get) {
    const realGet = desc.get;
    Object.defineProperty(Element.prototype, 'shadowRoot', {
      get: asNative(function shadowRoot() {
        return realGet.call(this) || hidden.get(this);
      }, realGet),
      configurable: desc.configurable,
      enumerable: desc.enumerable,
    });
  }
})();
"""

PROBE = """
() => ({
  flag: '_shadowRootPatched' in window,
  attachNative: /\\[native code\\]/.test(Element.prototype.attachShadow.toString()),
})
"""


def log(*a: object) -> None:
    """Print immediately."""
    print(*a, flush=True)


def cf_frame(page):
    """The turnstile widget frame."""
    for frame in page.frames:
        if "challenges.cloudflare.com" in frame.url and not frame.is_detached():
            return frame
    return None


async def widget_box(page):
    """Where the widget is drawn, in main-page coordinates."""
    try:
        el = page.locator('iframe[src*="challenges.cloudflare.com"]').first
        if await el.count():
            return await el.bounding_box()
    except Exception:  # noqa: BLE001
        pass
    return None


async def checkbox_state(page) -> str:
    """What the hidden input currently reports."""
    frame = cf_frame(page)
    if frame is None:
        return "no frame"
    try:
        box = frame.locator('input[type="checkbox"]')
        if not await box.count():
            return "no input"
        return f"checked={await box.first.is_checked()}"
    except Exception as exc:  # noqa: BLE001
        return f"unreadable ({str(exc)[:40]})"


async def main() -> None:
    """Load the challenge, press the widget like a person, watch the verdict."""
    OUT.mkdir(parents=True, exist_ok=True)
    log(f"### mode={MODE} {URL}")

    async with InvisiblePlaywright(
        headless=True, humanize=True, locale="auto", extra_prefs=PREFS
    ) as browser:
        context = await browser.new_context()
        page = await context.new_page()

        solver = None
        if MODE == "stealth":
            await page.add_init_script(STEALTH_UNLOCK)
        else:
            solver = ClickSolver(
                framework=FrameworkType.PLAYWRIGHT, page=page, max_attempts=1
            )
            await solver.__aenter__()

        await page.goto(URL, timeout=60_000)
        await page.wait_for_load_state("domcontentloaded", timeout=30_000)
        log(f"  on challenge page: {await page.evaluate(PROBE)}")

        # Wait for the checkbox to actually be presented, not merely for the
        # iframe to exist. Cloudflare cycles: the widget frame appears first
        # while it is still "checking if you are human" with no input in it,
        # and only then renders the checkbox. Pressing during that first phase
        # is a click into nothing, which is what every earlier probe did.
        ready = False
        for i in range(90):
            frame = cf_frame(page)
            if frame is not None:
                try:
                    count = await frame.locator('input[type="checkbox"]').count()
                except Exception:  # noqa: BLE001
                    count = 0
                if count:
                    log(f"  checkbox presented after {i}s")
                    ready = True
                    break
            await asyncio.sleep(1)
        if not ready:
            log("  checkbox never appeared")
            await page.screenshot(path=str(OUT / f"{MODE}-no-checkbox.png"))
            return

        # Let it settle, then confirm it is still presented before pressing.
        await asyncio.sleep(2)
        frame = cf_frame(page)
        if frame is None or not await frame.locator('input[type="checkbox"]').count():
            log("  checkbox vanished while settling -- Cloudflare moved on")
            return

        box = await widget_box(page)
        if not box:
            log("  widget has no bounding box")
            return
        log(f"  widget box: {box}")
        log(f"  before: {await checkbox_state(page)}")
        await page.screenshot(path=str(OUT / f"{MODE}-before-click.png"))

        # The checkbox sits at the left of the widget, vertically centred.
        x = box["x"] + 30
        y = box["y"] + box["height"] / 2
        await page.mouse.move(x - 200, y - 130)
        await asyncio.sleep(0.4)
        await page.mouse.move(x - 50, y - 25, steps=22)
        await asyncio.sleep(0.25)
        await page.mouse.move(x, y, steps=12)
        await asyncio.sleep(0.4)
        await page.mouse.down()
        await asyncio.sleep(0.08)
        await page.mouse.up()
        log(f"  pressed at ({x:.0f}, {y:.0f})")

        for i in range(WATCH // 3):
            await asyncio.sleep(3)
            title = await page.title()
            log(f"    +{(i + 1) * 3:3d}s {await checkbox_state(page)} title={title!r}")
            if "oment" not in title and "ierpliwo" not in title:
                log(f"  >>> CLEARED by mode={MODE}")
                await page.screenshot(path=str(OUT / f"{MODE}-cleared.png"))
                log(f"  cookies={[c['name'] for c in await context.cookies()]}")
                return
        await page.screenshot(path=str(OUT / f"{MODE}-end.png"))
        log(f"  mode={MODE}: still challenged")

        if solver:
            await solver.__aexit__(None, None, None)


if __name__ == "__main__":
    asyncio.run(main())
