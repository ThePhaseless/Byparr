#!/usr/bin/env bash
# Plain-HTTP reconnaissance of the sites that time out on GitHub runners.
# No browser, no project deps -- just what the network sees from this host.
set -uo pipefail

UA="Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"
URLS=(
  "https://ext.to/"
  "https://extratorrent.st/"
  "https://speed.cd/login"
  "https://1337x.to/home/"
  'https://www.yggtorrent.top/engine/search?do=search&order=desc&sort=publish_date&name=UNESCAPED+DOUBLEQUOTES&category=2145'
)

echo "===== host identity ====="
curl -sS -m 20 https://ipinfo.io/json || echo "(ipinfo failed)"
echo
echo "nproc=$(nproc)  mem=$(free -m | awk '/^Mem:/{print $2}')MB"
echo

for url in "${URLS[@]}"; do
  echo "===== $url ====="
  hdr=$(mktemp)
  body=$(mktemp)
  code=$(curl -sS -m 30 -A "$UA" -D "$hdr" -o "$body" -w '%{http_code}' "$url" 2>&1)
  echo "http_code=$code"
  grep -iE '^(HTTP/|cf-ray|cf-mitigated|cf-chl|server|location|retry-after|x-frame)' "$hdr" || true
  echo "--- title: $(grep -oiE '<title>[^<]*</title>' "$body" | head -1)"
  echo "--- body bytes: $(wc -c <"$body")"
  for marker in "Just a moment" "you have been blocked" "Error 1015" "Error 1020" \
    "Sorry, you have been blocked" "cf-chl" "turnstile" "Access denied" "Enable JavaScript"; do
    if grep -qiF "$marker" "$body"; then echo "--- MARKER: $marker"; fi
  done
  rm -f "$hdr" "$body"
  echo
done
