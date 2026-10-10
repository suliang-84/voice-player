# 波纹语音播放器 VoicePlayer 实现方案

> 技术栈：Vite + Vue3 + WaveSurfer.js
> 组件形态：单文件组件（SFC），可直接复制到其他项目使用

---

## 一、需求概述

| 需求项 | 说明 |
|--------|------|
| 波形渲染 | 加载音频后渲染完整文件波形（镜像对称柱状） |
| 双轨支持 | 支持 A/B 两路独立语音，各自有独立控制 |
| 单轨降级 | B 路可选，不传则退化为单轨模式 |
| 文件加载 | 支持 URL 字符串和本地 File 对象两种方式 |
| 超长音频 | 支持传入预生成峰值数据（peaks.json），跳过浏览器解码，适用于 >30 分钟音频 |
| 控制功能 | 播放/暂停、点击跳转、时间显示、音量、速度、区间循环、下载、跳过空音开关 |
| 选区操作 | 拖拽波形选中片段，选区上方浮动工具条提供：播放选区、循环选区、下载选区、清除选区 |
| 主题定制 | 通过 CSS 变量暴露所有视觉配置 |

---

## 二、依赖安装

```bash
npm install wavesurfer.js
```

仅需一个外部依赖，版本要求 `wavesurfer.js >= 7.x`（支持插件化架构）。

---

## 三、组件目录结构

```
src/
└── components/
    └── VoicePlayer.vue   ← 全部逻辑、样式封装于此，可独立复制使用
```

---

## 四、Props 接口设计

```ts
interface TrackConfig {
  src?: string       // 音频 URL（与 file 二选一）
  file?: File        // 本地 File 对象（与 src 二选一）
  label?: string     // 轨道标签，如 "A路" / "B路"
  peaks?: number[][] // 预生成峰值数据，用于超长音频（>30分钟）跳过浏览器解码
  duration?: number  // 音频总时长（秒），peaks 模式下必填
  silences?: Array<{ start: number, end: number }>  // 预扫描静音区间，peaks 模式下跳过空音必填
}

type WaveformType = 'mirror-bar' | 'mirror-spectrogram' | 'bar' | 'line'

interface PlayerOptions {
  // ── 波形类型 ────────────────────────────────────────────────────
  waveformType?: WaveformType  // 默认 'mirror-bar'（镜像对称柱状）

  // ── 通用波形外观 ─────────────────────────────────────────────────
  waveColor?: string       // 波形未播放部分颜色，默认读 --vp-wave-color
  progressColor?: string   // 波形已播放部分颜色，默认读 --vp-progress-color
  cursorColor?: string     // 游标颜色，默认读 --vp-cursor-color
  barWidth?: number        // 波形柱宽度（像素），默认 2，仅 bar/mirror-bar 有效
  barGap?: number          // 波形柱间距（像素），默认 1，仅 bar/mirror-bar 有效
  height?: number          // 波形区域高度（像素），默认 80

  // ── 频谱图专属配置（waveformType = 'mirror-spectrogram' 时生效）──
  spectrogramColorMap?: 'theme' | 'heatmap' | string  // 默认 'theme'
  // 'theme'   → 跟随主题色，低能量透明 → 高能量不透明
  // 'heatmap' → 热力图配色：蓝 → 绿 → 黄 → 红
  // string    → 自定义颜色（如 '#7c3aed'），按该色调深浅映射能量
  fftSize?: number         // FFT 窗口大小，默认 2048，越大频率分辨率越高
}

// Props 定义
props: {
  trackA: TrackConfig      // 必填，A 路音频
  trackB?: TrackConfig     // 可选，B 路音频；不传则单轨模式
  options?: PlayerOptions  // 可选，外观配置
}
```

### 使用示例

```vue
<!-- 单轨：传入 URL -->
<VoicePlayer :track-a="{ src: 'https://example.com/audio.mp3', label: '主音频' }" />

<!-- 单轨：传入 File 对象 -->
<VoicePlayer :track-a="{ file: fileObject, label: '录音' }" />

<!-- 双轨：AB 路独立控制 -->
<VoicePlayer
  :track-a="{ src: urlA, label: 'A路' }"
  :track-b="{ src: urlB, label: 'B路' }"
/>

<!-- 超长音频：peaks 模式（>30分钟，跳过浏览器解码） -->
<VoicePlayer
  :track-a="{
    src: 'https://example.com/long-audio.mp3',
    peaks: peaksData,
    duration: 3720,
    label: '长音频'
  }"
/>

<!-- 默认：镜像对称柱状波形，无需配置 -->
<VoicePlayer :track-a="{ src: url }" />

<!-- 镜像对称频谱图（跟随主题色） -->
<VoicePlayer
  :track-a="{ src: url }"
  :options="{ waveformType: 'mirror-spectrogram' }"
/>

<!-- 镜像对称频谱图（热力图配色） -->
<VoicePlayer
  :track-a="{ src: url }"
  :options="{ waveformType: 'mirror-spectrogram', spectrogramColorMap: 'heatmap' }"
/>

<!-- 镜像对称频谱图（自定义颜色） -->
<VoicePlayer
  :track-a="{ src: url }"
  :options="{ waveformType: 'mirror-spectrogram', spectrogramColorMap: '#7c3aed' }"
/>

<!-- 自定义主题（CSS 变量）-->
<VoicePlayer
  :track-a="{ src: url }"
  style="
    --vp-bg: #1a1a2e;
    --vp-wave-color: #7c3aed;
    --vp-progress-color: #a78bfa;
  "
/>
```

---

## 五、CSS 变量主题系统

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `--vp-bg` | `#ffffff` | 播放器整体背景色 |
| `--vp-border-color` | `#e5e7eb` | 轨道边框颜色 |
| `--vp-wave-color` | `#93c5fd` | 波形未播放部分颜色 |
| `--vp-progress-color` | `#2563eb` | 波形已播放部分颜色 |
| `--vp-cursor-color` | `#1d4ed8` | 播放游标颜色 |
| `--vp-region-color` | `rgba(37,99,235,0.2)` | 循环区间填充色 |
| `--vp-btn-color` | `#2563eb` | 按钮图标颜色 |
| `--vp-btn-hover-bg` | `#eff6ff` | 按钮 hover 背景色 |
| `--vp-label-color` | `#374151` | 轨道标签文字颜色 |
| `--vp-time-color` | `#6b7280` | 时间文字颜色 |
| `--vp-slider-color` | `#2563eb` | 滑块（音量/进度）颜色 |
| `--vp-radius` | `8px` | 播放器圆角 |

