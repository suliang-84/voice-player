import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from .. import deps
from ..auth import bearer_token, current_user, decode, issue_tokens, ANONYMOUS
from ..envelope import ok
from ..errors import AppError
from ..models import UserSettings
from ..services.pipeline import _iso

router = APIRouter(prefix="/api/v1")

DEFAULTS = {
    "playback": {"defaultSpeed": 1.0, "seekStep": 5, "playMode": "single", "skipSilence": False,
                 "stereo": False},
    "ui": {"theme": "light", "chatPanelVisible": False},
}


class PlaybackPatch(BaseModel):
    defaultSpeed: float | None = None
    seekStep: float | None = None
    playMode: str | None = None
    skipSilence: bool | None = None
    stereo: bool | None = None


class UiPatch(BaseModel):
    theme: str | None = None
    chatPanelVisible: bool | None = None


class SettingsPatch(BaseModel):
    playback: PlaybackPatch | None = None
    ui: UiPatch | None = None


def _validate(patch: dict) -> None:
    pb, ui = patch.get("playback", {}), patch.get("ui", {})
    if "defaultSpeed" in pb and not 0.5 <= pb["defaultSpeed"] <= 3.0:
        raise AppError(400, "defaultSpeed 取值范围为 0.5～3.0")
    if "seekStep" in pb and not 1 <= pb["seekStep"] <= 60:
        raise AppError(400, "seekStep 取值范围为 1～60 秒")
    if "playMode" in pb and pb["playMode"] not in ("single", "sequence"):
        raise AppError(400, "playMode 只能是 single 或 sequence")
    if "theme" in ui and ui["theme"] not in ("light", "dark"):
        raise AppError(400, "theme 只能是 light 或 dark")


def _merged(stored: dict | None) -> dict:
    stored = stored or {}
    return {k: {**DEFAULTS[k], **stored.get(k, {})} for k in DEFAULTS}


@router.get("/users/settings")
def get_settings(request: Request, user: str = Depends(current_user)):
    with deps.db_of(request).session() as s:
        row = s.get(UserSettings, user)
        return ok(_merged(row.data if row else None))


@router.put("/users/settings")
def update_settings(request: Request, body: SettingsPatch, user: str = Depends(current_user)):
    patch: dict[str, Any] = body.model_dump(exclude_none=True)
    _validate(patch)
    with deps.db_of(request).session() as s:
        row = s.get(UserSettings, user)
        stored = dict((row.data if row else None) or {})
        for k, v in patch.items():
            stored[k] = {**stored.get(k, {}), **v}
        if row:
            row.data = stored
        else:
            row = UserSettings(user_id=user, data=stored)
            s.add(row)
        s.commit()
        s.refresh(row)
        return ok({**_merged(row.data), "updatedAt": _iso(row.updated_at)}, "设置更新成功")


class RefreshBody(BaseModel):
    refreshToken: str | None = None


@router.post("/auth/refresh")
def refresh(request: Request, body: RefreshBody | None = None):
    """支持两种方式：body.refreshToken；或 Authorization 携带（可已过期的）访问令牌。"""
    settings = deps.settings_of(request)
    if body and body.refreshToken:
        claims = decode(settings, body.refreshToken, kind="refresh")
    else:
        token = bearer_token(request)
        if not token:
            raise AppError(401, "未授权：缺少令牌")
        claims = decode(settings, token, verify_exp=False)
        if claims.get("typ") != "access" or claims.get("exp", 0) + settings.refresh_token_ttl < time.time():
            raise AppError(401, "未授权：令牌已超出可刷新期限")
    return ok(issue_tokens(settings, claims["sub"] or ANONYMOUS))

