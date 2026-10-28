# VoicePlayer 语音播放器

基于 **Vite 5 + Vue 3 + WaveSurfer.js 7** 的双轨语音播放器组件。核心设计为单文件组件（SFC），可直接复制到任意 Vue 3 项目使用。

---

## 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue | 3.4 | 前端框架（Composition API） |
| Vite | 5.0 | 构建工具 |
| WaveSurfer.js | 7.8 | 波形渲染 + 音频播放核心 |
| Element Plus | 2.14 | 设置对话框 UI 组件 |
| SCSS | 1.105 | 样式预处理 |
| vite-plugin-svg-icons | 2.0 | SVG 图标自动注册 |

---

## 目录结构

```
voice-player/
├── index.html
├── package.json
├── vite.config.js
├── README.md
├── scripts/
│   └── gen-peaks.js              # 超长音频 peaks 预生成脚本（Node.js）
├── public/
│   ├── demo.mp3                  # 单轨演示音频（39 KB）
│   ├── demo-a.mp3                # 双轨 A 路演示音频（8.6 MB，约 9 分钟）
│   └── demo-b.mp3                # 双轨 B 路演示音频（13 MB，约 14 分钟）
└── src/
    ├── main.js                   # Vue 应用入口（注册全局组件和插件）
    ├── App.vue                   # 演示页（双轨模式）
    ├── components/
    │   ├── VoicePlayer.vue       # ⭐ 核心播放器组件（约 1650 行）
    │   └── SvgIcon.vue           # SVG 图标包装组件
    └── icons/                    # SVG 图标库
        ├── play.svg
        ├── pause.svg
        ├── previous.svg
        ├── next.svg
        ├── rewind.svg
        ├── forward.svg
        ├── volume_up.svg
        ├── volume_off.svg
        ├── download.svg
        └── setting.svg
```

---

## 功能列表

### 顶部控制栏

| 控件 | 功能 |
|------|------|
| 上一条 | 跳到音频开头（`ws.setTime(0)`） |
| 回退 | 后退 N 秒（默认 5 秒，可在设置中调整） |
| 播放/暂停 | AB 双轨同步播放/暂停 |
| 快进 | 快进 N 秒 |
| 下一条 | 跳到音频结尾 |
| 静音/取消静音 | AB 双轨统一静音 |
| 音量滑块 | AB 双轨统一音量控制 |
| 设置按钮 | 打开设置对话框 |
| 下载按钮 | 下载 AB 双轨音频文件 |

### 设置对话框

| 配置项 | 选项 |
|--------|------|
| 播放倍数 | 0.5x / 0.75x / 1x / 1.25x / 1.5x / 1.75x / 2x |
| 快进/后退秒数 | 1–60 秒（数字输入） |
| 播放模式 | 单条播放 / 顺序播放 |
| 主题 | 亮色 / 深色 |

> 点击"确认"后配置生效，点击"取消"或遮罩层不保存。

### 轨道级控制（每路独立）

| 控件 | 位置 | 功能 |
|------|------|------|
| 轨道标签 | 左上角 | 显示 A/B 路名称 |
| 时间显示 | 右侧 | `当前时间 / 总时长` |
| 静音按钮 | 右侧 | 单独静音当前轨道 |
| 下载按钮 | 右侧 | 单独下载当前轨道音频 |

### 波形交互

| 操作 | 功能 |
|------|------|
| 点击波形 | 跳转到对应位置（AB 双轨同步） |
| 拖拽波形 | 创建选区，弹出浮动工具条 |
| 滚轮上滚 | 放大波形（最大 200x） |
| 滚轮下滚 | 缩小波形（最小 1x） |
| 双击波形 | 添加书签（zoom > 1 时双击恢复原比例） |

### 选区浮动工具条

拖拽波形后，选区上方弹出工具条（AB 双轨同步选区范围）：

