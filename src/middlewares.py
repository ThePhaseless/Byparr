import time
from http import HTTPStatus
from json import JSONDecodeError

from fastapi import Request
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from src.models import LinkRequest
from src.utils import logger


class LogRequest(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        """Log requests."""
        if request.url.path != "/v1" or request.method != "POST":
            return await call_next(request)

        start_time = time.perf_counter()
        try:
            request_body = LinkRequest.model_validate(await request.json())
            request_url = request_body.url
        except (JSONDecodeError, ValidationError) as e:
            # Malformed body — let FastAPI's own validation produce the 4xx
            # instead of crashing the middleware with a 500.
            logger.debug(f"Could not pre-parse request body for logging: {e}")
            request_url = "<unparseable>"

        logger.info(
            f"From: {request.client.host if request.client else 'unknown'} at {time.strftime('%Y-%m-%d %H:%M:%S')}: {request_url}"
        )
        response = await call_next(request)
        process_time = time.perf_counter() - start_time

        if response.status_code == HTTPStatus.OK:
            logger.info(f"Done {request_url} in {process_time:.2f}s")
        else:
            logger.warning(f"Failed {request_url} in {process_time:.2f}s")

        return response
