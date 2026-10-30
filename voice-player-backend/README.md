# voice-player-backend

语音播放器后端：实现 `docs/接口设计说明书.md` 的接口，并提供播放器所需的音频流、波形、静音检测和下载。
FastAPI + SQLAlchemy（默认 SQLite），**单进程**运行（任务调度与 WebSocket 广播都在进程内）。

> 项目总览、当前哪些是 mock、如何接入真实模型，见仓库根目录的 [README.md](../README.md)。

## 运行

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env               # 默认 ASR_PROVIDER=mock、LLM_PROVIDER=mock，不需要任何模型
.venv/bin/python -m app            # 默认 http://localhost:10090
```

- 前端 `vite` 开发代理默认指向 `10090`，直接 `npm run dev` 即可联调。
- 改了 `.env` 要重启才生效。
- 测试：`.venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest`（73 个用例，测试里用假引擎，不调用真实模型）。
- 非 WAV 音频（mp3、m4a 等）依赖 ffmpeg 转码。

## 接口

契约接口见 `docs/接口设计说明书.md`（统一信封、业务码 40001–50002；HTTP 状态码如实返回，`40002` 为 200）。当前全部路由：

| 接口 | 说明 |
|---|---|
| `GET /api/v1/audios/{id}/stream?track=A\|B` | 该轨单声道 WAV，支持 Range；鉴权开启时可用 `?token=` |
| `GET /api/v1/audios/{id}/peaks` | 波形峰值，计算后缓存 |
| `GET /api/v1/audios/{id}/silences` | 静音区间。`tracks` 是每路单独的静音；`both` 是 **A、B 两路同时静音**的可跳过区间 + 与之互补的有声区间（`activeSegments`），默认阈值自适应、最短 1 秒 |
| `GET /api/v1/audios/{id}/download?track=A\|B\|mix\|stereo&start=&end=` | 下载 WAV：单路、两路混成单声道（`mix`）、立体声 A 左 B 右（`stereo`）；给 `start`/`end`（秒）只含该时间范围 |
| `GET /api/v1/audios/{id}/transcripts`、`translations`、`speakers`、`scenes` | 转写、译文、说话人、场景；转写未完成时 `40002` |
| `PUT /api/v1/transcripts/{id}/text`、`PUT /api/v1/translations/{id}` | 编辑转写 / 译文 |
| `GET/PUT /api/v1/users/settings` | 用户设置（倍速、步长、播放模式、跳过空音、立体声、主题、聊天面板），PUT 为合并语义并校验 |
| `POST /api/v1/auth/refresh` | 刷新令牌 |
| `POST /api/v1/audios/{id}/ingest` | **生产入口**：入库系统完成入库后调用，body 为 `{"source":{"type":"url","url":"…"},"force":false}`，后端按地址把音频拉到本地并触发后台峰值与转写；幂等；需配置 `INGEST_ALLOWED_HOSTS` |
| `POST /api/v1/audios` | 上传音频（multipart `file`，可选 `audioId`），仅用于开发测试；生产设 `UPLOAD_ENABLED=false` 关闭 |
| `WS /ws?token=` | 推送 `peaks_generated`、`transcription_progress`、`transcription_completed` |
| `GET /health` | 引擎状态（`asrState`：`loading/ready/failed/unavailable`） |

## 音频与数据

- 音频存放在 `DATA_DIR/audios/{audioId}.<ext>`，`audioId` 即文件名（规则 `^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$`）；也可以直接把文件放进该目录。
- **后端里没有对应音频时，`/stream`、`peaks` 等都返回 `40001`，播放器会显示「音频加载失败」。** `data/` 不入 git，克隆后执行 `.venv/bin/python scripts/seed_demo.py`，把仓库自带的演示音频（`demo/audio_003.flac`，AMI 真实会议录音，来源见 `demo/README.md`）复制进 `data/audios/`。
- **A 轨 = 左声道，B 轨 = 右声道**，单声道文件只有 A 轨。
- 派生文件在 `DATA_DIR/cache/{audioId}/`（`track_A.wav`、`track_B.wav`、`peaks_*.json`、`silences_*.json`），按源文件修改时间失效，删掉即可重算。

## 配置（`.env`，完整示例见 `.env.example`）

| 类别 | 配置项 | 说明 |
|---|---|---|
| 服务 | `HOST`、`PORT`（10090）、`CORS_ORIGINS`、`DATA_DIR`、`DATABASE_URL` | `DATABASE_URL` 为空时用 `DATA_DIR/voice_player.db`（SQLite） |
| 音频入口 | `UPLOAD_ENABLED`、`INGEST_ALLOWED_HOSTS`、`INGEST_TIMEOUT`、`MAX_UPLOAD_BYTES` | `INGEST_ALLOWED_HOSTS` 为空则不接受任何地址（防止被用来探测内网） |
| 静音 | `DEFAULT_SILENCE_THRESHOLD`（空 = 自适应）、`DEFAULT_SILENCE_MIN_DURATION`（1.0）、`SILENCE_SPEECH_OFFSET_DB`（20）、`SILENCE_MARGIN_DB`、`SILENCE_SMOOTH_MS`、`SILENCE_MIN_SPEECH`、`SILENCE_PADDING` | 只在 `audio_003` 上调过；`SILENCE_SPEECH_OFFSET_DB` 越小越容易判为静音 |
| 鉴权 | `AUTH_ENABLED`、`JWT_SECRET`、`ACCESS_TOKEN_TTL`、`REFRESH_TOKEN_TTL` | 开启时必须改 `JWT_SECRET` |
| 转写 | `ASR_PROVIDER`（`mock` / `faster-whisper` / `none`）、`MOCK_DELAY`、`WHISPER_MODEL`、`WHISPER_DEVICE`、`WHISPER_COMPUTE_TYPE`、`ASR_LOAD_TIMEOUT`、`ASR_RETRY_INTERVAL` | 默认 `mock` |
| 大模型 | `LLM_PROVIDER`（`mock` 或空）、`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`LLM_TIMEOUT`、`LLM_MAX_CHARS`、`DEFAULT_TRANSLATION_LANGUAGE` | `LLM_PROVIDER=mock` 时忽略后面三项地址配置 |
| 外部工具 | `FFMPEG_BIN`、`FFMPEG_TIMEOUT` | |

