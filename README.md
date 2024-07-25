# Byparr

An alternative to [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) as drop-in replacement, build with [nodriver](https://github.com/ultrafunkamsterdam/nodriver) and [FastAPI](https://fastapi.tiangolo.com).

> [!IMPORTANT]
> Currenly, due to [bug in nodriver](https://github.com/ultrafunkamsterdam/undetected-chromedriver/issues/1954), if you run ouside of prebuild container, you have to run `python fix_nodriver.py` after creating venv.

> [!NOTE]
> Thanks to FastAPI implementation, now you can also see the API documentation at `/docs` or `/` (redirect to `/docs`) endpoints.

## Early Development

Long story short, I created it in like 3 days, so if you get any bugs/hangs etc. please report, so both of us can enjoy non-blocked websites!

I focues maily on Cloudflare, which should be passing normally, I see one other anti-bot challenge, which passed normally, but please report these providers with example website ❤️

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

## Future Development

- [ ] Add more anti-bot challenges
- [ ] Add docstrings
- [ ] Use tabs instead of sprawning new browsers
