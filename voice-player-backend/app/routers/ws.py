from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..auth import decode
from ..errors import AppError

router = APIRouter()


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    settings, hub = ws.app.state.settings, ws.app.state.hub
    if settings.auth_enabled:
        try:
            decode(settings, ws.query_params.get("token", ""), kind="access")
        except AppError:
            await ws.close(code=4401)
            return
    await ws.accept()
    await hub.connect(ws)
    try:
        while True:
            await ws.receive_text()  # 仅保持连接；忽略客户端消息
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(ws)