| 按钮 | 功能 |
|------|------|
| ↓ | 下载选区片段（WAV 格式） |
| ✎ | 为选区添加文字批注 |
| ✕ | 清除选区 |

### 键盘快捷键

聚焦轨道后生效：

| 按键 | 功能 |
|------|------|
| `Space` | 播放 / 暂停 |
| `←` | 后退 5 秒 |
| `→` | 快进 5 秒 |
| `Shift + ←` | 后退 1 秒 |
| `Shift + →` | 快进 1 秒 |
| `[` | 跳到选区起点 |
| `]` | 跳到选区终点 |

### 书签

- 双击波形添加书签（弹出输入框，可自定义名称）
- 点击书签线跳转到对应时间
- 双击书签线删除书签
- 书签数据持久化到 `localStorage`（以音频 URL 为 key）

### 数据持久化

| 数据 | localStorage Key |
|------|-----------------|
| 书签 | `vp-bookmarks:{audioUrl}` |
| 批注 | `vp-annotations:{audioUrl}` |

---

## 核心架构

### VoicePlayer.vue 内部结构

```
VoicePlayer.vue
├── <template>
│   ├── 顶部控制栏（.vp-control-bar）
│   │   ├── 左侧播放控制（.vp-playback-controls）
│   │   └── 右侧辅助控制（.vp-aux-controls）
│   ├── 设置对话框（<teleport to="body">）
│   ├── 轨道列表（.vp-tracks-dual）
│   │   └── v-for 轨道（.vp-track）
│   │       ├── 轨道头部（标签 + 时间 + 静音 + 下载）
│   │       ├── 加载进度条
│   │       └── 波形区域（.vp-waveform-wrap）
│   │           ├── 浮动工具条（选区操作）
│   │           ├── 书签层（绝对定位）
│   │           └── WaveSurfer 渲染容器（.vp-waveform-top）
│   └── 统一滚动条（波形放大时显示）
│
├── <script setup>
│   ├── Props 定义
│   ├── 轨道状态工厂 createTrackState() → stateA / stateB
│   ├── 统一滚动条逻辑（rAF 同步）
│   ├── initWaveSurfer()       WaveSurfer 实例化 + 事件绑定
│   ├── loadAudio()            音频加载 + 事件监听
│   ├── 播放控制函数群
│   ├── 双轨统一控制函数群
│   ├── 跳过空音检测（Web Audio API AnalyserNode）
│   ├── 选区 + 浮动工具条管理
│   ├── 书签 + 批注管理
│   ├── WAV 编码（audioBufferToWav）
│   ├── 键盘快捷键处理
│   └── 生命周期钩子
│
└── <style lang="scss" scoped>
    ├── 15 个 --vp-* CSS 变量（亮色默认值）
    └── 所有组件样式
```

### WaveSurfer 配置要点

```js
WaveSurfer.create({
  container: waveContainer,
  media: mediaEl,          // 传入原生 <audio>，跳过 WaveSurfer 内部完整解码，支持流式播放
  height: 'auto',          // 自适应容器高度
  barHeight: 0.8,          // 波形振幅系数（基于 normalize）
  normalize: true,         // 峰值归一化，使波形始终撑满容器高度
  interact: false,         // 禁用 WaveSurfer 内置交互，由外层自定义实现
  autoCenter: true,        // 播放时游标自动居中
  autoScroll: true,        // 播放时自动滚动跟随
  hideScrollbar: true,     // 隐藏每路内置滚动条（改用统一滚动条）
  plugins: [RegionsPlugin],
})
```

### 统一滚动条实现原理

WaveSurfer v7 使用 Shadow DOM，滚动容器结构为：

```
waveRefs[id]（我们的容器 div）
  └── div（shadow host，由 WaveSurfer 创建）
        └── shadow root
              └── div.scroll（实际滚动容器）
                    └── div.wrapper（波形画布）
```

