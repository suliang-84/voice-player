# voice-player-backend

语音播放器后端：实现 `docs/接口设计说明书.md` 的全部接口，并提供播放器所需的音频流。
FastAPI + SQLAlchemy（默认 SQLite），**单进程**运行（任务调度与 WebSocket 广播都在进程内）。

## 运行

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m app            # 默认 http://localhost:10090
```

前端 `vite` 开发代理默认指向 `10090`，直接 `npm run dev` 即可联调。
测试：`.venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest`。

## 接口

契约接口见接口设计说明书（统一 envelope、业务码 40001–50002；HTTP 状态码如实返回，`40002` 为 200）。额外接口：

| 接口 | 说明 |
|---|---|
| `POST /api/v1/audios` | 上传音频（multipart `file`，可选 `audioId`），返回 `audioId/duration/sampleRate/channels`，并触发后台峰值与转写 |
| `GET /api/v1/audios/{id}/stream?track=A\|B` | 该轨单声道 WAV，支持 Range；鉴权开启时可用 `?token=` |
| `GET /health` | 引擎状态 |

音频存放在 `DATA_DIR/audios/{audioId}.<ext>`，`audioId` 即文件名；也可以直接把文件放进该目录。
**A 轨 = 左声道，B 轨 = 右声道**，单声道文件只有 A 轨。非 WAV 格式（mp3/m4a 等）依赖 ffmpeg 转码。

## 能力与降级

| 能力 | 实现 | 未配置时 |
|---|---|---|
| peaks / silences / stream | soundfile 分块流式处理，peaks 与声道文件落盘缓存 | — |
| 转写 | 每个声道独立转写（声道即说话人），faster-whisper，后台任务，进度经 WebSocket 推送；未完成时 `40002` | `status: "failed"` + `error` 说明原因 |
| 疑似身份 / 场景 / 翻译 | 大模型根据转写内容推断，身份为自由描述（如“某公司老板”），线索不足为 `unknown`；默认语种在转写后预翻译，其它语种按需翻译 | 身份 `unknown`、`scenes: []`、译文为空 |
| 转写/翻译编辑、用户设置 | 落库；设置按用户保存，PUT 为合并语义并校验取值 | — |
| WebSocket `/ws?token=` | `peaks_generated`、`transcription_progress`、`transcription_completed` | — |
| 鉴权 | `AUTH_ENABLED=true` 时校验 HS256 JWT；`/auth/refresh` 支持 `refreshToken` 或（可已过期的）访问令牌 | 关闭，所有请求视为同一匿名用户 |

大模型调用失败不影响转写结果，仅该部分退回默认值。

## 已知限制

- 没有声纹识别；身份只来自对话内容推断，`confidence` 是模型自评，没有校准。
- 没有登录接口：token 由业务系统签发。
- 音频不按用户隔离（契约未定义归属）；上传的音频所有已认证用户都可访问。
- 转写任务在进程内排队（2 个并发）；服务重启会自动恢复未完成的任务。
- 峰值与静音超过 2 声道的音频只处理前两个声道。