---

## 六、布局结构

```
┌──────────────────────────────────────────────┐
│  VoicePlayer 容器                             │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │  A路 [标签]                    [加载中] │  │
│  │                                        │  │
│  │         ┌─────────────────┐            │  │
│  │         │ ▶播放 ⟳循环 ↓下载 ✕│  ← 浮动工具条
│  │         └────────┬────────┘            │  │
│  │  ▔▔▔▔▔▁▁█████████████▅▅▃▃▁▁▔▔  │  │
│  │         └── 选区高亮 ──┘            │  │
│  │  ▶  00:12 / 01:30  🔊───  1x  ⟳  静  ↓  │  │
│  └────────────────────────────────────────┘  │
│                                              │
└──────────────────────────────────────────────┘
```

控制栏各元素说明：

| 元素 | 功能 |
|------|------|
| ▶ / ⏸ | 播放 / 暂停切换 |
| `00:12 / 01:30` | 当前时间 / 总时长 |
| 🔊 + 滑块 | 音量控制（0-100%），点击图标静音 |
| `1x` 按钮 | 循环切换 0.5 / 0.75 / 1 / 1.25 / 1.5 / 2x |
| ⟳ 区间循环 | 激活后在波形上拖选区间，选区上方弹出浮动工具条 |
| ↓ 下载 | 触发音频文件下载 |
| 跳过空音开关 | 默认开启；播放时自动检测静音段并跳过，关闭则连续播放 |

---

## 七、核心实现逻辑

### 7.1 波形渲染策略

根据 `waveformType` 选择不同渲染实现：

| waveformType | 实现方式 | 说明 |
|---|---|---|
| `mirror-bar`（默认） | WaveSurfer `barWidth` + Canvas 镜像绘制 | 上下对称柱状，无需插件 |
| `mirror-spectrogram` | WaveSurfer SpectrogramPlugin + Canvas 镜像翻转 | 上下对称频谱，实时 FFT |
| `bar` | WaveSurfer 原生柱状 | 标准单向柱状波形 |
| `line` | WaveSurfer `barWidth: 0` | 连续线形波形 |

**镜像对称频谱图实现原理：**

SpectrogramPlugin 渲染上半部分频谱，通过 CSS `transform: scaleY(-1)` 将其镜像复制到下半部分：

```
上半：SpectrogramPlugin 正常渲染（低频在下，高频在上）
下半：Canvas 复制上半内容，scaleY(-1) 翻转（视觉上低频在上，高频向下延伸）
```

**频谱图颜色映射（spectrogramColorMap）：**

```js
function buildColorMap(colorMap) {
  // 'theme'：取主题色，按透明度映射能量
  if (colorMap === 'theme' || !colorMap) {
    const base = getComputedStyle(el).getPropertyValue('--vp-progress-color').trim()
    return energy => `${base}${Math.round(energy * 255).toString(16).padStart(2, '0')}`
  }

  // 'heatmap'：蓝 → 绿 → 黄 → 红
  if (colorMap === 'heatmap') {
    return energy => {
      const h = (1 - energy) * 240  // 240=蓝, 0=红
      return `hsl(${h}, 100%, 50%)`
    }
  }

  // 自定义颜色字符串：按该色调深浅映射
  return energy => {
    const alpha = Math.round(energy * 255).toString(16).padStart(2, '0')
    return `${colorMap}${alpha}`
  }
}
```

### 7.3 WaveSurfer 实例初始化

```js
import WaveSurfer from 'wavesurfer.js'
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.js'
import SpectrogramPlugin from 'wavesurfer.js/dist/plugins/spectrogram.js'

function createWaveSurfer(container, options, rootEl) {
  const waveformType = options.waveformType ?? 'mirror-bar'
  const isSpectrogram = waveformType === 'mirror-spectrogram'

  const regions = RegionsPlugin.create()
  const plugins = [regions]

  // 频谱图插件（仅 mirror-spectrogram 时启用）
  let spectrogramPlugin = null
  if (isSpectrogram) {
    spectrogramPlugin = SpectrogramPlugin.create({
      container: container.querySelector('.vp-spectrogram-top'),
      colorMap: buildColorMap(options.spectrogramColorMap, rootEl),
      fftSamples: options.fftSize ?? 2048,
    })
    plugins.push(spectrogramPlugin)
  }

  const ws = WaveSurfer.create({
    container: container.querySelector('.vp-waveform-canvas'),
    waveColor: options.waveColor
      || getComputedStyle(rootEl).getPropertyValue('--vp-wave-color').trim()
      || '#93c5fd',
    progressColor: options.progressColor
      || getComputedStyle(rootEl).getPropertyValue('--vp-progress-color').trim()
      || '#2563eb',
    cursorColor: options.cursorColor
      || getComputedStyle(rootEl).getPropertyValue('--vp-cursor-color').trim()
      || '#1d4ed8',
    // mirror-bar / bar 模式启用柱状，line / spectrogram 不设
    barWidth: ['mirror-bar', 'bar'].includes(waveformType) ? (options.barWidth ?? 2) : undefined,
    barGap:   ['mirror-bar', 'bar'].includes(waveformType) ? (options.barGap ?? 1)   : undefined,
    height: options.height ?? 80,
    // mirror 系列：WaveSurfer 只渲染上半，下半通过 CSS 镜像
    splitChannels: false,
    plugins,
  })

  return { ws, regions, spectrogramPlugin }
}
```

**镜像下半部分 CSS 实现（mirror-bar / mirror-spectrogram 通用）：**

