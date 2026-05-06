#!/usr/bin/env node
/**
 * image-fetcher — local proxy that fetches source images through the
 * operator's residential IP and streams them back to the API on Render.
 *
 * Why: olympustaff / lek-manga / other CF-protected CDNs return 503 for
 * subresource fetches from Render's datacenter IP, even though direct
 * navigation works. Routing the binary fetch through this sidecar
 * (running on the operator's home VM) makes the request look like a
 * normal browser visit and the CDN serves it.
 *
 * Strategy (v2 — byparr-fork):
 *   We delegate the actual fetch to byparr's /binary endpoint, which
 *   performs the request from inside the same Camoufox browser context
 *   that solved the CF challenge. This eliminates the cf_clearance
 *   cookie-portability problem (CF binds the cookie to the browser's
 *   TLS+H2 fingerprint, so cookies minted in browser X don't work
 *   from HTTP client Y). v1 paid that cost via FlareSolverr → curl;
 *   v2 keeps the bytes inside the browser process from start to finish.
 *
 * Endpoints:
 *   GET /healthz-fetcher             → "ok" (path-distinct from FlareSolverr's /v1)
 *   GET /fetch?url=<encoded>&...     → streams the source image
 *
 * Auth:
 *   Requires `Authorization: Bearer <IMAGE_FETCHER_TOKEN>` from the API.
 *   Without a token configured, the server still runs (anonymous mode)
 *   but logs a warning.
 *
 * Config (env vars):
 *   IMAGE_FETCHER_PORT   default 8192
 *   IMAGE_FETCHER_TOKEN  shared secret (must match API env)
 *   BYPARR_URL           default http://localhost:8193 (byparr container)
 *   IMAGE_FETCHER_UA     User-Agent string for fallback path (legacy)
 *
 * Run manually:
 *   IMAGE_FETCHER_TOKEN=changeme node image-fetcher.mjs
 *
 * Run as a systemd service: see install-services.ps1.
 */

import http from 'node:http';
import { URL } from 'node:url';

const PORT = Number(process.env.IMAGE_FETCHER_PORT || 8192);
const TOKEN = process.env.IMAGE_FETCHER_TOKEN || '';
const BYPARR_URL = (process.env.BYPARR_URL || 'http://localhost:8193').replace(/\/+$/, '');
const DEFAULT_UA =
  process.env.IMAGE_FETCHER_UA ||
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
    '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';
const MAX_BYTES = 25 * 1024 * 1024; // 25 MB hard cap regardless of caller

if (!TOKEN) {
  console.warn(
    '[image-fetcher] WARNING: IMAGE_FETCHER_TOKEN not set — running unauthenticated.',
  );
}

function authorized(req) {
  if (!TOKEN) return true; // explicit anon mode
  const h = req.headers['authorization'] || '';
  const m = /^Bearer\s+(.+)$/i.exec(h);
  return m ? m[1] === TOKEN : false;
}

function sendJson(res, status, body) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(body));
}

