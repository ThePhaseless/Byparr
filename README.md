# Byparr

An alternative to [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) as a drop-in replacement, build with [seleniumbase](https://seleniumbase.io/) and [FastAPI](https://fastapi.tiangolo.com).

> [!WARNING]
> Due to recent challenge changes, this software does not guarantee that the Cloudflare challenge will be bypassed. Cloudflare likely requires valid network traffic originating from the user’s public IP address to mark a connection as legitimate. While this tool may bypass the initial browser check, it does not ensure that requests will consistently pass Cloudflare's validation. More testing and data are required to understand how Cloudflare identifies connections and requests as valid. Invalid requests will result in Byparr's looping and eventually time-outing.

> [!WARNING]
> Support for NAS devices (like Synology) is minimal. Please report issues, but do not expect it to be fixed quickly. The only ARM device I have is a free Ampere Oracle VM, so I can only test ARM support on that. See [#22](https://github.com/ThePhaseless/Byparr/issues/22) and [#3](https://github.com/ThePhaseless/Byparr/issues/3)

> [!NOTE]
> Thanks to FastAPI implementation, now you can also see the API documentation at `/docs` or `/` (redirect to `/docs`) endpoints.

## Troubleshooting

1. Clone repo to the host that has the container has issues on.
2. Using vscode and `SSH extention`, connect to the host and open repo in it.
3. Download `devcontainers` extention and reopen repo in container (with `CTRL + SHIFT + P` -> `Reopen in devcontainer`)
4. Forward port 6080 from devcontainer (port of noVNC server) to the host.
5. Open `http://localhost:6080` and connect to the virtual desktop.
6. Check if `chromium` works by running in VNC's terminal command `chromium --no-sandbox`.
7. If chromium works, run (or debug) tests from VS Code.
   1. If code works, congrats! (/s) You are on your own.
   2. If it does not, try another host or network, try again and create issue about the problem.

## Usage

### Docker Compose

```yaml
services:
  byparr:
    image: ghcr.io/thephaseless/byparr:latest
    environment:
      - LOG_LEVEL=INFO # optional
    ports:
      - "8191:8191" # Optional if needed to make make requests/check docs on host
```

## Need help with / TODO

- [x] Slimming container (only ~650 mB now!)
- [x] Add more anti-bot challenges
- [x] Add docstrings
- [x] Implement versioning
- [ ] Proxy support
- [x] Add more architectures support