```css
/* 波形容器：上下两层叠放 */
.vp-waveform-wrap {
  display: flex;
  flex-direction: column;
  position: relative;
}

/* 下半镜像层：将上半内容垂直翻转复制 */
.vp-waveform-mirror {
  transform: scaleY(-1);
  opacity: 0.6;       /* 下半略淡，强调上半为主视图 */
  pointer-events: none;
}
```

```vue
<div class="vp-waveform-wrap">
  <!-- 上半（WaveSurfer 正常渲染） -->
  <div class="vp-waveform-top" :ref="el => setWaveRef(el, track.id)"></div>
  <!-- 下半（CSS 镜像） -->
  <div class="vp-waveform-mirror" :ref="el => setMirrorRef(el, track.id)"></div>
</div>
```

### 7.2 三种加载模式

```js
async function loadTrack(ws, config, state) {
  const url = config.file
    ? (state.objectUrl = URL.createObjectURL(config.file))
    : config.src

  if (config.peaks) {
    // ── 峰值模式（超长音频）：直接用预生成数据，跳过解码 ──────────
    // 渲染几乎瞬时完成，适合 >30 分钟音频
    ws.load(url, config.peaks, config.duration)
  } else {
    // ── 标准模式：WaveSurfer 内部用 Web Worker 解码全文件 ──────────
    // <30 分钟音频无感知，>30 分钟加载时间较长
    await ws.load(url)
  }
}

// 注意：File 模式创建的 ObjectURL 在组件卸载时需 URL.revokeObjectURL() 释放
```

### 7.2.1 peaks 预生成方法（服务器批处理）

音频文件存放在服务器上，直接在服务器执行批处理脚本，同步生成 peaks 和 silences 文件。

**前提：** 服务器已安装 `ffmpeg` 和 `Node.js`。

**第一步：安装 ffmpeg 和 Node.js（服务器执行一次）**

```bash
# Ubuntu / Debian
apt-get install -y ffmpeg nodejs

# CentOS / RHEL
yum install -y ffmpeg nodejs
```

**第二步：编写 gen-peaks.js 脚本**

```js
// gen-peaks.js — 将 PCM 数据聚合为峰值数组，同步输出 silences 区间
const fs = require('fs')
const path = require('path')

const SAMPLES_PER_POINT = 80    // 每个峰值点聚合的采样数，越大 peaks 文件越小
const SAMPLE_RATE = 8000        // 与 ffmpeg -ar 保持一致
const SILENCE_THRESHOLD = 0.001 // 低于此振幅视为静音
const MIN_SILENCE_DURATION = 0.2 // 静音段短于此秒数不记录（秒）

const outputBase = process.argv[2]  // 输出文件路径前缀，如 /data/audio/call_001
const chunks = []

process.stdin.on('data', chunk => chunks.push(chunk))
process.stdin.on('end', () => {
  const buf = Buffer.concat(chunks)
  const peaks = [[], []]
  const silentRanges = []
  let silenceStart = null
  let sampleIndex = 0

  for (let i = 0; i < buf.length - SAMPLES_PER_POINT * 2; i += SAMPLES_PER_POINT * 2) {
    let max = 0, min = 0, rms = 0

    for (let j = 0; j < SAMPLES_PER_POINT * 2; j += 2) {
      const val = buf.readInt16LE(i + j) / 32768
      if (val > max) max = val
      if (val < min) min = val
      rms += val * val
    }

    rms = Math.sqrt(rms / SAMPLES_PER_POINT)
    peaks[0].push(Math.round(max * 1000) / 1000)
    peaks[1].push(Math.round(min * 1000) / 1000)

    // 静音检测
    const time = sampleIndex / SAMPLE_RATE
    if (rms < SILENCE_THRESHOLD) {
      if (silenceStart === null) silenceStart = time
    } else {
      if (silenceStart !== null) {
        if (time - silenceStart >= MIN_SILENCE_DURATION) {
          silentRanges.push({ start: Math.round(silenceStart * 100) / 100, end: Math.round(time * 100) / 100 })
        }
        silenceStart = null
      }
    }

    sampleIndex += SAMPLES_PER_POINT
  }

  fs.writeFileSync(`${outputBase}.peaks.json`, JSON.stringify(peaks))
  fs.writeFileSync(`${outputBase}.silences.json`, JSON.stringify(silentRanges))
  console.log(`✓ ${path.basename(outputBase)}: ${peaks[0].length} peaks, ${silentRanges.length} silent ranges`)
})
```

**第三步：批量处理所有音频（服务器执行）**

```bash
# 对 /data/audio/ 下所有 mp3 批量生成 peaks + silences
for f in /data/audio/*.mp3; do
  base="${f%.mp3}"
  ffmpeg -i "$f" -filter:a aformat=channel_layouts=mono \
    -f s16le -ar 8000 pipe:1 2>/dev/null | \
    node gen-peaks.js "$base"
done
```

执行完后目录结构：

```
/data/audio/
├── call_001.mp3
├── call_001.peaks.json      ← 波形峰值，约 8KB（1小时音频）
├── call_001.silences.json   ← 静音区间，约 1KB
├── call_002.mp3
├── call_002.peaks.json
├── call_002.silences.json
└── ...
```

**第四步：前端按命名规律加载**

```js
// 按文件名规律自动推导 peaks / silences 路径
async function loadTrackMeta(src) {
  const base = src.replace(/\.(mp3|wav|ogg|m4a)$/, '')
  const [peaks, silences] = await Promise.all([
    fetch(`${base}.peaks.json`).then(r => r.json()),
    fetch(`${base}.silences.json`).then(r => r.json()),
  ])
  return { peaks, silences }
}
```

```vue
<script setup>
const src = 'https://your-server.com/audio/call_001.mp3'
const { peaks, silences } = await loadTrackMeta(src)
</script>

<VoicePlayer
  :track-a="{ src, peaks, silences, duration: 3720 }"
/>
```
```

### 7.3 区间循环实现

```js
// 激活区间模式：允许用户在波形上拖拽创建区间
function enableRegionLoop(regions, ws) {
  regions.enableDragSelection({ color: 'var(--vp-region-color)' })

  regions.on('region-created', (region) => {
    // 删除旧区间，保留最新一个
    regions.getRegions().forEach(r => { if (r.id !== region.id) r.remove() })
  })

  ws.on('timeupdate', (time) => {
    const [region] = regions.getRegions()
    if (region && time >= region.end) {
      ws.setTime(region.start)  // 跳回区间起点
    }
  })
}

