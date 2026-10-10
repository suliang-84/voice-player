# VoicePlayer 波纹语音播放器

基于 **Vite + Vue3 + WaveSurfer.js** 的波纹语音播放器组件。核心设计为单文件组件（SFC），可直接复制到任意 Vue3 项目使用。

---

## 目录结构

```
voice-player/
├── index.html                        # 入口 HTML
├── package.json
├── vite.config.js
├── README.md
├── 2026-10-10-voice-player.md        # 实现计划文档
├── waveform-preview.html             # 波形样式独立预览页
├── scripts/
│   └── gen-peaks.js                  # 服务器批处理脚本（Node.js）
├── src/
│   ├── main.js                       # Vue 应用入口
│   ├── App.vue                       # Demo 演示页
│   └── components/
│       └── VoicePlayer.vue           # ⭐ 核心组件（可独立复制使用）
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-10-10-voice-player-design.md  # 详细设计文档
```

---

## 代码框架描述

### VoicePlayer.vue 内部结构

```
VoicePlayer.vue
├── <template>
│   ├── AB 同步按钮（双轨模式）
│   ├── v-for 轨道列表（A路 / B路）
│   │   ├── 轨道头部（标签 + 加载状态 / 错误提示）
│   │   ├── 加载进度条
│   │   ├── 波形区域（.vp-waveform-wrap）
│   │   │   ├── 浮动工具条（选区操作：播放/循环/下载/批注/清除）
│   │   │   ├── 书签层（.vp-bookmarks-layer）
│   │   │   ├── 上半波形（WaveSurfer 渲染）
│   │   │   └── 下半镜像（rAF drawImage 实时镜像）
│   │   └── 控制栏（播放/时间/音量/速度/选区/跳过空音/导出/下载）
│   └── AB 音量差可视化（双轨模式）
│
├── <script setup>
│   ├── Props 定义（trackA / trackB / options）
│   ├── 常量（SPEEDS 速度档位）
│   ├── 状态工厂 createTrackState(id) → stateA / stateB
│   ├── tracks 计算属性（单/双轨列表）
│   ├── DOM refs（waveRefs / mirrorRefs / wrapRefs）
│   ├── buildColorMap()          # 频谱图颜色映射
│   ├── initWaveSurfer(track)    # WaveSurfer 实例化 + 事件绑定
│   ├── loadAudio(track)         # URL / File / Peaks 三模式加载
│   ├── 播放控制函数群            # togglePlay / setVolume / cycleSpeed ...
│   ├── 跳过空音                  # startSilenceDetection / toggleSkipSilence
│   ├── 选区与浮动工具条          # toggleRegionMode / playRegion / downloadRegion ...
│   ├── 键盘快捷键               # handleKeydown
│   ├── 书签                     # addBookmark / removeBookmark
│   ├── 导出报告                  # exportReport
│   └── 生命周期（onMounted / onBeforeUnmount / watch）
│
└── <style scoped>
    └── 17 个 --vp-* CSS 变量 + 所有组件样式
```

### 关键技术点

| 模块 | 实现方式 |
|------|---------|
| 波形渲染 | WaveSurfer.js v7，支持 `mirror-bar` / `mirror-spectrogram` / `bar` / `line` |
| 镜像波形 | 上半由 WaveSurfer 渲染，下半通过 `requestAnimationFrame` + `ctx.drawImage` 实时同步 |
| 超长音频 | 传入预生成 `peaks` 数据跳过浏览器解码，渲染瞬时完成 |
| 跳过空音 | 标准模式：Web Audio API `AnalyserNode` 实时 RMS 检测；Peaks 模式：`silences` 区间跳转 |
| 选区下载 | Web Audio API 裁剪 `AudioBuffer` → WAV 编码 → Blob 下载，无外部依赖 |
| 主题系统 | 17 个 `--vp-*` CSS 变量，外部通过 `style` 属性覆盖 |
| 持久化 | 书签、批注存储于 `localStorage`，以音频 URL 为 key |

---

## 功能描述

### 核心功能

