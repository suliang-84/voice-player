from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 10090
    cors_origins: str = "*"  # 逗号分隔；播放器作为公共组件可能跨域访问

    # 存储
    data_dir: Path = Path("data")
    database_url: str = ""  # 为空时使用 data_dir/voice_player.db（SQLite）
    max_upload_bytes: int = 500 * 1024 * 1024

    # 波形 / 静音默认值
    default_peaks_points: int = 8000
    default_silence_threshold: float | None = None  # RMS（0～1）；为空则按各声道底噪自适应
    default_silence_min_duration: float = 1.0
    silence_frame_ms: int = 10
    silence_margin_db: float = 12.0  # 自适应阈值 = 底噪 + 该值
    silence_speech_offset_db: float = 20.0  # 自适应阈值的另一依据：语音电平 − 该值。越小越容易判静音（越激进）
    silence_smooth_ms: int = 150  # 帧能量先做该时长的滑动平滑，抹掉数十毫秒的小杂音
    silence_min_speech: float = 0.3  # 联合静音：夹在静音间短于该秒数的有声帧并入静音
    silence_padding: float = 0.15  # 联合静音：可跳过区间两端各留出的秒数

    # 外部工具
    ffmpeg_bin: str = "ffmpeg"
    ffmpeg_timeout: int = 600

    # 鉴权：token 由业务系统签发，这里只校验（HS256）
    auth_enabled: bool = False
    jwt_secret: str = "change-me"
    access_token_ttl: int = 3600
    refresh_token_ttl: int = 7 * 24 * 3600

    # 转写：faster-whisper（需安装 requirements-asr.txt）；none 表示不启用
    asr_provider: str = "faster-whisper"
    whisper_model: str = "small"
    whisper_device: str = "auto"
    whisper_compute_type: str = "default"
    asr_load_timeout: float = 120  # 转写任务等待模型加载（首次使用需下载）的最长秒数
    asr_retry_interval: float = 60  # 模型加载失败后，隔多久才允许在下次访问时重新加载（期间前端能稳定看到失败原因）

    # 大模型（OpenAI 兼容接口）：用于身份推断、场景分析、翻译；未配置则退回 unknown / 空
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout: int = 120
    llm_max_chars: int = 12000
    default_translation_language: str = "en"

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audios"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def db_url(self) -> str:
        return self.database_url or f"sqlite:///{(self.data_dir / 'voice_player.db').resolve()}"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_base_url and self.llm_model)

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.audio_dir, self.cache_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
