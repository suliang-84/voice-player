# voice-player 双轨语音播放器

通话 / 对话录音的双轨（A 路、B 路）播放器：波形展示、跳过空音、混声 / 立体声播放、按路或合并下载、选区截取，以及转写、说话人身份、场景分析。前端 Vue 3 组件 + 后端 FastAPI 服务。

> **接手须知（先看这里）**
> 1. 转写、说话人身份、场景、翻译**现在全是 mock 数据**（见第四章），没有对接任何真实模型。**你们要做的就是把真实模型接进来**（第五章）。
> 2. `data/`（音频副本、缓存、数据库）不在 git 里；克隆后执行 `scripts/seed_demo.py`，把仓库自带的演示音频复制进去（第三章）。

## 一、仓库结构

```
voice-player/
├── README.md                        # 本文：总入口
├── docs/
│   ├── 接口设计说明书.md             # ⭐ 接口契约（唯一权威）
│   ├── 实现方案.md                    # ⭐ 当前实现：前后端架构、流程、与模型的对接、模型能力
│   ├── 本机模型对接实现方案.md        # 模型部署在本机时的对接方案（设计稿；mock、入库已落地，真实模型待接入）
│   └── 本地模型转写方案.md            # 模型在另一台机器时的对接指南（设计稿，未实现）
├── voice-player-backend/            # 后端：FastAPI + SQLAlchemy(SQLite)，详见其 README
│   ├── app/
│   │   ├── main.py                  # 应用装配：引擎、大模型、流水线、路由
│   │   ├── config.py                # 全部配置项（环境变量 / .env）
│   │   ├── routers/                 # audios（音频、波形、静音、下载、入库）、content（转写等）、account、ws
│   │   └── services/                # asr、llm、mock、pipeline、audio、storage、ingest、*_cache
│   ├── demo/                        # 演示音频 audio_003.flac（入 git）、AMI 原始录音 source/ 及来源说明
│   ├── scripts/seed_demo.py         # 把 demo/ 里的演示音频复制进 data/audios
│   ├── tests/                       # pytest，73 个用例
│   └── data/                        # 运行时数据（不入 git）：audios/、cache/、voice_player.db
└── voice-player-frontend/           # 前端：Vue 3 + Vite + WaveSurfer.js 7，详见其 README
    └── src/
        ├── App.vue                  # 演示页：播放列表
        ├── components/VoicePlayer.vue   # ⭐ 核心播放器组件（单文件，约 1700 行）
        ├── composables/useAudioData.js  # 按 audioId 拉取波形、静音、转写、说话人、场景
        └── api/                     # axios 封装、接口、鉴权、WebSocket
```

## 二、快速开始

需要：Python 3.10+（开发环境用的是 3.13）、Node 18+、ffmpeg（非 WAV 音频转码用）。

```bash
# 1. 后端（端口 10090）
cd voice-player-backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # 默认 ASR_PROVIDER=mock、LLM_PROVIDER=mock，无需任何模型
.venv/bin/python -m app

# 2. 前端（端口 5173，开发代理 /api、/ws 到 10090）
cd voice-player-frontend
npm install && npm run dev      # → http://localhost:5173

# 3. 后端测试
cd voice-player-backend
.venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest
```

改了 `.env` 要**重启后端**才生效。前端播放哪条音频由 `voice-player-frontend/src/App.vue` 的 `playlist` 决定（目前只有 `audio_003`）。

## 三、演示数据

后端按 `audioId` 在 `data/audios/{audioId}.<ext>` 找音频，**没有对应文件时所有音频相关接口返回 `40001`，播放器显示「音频加载失败」**。`data/` 不入 git，但演示音频随仓库提供在 `voice-player-backend/demo/`，克隆后执行一次：

```bash
cd voice-player-backend && .venv/bin/python scripts/seed_demo.py   # 把 demo/ 里的音频复制进 data/audios/，已存在的跳过
```

| audioId | 内容 |
|---|---|
| `audio_003` | **真实多人会议录音**（AMI 会议语料 ES2002a，约 21 分钟，英文，无损 FLAC 约 38MB）。A 路 = Headset-1，B 路 = Headset-3，立体声 A 左 B 右 |

AMI 的 A、B 两路**原始录音**（无损 FLAC）也随仓库放在 `voice-player-backend/demo/source/`，不需要再去官网下载；来源、许可（CC BY，使用时需署名）和用它们重新生成 `audio_003` 的命令见 `voice-player-backend/demo/README.md`。这是**会议**不是电话，且麦克风之间有串音。原来的 `audio_001`、`audio_002` 旧演示数据已删除。

## 四、当前状态：哪些是真的，哪些是 mock