// 停用区间模式
function disableRegionLoop(regions) {
  regions.getRegions().forEach(r => r.remove())
  regions.disableDragSelection()
}
```

### 7.4 选区浮动工具条

选区与区间循环共用同一个 `RegionsPlugin` 拖拽交互，选区创建后在其上方动态定位浮动工具条。

**浮动工具条按钮：**

| 按钮 | 功能 |
|------|------|
| ▶ 播放选区 | 跳到选区起点开始播放，到终点自动停止 |
| ⟳ 循环选区 | 在选区内循环播放（即原区间循环功能） |
| ↓ 下载选区 | 用 Web Audio API 裁剪音频片段后下载 |
| ✕ 清除选区 | 删除选区，工具条消失 |

**位置计算：** 工具条水平居中对齐选区，紧贴波形容器顶部上方：

```js
// 监听选区变化，更新浮动工具条位置
regions.on('region-updated', (region) => {
  const waveRect = waveContainer.getBoundingClientRect()
  const regionStart = region.start / ws.getDuration()
  const regionEnd = region.end / ws.getDuration()
  const left = waveRect.width * regionStart
  const width = waveRect.width * (regionEnd - regionStart)

  state.toolbar = {
    visible: true,
    left: left + width / 2,  // 水平居中
    region,
  }
})

regions.on('region-removed', () => {
  state.toolbar = { visible: false, left: 0, region: null }
})
```

**模板结构（相对于 `.vp-waveform` 定位）：**

```vue
<div class="vp-waveform-wrap">
  <!-- 浮动工具条 -->
  <div
    v-if="track.state.toolbar.visible"
    class="vp-region-toolbar"
    :style="{ left: track.state.toolbar.left + 'px' }"
  >
    <button @click="playRegion(track)">▶</button>
    <button @click="toggleLoop(track)">⟳</button>
    <button @click="downloadRegion(track)">↓</button>
    <button @click="clearRegion(track)">✕</button>
  </div>

  <!-- 波形容器 -->
  <div :ref="el => setWaveRef(el, track.id)" class="vp-waveform"></div>
</div>
```

**播放选区实现：**

```js
function playRegion(track) {
  const region = track.state.toolbar.region
  if (!region) return
  track.state.ws.setTime(region.start)
  track.state.ws.play()
  track.state.isPlaying = true

  // 到达终点自动停止
  const stop = (time) => {
    if (time >= region.end) {
      track.state.ws.pause()
      track.state.isPlaying = false
      track.state.ws.un('timeupdate', stop)
    }
  }
  track.state.ws.on('timeupdate', stop)
}
```

**下载选区实现（Web Audio API 裁剪）：**

```js
async function downloadRegion(track) {
  const region = track.state.toolbar.region
  if (!region) return

  const audioCtx = new AudioContext()
  const url = track.state.objectUrl || track.config.src

  // 获取原始 ArrayBuffer
  const arrayBuffer = await fetch(url).then(r => r.arrayBuffer())
  const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer)

  // 裁剪选区时间段
  const startSample = Math.floor(region.start * audioBuffer.sampleRate)
  const endSample = Math.floor(region.end * audioBuffer.sampleRate)
  const length = endSample - startSample

  const clipped = audioCtx.createBuffer(
    audioBuffer.numberOfChannels,
    length,
    audioBuffer.sampleRate
  )

  for (let ch = 0; ch < audioBuffer.numberOfChannels; ch++) {
    clipped.copyToChannel(
      audioBuffer.getChannelData(ch).slice(startSample, endSample),
      ch
    )
  }

  // 编码为 WAV 并下载
  const wav = audioBufferToWav(clipped)  // 见下方工具函数
  const blob = new Blob([wav], { type: 'audio/wav' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `clip_${region.start.toFixed(1)}-${region.end.toFixed(1)}.wav`
  a.click()
  URL.revokeObjectURL(a.href)
}

// WAV 编码工具函数
function audioBufferToWav(buffer) {
  const numCh = buffer.numberOfChannels
  const length = buffer.length * numCh * 2 + 44
  const out = new ArrayBuffer(length)
  const view = new DataView(out)
  const writeStr = (o, s) => [...s].forEach((c, i) => view.setUint8(o + i, c.charCodeAt(0)))

  writeStr(0, 'RIFF'); view.setUint32(4, length - 8, true)
  writeStr(8, 'WAVE'); writeStr(12, 'fmt ')
  view.setUint32(16, 16, true); view.setUint16(20, 1, true)
  view.setUint16(22, numCh, true)
  view.setUint32(24, buffer.sampleRate, true)
  view.setUint32(28, buffer.sampleRate * numCh * 2, true)
  view.setUint16(32, numCh * 2, true); view.setUint16(34, 16, true)
  writeStr(36, 'data'); view.setUint32(40, buffer.length * numCh * 2, true)

  let offset = 44
  for (let i = 0; i < buffer.length; i++) {
    for (let ch = 0; ch < numCh; ch++) {
      const s = Math.max(-1, Math.min(1, buffer.getChannelData(ch)[i]))
      view.setInt16(offset, s < 0 ? s * 32768 : s * 32767, true)
      offset += 2
    }
  }
  return out
}
```

**CSS 浮动工具条样式：**

```css
.vp-waveform-wrap {
  position: relative;
}

.vp-region-toolbar {
  position: absolute;
  top: -36px;
  transform: translateX(-50%);
  background: var(--vp-bg);
  border: 1px solid var(--vp-border-color);
  border-radius: 6px;
  padding: 4px 6px;
  display: flex;
  gap: 4px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  z-index: 10;
  white-space: nowrap;
}

.vp-region-toolbar button {
  background: none;
  border: none;
  color: var(--vp-btn-color);
  cursor: pointer;
  font-size: 13px;
  padding: 2px 6px;
  border-radius: 4px;
}

.vp-region-toolbar button:hover {
  background: var(--vp-btn-hover-bg);
}
```

### 7.5 跳过空音实现

两种加载模式采用不同方案：

| 模式 | 跳过空音方式 |
|------|-------------|
| 标准模式（< 30分钟） | `SkipSilencePlugin` 实时检测（Web Audio API AnalyserNode） |
| peaks 模式（> 30分钟） | 预扫描生成 `silences.json`，播放时按区间跳转 |

#### 标准模式：SkipSilencePlugin

```js
import SkipSilencePlugin from 'wavesurfer.js/dist/plugins/skip-silence.js'

const skipSilence = SkipSilencePlugin.create({
  threshold: 0.001,  // 振幅低于此值视为静音（0~1）
  margin: 0.2,       // 静音持续超过此秒数才跳，避免截断过猛
})

const ws = WaveSurfer.create({
  ...
  plugins: [regions, skipSilence],
})

// 开关控制
function toggleSkipSilence(track) {
  track.state.skipSilence = !track.state.skipSilence
  track.state.skipSilencePlugin.setOptions({
    enabled: track.state.skipSilence,
  })
}
```

**原理：** 插件通过 `AnalyserNode` 持续采样当前帧的 RMS（均方根音量），低于 `threshold` 且持续超过 `margin` 秒时，自动跳到下一个有声区起点。属于实时检测，必须"播放经过"静音段才能触发跳转。

#### peaks 模式：预扫描 + 区间跳转

peaks 模式下 `AnalyserNode` 无真实 AudioBuffer 可读，`SkipSilencePlugin` 失效。需在生成 peaks 时同步输出静音区间：

```js
// gen-peaks.js 扩展：同步输出 silences.json
const SILENCE_THRESHOLD = 0.001
const MIN_SILENCE_DURATION = 0.2  // 秒，短于此的静音不记录

const silentRanges = []
let silenceStart = null
const sampleRate = 8000

for (let i = 0; i < samples.length; i++) {
  const isSilent = Math.abs(samples[i]) < SILENCE_THRESHOLD
  const time = i / sampleRate

  if (isSilent && silenceStart === null) {
    silenceStart = time
  } else if (!isSilent && silenceStart !== null) {
    if (time - silenceStart >= MIN_SILENCE_DURATION) {
      silentRanges.push({ start: silenceStart, end: time })
    }
    silenceStart = null
  }
}

// 输出两个文件
fs.writeFileSync('audio.peaks.json', JSON.stringify(peaks))
fs.writeFileSync('audio.silences.json', JSON.stringify(silentRanges))
// silences.json 格式：[{ start: 5.2, end: 8.7 }, { start: 32.1, end: 35.0 }, ...]
```

前端加载并在 `timeupdate` 中跳转：

```js
// TrackConfig 新增 silences 字段
// silences?: Array<{ start: number, end: number }>

ws.on('timeupdate', (time) => {
  if (!state.skipSilence || !config.silences) return
  const silent = config.silences.find(r => time >= r.start && time < r.end)
  if (silent) ws.setTime(silent.end)
})
```

peaks 模式使用示例：

```vue
<script setup>
const peaks = await fetch('/audio/long.peaks.json').then(r => r.json())
const silences = await fetch('/audio/long.silences.json').then(r => r.json())
</script>

<VoicePlayer
  :track-a="{
    src: '/audio/long.mp3',
    peaks,
    silences,
    duration: 3720
  }"