async function handleFetch(req, res, parsed) {
  const target = parsed.searchParams.get('url');
  if (!target) return sendJson(res, 400, { error: 'missing url param' });

  let u;
  try {
    u = new URL(target);
  } catch {
    return sendJson(res, 400, { error: 'invalid url' });
  }
  if (u.protocol !== 'http:' && u.protocol !== 'https:') {
    return sendJson(res, 400, { error: 'only http(s) urls allowed' });
  }

  const referer = parsed.searchParams.get('referer') || `${u.protocol}//${u.host}/`;
  const maxBytesQ = Number(parsed.searchParams.get('maxBytes')) || MAX_BYTES;
  const maxBytes = Math.min(MAX_BYTES, Math.max(1, maxBytesQ));

  // Build byparr /binary URL
  const byparrUrl = new URL(`${BYPARR_URL}/binary`);
  byparrUrl.searchParams.set('url', u.toString());
  byparrUrl.searchParams.set('referer', referer);
  byparrUrl.searchParams.set('max_bytes', String(maxBytes));
  byparrUrl.searchParams.set('max_timeout', '120');

  const ctrl = new AbortController();
  // Give byparr generous time: solving CF can take 25-35s; first hit on a
  // cold host can be 60s+. Cap total at 150s so we don't pin the client.
  const timeout = setTimeout(() => ctrl.abort(), 150_000);
  let upstream;
  try {
    upstream = await fetch(byparrUrl.toString(), {
      method: 'GET',
      signal: ctrl.signal,
      headers: {
        Accept: 'image/avif,image/webp,image/*,*/*;q=0.8',
        // BUGFIX 2026-05-06: undici (Node fetch) auto-sends an
        // accept-encoding header. uvicorn (byparr's server) honors it
        // and returns gzip-compressed bytes with Content-Length set
        // to the GZIP size — but undici transparently decompresses
        // the streamed body. We were forwarding the (smaller) gzip
        // Content-Length downstream while writing the (larger)
        // decompressed body, causing the client to truncate at the
        // gzip-size mark and miss the JPEG EOI bytes. >50% of chapter
        // images then crashed Sharp with "VipsJpeg: Premature end of
        // input file". Disabling compression on this hop side-steps
        // the entire mismatch.
        'Accept-Encoding': 'identity',
      },
    });
  } catch (err) {
    clearTimeout(timeout);
    return sendJson(res, 502, {
      error: 'byparr /binary fetch failed',
      detail: String(err && err.message ? err.message : err),
      target: u.toString(),
    });
  }
  clearTimeout(timeout);

  if (!upstream.ok) {
    let detail = '';
    try { detail = (await upstream.text()).slice(0, 500); } catch {}
    return sendJson(res, upstream.status === 413 ? 413 : 502, {
      error: `byparr /binary returned HTTP ${upstream.status}`,
      detail,
      target: u.toString(),
    });
  }

  // Stream through. byparr already enforces max_bytes server-side, but
  // we double-check on this side for defense-in-depth.
  const ct = upstream.headers.get('content-type') || 'application/octet-stream';
  const cl = upstream.headers.get('content-length');
  // Don't trust the upstream Content-Length even after the
  // accept-encoding=identity fix above — any future intermediate
  // (proxy, sidecar, etc.) could re-introduce the mismatch.
  // Falling through to chunked-transfer encoding is safe: clients
  // that don't speak chunked don't exist in 2026.
  const ce = upstream.headers.get('content-encoding');
  const lengthIsTrustworthy = !ce || ce.toLowerCase() === 'identity';
  if (cl && Number(cl) > maxBytes) {
    return sendJson(res, 413, { error: `Content-Length ${cl} exceeds ${maxBytes}` });
  }
  res.writeHead(200, {
    'Content-Type': ct,
    'Cache-Control': 'no-store',
    ...(cl && lengthIsTrustworthy ? { 'Content-Length': cl } : {}),
  });

  const reader = upstream.body && upstream.body.getReader();
  if (!reader) {
    res.end();
    return;
  }
  let total = 0;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    if (!value) continue;
    total += value.byteLength;
    if (total > maxBytes) {
      try { await reader.cancel(); } catch {}
      try { res.end(); } catch {}
      return;
    }
    res.write(Buffer.from(value));
  }
  res.end();
}

const server = http.createServer((req, res) => {
  const parsed = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  if (
    req.method === 'GET' &&
    (parsed.pathname === '/healthz-fetcher' || parsed.pathname === '/health')
  ) {
    return sendJson(res, 200, {
      ok: true,
      authMode: TOKEN ? 'bearer' : 'anonymous',
      maxBytes: MAX_BYTES,
      backend: 'byparr-binary',
      byparrUrl: BYPARR_URL,
    });
  }
  if (req.method === 'GET' && parsed.pathname === '/fetch') {
    if (!authorized(req)) return sendJson(res, 401, { error: 'unauthorized' });
    return handleFetch(req, res, parsed).catch((err) => {
      console.error('[image-fetcher] fetch handler crashed', err);
      try { sendJson(res, 500, { error: 'internal error' }); } catch {}
    });
  }
  sendJson(res, 404, { error: 'not found' });
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(
    `[image-fetcher] listening on :${PORT} (auth=${TOKEN ? 'bearer' : 'anonymous'}, backend=byparr@${BYPARR_URL})`,
  );
});
