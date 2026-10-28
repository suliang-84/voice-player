import asyncio
import logging

from fastapi import WebSocket

log = logging.getLogger("voice_player")


class Hub:
    """进程内 WebSocket 广播：工作线程通过 publish 线程安全地推送事件。"""

    def __init__(self):
        self.connections: set[WebSocket] = set()
        self.loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    async def connect(self, ws: WebSocket) -> None:
        self.connections.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.connections.discard(ws)

    def publish(self, event: dict) -> None:
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self._broadcast(event), self.loop)

    async def _broadcast(self, event: dict) -> None:
        for ws in list(self.connections):
            try:
                await ws.send_json(event)
            except Exception:
                self.disconnect(ws)
