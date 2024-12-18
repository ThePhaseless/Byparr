# Byparr

An alternative to [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) as a drop-in replacement, build with [seleniumbase](https://seleniumbase.io/) and [FastAPI](https://fastapi.tiangolo.com).

> [!IMPORTANT]
> Due to recent challenge changes, this software does not guarantee that the Cloudflare challenge will be bypassed. Cloudflare likely requires valid network traffic originating from the user’s public IP address to mark a connection as legitimate. While this tool may bypass the initial browser check, it does not ensure that requests will consistently pass Cloudflare's validation. More testing and data are required to understand how Cloudflare identifies connections and requests as valid. Invalid requests will result in Byparr's looping and eventually time-outing.

> [!IMPORTANT]
> Support for NAS devices (like Synology) is minimal. Please report issues, but do not expect it to be fixed quickly. The only ARM device I have is a free Ampere Oracle VM, so I can only test ARM support on that. See [#22](https://github.com/ThePhaseless/Byparr/issues/22) and [#3](https://github.com/ThePhaseless/Byparr/issues/3)

> [!NOTE]
> Thanks to FastAPI implementation, now you can also see the API documentation at `/docs` or `/` (redirect to `/docs`) endpoints.

## Troubleshooting (Docker required)

1. Clone repo to the host that has the container has issues on.
2. Using vscode and `SSH extension`, connect to the host and open repo in it.
3. Download `Dev Containers` extension and reopen repo in container (with `CTRL + SHIFT + P` -> `Reopen in devcontainer`)
4. Forward port 6080 from devcontainer (port of noVNC server) to the host.
5. Open `http://localhost:6080` and connect to the virtual desktop.
6. Check if `chromium` works by running in VNC's terminal command `chromium --no-sandbox`.
7. If chromium works, run (or debug) tests from VS Code.
   1. If code works, congrats! (not really) You are on your own.
   2. If it does not, try on another host or network and create an issue if problem persists.

## Options

| Env        | Default | Description                                                                                                                |
| ---------- | ------- | -------------------------------------------------------------------------------------------------------------------------- |
| `USE_XVFB` | `false` | Use Xvfb instead of headless chromium. (Can cause performance hog [#14](https://github.com/ThePhaseless/Byparr/issues/14)) |

## Tags

- `v*.*.*`/`latest` - Releases considered stable
- `main` - Latest release from main branch (untested)

## Usage

### Docker Compose

See `compose.yaml`

### Docker

```bash
docker run -p 8191:8191 ghcr.io/thephaseless/byparr:latest
```

### Local

```bash
uv sync && ./cmd.sh
```

## Need help with / TODO

- [x] Slimming container (only ~650 MB now!)
- [x] Add more anti-bot challenges
- [x] Add doc strings
- [x] Implement versioning
- [ ] Proxy support
- [x] Add more architectures support
