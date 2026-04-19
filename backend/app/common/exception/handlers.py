from fastapi.responses import JSONResponse

from app.common.exception.code import StatusCode
from app.common.exception.exception import AuthException, BusinessException
from app.common.result.result import Result

def register_exception_handlers(app):
    @app.exception_handler(AuthException)
    async def auth_handler(request, exc: AuthException):
        return JSONResponse(
            status_code=200,
            content=Result.error(
                code=exc.code,
                message=exc.message,
            ).model_dump()
        )

    @app.exception_handler(BusinessException)
    async def business_handler(request, exc: BusinessException):
        return JSONResponse(
            status_code=200,
            content=Result.error(
                code=exc.code,
                message=exc.message,
            ).model_dump()
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc: Exception):
        return JSONResponse(
            status_code=200,
            content=Result.error(
                code=StatusCode.INTERNAL_ERROR.value.code,
                message=StatusCode.INTERNAL_ERROR.value.message,
                data=None
            ).model_dump()
        )