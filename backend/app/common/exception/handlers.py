from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.common.exception.code import StatusCode
from app.common.exception.exception import AuthException, BusinessException
from app.common.result.result import Result
from app.infrastructure.log.logging_config import get_logger

logger = get_logger(__name__)


def register_exception_handlers(app) -> None:

    @app.exception_handler(AuthException)
    async def auth_handler(request: Request, exc: AuthException) -> JSONResponse:
        return JSONResponse(
            status_code=200,
            content=Result.error(code=exc.code, message=exc.message).model_dump(),
        )

    @app.exception_handler(BusinessException)
    async def business_handler(request: Request, exc: BusinessException) -> JSONResponse:
        return JSONResponse(
            status_code=200,
            content=Result.error(code=exc.code, message=exc.message).model_dump(),
        )

    @app.exception_handler(HTTPException)
    async def http_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=Result.error(code=exc.status_code, message=str(exc.detail)).model_dump(),
        )

    @app.exception_handler(Exception)
    async def global_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "-")
        logger.error(
            "Unhandled exception [rid=%s] %s %s: %s",
            request_id,
            request.method,
            request.url.path,
            exc,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content=Result.error(
                code=StatusCode.INTERNAL_ERROR.value.code,
                message=StatusCode.INTERNAL_ERROR.value.message,
            ).model_dump(),
        )
