import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, get_settings
from .db import Database
from .envelope import install_error_handlers, ok
from .routers import account, audios, content, ws
from .services.asr import AsrProvider, build_provider
from .services.hub import Hub
from .services.llm import LlmClient
from .services.pipeline import Pipeline
from .services.storage import Storage

log = logging.getLogger("voice_player")


def create_app(settings: Settings | None = None, *, asr: AsrProvider | None = None,
               asr_error: str = "", llm: LlmClient | None = None) -> FastAPI:
    """asr / llm 可注入（测试用）；未注入时按配置构建。"""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.auth_enabled and settings.jwt_secret in ("", "change-me"):
            raise RuntimeError("AUTH_ENABLED=true 时必须设置 JWT_SECRET")
        settings.ensure_dirs()
        db = Database(settings.db_url)
        db.create_all()
        hub = Hub()
        hub.bind_loop(asyncio.get_running_loop())
        provider, err = (asr, asr_error) if asr is not None else build_provider(settings)
        client = llm or (LlmClient(settings) if settings.llm_enabled else None)
        storage = Storage(settings)
        pipeline = Pipeline(settings, db, storage, hub, provider, err, client)
        app.state.settings, app.state.db, app.state.hub = settings, db, hub
        app.state.storage, app.state.pipeline = storage, pipeline
        if provider is None:
            log.warning("转写引擎不可用：%s", err)
        if hasattr(provider, "start_preload"):
            provider.start_preload()  # 后台加载模型，不阻塞启动
        pipeline.resume_unfinished()
        yield
        pipeline.shutdown()

    app = FastAPI(title="voice-player-backend", version="1.0.0", lifespan=lifespan)
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"],
                       expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"])
    install_error_handlers(app)
    for r in (audios.router, content.router, account.router, ws.router):
        app.include_router(r)

    @app.get("/health")
    def health():
        p = app.state.pipeline
        state = p.engine_state()
        return ok({"status": "ok" if state == "ready" else "degraded", "asr": state == "ready",
                   "asrState": state, "asrError": getattr(p.asr, "error", "") or p.asr_error,
                   "llm": p.llm is not None})

    return app