| 功能 | 状态 |
|---|---|
| 播放、双轨同步、波形、缩放、选区、书签、主题、键盘快捷键 | ✅ 真实实现 |
| 波形峰值（peaks） | ✅ 后端真实计算并缓存 |
| 跳过空音：A、B 两路**同时**静音才跳；波形上标出有声部分 | ✅ 真实实现（自适应阈值，只在 `audio_003` 上调过参） |
| 混声 / 立体声开关（A 左耳、B 右耳）；最上方下载随之合并 | ✅ 实现，**前端未做完整浏览器点测** |
| 下载：单路 / 两路合并（混声或立体声）/ 选区（后端截取 WAV） | ✅ 接口已用真实音频验证，**前端按钮未做完整点测** |
| 音频入库接口 `POST /audios/{audioId}/ingest`（按地址拉取） | ✅ 实现并有测试 |
| 转写任务流水线：排队、进度、WebSocket 推送、落库、可编辑 | ✅ 框架真实 |
| **转写文字**（`ASR_PROVIDER=mock`） | 🟡 **mock**：时间点按音频真实说话时段生成，**文字是虚构的**（遥控器设计会议） |
| **说话人身份、场景、翻译**（`LLM_PROVIDER=mock`） | 🟡 **mock**：对任何音频都返回固定内容 |
| 真实语音转写引擎 | ❌ 未接入。`faster-whisper` 的代码路径存在，但在开发机上因依赖问题报错 `open() got an unexpected keyword argument 'metadata_errors'`（疑为依赖版本不匹配，未排查） |
| 真实大模型（身份、场景、翻译） | ❌ 未接入。`LlmClient` 支持任意 OpenAI 兼容接口，但没有真实调用验证过 |
| 说话人分离、情感、声纹 | ❌ 未做（设计见 `docs/本机模型对接实现方案.md`） |

## 五、接入真实模型（接手后要做的事）

### 扩展点

**1. 转写引擎** —— `voice-player-backend/app/services/asr.py`

```python
class AsrProvider(Protocol):
    def transcribe(self, path: Path, on_progress: Callable[[float], None]) -> tuple[str, list[Segment]]:
        """path 是单声道 WAV；返回 (BCP 47 语种, 片段)；on_progress 参数 0~1"""
```

- 双声道音频由 `pipeline.py` 先拆成 A、B 两个单声道文件，**逐声道调用**（声道即说话人），`Segment(start, end, text, confidence)`，时间单位秒、以整条音频开头为 0。
- 可选属性 `state`（`idle/loading/ready/failed`）、`error`、`start_preload()`、`wait_ready(timeout)`：流水线用它们判断引擎是否就绪；抛出 `AsrUnavailable` 会让任务显示「转写引擎不可用」，引擎恢复后下次访问**自动重试**。
- 在 `build_provider()` 里加一个分支，用 `ASR_PROVIDER=<名字>` 切换。参考实现：`FasterWhisperProvider`（真实）、`mock.py` 的 `MockAsrProvider`。

**2. 大模型** —— `voice-player-backend/app/services/llm.py`

