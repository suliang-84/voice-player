import time

import jwt
from fastapi import Request

from .config import Settings
from .errors import AppError

ANONYMOUS = "anonymous"


def _encode(settings: Settings, sub: str, kind: str, ttl: int) -> str:
    now = int(time.time())
    return jwt.encode({"sub": sub, "typ": kind, "iat": now, "exp": now + ttl}, settings.jwt_secret, algorithm="HS256")


def issue_tokens(settings: Settings, user_id: str) -> dict:
    return {
        "token": _encode(settings, user_id, "access", settings.access_token_ttl),
        "refreshToken": _encode(settings, user_id, "refresh", settings.refresh_token_ttl),
        "expiresIn": settings.access_token_ttl,
    }


def decode(settings: Settings, token: str, *, kind: str | None = None, verify_exp: bool = True) -> dict:
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"],
                            options={"verify_exp": verify_exp, "require": ["sub"]})
    except jwt.PyJWTError:
        raise AppError(401, "未授权：令牌无效或已过期")
    if kind and claims.get("typ") != kind:
        raise AppError(401, "未授权：令牌类型不正确")
    return claims


def bearer_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    # <audio> 元素无法携带 Authorization 头，/stream 允许 query 传 token
    return request.query_params.get("token", "")


def current_user(request: Request) -> str:
    settings: Settings = request.app.state.settings
    if not settings.auth_enabled:
        return ANONYMOUS
    token = bearer_token(request)
    if not token:
        raise AppError(401, "未授权：缺少访问令牌")
    return decode(settings, token, kind="access")["sub"]