/>

### 7.5 下载实现

```js
function downloadAudio(track, resolvedUrl) {
  const a = document.createElement('a')
  a.href = resolvedUrl
  a.download = track.file?.name || resolvedUrl.split('/').pop() || 'audio'
  a.click()
}
```

### 7.6 双轨管理

```js
// 组件内部维护两个独立状态对象
const tracks = computed(() => {
  const result = [{ config: props.trackA, id: 'A' }]
  if (props.trackB) result.push({ config: props.trackB, id: 'B' })
  return result
})

// 每个轨道独立的响应式状态
function createTrackState() {
  return reactive({
    isPlaying: false,
    isLoading: false,
    currentTime: 0,
    duration: 0,
    volume: 1,
    speed: 1,
    loopEnabled: false,
    skipSilence: true, // 默认开启跳过空音
    ws: null,
    regions: null,
    objectUrl: null,   // 用于 File 模式下的内存释放
  })
}
```

---

## 八、完整组件结构（VoicePlayer.vue）

```vue
<template>
  <div class="voice-player">
    <div
      v-for="track in tracks"
      :key="track.id"
      class="vp-track"
    >
      <!-- 轨道头部：标签 + 加载状态 -->
      <div class="vp-track-header">
        <span class="vp-label">{{ track.config.label || `${track.id}路` }}</span>
        <span v-if="track.state.isLoading" class="vp-loading">加载中...</span>
      </div>

      <!-- 波形容器 -->
      <div :ref="el => setWaveRef(el, track.id)" class="vp-waveform"></div>

      <!-- 控制栏 -->
      <div class="vp-controls">
        <!-- 播放/暂停 -->
        <button class="vp-btn" @click="togglePlay(track)">
          <span>{{ track.state.isPlaying ? '⏸' : '▶' }}</span>
        </button>

        <!-- 时间显示 -->
        <span class="vp-time">
          {{ formatTime(track.state.currentTime) }} /
          {{ formatTime(track.state.duration) }}
        </span>

        <!-- 音量 -->
        <button class="vp-btn" @click="toggleMute(track)">
          <span>{{ track.state.volume === 0 ? '🔇' : '🔊' }}</span>
        </button>
        <input
          type="range" min="0" max="1" step="0.01"
          :value="track.state.volume"
          class="vp-slider vp-volume-slider"
          @input="setVolume(track, $event.target.value)"
        />

        <!-- 播放速度 -->
        <button class="vp-btn vp-speed-btn" @click="cycleSpeed(track)">
          {{ track.state.speed }}x
        </button>

        <!-- 区间循环 -->
        <button
          class="vp-btn"
          :class="{ 'vp-btn--active': track.state.loopEnabled }"
          @click="toggleLoop(track)"
          title="区间循环"
        >⟳</button>

        <!-- 跳过空音开关 -->
        <button
          class="vp-btn vp-skip-btn"
          :class="{ 'vp-btn--active': track.state.skipSilence }"
          @click="toggleSkipSilence(track)"
          title="跳过空音"
        >静</button>

        <!-- 下载 -->
        <button class="vp-btn" @click="download(track)" title="下载">↓</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import WaveSurfer from 'wavesurfer.js'
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.js'

// ── Props ──────────────────────────────────────────────────────────────
const props = defineProps({
  trackA: { type: Object, required: true },
  trackB: { type: Object, default: null },
  options: { type: Object, default: () => ({}) },
})

// ── 速度档位 ────────────────────────────────────────────────────────────
const SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 2]

// ── 轨道状态工厂 ────────────────────────────────────────────────────────
function createTrackState(id) {
  return reactive({
    id,
    isPlaying: false,
    isLoading: false,
    currentTime: 0,
    duration: 0,
    volume: 1,
    isMuted: false,
    speed: 1,
    loopEnabled: false,
    ws: null,
    regions: null,
    objectUrl: null,
  })
}

const stateA = createTrackState('A')
const stateB = createTrackState('B')

const tracks = computed(() => {
  const result = [{ id: 'A', config: props.trackA, state: stateA }]
  if (props.trackB) result.push({ id: 'B', config: props.trackB, state: stateB })
  return result
})

// ── DOM refs ────────────────────────────────────────────────────────────
const waveRefs = {}
function setWaveRef(el, id) {
  if (el) waveRefs[id] = el
}

// ── WaveSurfer 初始化 ───────────────────────────────────────────────────
async function initTrack(track) {
  const { config, state } = track
  const container = waveRefs[track.id]
  if (!container) return

  state.isLoading = true

  const regions = RegionsPlugin.create()
  const ws = WaveSurfer.create({
    container,
    waveColor: props.options.waveColor || 'var(--vp-wave-color, #93c5fd)',
    progressColor: props.options.progressColor || 'var(--vp-progress-color, #2563eb)',
    cursorColor: props.options.cursorColor || 'var(--vp-cursor-color, #1d4ed8)',
    barWidth: props.options.barWidth ?? 2,
    barGap: props.options.barGap ?? 1,
    height: props.options.height ?? 80,
    plugins: [regions],
  })

  state.ws = ws
  state.regions = regions

  const url = config.file
    ? (state.objectUrl = URL.createObjectURL(config.file))
    : config.src

  await loadTrack(ws, config, state)

  ws.on('ready', () => {
    state.duration = ws.getDuration()
    state.isLoading = false
  })

  ws.on('timeupdate', (time) => {
    state.currentTime = time
    // 区间循环检测
    if (state.loopEnabled) {
      const [region] = regions.getRegions()
      if (region && time >= region.end) {
        ws.setTime(region.start)
      }
    }
  })

  ws.on('finish', () => { state.isPlaying = false })
}

// ── 控制方法 ────────────────────────────────────────────────────────────
function togglePlay(track) {
  track.state.ws?.playPause()
  track.state.isPlaying = !track.state.isPlaying
}

function setVolume(track, val) {
  const v = parseFloat(val)
  track.state.volume = v
  track.state.isMuted = v === 0
  track.state.ws?.setVolume(v)
}

function toggleMute(track) {
  if (track.state.isMuted) {
    setVolume(track, track.state.volume || 0.8)
  } else {
    const prev = track.state.volume
    track.state.ws?.setVolume(0)
    track.state.isMuted = true
    track.state.volume = prev  // 保留静音前音量，恢复时使用
  }
}

function cycleSpeed(track) {
  const idx = SPEEDS.indexOf(track.state.speed)
  const next = SPEEDS[(idx + 1) % SPEEDS.length]
  track.state.speed = next
  track.state.ws?.setPlaybackRate(next)
}

function toggleLoop(track) {
  track.state.loopEnabled = !track.state.loopEnabled
  if (track.state.loopEnabled) {
    track.state.regions.enableDragSelection({
      color: 'var(--vp-region-color, rgba(37,99,235,0.2))',
    })
    track.state.regions.on('region-created', (region) => {
      track.state.regions.getRegions().forEach(r => {
        if (r.id !== region.id) r.remove()
      })
    })
  } else {
    track.state.regions.getRegions().forEach(r => r.remove())
    track.state.regions.disableDragSelection()
  }
}

function download(track) {
  const url = track.state.objectUrl || track.config.src
  if (!url) return
  const a = document.createElement('a')
  a.href = url
  a.download = track.config.file?.name || url.split('/').pop() || 'audio'
  a.click()
}

// ── 工具函数 ────────────────────────────────────────────────────────────
function formatTime(seconds) {
  if (!seconds || isNaN(seconds)) return '00:00'
  const m = Math.floor(seconds / 60).toString().padStart(2, '0')
  const s = Math.floor(seconds % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

// ── 生命周期 ────────────────────────────────────────────────────────────
onMounted(async () => {
  await nextTick()
  for (const track of tracks.value) {
    await initTrack(track)
  }
})

onBeforeUnmount(() => {
  for (const track of tracks.value) {
    track.state.ws?.destroy()
    if (track.state.objectUrl) {
      URL.revokeObjectURL(track.state.objectUrl)
    }
  }
})

// trackB 动态变化时重新初始化
watch(() => props.trackB, async (newVal) => {
  if (newVal && !stateB.ws) {
    await nextTick()
    await initTrack({ id: 'B', config: newVal, state: stateB })
  }
})
</script>

<style scoped>
/* ── CSS 变量默认值 ──────────────────────────────────────────────── */
.voice-player {
  --vp-bg: #ffffff;
  --vp-border-color: #e5e7eb;
  --vp-wave-color: #93c5fd;
  --vp-progress-color: #2563eb;
  --vp-cursor-color: #1d4ed8;
  --vp-region-color: rgba(37, 99, 235, 0.2);
  --vp-btn-color: #2563eb;
  --vp-btn-hover-bg: #eff6ff;
  --vp-label-color: #374151;
  --vp-time-color: #6b7280;
  --vp-slider-color: #2563eb;
  --vp-radius: 8px;

  background: var(--vp-bg);
  border-radius: var(--vp-radius);
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  font-family: system-ui, sans-serif;
}

/* ── 轨道 ────────────────────────────────────────────────────────── */
.vp-track {
  border: 1px solid var(--vp-border-color);
  border-radius: calc(var(--vp-radius) - 2px);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.vp-track-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.vp-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--vp-label-color);
}

.vp-loading {
  font-size: 12px;
  color: var(--vp-time-color);
}

/* ── 波形容器 ─────────────────────────────────────────────────────── */
.vp-waveform {
  width: 100%;
  cursor: pointer;
}

/* ── 控制栏 ──────────────────────────────────────────────────────── */
.vp-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.vp-btn {
  background: none;
  border: 1px solid transparent;
  border-radius: 6px;
  color: var(--vp-btn-color);
  cursor: pointer;
  font-size: 15px;
  padding: 4px 8px;
  line-height: 1;
  transition: background 0.15s;
}

.vp-btn:hover {
  background: var(--vp-btn-hover-bg);
}

.vp-btn--active {
  background: var(--vp-btn-hover-bg);
  border-color: var(--vp-btn-color);
}

.vp-speed-btn {
  font-size: 12px;
  font-weight: 600;
  min-width: 36px;
}

/* ── 时间 ────────────────────────────────────────────────────────── */
.vp-time {
  font-size: 12px;
  color: var(--vp-time-color);
  font-variant-numeric: tabular-nums;
  min-width: 80px;
}

/* ── 滑块 ────────────────────────────────────────────────────────── */
.vp-slider {
  -webkit-appearance: none;
  appearance: none;
  height: 4px;
  border-radius: 2px;
  background: var(--vp-border-color);
  outline: none;
  cursor: pointer;
}

.vp-volume-slider {
  width: 70px;
}

.vp-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--vp-slider-color);
  cursor: pointer;
}
</style>
```

