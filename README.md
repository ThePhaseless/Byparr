# Byparr

An alternative to [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) as a drop-in replacement, build with [nodriver](https://github.com/ultrafunkamsterdam/nodriver) and [FastAPI](https://fastapi.tiangolo.com).

> [!WARNING]
> Due to recent challenge changes, this software does not guarantee that the Cloudflare challenge will be bypassed. Cloudflare likely requires valid network traffic originating from the user’s public IP address to mark a connection as legitimate. While this tool may bypass the initial browser check, it does not ensure that requests will consistently pass Cloudflare's validation. More testing and data are required to understand how Cloudflare identifies connections and requests as valid. Invalid requests will result in Byparr's looping and eventually timeouting.

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
4. Download `devcontainers` extention and reopen repo in container (with `CTRL + SHIFT + P` -> `Reopen in devcontainer`)
3. Open vscode terminal (`` CTRL + ` ``) and run `./run_vnc.sh` script.
5. Write down the port from `Forwarded Address` in `Ports` tab in vscode (probably 5900).
6. Open <https://novnc.com/noVNC/vnc.html> in your pc's browser and using settings on left under websocket, set host to `localhost` nad port to the port you wrote down and disable encryption.
7. Connect to the VNC server on container.
8. Check if `chromium` works by running in VNC's terminal command `chromium --no-sandbox`
9. If chromium works, run (or run debug) tests from VS Code.
10. Check if everything works by observing VNC in the browser as code is being tested.
11. If code works, congrats! (/s) You are on your own.
12. If it does not, try another host or network and try again.

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
