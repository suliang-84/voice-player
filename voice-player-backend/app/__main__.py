import logging

import uvicorn

from .config import get_settings

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    s = get_settings()
    # 单进程：任务调度与 WebSocket 广播都在进程内
    uvicorn.run("app.main:create_app", factory=True, host=s.host, port=s.port, workers=1)