通过 `firstElementChild.shadowRoot.querySelector('.scroll')` 访问滚动元素，使用 `ws.getScroll()` / `ws.setScroll()` 读写位置，`requestAnimationFrame` 循环同步 AB 双轨位置。

### 原生 Audio 流式播放

为解决大文件播放卡顿，使用原生 `<audio>` 元素替代 WaveSurfer 内部加载：

```js
const mediaEl = document.createElement('audio')
mediaEl.src = url
mediaEl.preload = 'auto'
mediaEl.crossOrigin = 'anonymous'
// 传入 WaveSurfer，跳过其内部 fetch + 解码流程
WaveSurfer.create({ media: mediaEl, ... })
```

浏览器原生支持边缓冲边播放，彻底解决需要完整解码才能播放的性能瓶颈。

---

## 主题定制（CSS 变量）

在组件外层覆盖变量即可切换主题：

| 变量 | 亮色默认值 | 深色值 | 说明 |
|------|-----------|--------|------|
| `--vp-bg` | `#ffffff` | `#0f172a` | 播放器背景 |
| `--vp-border-color` | `#e0e7ff` | `#312e81` | 轨道边框 |
| `--vp-wave-color` | `#818cf8` | — | 波形未播放色 |
| `--vp-progress-color` | `#6366f1` | `#a5b4fc` | 波形已播放色 |
| `--vp-cursor-color` | `#4f46e5` | `#c7d2fe` | 播放游标色 |
| `--vp-region-color` | `rgba(99,102,241,0.15)` | `rgba(165,180,252,0.2)` | 选区填充色 |
| `--vp-btn-color` | `#6366f1` | `#a5b4fc` | 按钮颜色 |
| `--vp-label-color` | `#374151` | `#e0e7ff` | 标签文字色 |
| `--vp-time-color` | `#6b7280` | `#94a3b8` | 时间文字色 |
| `--vp-slider-color` | `#6366f1` | `#a5b4fc` | 滑块颜色 |
| `--vp-radius` | `8px` | — | 圆角大小 |
| `--vp-bookmark-color` | `#f59e0b` | `#fbbf24` | 书签颜色 |
| `--vp-error-color` | `#ef4444` | — | 错误提示色 |
| `--vp-progress-bar-color` | `#6366f1` | `#a5b4fc` | 加载进度条色 |

主题也可通过播放器内置设置对话框在运行时切换（亮色/深色）。

---

## 已知问题

| 问题 | 原因 | 状态 |
|------|------|------|
| 波形放大后底部统一滚动条未显示 | WaveSurfer Shadow DOM 访问方式错误 | 修复中 |
| 播放时进度条跳跃感 | WaveSurfer `scrollIntoView` 在高缩放时直接赋值 `scrollLeft` | 已通过统一滚动条规避 |
| 波形缩放性能卡顿 | 高频 wheel 事件触发多次重绘 | 已加 150ms 节流优化 |
| 跨域音频无法下载选区 | Web Audio API CORS 限制 | 需服务端配置响应头 |
| SSR 不支持 | WaveSurfer 依赖浏览器 Web API | 需在客户端挂载 |
| AudioContext 挂起 | 浏览器要求用户手势才能启动 | 已在首次播放时懒初始化 |

---

## 本地开发

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev
# → http://localhost:5173

# 生产构建
npm run build
```

---

## 集成到其他 Vue 3 项目

### 1. 安装核心依赖

```bash
npm install wavesurfer.js element-plus vite-plugin-svg-icons
```

### 2. 配置 vite.config.js

```js
import { createSvgIconsPlugin } from 'vite-plugin-svg-icons'
import path from 'path'

