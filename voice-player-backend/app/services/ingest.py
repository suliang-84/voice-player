"""入库：按地址把音频拉到本地。只负责校验地址与下载，不碰数据库和流水线。"""
from pathlib import Path
from urllib.parse import urlparse

import httpx

from ..config import Settings
from ..errors import AppError
from .storage import ALLOWED_EXTS

CONTENT_TYPE_EXT = {
    "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/wave": ".wav", "audio/vnd.wave": ".wav",
    "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/flac": ".flac", "audio/x-flac": ".flac",
    "audio/ogg": ".ogg", "audio/opus": ".opus", "audio/mp4": ".m4a", "audio/x-m4a": ".m4a",
    "audio/aac": ".aac", "audio/webm": ".webm", "audio/x-ms-wma": ".wma",
}


def check_url(settings: Settings, url: str) -> None:
    """只允许白名单主机的 http(s) 地址，避免被用来探测内网（SSRF）。"""
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise AppError(400, "source.url 必须是 http(s) 地址")
    allowed = {h.strip().lower() for h in settings.ingest_allowed_hosts.split(",") if h.strip()}
    if parts.hostname.lower() not in allowed and parts.netloc.lower() not in allowed:
        raise AppError(403, f"地址不在允许列表中：{parts.netloc}（请配置 INGEST_ALLOWED_HOSTS）")


def pick_ext(url: str, content_type: str, hint: str | None) -> str:
    """格式优先级：调用方指定 > 地址后缀 > Content-Type。"""
    candidates = [hint, Path(urlparse(url).path).suffix, CONTENT_TYPE_EXT.get(content_type.split(";")[0].strip().lower())]
    for c in candidates:
        if not c:
            continue
        c = c.lower()
        c = c if c.startswith(".") else f".{c}"
        if c in ALLOWED_EXTS:
            return c
    raise AppError(40003, "无法确定音频格式：请在 source.ext 中指定，或使用带后缀的地址")


def download(settings: Settings, url: str, headers: dict[str, str] | None, ext_hint: str | None, dest: Path) -> str:
    """流式下载到 dest，返回文件后缀。不跟随重定向（重定向目标没有经过白名单校验）；
    不读取环境里的代理设置（入库地址通常是内网，走代理会被拦）。"""
    try:
        with httpx.Client(timeout=settings.ingest_timeout, follow_redirects=False, trust_env=False) as client:
            with client.stream("GET", url, headers=headers) as resp:
                if resp.status_code != 200:
                    raise AppError(50001, f"下载音频失败：对方返回 {resp.status_code}", http_status=502)
                ext = pick_ext(url, resp.headers.get("content-type", ""), ext_hint)
                length = resp.headers.get("content-length")
                if length and length.isdigit() and int(length) > settings.max_upload_bytes:
                    raise AppError(40004, "文件大小超过限制")
                size = 0
                with dest.open("wb") as out:
                    for chunk in resp.iter_bytes(1 << 20):
                        size += len(chunk)
                        if size > settings.max_upload_bytes:
                            raise AppError(40004, "文件大小超过限制")
                        out.write(chunk)
                if size == 0:
                    raise AppError(400, "文件为空")
                return ext
    except httpx.HTTPError as e:
        raise AppError(50001, f"下载音频失败：{e.__class__.__name__}", http_status=502)
