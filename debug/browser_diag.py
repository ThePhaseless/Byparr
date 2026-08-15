"""Run the real browser stack against the flaky sites and record what happens.

Meant to run inside the built image (`uv run python debug/browser_diag.py`) so the
browser, prefs and network path are exactly the ones the Docker test stage uses.
Artifacts (screenshots, HTML, JSON summary) are written to /out.
"""

import asyncio
import json
import os
import pathlib
import re
import time
import traceback

import httpx2
from playwright_captcha import CaptchaType
from playwright_captcha.solvers.click.cloudflare.utils.detection import (
    detect_cloudflare_challenge,
)

from src.utils import get_browser

URLS = [
    "https://ext.to/",
    "https://extratorrent.st/",
    "https://speed.cd/login",
    "https://1337x.to/home/",
]

GOTO_TIMEOUT_MS = 60_000
SOLVE_TIMEOUT_S = 120
OUT = pathlib.Path(os.environ.get("DIAG_OUT", "/out"))
LABEL = os.environ.get("DIAG_LABEL", "unknown")


def slug(url: str) -> str:
    """Filesystem-safe name for a URL."""
    return re.sub(r"[^a-z0-9]+", "-", url.lower()).strip("-")[:60]


def snippet(html: str) -> str:
    """Text-ish preview of a page body for the log."""
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:400]


async def challenge_evidence(page) -> dict:
    """Separate a real challenge from Cloudflare's post-challenge telemetry script.

    `detect_cloudflare_challenge(..., "interstitial")` only looks for a
    `script[src*="/cdn-cgi/challenge-platform/"]` tag. Cloudflare also injects
    that script (the "jsd" bot-detection beacon) into ordinary pages, so the
    selector alone cannot tell the two apart. These counts can.
    """
    out: dict = {}
    try:
        out["cp_scripts"] = await page.locator(
            'script[src*="/cdn-cgi/challenge-platform/"]'
        ).count()
        out["cp_script_srcs"] = await page.locator(
            'script[src*="/cdn-cgi/challenge-platform/"]'
        ).evaluate_all("els => els.map(e => e.getAttribute('src'))")
        out["cf_iframes"] = await page.locator(
            'iframe[src*="challenges.cloudflare.com"]'
        ).count()
        out["challenge_form"] = await page.locator("#challenge-form, #cf-chl-widget").count()
        out["body_chars"] = len(await page.locator("body").inner_text())
    except Exception as exc:  # noqa: BLE001
        out["evidence_error"] = repr(exc)[:200]
    return out


