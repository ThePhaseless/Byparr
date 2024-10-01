# Byparr

An alternative to [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) as a drop-in replacement, build with [nodriver](https://github.com/ultrafunkamsterdam/nodriver) and [FastAPI](https://fastapi.tiangolo.com).

> [!IMPORTANT]
> Currenly, due to [bug in nodriver](https://github.com/ultrafunkamsterdam/undetected-chromedriver/issues/1954), if you want to run this project ouside of prebuild container, you have to run `python fix_nodriver.py` after creating venv to patch the library.

> [!NOTE]
> Thanks to FastAPI implementation, now you can also see the API documentation at `/docs` or `/` (redirect to `/docs`) endpoints.

## Early Development

Long story short, I created it in like 3 days, so if you get any bugs/hangs etc. please report it, so both of us can enjoy unblocked websites!

I focus maily on Cloudflare, which is tested daily, any other anti-bot challenges should pass out of the box, but if any issues, please report these providers with an example website ❤️

## Troubleshooting
1. Clone repo to the host that has the container has issues on.
2. Using vscode and `SSH extention`, connect to the host and open repo in it.
3. Download `devcontainers` extention and reopen repo in container (with `CTRL + SHIFT + P` -> `Reopen in devcontainer`)
4. Open forwarded port from `Ports` tab in your browser to see emulated display 
5. Check if `chrome` works by running in VNCs terminal command `chrome --no-sandbox`
6. If chrome works, run API by pressing F5 in vscode
7. In Prowlarr (or target client) change port byparrs port to `8181` instead of `8191` (Port opened by and pointing to devcontainer)
8. Check if everything works by testing byparr and observing VNC in browser

## Usage

### Docker Compose

```yaml
services:
  byparr:
    image: ghcr.io/thephaseless/byparr
    environment:
      - LOG_LEVEL=INFO # optional
    ports:
      - "8191:8191" # Optional if used with *arr network
```

## Need help with / TODO

- [ ] Slimming container (~3GB bruh)
- [ ] Add more anti-bot challenges
- [x] Add docstrings
- [ ] Implement versioning
- [ ] Proxy support
- [ ] Add more architectures support
