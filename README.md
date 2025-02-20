# Byparr

An alternative to [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) as a drop-in replacement, built with [seleniumbase](https://seleniumbase.io/) and [FastAPI](https://fastapi.tiangolo.com).

> [!IMPORTANT]
> Due to recent challenge changes, this software does not guarantee that the Cloudflare challenge will be bypassed. Cloudflare likely requires valid network traffic originating from the user’s public IP address to mark a connection as legitimate. While this tool may bypass the initial browser check, it does not ensure that requests will consistently pass Cloudflare's validation. More testing and data are required to understand how Cloudflare identifies connections and requests as valid. Invalid requests will result in Byparr's looping and eventually time-outing.

> [!IMPORTANT]
> Support for NAS devices (like Synology) is minimal. Please report issues, but do not expect it to be fixed quickly. The only ARM device I have is a free Ampere Oracle VM, so I can only test ARM support on that. See [#22](https://github.com/ThePhaseless/Byparr/issues/22) and [#3](https://github.com/ThePhaseless/Byparr/issues/3)

> [!NOTE]
> Thanks to FastAPI implementation, now you can also see the API documentation at `/docs` or `/` (redirect to `/docs`) endpoints.

## Troubleshooting

### Docker

1. Clone repo to the host that has issues with Byparr.
2. Run `docker build --target test .`
3. Depending of the build success:
   1. If run successfully, try updating container or if already on newest stable release create an issue for creating new release with new dependencies
   2. If build fails, try troubleshooting on another host/using other method

### Local

1. Download [uv](https://docs.astral.sh/uv/getting-started/installation/)
2. Download dependencies using `uv sync --group test`
3. Run tests with `uv run pytest --retries 3` (You can add `-n auto` for parallelization)
4. If you see any `F` character in terminal, that means test failed even after retries.
5. Depending of the test success:
   1. If run successfully, try updating container or if already on newest stable release create an issue for creating new release with new dependencies
   2. If test fails, try troubleshooting on another host/using other method

## Options

| Env            | Default                | Description                                                                                                                     |
| -------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `USE_XVFB`     | `SeleniumBase default` | Use virtual desktop with Xvfb. (Linux only) (Can cause performance hog [#14](https://github.com/ThePhaseless/Byparr/issues/14)) |
| `USE_HEADLESS` | `SeleniumBase default` | Use headless  chromium.                                                                                                         |
| `PROXY`        | None                   | Proxy to use. (format: `username:password@host:port`)                                                                           |

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
- [x] Proxy support
- [x] Add more architectures support