export default defineConfig({
  plugins: [
    vue(),
    createSvgIconsPlugin({
      iconDirs: [path.resolve(process.cwd(), 'src/icons')],
      symbolId: 'icon-[name]',
    }),
  ],
})
```

### 3. 复制文件

```
src/components/VoicePlayer.vue  →  目标项目组件目录
src/components/SvgIcon.vue      →  目标项目组件目录
src/icons/                      →  目标项目 src/icons/
```

### 4. 注册全局组件（main.js）

```js
import 'virtual:svg-icons-register'
import SvgIcon from './components/SvgIcon.vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

app.component('SvgIcon', SvgIcon)
app.use(ElementPlus)
```

### 5. 使用示例

```vue
<template>
  <!-- 双轨模式 -->
  <VoicePlayer
    :track-a="{ src: '/audio/track-a.mp3', label: '主动方' }"
    :track-b="{ src: '/audio/track-b.mp3', label: '接收方' }"
  />

  <!-- 单轨模式 -->
  <VoicePlayer
    :track-a="{ src: '/audio/recording.mp3', label: '录音' }"
  />

  <!-- 本地文件上传 -->
  <VoicePlayer
    :track-a="{ file: selectedFile, label: '本地文件' }"
  />
</template>

<script setup>
import VoicePlayer from '@/components/VoicePlayer.vue'
</script>
```

### Props 类型定义

```ts
interface TrackConfig {
  src?: string      // 音频文件 URL（与 file 二选一）
  file?: File       // 本地 File 对象（与 src 二选一）
  label?: string    // 轨道标签名称
}

interface PlayerOptions {
  waveColor?: string
  progressColor?: string
  cursorColor?: string
  height?: number | 'auto'
}

// 组件 Props
props: {
  trackA: TrackConfig      // 必填
  trackB?: TrackConfig     // 可选，不传则单轨模式
  options?: PlayerOptions  // 可选，覆盖默认外观配置
}
```

---

## 超长音频优化建议

对于 30 分钟以上的音频文件，建议在服务端预生成 peaks 数据（WaveSurfer 支持传入 peaks 跳过客户端解码）。项目中的 `scripts/gen-peaks.js` 提供了基于 Node.js 的批量处理脚本。

波形缩放性能优化已通过 150ms 节流实现，后续可进一步考虑 WebWorker 解码 + 离线 peaks 缓存方案。

---

## 浏览器兼容性

| 浏览器 | 最低版本 | 备注 |
|--------|----------|------|
| Chrome | 80+ | 推荐 |
| Firefox | 75+ | |
| Safari | 14+ | |
| Edge | 80+ | |

---

## 对接后端

播放器是公共组件：播放列表由业务系统获取，通过 props 传入 `audioId`、`trackA`、`trackB`，播放器不关心列表来源。接口约定见 `docs/接口设计说明书.md`。

| 项 | 说明 |
|----|------|
| 音频源 | `trackA` / `trackB` 未提供 `src` 或 `file` 时，默认使用 `GET {VITE_API_BASE}/audios/{audioId}/stream?track=A\|B`（单声道 WAV，需支持 Range）；传入 `src` / `file` 则以传入为准 |
| 环境变量 | `VITE_API_BASE`（默认 `/api/v1`）、`VITE_WS_URL`（为空则不连 WebSocket，转写中改为轮询）、`VITE_PROXY_TARGET`（开发代理目标，默认 `http://localhost:10090`） |
| 超时 | peaks / silences / transcripts / speakers / scenes 为 120s，其余 30s |
| 鉴权 | `src/api/auth.js` 的 `configureAuth` 注入 token；`<audio>` 无法带 `Authorization` 头，后端启用鉴权后需另行约定（query token 或 cookie） |

### 本地联调

先启动 `voice-player-backend`（端口 10090，见其 README），或在后端未就绪时用 mock 服务（按接口文档返回数据，监听 10090）：

```bash
node scripts/mock-server.js   # 终端 1
npm run dev                   # 终端 2
```

后端当前限制：设置 / 翻译 / 编辑为演示数据，不落库；`/ws` 为占位，不推送事件；`confidence` 等字段可能为 `null`。
