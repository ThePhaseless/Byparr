# Byparr

<p align="center">
   <img src="icon/logo-byparr.svg" alt="Byparr logo" width="120" />
</p>

> [!IMPORTANT]
> This software does not **guarantee** (only greatly increases the chance) that any challenge will be bypassed. While this tool passes the initial browser check, Cloudflare and other captcha providers likely require valid network traffic originating from the user’s public IP address to mark a connection as legitimate. If any website does not pass the challenge, please run troubleshooting steps and check if other websites work before you create an GitHub issue.

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

> [!IMPORTANT]
> Support for NAS devices (like Synology) is minimal. Please report issues, but do not expect it to be fixed quickly. The only ARM device I have is a free Ampere Oracle VM, so I can only test ARM support on that. See [#22](https://github.com/ThePhaseless/Byparr/issues/22) and [#3](https://github.com/ThePhaseless/Byparr/issues/3)

### Docker Compose setup

1. Review settings in `compose.yaml`.
2. Start the service:

```bash
docker compose up -d
```

### Docker install

1. Pull and run the image:

   ```bash
   docker run -p 8191:8191 ghcr.io/thephaseless/byparr:latest
   ```

2. Optional: set env vars using `-e` or `--env-file`.

### Local install

1. Install ([or update when Python version changes](https://github.com/astral-sh/uv/issues/17887)) [uv](https://docs.astral.sh/uv/getting-started/installation/).
2. Clone this repo - `git clone https://github.com/ThePhaseless/Byparr`
3. Run `uv run main.py`
4. Enjoy!

### API Docs

Once running, open:

- `http://localhost:8191/docs`
- `http://localhost:8191/` (redirects to `/docs`)

## Troubleshooting

### Docker troubleshooting

1. Clone repo to the host that has issues with Byparr.
2. Run `docker build --target test .`
3. Depending of the build success:
   1. If run successfully, try updating container or if already on newest stable release create an issue for creating new release with new dependencies
   2. If build fails, try troubleshooting on another host/using other method

### Local troubleshooting

1. Download [uv](https://docs.astral.sh/uv/getting-started/installation/)
2. Download dependencies using `uv sync --group test`
3. Run tests with `uv run pytest --retries 3` (You can add `-n auto` for parallelization)
4. If you see any `F` character in terminal, that means test failed even after retries.
5. Depending of the test success:
   1. If run successfully, try updating container or if already on newest stable release create an issue for creating new release with new dependencies
   2. If test fails, try troubleshooting on another host/using other method
