import logging
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .errors import AppError

log = logging.getLogger("voice_player")


def envelope(data=None, code: int = 0, message: str = "success") -> dict:
    return {"code": code, "message": message, "data": data, "timestamp": int(time.time() * 1000)}


def ok(data=None, message: str = "success") -> dict:
    return envelope(data, 0, message)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, e: AppError):
        return JSONResponse(envelope(e.data, e.code, e.message), status_code=e.http_status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, e: RequestValidationError):
        detail = "; ".join(f"{'.'.join(str(p) for p in x['loc'][1:])}: {x['msg']}" for x in e.errors())
        return JSONResponse(envelope(None, 400, f"参数验证失败：{detail}"), status_code=400)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, e: StarletteHTTPException):
        message = {404: "资源不存在", 405: "请求方法不支持"}.get(e.status_code, str(e.detail))
        return JSONResponse(envelope(None, e.status_code, message), status_code=e.status_code,
                            headers=getattr(e, "headers", None))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, e: Exception):
        log.exception("unhandled error")
        return JSONResponse(envelope(None, 500, "服务端错误"), status_code=500)