---

## 九、产品增强功能

### 9.1 键盘快捷键

| 快捷键 | 功能 |
|--------|------|
| `空格` | 播放 / 暂停（聚焦轨道） |
| `←` / `→` | 后退 / 前进 5 秒 |
| `Shift + ←` / `→` | 后退 / 前进 1 秒 |
| `[` | 跳到选区起点 |
| `]` | 跳到选区终点 |

```js
// 键盘事件绑定（挂载在 .vp-track 上，聚焦时生效）
function bindKeyboard(track) {
  const handler = (e) => {
    switch (e.key) {
      case ' ':
        e.preventDefault()
        togglePlay(track)
        break
      case 'ArrowLeft':
        track.state.ws.setTime(Math.max(0,
          track.state.currentTime - (e.shiftKey ? 1 : 5)))
        break
      case 'ArrowRight':
        track.state.ws.setTime(Math.min(track.state.duration,
          track.state.currentTime + (e.shiftKey ? 1 : 5)))
        break
      case '[': {
        const region = track.state.toolbar.region
        if (region) track.state.ws.setTime(region.start)
        break
      }
      case ']': {
        const region = track.state.toolbar.region
        if (region) track.state.ws.setTime(region.end)
        break
      }
    }
  }
  return handler
}
```

---

### 9.2 书签 / 标记点

