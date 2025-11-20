# Byparr

Built with [camoufox](https://camoufox.com/) and [FastAPI](https://fastapi.tiangolo.com), this project aims to mimic [FlareSolverr's](https://github.com/FlareSolverr/FlareSolverr) API and functionality of providing you with http cookies and headers for websites protected with anti-bot protections.

> [!IMPORTANT]
> This software does not **guarantee** (only greatly increases the chance) that any challenge will be bypassed. While this tool passes the initial browser check, Cloudflare and other captcha providers likely require valid network traffic originating from the user’s public IP address to mark a connection as legitimate. If any website does not pass the challenge, please run troubleshooting steps and check if other websites work before you create an GitHub issue.

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

| Environment Variable | Default   | Description                                                                                                                                                       |
| -------------------- | --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `HOST`               | `0.0.0.0` | Host address to bind the server to. Use `0.0.0.0` to bind to all IPv4 interfaces, `::` for all IPv6 interfaces, or `127.0.0.1`/`localhost` for local access only. |
| `PORT`               | `8191`    | Port to bind the server to.                                                                                                                                       |
| `PROXY_SERVER`       | None      | Proxy to use in format: `protocol://host:port`.                                                                                                                   |
| `PROXY_USERNAME`     | None      | Username for proxy authentication.                                                                                                                                |
| `PROXY_PASSWORD`     | None      | Password for proxy authentication.                                                                                                                                |

## Proxy Recommendation

Recently I've partnered with a _new in town_ proxy service - ProxyBase - to offer affordable proxy services that seems to work seamlessly with Byparr! Using my affiliate code `byparr` (case sensitive!) when signing up will not only get you access to their cost-effective (**$0.69/GB with occasional promotions** _at the time of writing_) proxy network but will also help support the continued development of this project. ProxyBase's proxies can significantly improve your success rate when bypassing anti-bot challenges. [Check out ProxyBase](https://client.proxybase.org/signup?ref=byparr) and enhance your Byparr experience!

## Tags

- `v*.*.*`/`latest` - Releases considered stable
- `main` - Latest release from main branch (untested)
- `pr-{number}` - Pull request images for testing (automatically cleaned up when PR closes)

## Usage

### Docker Compose

See `compose.yaml`

### Docker

```bash
docker run -p 8191:8191 ghcr.io/thephaseless/byparr:latest
```

### Local

```bash
uv sync && uv run main.py
```

## Need help with / TODO

- [x] Slimming container (only ~1.11 GB now!)
- [x] Add more anti-bot challenges
- [x] Add doc strings
- [x] Implement versioning
- [x] Proxy support
- [x] Add more architectures support