async def probe(url: str) -> dict:
    """Drive one URL through goto -> detect -> solve, recording every stage."""
    name = slug(url)
    rec: dict = {"url": url, "label": LABEL}

    t0 = time.perf_counter()
    try:
        plain = httpx2.get(url)
        rec["httpx_status"] = plain.status_code
        rec["httpx_cf_mitigated"] = plain.headers.get("cf-mitigated")
        rec["httpx_title"] = snippet(plain.text)[:120]
    except Exception as exc:  # noqa: BLE001
        rec["httpx_error"] = repr(exc)[:200]
    rec["httpx_s"] = round(time.perf_counter() - t0, 1)

    async for dep in get_browser():
        page = dep.page
        t0 = time.perf_counter()
        try:
            response = await page.goto(url, timeout=GOTO_TIMEOUT_MS)
            rec["goto_s"] = round(time.perf_counter() - t0, 1)
            rec["goto_status"] = response.status if response else None
            if response:
                headers = response.headers
                rec["cf_ray"] = headers.get("cf-ray")
                rec["cf_mitigated"] = headers.get("cf-mitigated")
                rec["server"] = headers.get("server")
                rec["ua_sent"] = response.request.headers.get("user-agent")
        except Exception as exc:  # noqa: BLE001
            rec["goto_s"] = round(time.perf_counter() - t0, 1)
            rec["goto_error"] = repr(exc)[:300]

        try:
            await page.wait_for_load_state("domcontentloaded", timeout=30_000)
        except Exception as exc:  # noqa: BLE001
            rec["dcl_error"] = repr(exc)[:200]

        rec["title"] = await page.title()
        rec["page_url"] = page.url
        rec["interstitial"] = await detect_cloudflare_challenge(page, "interstitial")
        rec["turnstile"] = await detect_cloudflare_challenge(page, "turnstile")
        rec["evidence"] = await challenge_evidence(page)

        # Watch the page settle: a real interstitial auto-resolves within seconds.
        rec["timeline"] = []
        for _ in range(6):
            await asyncio.sleep(5)
            rec["timeline"].append(
                {
                    "t": len(rec["timeline"]) * 5 + 5,
                    "title": await page.title(),
                    "detected": await detect_cloudflare_challenge(page, "interstitial"),
                    **await challenge_evidence(page),
                }
            )

        html = await page.content()
        rec["content_len"] = len(html)
        rec["content_snippet"] = snippet(html)
        (OUT / f"{LABEL}-{name}-before.html").write_text(html, errors="replace")
        try:
            await page.screenshot(path=str(OUT / f"{LABEL}-{name}-before.png"))
        except Exception as exc:  # noqa: BLE001
            rec["screenshot_error"] = repr(exc)[:200]

        if rec["interstitial"] or rec["turnstile"]:
            t0 = time.perf_counter()
            try:
                await asyncio.wait_for(
                    dep.solver.solve_captcha(
                        captcha_container=page,
                        captcha_type=CaptchaType.CLOUDFLARE_INTERSTITIAL,
                        wait_checkbox_attempts=1,
                        wait_checkbox_delay=0.5,
                    ),
                    timeout=SOLVE_TIMEOUT_S,
                )
                rec["solve_result"] = "returned"
            except TimeoutError:
                rec["solve_result"] = f"timeout after {SOLVE_TIMEOUT_S}s"
            except Exception as exc:  # noqa: BLE001
                rec["solve_result"] = f"error {exc!r}"[:300]
            rec["solve_s"] = round(time.perf_counter() - t0, 1)

            rec["title_after"] = await page.title()
            rec["interstitial_after"] = await detect_cloudflare_challenge(
                page, "interstitial"
            )
            html = await page.content()
            rec["content_len_after"] = len(html)
            rec["content_snippet_after"] = snippet(html)
            (OUT / f"{LABEL}-{name}-after.html").write_text(html, errors="replace")
            try:
                await page.screenshot(path=str(OUT / f"{LABEL}-{name}-after.png"))
            except Exception as exc:  # noqa: BLE001
                rec["screenshot_after_error"] = repr(exc)[:200]

    return rec


async def egress_identity() -> dict:
    """What the browser itself looks like on the wire."""
    rec: dict = {}
    async for dep in get_browser():
        try:
            await dep.page.goto("https://api.ipify.org?format=json", timeout=30_000)
            rec["ip"] = (await dep.page.locator("body").inner_text())[:200]
        except Exception as exc:  # noqa: BLE001
            rec["ip_error"] = repr(exc)[:200]
        try:
            await dep.page.goto("https://tls.browserleaks.com/json", timeout=30_000)
            body = (await dep.page.locator("body").inner_text())[:4000]
            data = json.loads(body)
            rec["ja3_hash"] = data.get("ja3_hash")
            rec["ja4"] = data.get("ja4")
            rec["user_agent"] = data.get("user_agent")
        except Exception as exc:  # noqa: BLE001
            rec["tls_error"] = repr(exc)[:200]
    return rec


async def main() -> None:
    """Run every probe and dump a JSON summary."""
    OUT.mkdir(parents=True, exist_ok=True)
    results = {"label": LABEL, "egress": {}, "sites": []}

    try:
        results["egress"] = await egress_identity()
    except Exception:  # noqa: BLE001
        results["egress"] = {"fatal": traceback.format_exc()[-800:]}
    print(f"[egress] {json.dumps(results['egress'])}", flush=True)

    for url in URLS:
        print(f"\n===== [{LABEL}] {url} =====", flush=True)
        try:
            rec = await probe(url)
        except Exception:  # noqa: BLE001
            rec = {"url": url, "fatal": traceback.format_exc()[-1500:]}
        results["sites"].append(rec)
        print(json.dumps(rec, indent=2, default=str), flush=True)

    (OUT / f"{LABEL}-summary.json").write_text(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