- `analyze(dialogue, track_ids)` 返回说话人身份 + 场景（经 `normalize_analysis` 收敛为接口约定的结构），`translate(items, language)` 返回 `{id: 译文}`。
- 真实实现 `LlmClient` 调用 OpenAI 兼容的 `/chat/completions`：配置 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`，并**清空** `LLM_PROVIDER`（它为 `mock` 时优先用 mock）。本地推理服务（如 Ollama、vLLM 的 OpenAI 兼容接口）可直接用。
- 调用失败抛 `LlmError`，只会让身份、场景、翻译退回默认值，**不影响转写结果**。

**3. 流水线** —— `pipeline.py` 的 `Pipeline._run`：逐声道转写 → 合并写入转写表 → `_analyze` → `_translate` → 任务完成，各阶段通过 WebSocket 推送进度。

### 建议步骤

1. 先把 `.env` 的 `ASR_PROVIDER` 换成真实引擎，用 60 秒左右的音频验证：文字、时间戳、进度、失败后的提示。
2. 再接大模型，对照 `app/services/llm.py` 里的提示词，检查返回结构是否被 `normalize_analysis` 正确收敛。
3. 要做说话人分离、情感、声纹、串音过滤，以及把模型放到另一台机器上，**直接看** `docs/本机模型对接实现方案.md` 和 `docs/本地模型转写方案.md`（设计稿，含接口约定、内存调度、数据库变更）。注意其中的模型调用方式没有对照官方文档核实。

## 六、关键设计与约定

- **接口契约**：以 `docs/接口设计说明书.md` 为准。JSON 字段 camelCase；统一信封 `{code, message, data, timestamp}`；业务码见 `app/errors.py`，HTTP 状态码如实返回（`40002` 转写未完成返回 200）。
- **声道**：A 轨 = 左声道，B 轨 = 右声道；单声道文件只有 A 轨；超过 2 声道只处理前两个。时间一律是秒（浮点）。
- **audioId**：匹配 `^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$`，同时是文件名。
- **单进程**：任务调度（线程池，2 个并发）和 WebSocket 广播都在进程内；阻塞的音频处理放在 `run_in_threadpool`。
- **派生缓存**：`data/cache/{audioId}/` 下有 `track_A.wav`、`peaks_*.json`、`silences_*.json`，按源文件修改时间失效；删掉即可重算。
- **数据库**：SQLite，启动时 `create_all`，**它不会给已存在的表加列**。改了表结构要自己迁移，或删除 `data/voice_player.db`（会丢用户设置和转写编辑）。
- **测试**：`tests/conftest.py` 的 `make_client` 可注入假的转写引擎和大模型，**测试里不要调用真实模型**。
- **前端**：播放器是一个大的单文件组件，数据请求都集中在 `composables/useAudioData.js` 和 `api/`；顶部控制栏、轨道、波形、聊天面板、场景弹窗都在 `VoicePlayer.vue`。
- **代码风格**：注释用中文，与周围代码保持一致。

### 要改什么去哪里

| 想做的事 | 去哪里 |
|---|---|
| 接真实转写引擎 | `app/services/asr.py`（`build_provider`）、`pipeline.py` |
| 接真实大模型、改提示词 | `app/services/llm.py`、`app/main.py`（`build_llm`） |
| 调跳过空音的灵敏度 | `app/config.py` 的 `SILENCE_*`，算法在 `app/services/audio.py` 的 `detect_silences` |
| 改下载规则（混声、立体声、选区） | `app/routers/audios.py` 的 `download`、`app/services/audio.py` 的 `render_wav` |
| 音频入库方式 | `app/routers/audios.py` 的 `ingest_audio`、`app/services/ingest.py` |
| 加接口字段 | `docs/接口设计说明书.md` 先改，再改 `app/routers/*`、前端 `api/` |
| 播放器界面和交互 | `voice-player-frontend/src/components/VoicePlayer.vue` |

## 七、已知问题与注意事项

- **开发机没有 GPU**（Intel Mac，16GB 内存），本地大模型的速度和内存需要在目标机器上实测。
- **用 `curl` 访问本机服务**时，如果环境配置了 HTTP 代理，会返回 502：加 `--noproxy '*'`。
- **立体声依赖浏览器的 WebAudio**：音频需要同源或后端返回 CORS 头（开发时经 vite 代理是同源，没有问题）；开启立体声后音量滑块、静音是否仍然有效没有验证。
- **跳过空音的参数**（`SILENCE_SPEECH_OFFSET_DB` 等）只在 `audio_003` 上调过；更轻的附和声可能被当成静音跳过。
- **`audio_003` 是会议录音**，麦克风互相串音，转写时会把对方的声音当成本路内容（真实转写引擎接入后需要做串音过滤，见设计稿）。
- 前端的 `dist/` 目录被提交进了 git，`npm run build` 会改动它。
- 前端 README 里「已知问题」一节部分内容较旧，以代码为准。

## 八、文档索引

| 文档 | 用途 | 状态 |
|---|---|---|
| `docs/接口设计说明书.md` | 接口契约 | ✅ 权威，随代码更新 |
| `docs/实现方案.md` | 当前实现的整体说明：前后端架构、关键流程、与模型的对接方式、模型能力、能力×状态 | ✅ 与当前代码一致 |
| `voice-player-backend/README.md` | 后端运行、接口、配置、降级 | ✅ |
| `voice-player-frontend/README.md` | 前端组件、功能、集成 | ✅（已知问题一节较旧） |
| `docs/本机模型对接实现方案.md` | 模型在本机时的对接方案，含当前代码状态、已确认的决策、两段式输出、改动清单（标注已完成/待做） | 设计稿；mock、入库已落地，真实模型待接入 |
| `docs/本地模型转写方案.md` | 模型在另一台机器时的对接指南 | 设计稿，未实现 |

## 九、交接检查清单

- [ ] 能按第二章启动前后端，页面能打开
- [ ] `.venv/bin/python -m pytest` 全部通过
- [ ] 准备好演示音频（第三章），页面能播放并看到转写、说话人、场景
- [ ] 确认目标机器的硬件（GPU、内存）和要用的模型
- [ ] 用真实引擎替换 `ASR_PROVIDER=mock`，用 60 秒音频验证（第五章）
- [ ] 用真实大模型替换 `LLM_PROVIDER=mock`
- [ ] 在浏览器里点测立体声开关、三种下载、波形上的有声标记（这几项前端改动没有做完整点测）