| 功能 | 说明 |
|------|------|
| 波形渲染 | 加载音频后渲染完整文件波形，默认镜像对称柱状 |
| 双轨支持 | A/B 两路完全独立控制；B 路不传则自动降级为单轨 |
| 文件加载 | 支持 URL 字符串和本地 `File` 对象两种方式 |
| 超长音频 | 传入预生成 `peaks.json` + `silences.json`，跳过浏览器解码 |

### 播放控制

| 控件 | 功能 |
|------|------|
| ▶ / ⏸ | 播放 / 暂停 |
| 时间显示 | 当前时间 / 总时长，点击复制到剪贴板 |
| 🔊 + 滑块 | 音量控制（0–100%），点击图标静音/恢复 |
| 速度按钮 | 循环切换 0.5x / 0.75x / 1x / 1.25x / 1.5x / 2x |
| ⟳ 选区 | 拖拽波形创建选区，出现浮动工具条 |
| 静 | 跳过空音开关（默认开启） |
| 📄 | 导出书签 + 批注 JSON 报告 |
| ↓ | 下载完整音频文件 |

### 选区浮动工具条

拖拽波形后，选区上方弹出工具条：

| 按钮 | 功能 |
|------|------|
| ▶ | 仅播放选区片段 |
| ⟳ | 循环播放选区 |
| ↓ | 下载选区片段（WAV 格式） |
| ✎ | 为选区添加文字批注 |
| ✕ | 清除选区 |

### 增强功能

| 功能 | 说明 |
|------|------|
| 键盘快捷键 | 空格=播放/暂停，←/→=±5s，Shift+←/→=±1s，`[`/`]`=跳到选区起/终点 |
| 书签 | 双击波形添加书签，点击跳转，再次双击删除，自动持久化到 localStorage |
| 波形缩放 | 鼠标滚轮缩放波形（1x–200x），放大后支持横向滚动 |
| AB 同步 | 开启后 A 路跳转自动联动 B 路到相同时间点 |
| AB 音量差 | 双轨底部实时显示两路音量差异色条（绿=正常，红=差异大） |
| 加载进度条 | 大文件加载时显示解码进度百分比 |
| 错误处理 | 加载失败显示错误信息 + 重试按钮 |

---

## 波形类型配置

通过 `options.waveformType` 切换：

| 类型 | 说明 |
|------|------|
| `mirror-bar`（默认） | 镜像对称柱状波形 |
| `mirror-spectrogram` | 镜像对称频谱图（实时 FFT） |
| `bar` | 标准单向柱状波形 |
| `line` | 连续线形波形 |

---

## 主题定制（CSS 变量）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `--vp-bg` | `#ffffff` | 播放器背景色 |
| `--vp-border-color` | `#e5e7eb` | 轨道边框颜色 |
| `--vp-wave-color` | `#93c5fd` | 波形未播放颜色 |
| `--vp-progress-color` | `#2563eb` | 波形已播放颜色 |
| `--vp-cursor-color` | `#1d4ed8` | 播放游标颜色 |
| `--vp-region-color` | `rgba(37,99,235,0.2)` | 选区填充色 |
| `--vp-btn-color` | `#2563eb` | 按钮颜色 |
| `--vp-btn-hover-bg` | `#eff6ff` | 按钮 hover 背景 |
| `--vp-label-color` | `#374151` | 标签文字颜色 |
| `--vp-time-color` | `#6b7280` | 时间文字颜色 |
| `--vp-slider-color` | `#2563eb` | 滑块颜色 |
| `--vp-radius` | `8px` | 圆角大小 |
| `--vp-bookmark-color` | `#f59e0b` | 书签颜色 |
| `--vp-error-color` | `#ef4444` | 错误提示颜色 |
| `--vp-progress-bar-color` | `#2563eb` | 加载进度条颜色 |
| `--vp-diff-ok-color` | `#22c55e` | AB 音量差正常颜色 |
| `--vp-diff-warn-color` | `#ef4444` | AB 音量差异常颜色 |

---