## 能力与降级

| 能力 | 实现 | 未配置时 |
|---|---|---|
| peaks / silences / stream / download | soundfile 分块流式处理，peaks、静音结果与声道文件落盘缓存 | — |
| 转写 | 每个声道独立转写（声道即说话人），后台任务，进度经 WebSocket 推送；未完成时 `40002`。引擎可选：**`mock`**（默认，见下）、`faster-whisper`（真实，需 `requirements-asr.txt`，启动时后台预加载模型） | `status: "failed"` + `error` 说明原因 |
| 疑似身份 / 场景 / 翻译 | 大模型根据转写内容推断；默认语种在转写后预翻译，其它语种按需翻译。可选：**`mock`**（默认）或 OpenAI 兼容接口 | 身份 `unknown`、`scenes: []`、译文为空 |
| 转写 / 翻译编辑、用户设置 | 落库；设置按用户保存 | — |
| 鉴权 | `AUTH_ENABLED=true` 时校验 HS256 JWT；`/auth/refresh` 支持 `refreshToken` 或（可已过期的）访问令牌 | 关闭，所有请求视为同一匿名用户 |

大模型调用失败不影响转写结果，仅该部分退回默认值。

### mock 模式（默认）

没有真实模型时用来跑通整条流程，实现在 `app/services/mock.py`：

- **转写**（`ASR_PROVIDER=mock`）：按音频**真实的说话时段**切句，所以播放时高亮的句子和波形对得上；**句子文字是虚构的**，内容是「遥控器设计启动会议」（A 路项目经理、B 路工业设计师）。同一声道每次结果一致。
- **身份、场景、翻译**（`LLM_PROVIDER=mock`）：对任何音频都返回同样的固定内容；`?language=zh` 返回内置的中文译文，其它语种加语种前缀。
- 不用于评估转写效果。接入真实模型的方法见根目录 README 的「接入真实模型」。

### 引擎加载慢或失败（faster-whisper）

任务最多等待 `ASR_LOAD_TIMEOUT` 秒（默认 120），模型仍未就绪就置为 `failed`，`error` 说明原因，不会一直停在 0%。模型就绪后下次访问自动重试；加载失败时需隔 `ASR_RETRY_INTERVAL` 秒（默认 60）才重新尝试加载。离线环境可把 `WHISPER_MODEL` 设为本地的 faster-whisper 模型目录。
**已知问题：** 在开发机上该引擎报 `open() got an unexpected keyword argument 'metadata_errors'`（疑为依赖版本不匹配，未排查）。因为这类错误不属于「引擎不可用」，任务会停在 `failed` 而不会自动重试；切换引擎后需要清掉对应的失败任务（删除 `tasks` 表里该 `audio_id` 的记录），或用 `ingest` 的 `force=true` 重新处理。

## 已知限制

- 转写、身份、场景目前是 mock；说话人分离、情感、声纹、串音过滤都没有做（设计稿见 `docs/本机模型对接实现方案.md`）。
- 数据库用 `create_all` 建表，**不会给已存在的表加列**，改表结构要自己迁移或删库。
- 没有登录接口：token 由业务系统签发。
- 音频不按用户隔离（契约未定义归属）；所有已认证用户都可访问。
- 转写任务在进程内排队（2 个并发）；服务重启会自动恢复未完成的任务。
- 峰值与静音超过 2 声道的音频只处理前两个声道。
