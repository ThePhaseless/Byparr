import time
from http import HTTPStatus

from starlette.middleware.base import BaseHTTPMiddleware

from src.models import LinkRequest
from src.utils import logger


class LogRequest(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        """Log requests."""
        if request.url.path != "/v1":
            return await call_next(request)

        start_time = time.perf_counter()
        request_body = LinkRequest.model_validate(await request.json())
        logger.info(
            f"From: {request.client.host if request.client else 'unknown'} at {time.strftime('%Y-%m-%d %H:%M:%S')}: {request_body.url}"
        )
        response = await call_next(request)
        process_time = time.perf_counter() - start_time

        if response.status_code == HTTPStatus.OK:
            logger.info(f"Done {request_body.url} in {process_time:.2f}s")
        else:
            logger.info(f"Failed {request_body.url} in {process_time:.2f}s")

        return response