在波形上打标记，可命名，点击跳转，书签数据持久化到 `localStorage`。

```
波形：▔▔▔▁▂▃▄▅▁▁▁▂▃▄▅▁▁
              🔖           ← 书签竖线
           客户投诉         ← 书签标签（hover 显示）
```

**数据结构：**

```ts
interface Bookmark {
  id: string
  time: number    // 秒
  label: string   // 书签名称
}
```

**实现要点：**

```js
// 双击波形添加书签
waveContainer.addEventListener('dblclick', (e) => {
  const rect = waveContainer.getBoundingClientRect()
  const time = ((e.clientX - rect.left) / rect.width) * track.state.duration
  const label = prompt('书签名称', `标记 ${formatTime(time)}`)
  if (label === null) return
  addBookmark(track, { id: Date.now().toString(), time, label })
})

// 书签渲染（绝对定位竖线 + hover 标签）
// 书签存储（localStorage，按音频 src 为 key）
function saveBookmarks(src, bookmarks) {
  localStorage.setItem(`vp-bookmarks:${src}`, JSON.stringify(bookmarks))
}
function loadBookmarks(src) {
  return JSON.parse(localStorage.getItem(`vp-bookmarks:${src}`) || '[]')
}
```

**TrackConfig 新增字段：**

```ts
bookmarks?: Bookmark[]  // 外部传入书签，不传则从 localStorage 加载
```

---

### 9.3 波形缩放

长音频支持滚轮缩放，放大后出现横向滚动条定位：

```js
// WaveSurfer 内置 zoom 支持
waveContainer.addEventListener('wheel', (e) => {
  e.preventDefault()
  const currentZoom = track.state.zoom ?? 1
  const delta = e.deltaY > 0 ? -10 : 10
  const nextZoom = Math.max(1, Math.min(200, currentZoom + delta))
  track.state.zoom = nextZoom
  track.state.ws.zoom(nextZoom)  // WaveSurfer 内置 zoom() 方法
}, { passive: false })
```

`zoom(1)` 为默认视图，`zoom(200)` 为最大放大。放大后波形容器自动出现横向滚动，WaveSurfer 内置处理。

---

### 9.4 时间戳点击复制

点击时间显示区域复制当前时间到剪贴板，并短暂显示"已复制"反馈：

```js
async function copyTime(track) {
  const time = formatTime(track.state.currentTime)
  await navigator.clipboard.writeText(time)
  track.state.timeCopied = true
  setTimeout(() => { track.state.timeCopied = false }, 1500)
}
```

```vue
<span class="vp-time" @click="copyTime(track)" title="点击复制时间">
  {{ track.state.timeCopied ? '已复制' : formatTime(track.state.currentTime) }}
  / {{ formatTime(track.state.duration) }}
</span>
```