## 本地启动

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev
# → http://localhost:5173
```

Demo 页面展示了 4 种使用场景：单轨、文件上传、双轨暗色主题、频谱图模式。

---

## 打包

```bash
npm run build
```

产物输出到 `dist/`，可直接部署到静态服务器。

---

## 在其他项目中引入

### 第一步：安装依赖

```bash
npm install wavesurfer.js
```

### 第二步：复制组件文件

将 `src/components/VoicePlayer.vue` 复制到目标项目的组件目录，无需其他文件。

### 第三步：使用组件

```vue
<template>
  <!-- 单轨 URL -->
  <VoicePlayer :track-a="{ src: 'https://example.com/audio.mp3', label: '录音' }" />

  <!-- 单轨 File 对象 -->
  <VoicePlayer :track-a="{ file: fileObject, label: '本地录音' }" />

  <!-- 双轨 -->
  <VoicePlayer
    :track-a="{ src: urlA, label: 'A路' }"
    :track-b="{ src: urlB, label: 'B路' }"
  />

  <!-- 频谱图模式 + 自定义主题 -->
  <VoicePlayer
    :track-a="{ src: url }"
    :options="{ waveformType: 'mirror-spectrogram', spectrogramColorMap: 'heatmap' }"
    style="--vp-bg: #0f172a; --vp-wave-color: #4f46e5;"
  />
</template>

<script setup>
import VoicePlayer from '@/components/VoicePlayer.vue'
</script>
```

### Props 说明

```ts
// 轨道配置
interface TrackConfig {
  src?: string                              // 音频 URL
  file?: File                              // 本地 File 对象
  label?: string                           // 轨道标签
  peaks?: number[][]                       // 预生成峰值（超长音频用）
  duration?: number                        // 总时长秒数（peaks 模式必填）
  silences?: Array<{ start: number, end: number }>  // 静音区间（peaks 模式跳过空音用）
}

// 外观配置
interface PlayerOptions {
  waveformType?: 'mirror-bar' | 'mirror-spectrogram' | 'bar' | 'line'
  waveColor?: string
  progressColor?: string
  cursorColor?: string
  barWidth?: number
  barGap?: number
  height?: number
  spectrogramColorMap?: 'theme' | 'heatmap' | string  // 频谱图配色
  fftSize?: number                                      // 频谱分辨率，默认 2048
}

// 组件 Props
props: {
  trackA: TrackConfig      // 必填
  trackB?: TrackConfig     // 可选，不传则单轨模式
  options?: PlayerOptions  // 可选
}
```

---

## 超长音频处理（Peaks 模式）

对于超过 30 分钟的音频，建议在服务器预生成 peaks 数据：

### 服务器批处理（需安装 ffmpeg 和 Node.js）

```bash
# 批量处理目录下所有 mp3
for f in /data/audio/*.mp3; do
  base="${f%.mp3}"
  ffmpeg -i "$f" -filter:a aformat=channel_layouts=mono \
    -f s16le -ar 8000 pipe:1 2>/dev/null | \
    node scripts/gen-peaks.js "$base"
done
```

执行后每个音频文件旁生成：
- `audio.peaks.json` — 波形峰值（约 8KB/小时）
- `audio.silences.json` — 静音区间

### 前端加载

```js
const base = audioUrl.replace(/\.(mp3|wav|ogg|m4a)$/, '')
const [peaks, silences] = await Promise.all([
  fetch(`${base}.peaks.json`).then(r => r.json()),
  fetch(`${base}.silences.json`).then(r => r.json()),
])
```

```vue
<VoicePlayer
  :track-a="{ src: audioUrl, peaks, silences, duration: 3720 }"
/>
```

---

## 注意事项

| 事项 | 说明 |
|------|------|
| 跨域音频 | 服务端需配置 `Access-Control-Allow-Origin` 响应头 |
| SSR | WaveSurfer.js 依赖 Web API，不支持 SSR，需确保在客户端挂载 |
| 浏览器兼容 | Chrome 80+ / Firefox 75+ / Safari 14+ |
| 选区下载 | 跨域音频无法使用选区下载（Web Audio API 限制），需服务端配置 CORS |