---

### 9.5 AB 路同步模式

同步模式开启时，A 路时间变化联动 B 路跳转到相同时间点：

```js
// 同步开关（组件级，非轨道级）
const syncAB = ref(false)

// A 路 timeupdate 时同步 B 路
stateA.ws?.on('timeupdate', (time) => {
  if (syncAB.value && stateB.ws && !stateB.isPlaying) {
    stateB.ws.setTime(time)
  }
})
```

控制栏增加同步按钮（仅双轨模式显示）：

```vue
<button
  v-if="props.trackB"
  class="vp-btn"
  :class="{ 'vp-btn--active': syncAB }"
  @click="syncAB = !syncAB"
  title="AB 路同步"
>AB</button>
```

---

### 9.6 加载失败处理

音频加载失败时显示明确错误提示 + 重试按钮：

```js
ws.on('error', (err) => {
  state.isLoading = false
  state.loadError = err.message || '音频加载失败'
})
```

```vue
<div v-if="track.state.loadError" class="vp-error">
  <span>⚠ {{ track.state.loadError }}</span>
  <button class="vp-btn" @click="retryLoad(track)">重试</button>
</div>
<div v-else-if="track.state.isLoading" class="vp-loading">
  加载中 {{ track.state.loadProgress }}%
</div>
```

---

### 9.7 加载进度条

WaveSurfer 提供 `loading` 事件，实时更新解码进度：

```js
ws.on('loading', (percent) => {
  state.loadProgress = percent  // 0-100
})
```

```vue
<div v-if="track.state.isLoading" class="vp-progress-bar">
  <div class="vp-progress-fill"
    :style="{ width: track.state.loadProgress + '%' }">
  </div>
  <span>{{ track.state.loadProgress }}%</span>
</div>
```

---

### 9.8 批注功能

选区浮动工具条增加"批注"按钮，对片段添加文字说明，存 `localStorage`：

```ts
interface Annotation {
  id: string
  start: number
  end: number
  note: string
}
```

```js
function addAnnotation(track, region) {
  const note = prompt('添加批注')
  if (!note) return
  const ann = { id: Date.now().toString(), start: region.start, end: region.end, note }
  track.state.annotations.push(ann)
  saveAnnotations(track.config.src, track.state.annotations)
}
```

---

### 9.9 导出标注报告

将书签、批注、选区信息导出为 JSON 文件：

```js
function exportReport(track) {
  const report = {
    audio: track.config.src || track.config.file?.name,
    duration: track.state.duration,
    exportedAt: new Date().toISOString(),
    bookmarks: track.state.bookmarks,
    annotations: track.state.annotations,
  }
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `report_${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(a.href)
}
```

导出格式示例：

```json
{
  "audio": "call_001.mp3",
  "duration": 3720,
  "exportedAt": "2026-10-10T08:00:00.000Z",
  "bookmarks": [
    { "id": "1", "time": 83.5, "label": "客户投诉" },
    { "id": "2", "time": 210.2, "label": "坐席话术问题" }
  ],
  "annotations": [
    { "id": "3", "start": 83.5, "end": 95.0, "note": "需要复核" }
  ]
}
```

---

### 9.10 AB 路音量差异可视化

双轨模式下，在两个波形之间绘制一条细线，实时反映 A/B 音量差值：

```js
// 监听双轨 timeupdate，计算音量差并更新指示条宽度
function updateVolumeDiff() {
  if (!stateA.ws || !stateB.ws) return
  const diff = Math.abs(stateA.volume - stateB.volume)  // 0~1
  volumeDiffBar.style.width = (diff * 100) + '%'
  volumeDiffBar.style.background = diff > 0.3 ? '#ef4444' : '#22c55e'
}
```

```vue
<!-- 仅双轨模式显示，位于两个轨道之间 -->
<div v-if="props.trackB" class="vp-volume-diff">
  <span class="vp-volume-diff-label">音量差</span>
  <div class="vp-volume-diff-track">
    <div class="vp-volume-diff-bar" :style="volumeDiffStyle"></div>
  </div>
</div>
```

---

## 十、CSS 变量补充（新增功能）

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `--vp-bookmark-color` | `#f59e0b` | 书签竖线颜色 |
| `--vp-error-color` | `#ef4444` | 错误提示文字颜色 |
| `--vp-progress-bar-color` | `#2563eb` | 加载进度条颜色 |
| `--vp-diff-ok-color` | `#22c55e` | AB 音量差正常颜色 |
| `--vp-diff-warn-color` | `#ef4444` | AB 音量差异常颜色 |

---

## 十一、暗色主题示例

```vue
<VoicePlayer
  :track-a="{ src: audioUrl, label: 'A路' }"
  :track-b="{ src: audioUrlB, label: 'B路' }"
  style="
    --vp-bg: #0f172a;
    --vp-border-color: #1e293b;
    --vp-wave-color: #4f46e5;
    --vp-progress-color: #818cf8;
    --vp-cursor-color: #a5b4fc;
    --vp-region-color: rgba(129,140,248,0.25);
    --vp-btn-color: #818cf8;
    --vp-btn-hover-bg: #1e293b;
    --vp-label-color: #e2e8f0;
    --vp-time-color: #94a3b8;
    --vp-slider-color: #818cf8;
  "
/>
```

---

## 十二、注意事项

| 事项 | 说明 |
|------|------|
| 跨域音频 | 服务端需配置 `Access-Control-Allow-Origin` 响应头，否则 WaveSurfer 无法解码波形 |
| 大文件性能 | 超过 30 分钟音频：本地用 ffmpeg 预生成 `peaks.json` 随文件部署，传入 `peaks` + `duration` prop，渲染瞬时完成 |
| 内存释放 | `File` 模式创建的 ObjectURL 在组件 `onBeforeUnmount` 时自动释放 |
| SSR 兼容 | WaveSurfer.js 依赖 Web API，不兼容 SSR，使用时需确保在客户端环境中挂载 |
| 浏览器兼容 | 支持所有现代浏览器（Chrome 80+、Firefox 75+、Safari 14+） |
