# VoicePlayer 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现一个基于 Vite + Vue3 + WaveSurfer.js 的波纹语音播放器单文件组件（VoicePlayer.vue），支持双轨、多种波形、超长音频、选区操作、书签批注等功能。

**Architecture:** 全部业务逻辑封装在单个 `VoicePlayer.vue` SFC 中，可直接复制到其他项目使用。每个轨道（A/B）维护独立的响应式状态对象，WaveSurfer 实例按轨道独立创建和销毁。波形渲染策略通过 `options.waveformType` 在初始化时决定，镜像效果用 CSS `scaleY(-1)` 实现。

**Tech Stack:** Vite 5, Vue 3.4, wavesurfer.js ^7.x, Web Audio API (原生), localStorage (书签/批注持久化)

**Spec:** `docs/superpowers/specs/2026-10-10-voice-player-design.md`

## Global Constraints

- wavesurfer.js >= 7.x（插件化架构）
- Vue 3 Composition API + `<script setup>`
- 单文件组件，复制 VoicePlayer.vue + `npm install wavesurfer.js` 即可使用
- 默认波形类型：`mirror-bar`（镜像对称柱状）
- 默认跳过空音：开启
- 浏览器兼容：Chrome 80+、Firefox 75+、Safari 14+
- 不依赖后端服务，peaks/silences 为静态文件

---

## 文件结构

```
/Users/suliang/project/voice-player/
├── index.html                        ← Demo 页（验证用）
├── package.json
├── vite.config.js
├── scripts/
│   └── gen-peaks.js                  ← 服务器批处理脚本（Node.js）
└── src/
    ├── main.js
    ├── App.vue                       ← Demo 入口
    └── components/
        └── VoicePlayer.vue           ← 核心组件（所有逻辑在此）
```

---

## Task 1: 项目脚手架

**Files:**
- Create: `package.json`
- Create: `vite.config.js`
- Create: `index.html`
- Create: `src/main.js`
- Create: `src/App.vue`

**Interfaces:**
- Produces: 可运行的 Vite + Vue3 开发环境，`npm run dev` 可访问 demo 页

- [ ] **Step 1: 初始化 package.json**

```json
{
  "name": "voice-player",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "wavesurfer.js": "^7.8.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^5.0.0"
  }
}
```

- [ ] **Step 2: 安装依赖**

```bash
cd /Users/suliang/project/voice-player
npm install
```

Expected: `node_modules/` 创建，`wavesurfer.js` 安装成功

- [ ] **Step 3: 创建 vite.config.js**

```js
// vite.config.js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
})
```

- [ ] **Step 4: 创建 index.html**

```html
<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>VoicePlayer Demo</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #f1f5f9; padding: 24px; font-family: system-ui, sans-serif; }
  </style>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

- [ ] **Step 5: 创建 src/main.js**

```js
import { createApp } from 'vue'
import App from './App.vue'
createApp(App).mount('#app')
```

- [ ] **Step 6: 创建 src/App.vue（最简占位）**

```vue
<template>
  <div style="padding: 24px">
    <h1 style="margin-bottom: 24px; font-size: 18px; color: #374151">VoicePlayer Demo</h1>
    <p style="color: #6b7280">组件开发中...</p>
  </div>
</template>
```

- [ ] **Step 7: 验证开发服务器启动**

```bash
npm run dev
```

Expected: 浏览器打开 `http://localhost:5173`，显示"组件开发中..."

- [ ] **Step 8: Commit**

```bash
git init
git add package.json vite.config.js index.html src/
git commit -m "feat: 初始化 Vite + Vue3 项目脚手架"
```

---

## Task 2: VoicePlayer.vue — Props、状态工厂、CSS 变量

**Files:**
- Create: `src/components/VoicePlayer.vue`

**Interfaces:**
- Produces:
  - `createTrackState(id: string): TrackState` — 轨道响应式状态对象
  - `tracks: ComputedRef<Track[]>` — 当前活跃轨道列表
  - CSS 变量系统，17 个 `--vp-*` 变量

- [ ] **Step 1: 创建 VoicePlayer.vue 基础骨架**

```vue
<!-- src/components/VoicePlayer.vue -->
<template>
  <div class="voice-player" ref="rootEl">
    <!-- AB 路同步按钮（仅双轨时显示） -->
    <div v-if="props.trackB" class="vp-sync-bar">
      <button
        class="vp-btn"
        :class="{ 'vp-btn--active': syncAB }"
        @click="syncAB = !syncAB"
        title="AB 路时间同步"
      >AB 同步</button>
    </div>

    <!-- 轨道列表 -->
    <div
      v-for="track in tracks"
      :key="track.id"
      class="vp-track"
      tabindex="0"
      @keydown="handleKeydown($event, track)"
    >
      <!-- 头部：标签 + 加载状态/错误 -->
      <div class="vp-track-header">
        <span class="vp-label">{{ track.config.label || `${track.id}路` }}</span>
        <div class="vp-header-right">
          <span v-if="track.state.loadError" class="vp-error-text">
            ⚠ {{ track.state.loadError }}
            <button class="vp-btn vp-retry-btn" @click="retryLoad(track)">重试</button>
          </span>
          <span v-else-if="track.state.isLoading" class="vp-loading-text">
            加载中 {{ track.state.loadProgress }}%
          </span>
        </div>
      </div>

      <!-- 加载进度条 -->
      <div v-if="track.state.isLoading" class="vp-load-progress">
        <div class="vp-load-progress-fill" :style="{ width: track.state.loadProgress + '%' }"></div>
      </div>

      <!-- 波形区域 -->
      <div class="vp-waveform-wrap" :ref="el => setWrapRef(el, track.id)">
        <!-- 浮动工具条 -->
        <div
          v-if="track.state.toolbar.visible"
          class="vp-region-toolbar"
          :style="{ left: track.state.toolbar.left + 'px' }"
        >
          <button @click="playRegion(track)" title="播放选区">▶</button>
          <button @click="loopRegion(track)" :class="{ 'vp-btn--active': track.state.loopEnabled }" title="循环选区">⟳</button>
          <button @click="downloadRegion(track)" title="下载选区">↓</button>
          <button @click="addAnnotation(track)" title="添加批注">✎</button>
          <button @click="clearRegion(track)" title="清除选区">✕</button>
        </div>

        <!-- 书签层 -->
        <div class="vp-bookmarks-layer">
          <div
            v-for="bm in track.state.bookmarks"
            :key="bm.id"
            class="vp-bookmark"
            :style="{ left: (bm.time / track.state.duration * 100) + '%' }"
            :title="bm.label"
            @click="track.state.ws?.setTime(bm.time)"
            @dblclick.stop="removeBookmark(track, bm.id)"
          >
            <div class="vp-bookmark-line"></div>
            <div class="vp-bookmark-label">{{ bm.label }}</div>
          </div>
        </div>

        <!-- 上半波形（WaveSurfer 渲染） -->
        <div :ref="el => setWaveRef(el, track.id)" class="vp-waveform-top"></div>

        <!-- 下半镜像（CSS scaleY(-1)） -->
        <div :ref="el => setMirrorRef(el, track.id)" class="vp-waveform-mirror"></div>
      </div>

      <!-- 控制栏 -->
      <div class="vp-controls">
        <button class="vp-btn vp-play-btn" @click="togglePlay(track)">
          {{ track.state.isPlaying ? '⏸' : '▶' }}
        </button>

        <span
          class="vp-time"
          @click="copyTime(track)"
          :title="track.state.timeCopied ? '已复制！' : '点击复制时间'"
        >
          {{ track.state.timeCopied ? '已复制' : formatTime(track.state.currentTime) }}
          / {{ formatTime(track.state.duration) }}
        </span>

        <button class="vp-btn" @click="toggleMute(track)" :title="track.state.isMuted ? '取消静音' : '静音'">
          {{ track.state.isMuted ? '🔇' : '🔊' }}
        </button>
        <input
          type="range" min="0" max="1" step="0.01"
          :value="track.state.isMuted ? 0 : track.state.volume"
          class="vp-slider vp-volume-slider"
          @input="setVolume(track, $event.target.value)"
        />

        <button class="vp-btn vp-speed-btn" @click="cycleSpeed(track)" title="播放速度">
          {{ track.state.speed }}x
        </button>

        <button
          class="vp-btn"
          :class="{ 'vp-btn--active': track.state.loopEnabled }"
          @click="toggleRegionMode(track)"
          title="拖拽选区"
        >⟳</button>

        <button
          class="vp-btn"
          :class="{ 'vp-btn--active': track.state.skipSilence }"
          @click="toggleSkipSilence(track)"
          title="跳过空音"
        >静</button>

        <button class="vp-btn" @click="exportReport(track)" title="导出标注报告">📄</button>
        <button class="vp-btn" @click="downloadAudio(track)" title="下载音频">↓</button>
      </div>
    </div>

    <!-- AB 音量差（双轨模式） -->
    <div v-if="props.trackB" class="vp-volume-diff">
      <span class="vp-volume-diff-label">音量差</span>
      <div class="vp-volume-diff-track">
        <div class="vp-volume-diff-bar" :style="volumeDiffStyle"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'

// ── Props ──────────────────────────────────────────────────────────────────
const props = defineProps({
  trackA: { type: Object, required: true },
  trackB: { type: Object, default: null },
  options: { type: Object, default: () => ({}) },
})

// ── 常量 ───────────────────────────────────────────────────────────────────
const SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 2]

// ── 根元素 ref ─────────────────────────────────────────────────────────────
const rootEl = ref(null)

// ── AB 同步开关 ────────────────────────────────────────────────────────────
const syncAB = ref(false)

// ── 轨道状态工厂 ───────────────────────────────────────────────────────────
function createTrackState(id) {
  return reactive({
    id,
    isPlaying: false,
    isLoading: false,
    loadProgress: 0,
    loadError: null,
    currentTime: 0,
    duration: 0,
    volume: 1,
    isMuted: false,
    speed: 1,
    zoom: 1,
    loopEnabled: false,
    skipSilence: true,
    timeCopied: false,
    ws: null,
    regions: null,
    skipSilencePlugin: null,
    objectUrl: null,
    toolbar: { visible: false, left: 0, region: null },
    bookmarks: [],
    annotations: [],
  })
}

const stateA = createTrackState('A')
const stateB = createTrackState('B')

const tracks = computed(() => {
  const result = [{ id: 'A', config: props.trackA, state: stateA }]
  if (props.trackB) result.push({ id: 'B', config: props.trackB, state: stateB })
  return result
})

// ── DOM refs ───────────────────────────────────────────────────────────────
const waveRefs = {}
const mirrorRefs = {}
const wrapRefs = {}

function setWaveRef(el, id) { if (el) waveRefs[id] = el }
function setMirrorRef(el, id) { if (el) mirrorRefs[id] = el }
function setWrapRef(el, id) { if (el) wrapRefs[id] = el }
</script>

<style scoped>
/* ── CSS 变量默认值 ────────────────────────────────────────────────────── */
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
  --vp-bookmark-color: #f59e0b;
  --vp-error-color: #ef4444;
  --vp-progress-bar-color: #2563eb;
  --vp-diff-ok-color: #22c55e;
  --vp-diff-warn-color: #ef4444;

  background: var(--vp-bg);
  border-radius: var(--vp-radius);
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  font-family: system-ui, sans-serif;
}

/* ── 同步栏 ──────────────────────────────────────────────────────────── */
.vp-sync-bar {
  display: flex;
  justify-content: flex-end;
}

/* ── 轨道 ────────────────────────────────────────────────────────────── */
.vp-track {
  border: 1px solid var(--vp-border-color);
  border-radius: calc(var(--vp-radius) - 2px);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  outline: none;
}
.vp-track:focus-within { border-color: var(--vp-btn-color); }

/* ── 头部 ────────────────────────────────────────────────────────────── */
.vp-track-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 20px;
}
.vp-label { font-size: 13px; font-weight: 600; color: var(--vp-label-color); }
.vp-header-right { display: flex; align-items: center; gap: 8px; }
.vp-loading-text { font-size: 12px; color: var(--vp-time-color); }
.vp-error-text { font-size: 12px; color: var(--vp-error-color); display: flex; align-items: center; gap: 6px; }
.vp-retry-btn { font-size: 11px; padding: 2px 6px; }

/* ── 加载进度条 ───────────────────────────────────────────────────────── */
.vp-load-progress {
  height: 3px;
  background: var(--vp-border-color);
  border-radius: 2px;
  overflow: hidden;
}
.vp-load-progress-fill {
  height: 100%;
  background: var(--vp-progress-bar-color);
  transition: width 0.2s;
}

/* ── 波形区域 ────────────────────────────────────────────────────────── */
.vp-waveform-wrap {
  position: relative;
  cursor: pointer;
  overflow: hidden;
}
.vp-waveform-top { width: 100%; }
.vp-waveform-mirror {
  width: 100%;
  transform: scaleY(-1);
  opacity: 0.5;
  pointer-events: none;
}

/* ── 浮动工具条 ──────────────────────────────────────────────────────── */
.vp-region-toolbar {
  position: absolute;
  top: 4px;
  transform: translateX(-50%);
  background: var(--vp-bg);
  border: 1px solid var(--vp-border-color);
  border-radius: 6px;
  padding: 3px 5px;
  display: flex;
  gap: 2px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  z-index: 20;
  white-space: nowrap;
}
.vp-region-toolbar button {
  background: none;
  border: none;
  color: var(--vp-btn-color);
  cursor: pointer;
  font-size: 13px;
  padding: 2px 5px;
  border-radius: 4px;
  line-height: 1.4;
}
.vp-region-toolbar button:hover { background: var(--vp-btn-hover-bg); }

/* ── 书签层 ──────────────────────────────────────────────────────────── */
.vp-bookmarks-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 10;
}
.vp-bookmark {
  position: absolute;
  top: 0;
  height: 100%;
  pointer-events: all;
  cursor: pointer;
  transform: translateX(-50%);
}
.vp-bookmark-line {
  width: 2px;
  height: 100%;
  background: var(--vp-bookmark-color);
  margin: 0 auto;
}
.vp-bookmark-label {
  position: absolute;
  top: 2px;
  left: 4px;
  font-size: 10px;
  color: var(--vp-bookmark-color);
  white-space: nowrap;
  background: var(--vp-bg);
  padding: 0 2px;
  border-radius: 2px;
  opacity: 0;
  transition: opacity 0.15s;
  pointer-events: none;
}
.vp-bookmark:hover .vp-bookmark-label { opacity: 1; }

/* ── 控制栏 ──────────────────────────────────────────────────────────── */
.vp-controls {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

/* ── 通用按钮 ────────────────────────────────────────────────────────── */
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
  white-space: nowrap;
}
.vp-btn:hover { background: var(--vp-btn-hover-bg); }
.vp-btn--active { background: var(--vp-btn-hover-bg); border-color: var(--vp-btn-color); }
.vp-speed-btn { font-size: 12px; font-weight: 600; min-width: 36px; }

/* ── 时间 ────────────────────────────────────────────────────────────── */
.vp-time {
  font-size: 12px;
  color: var(--vp-time-color);
  font-variant-numeric: tabular-nums;
  min-width: 90px;
  cursor: pointer;
  user-select: none;
}
.vp-time:hover { color: var(--vp-btn-color); }

/* ── 滑块 ────────────────────────────────────────────────────────────── */
.vp-slider {
  -webkit-appearance: none;
  appearance: none;
  height: 4px;
  border-radius: 2px;
  background: var(--vp-border-color);
  outline: none;
  cursor: pointer;
}
.vp-volume-slider { width: 70px; }
.vp-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 12px; height: 12px;
  border-radius: 50%;
  background: var(--vp-slider-color);
  cursor: pointer;
}

/* ── AB 音量差 ───────────────────────────────────────────────────────── */
.vp-volume-diff {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}
.vp-volume-diff-label { font-size: 11px; color: var(--vp-time-color); white-space: nowrap; }
.vp-volume-diff-track {
  flex: 1;
  height: 4px;
  background: var(--vp-border-color);
  border-radius: 2px;
  overflow: hidden;
}
.vp-volume-diff-bar { height: 100%; border-radius: 2px; transition: width 0.3s, background 0.3s; }
</style>
```

- [ ] **Step 2: 在 App.vue 中引入组件验证渲染**

```vue
<!-- src/App.vue -->
<template>
  <div style="max-width: 800px; margin: 0 auto; padding: 24px">
    <h1 style="margin-bottom: 24px; font-size: 18px; color: #374151">VoicePlayer Demo</h1>
    <VoicePlayer :track-a="{ src: '', label: 'A路测试' }" />
  </div>
</template>

<script setup>
import VoicePlayer from './components/VoicePlayer.vue'
</script>
```

- [ ] **Step 3: 启动 dev server，验证骨架渲染无报错**

```bash
npm run dev
```

Expected: 浏览器显示播放器骨架（控制栏、标签），控制台无 Vue 错误

- [ ] **Step 4: Commit**

```bash
git add src/components/VoicePlayer.vue src/App.vue
git commit -m "feat: VoicePlayer 骨架 - props、状态工厂、CSS 变量系统"
```

---

## Task 3: WaveSurfer 初始化与波形渲染

**Files:**
- Modify: `src/components/VoicePlayer.vue` — 在 `<script setup>` 中添加 WaveSurfer 初始化逻辑

**Interfaces:**
- Consumes: `createTrackState()`, `waveRefs`, `mirrorRefs`, `wrapRefs`, `props.options`
- Produces:
  - `buildColorMap(colorMap, rootEl): (energy: number) => string`
  - `initWaveSurfer(track): Promise<void>` — 初始化 WaveSurfer 实例，挂到 `track.state.ws`

- [ ] **Step 1: 在 script setup 顶部添加 WaveSurfer imports**

在 `<script setup>` 的 import 区域追加：

```js
import WaveSurfer from 'wavesurfer.js'
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js'
import SpectrogramPlugin from 'wavesurfer.js/dist/plugins/spectrogram.esm.js'
import SkipSilencePlugin from 'wavesurfer.js/dist/plugins/skip-silence.esm.js'
```

- [ ] **Step 2: 添加 buildColorMap 工具函数**

在 `// ── DOM refs` 区域之后添加：

```js
// ── 频谱图颜色映射 ─────────────────────────────────────────────────────
function buildColorMap(colorMap) {
  const root = rootEl.value
  if (colorMap === 'theme' || !colorMap) {
    const base = root
      ? getComputedStyle(root).getPropertyValue('--vp-progress-color').trim()
      : '#2563eb'
    // 返回 256 色阶数组（WaveSurfer SpectrogramPlugin 需要此格式）
    return Array.from({ length: 256 }, (_, i) => {
      const alpha = Math.round((i / 255) * 255).toString(16).padStart(2, '0')
      return base.startsWith('#') && base.length === 7
        ? base + alpha
        : `rgba(37,99,235,${(i / 255).toFixed(3)})`
    })
  }
  if (colorMap === 'heatmap') {
    return Array.from({ length: 256 }, (_, i) => {
      const h = Math.round((1 - i / 255) * 240)
      return `hsl(${h},100%,50%)`
    })
  }
  // 自定义颜色字符串
  return Array.from({ length: 256 }, (_, i) => {
    const alpha = i.toString(16).padStart(2, '0')
    return colorMap.startsWith('#') && colorMap.length === 7
      ? colorMap + alpha
      : `rgba(37,99,235,${(i / 255).toFixed(3)})`
  })
}
```

- [ ] **Step 3: 添加 initWaveSurfer 函数**

```js
// ── WaveSurfer 初始化 ──────────────────────────────────────────────────
async function initWaveSurfer(track) {
  const { config, state } = track
  const waveContainer = waveRefs[track.id]
  if (!waveContainer) return

  const opt = props.options || {}
  const waveformType = opt.waveformType ?? 'mirror-bar'
  const isMirror = waveformType.startsWith('mirror-')
  const isSpectrogram = waveformType === 'mirror-spectrogram'

  // ── 构建插件列表 ────────────────────────────────────────────────────
  const regions = RegionsPlugin.create()
  const plugins = [regions]

  let spectrogramPlugin = null
  if (isSpectrogram) {
    spectrogramPlugin = SpectrogramPlugin.create({
      colorMap: buildColorMap(opt.spectrogramColorMap),
      fftSamples: opt.fftSize ?? 2048,
      height: (opt.height ?? 80),
    })
    plugins.push(spectrogramPlugin)
  }

  let skipSilencePlugin = null
  if (!config.peaks) {
    // 标准模式才用插件，peaks 模式用 timeupdate 跳转
    skipSilencePlugin = SkipSilencePlugin.create({
      threshold: 0.001,
      margin: 0.2,
    })
    plugins.push(skipSilencePlugin)
  }

  // ── 创建 WaveSurfer 实例 ────────────────────────────────────────────
  const ws = WaveSurfer.create({
    container: waveContainer,
    waveColor: opt.waveColor
      || (rootEl.value ? getComputedStyle(rootEl.value).getPropertyValue('--vp-wave-color').trim() : '')
      || '#93c5fd',
    progressColor: opt.progressColor
      || (rootEl.value ? getComputedStyle(rootEl.value).getPropertyValue('--vp-progress-color').trim() : '')
      || '#2563eb',
    cursorColor: opt.cursorColor
      || (rootEl.value ? getComputedStyle(rootEl.value).getPropertyValue('--vp-cursor-color').trim() : '')
      || '#1d4ed8',
    barWidth: ['mirror-bar', 'bar'].includes(waveformType) ? (opt.barWidth ?? 2) : undefined,
    barGap: ['mirror-bar', 'bar'].includes(waveformType) ? (opt.barGap ?? 1) : undefined,
    height: opt.height ?? 80,
    plugins,
  })

  state.ws = ws
  state.regions = regions
  state.skipSilencePlugin = skipSilencePlugin

  // ── 镜像下半：克隆 WaveSurfer canvas 到 mirror div ─────────────────
  if (isMirror) {
    ws.on('ready', () => {
      const mirrorDiv = mirrorRefs[track.id]
      if (!mirrorDiv) return
      mirrorDiv.innerHTML = ''
      const sourceCanvas = waveContainer.querySelector('canvas')
      if (sourceCanvas) {
        const clone = sourceCanvas.cloneNode(true)
        mirrorDiv.appendChild(clone)
      }
    })
    // 进度更新时同步镜像
    ws.on('timeupdate', () => {
      const mirrorDiv = mirrorRefs[track.id]
      if (!mirrorDiv) return
      mirrorDiv.innerHTML = ''
      const sourceCanvas = waveContainer.querySelector('canvas')
      if (sourceCanvas) {
        const clone = sourceCanvas.cloneNode(true)
        mirrorDiv.appendChild(clone)
      }
    })
  }
}
```

- [ ] **Step 4: 添加生命周期钩子（onMounted / onBeforeUnmount）**

```js
// ── 生命周期 ────────────────────────────────────────────────────────────
onMounted(async () => {
  await nextTick()
  for (const track of tracks.value) {
    await initWaveSurfer(track)
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

// trackB 动态变化时初始化
watch(() => props.trackB, async (newVal) => {
  if (newVal && !stateB.ws) {
    await nextTick()
    await initWaveSurfer({ id: 'B', config: newVal, state: stateB })
  }
})
```

- [ ] **Step 5: 更新 App.vue，传入真实音频 URL 验证波形渲染**

使用公开可用的测试音频 URL：

```vue
<!-- src/App.vue -->
<template>
  <div style="max-width: 800px; margin: 0 auto; padding: 24px">
    <h1 style="margin-bottom: 24px; font-size: 18px">VoicePlayer Demo</h1>
    <VoicePlayer
      :track-a="{ src: 'https://www.w3schools.com/html/horse.ogg', label: 'A路测试' }"
    />
  </div>
</template>
<script setup>
import VoicePlayer from './components/VoicePlayer.vue'
</script>
```

- [ ] **Step 6: 浏览器验证波形渲染**

Expected:
- 加载进度条出现后消失
- 波形柱状图渲染（上半）
- 镜像下半出现（略透明）
- 控制台无报错

- [ ] **Step 7: Commit**

```bash
git add src/components/VoicePlayer.vue src/App.vue
git commit -m "feat: WaveSurfer 初始化与镜像波形渲染"
```

---

## Task 4: 音频加载（URL / File / Peaks 三种模式）

**Files:**
- Modify: `src/components/VoicePlayer.vue`

**Interfaces:**
- Consumes: `track.state.ws`, `track.config`
- Produces:
  - `loadAudio(track): Promise<void>` — 统一加载入口，处理三种模式
  - WaveSurfer `ready` / `loading` / `error` 事件绑定

- [ ] **Step 1: 添加 loadAudio 函数（在 initWaveSurfer 内部 ws 创建后调用）**

在 `initWaveSurfer` 末尾的 `state.ws = ws` 之后，添加以下 `loadAudio` 函数并调用：

```js
async function loadAudio(track) {
  const { config, state } = track
  const ws = state.ws

  // ── 绑定加载事件 ────────────────────────────────────────────────────
  ws.on('loading', (percent) => {
    state.loadProgress = percent
  })

  ws.on('ready', () => {
    state.duration = ws.getDuration()
    state.isLoading = false
    state.loadProgress = 100
    state.loadError = null
    // 加载书签
    const storageKey = config.src || config.file?.name
    if (storageKey) {
      const saved = localStorage.getItem(`vp-bookmarks:${storageKey}`)
      if (saved) state.bookmarks = JSON.parse(saved)
      const savedAnn = localStorage.getItem(`vp-annotations:${storageKey}`)
      if (savedAnn) state.annotations = JSON.parse(savedAnn)
    }
  })

  ws.on('error', (err) => {
    state.isLoading = false
    state.loadError = err?.message || '音频加载失败，请检查文件路径或网络'
  })

  ws.on('finish', () => { state.isPlaying = false })

  ws.on('timeupdate', (time) => {
    state.currentTime = time

    // peaks 模式跳过空音
    if (state.skipSilence && config.silences?.length) {
      const silent = config.silences.find(r => time >= r.start && time < r.end)
      if (silent) ws.setTime(silent.end)
    }

    // AB 同步
    if (track.id === 'A' && syncAB.value && stateB.ws && !stateB.isPlaying) {
      stateB.ws.setTime(time)
    }

    // 区间循环
    if (state.loopEnabled && state.toolbar.region) {
      const region = state.toolbar.region
      if (time >= region.end) ws.setTime(region.start)
    }
  })

  // ── 解析 URL ─────────────────────────────────────────────────────────
  const url = config.file
    ? (state.objectUrl = URL.createObjectURL(config.file))
    : config.src

  if (!url) {
    state.isLoading = false
    return
  }

  state.isLoading = true
  state.loadProgress = 0

  if (config.peaks) {
    // peaks 模式：跳过解码，直接渲染
    ws.load(url, config.peaks, config.duration)
  } else {
    // 标准模式：WaveSurfer Web Worker 解码
    ws.load(url)
  }
}
```

在 `initWaveSurfer` 末尾调用：

```js
  // initWaveSurfer 末尾追加
  await loadAudio(track)
}
```

- [ ] **Step 2: 添加 retryLoad 函数**

```js
async function retryLoad(track) {
  track.state.loadError = null
  track.state.ws?.destroy()
  track.state.ws = null
  await nextTick()
  await initWaveSurfer(track)
}
```

- [ ] **Step 3: 验证 URL 加载模式**

在 App.vue 保持公开 URL，刷新浏览器：

Expected:
- 进度条从 0% 到 100%
- 波形渲染完整
- 时间显示 `00:00 / 00:04`（horse.ogg 约 4 秒）

- [ ] **Step 4: 验证 File 加载模式**

在 App.vue 临时添加文件输入：

```vue
<input type="file" accept="audio/*" @change="onFile" />
<VoicePlayer v-if="trackFile" :track-a="trackFile" />

<script setup>
import { ref } from 'vue'
import VoicePlayer from './components/VoicePlayer.vue'
const trackFile = ref(null)
function onFile(e) {
  const file = e.target.files[0]
  if (file) trackFile.value = { file, label: file.name }
}
</script>
```

Expected: 选择本地 mp3/wav 后，波形渲染正常

- [ ] **Step 5: 验证错误处理**

在 App.vue 传入不存在的 URL：

```vue
<VoicePlayer :track-a="{ src: 'https://notexist.example.com/audio.mp3', label: '错误测试' }" />
```

Expected: 显示"⚠ 音频加载失败" + 重试按钮

- [ ] **Step 6: Commit**

```bash
git add src/components/VoicePlayer.vue
git commit -m "feat: 音频加载 URL/File/Peaks 三模式 + 错误处理"
```

---

## Task 5: 基础播放控制

**Files:**
- Modify: `src/components/VoicePlayer.vue`

**Interfaces:**
- Consumes: `track.state.ws`, `track.state`
- Produces:
  - `togglePlay(track)`
  - `setVolume(track, val: string)`
  - `toggleMute(track)`
  - `cycleSpeed(track)`
  - `downloadAudio(track)`
  - `formatTime(seconds: number): string`
  - `copyTime(track)`
  - `volumeDiffStyle: ComputedRef<{width, background}>`

- [ ] **Step 1: 添加播放控制函数**

```js
// ── 播放控制 ────────────────────────────────────────────────────────────
function togglePlay(track) {
  if (!track.state.ws) return
  track.state.ws.playPause()
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
    const v = track.state.volume || 0.8
    track.state.ws?.setVolume(v)
    track.state.isMuted = false
  } else {
    track.state.ws?.setVolume(0)
    track.state.isMuted = true
  }
}

function cycleSpeed(track) {
  const idx = SPEEDS.indexOf(track.state.speed)
  const next = SPEEDS[(idx + 1) % SPEEDS.length]
  track.state.speed = next
  track.state.ws?.setPlaybackRate(next)
}

function downloadAudio(track) {
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

async function copyTime(track) {
  const time = formatTime(track.state.currentTime)
  try {
    await navigator.clipboard.writeText(time)
    track.state.timeCopied = true
    setTimeout(() => { track.state.timeCopied = false }, 1500)
  } catch (_) {}
}

// ── AB 音量差可视化 ─────────────────────────────────────────────────────
const volumeDiffStyle = computed(() => {
  const diff = Math.abs(stateA.volume - stateB.volume)
  return {
    width: (diff * 100) + '%',
    background: diff > 0.3
      ? 'var(--vp-diff-warn-color, #ef4444)'
      : 'var(--vp-diff-ok-color, #22c55e)',
  }
})
```

- [ ] **Step 2: 浏览器验证播放控制**

Expected:
- 点击 ▶ 开始播放，图标变 ⏸，时间递增
- 点击 🔊 静音，再次点击恢复
- 拖动音量滑块，音量变化
- 点击速度按钮，速度在 0.5x → 0.75x → ... → 2x → 0.5x 循环
- 点击时间文字，显示"已复制"，1.5s 后恢复
- 点击 ↓ 触发浏览器下载对话框

- [ ] **Step 3: Commit**

```bash
git add src/components/VoicePlayer.vue
git commit -m "feat: 基础播放控制 - 播放/暂停/音量/速度/下载/时间复制"
```

---

## Task 6: 跳过空音

**Files:**
- Modify: `src/components/VoicePlayer.vue`

**Interfaces:**
- Consumes: `track.state.skipSilencePlugin`, `track.config.silences`, `track.state.skipSilence`
- Produces: `toggleSkipSilence(track)`

- [ ] **Step 1: 添加 toggleSkipSilence 函数**

```js
// ── 跳过空音 ────────────────────────────────────────────────────────────
function toggleSkipSilence(track) {
  track.state.skipSilence = !track.state.skipSilence

  // 标准模式：通过插件控制
  if (track.state.skipSilencePlugin) {
    // SkipSilencePlugin v7 通过 destroy/recreate 控制，或直接 setOptions
    try {
      track.state.skipSilencePlugin.setOptions({
        threshold: track.state.skipSilence ? 0.001 : 1,  // threshold=1 相当于禁用
      })
    } catch (_) {
      // 部分版本不支持 setOptions，用 threshold=1 绕过
    }
  }
  // peaks 模式：通过 state.skipSilence 标志控制（在 timeupdate 中判断）
}
```

- [ ] **Step 2: 验证标准模式跳过空音**

使用含静音段的音频测试：
- 上传一个有明显停顿的本地录音文件
- 确认"静"按钮高亮时，播放跳过静音段
- 关闭后，静音段正常播放

- [ ] **Step 3: Commit**

```bash
git add src/components/VoicePlayer.vue
git commit -m "feat: 跳过空音 - 标准模式插件 + peaks 模式区间跳转"
```

---

## Task 7: 选区与浮动工具条

**Files:**
- Modify: `src/components/VoicePlayer.vue`

**Interfaces:**
- Consumes: `track.state.regions`, `track.state.ws`, `wrapRefs`
- Produces:
  - `toggleRegionMode(track)` — 开启/关闭拖拽选区
  - `playRegion(track)`
  - `loopRegion(track)`
  - `downloadRegion(track)` — 裁剪 WAV 下载
  - `addAnnotation(track)` — 添加批注
  - `clearRegion(track)`
  - `audioBufferToWav(buffer: AudioBuffer): ArrayBuffer`

- [ ] **Step 1: 添加选区模式切换**

```js
// ── 选区与浮动工具条 ─────────────────────────────────────────────────────
function toggleRegionMode(track) {
  track.state.loopEnabled = !track.state.loopEnabled

  if (track.state.loopEnabled) {
    track.state.regions.enableDragSelection({
      color: getComputedStyle(rootEl.value || document.body)
        .getPropertyValue('--vp-region-color').trim() || 'rgba(37,99,235,0.2)',
    })

    track.state.regions.on('region-created', (region) => {
      // 保留最新一个选区
      track.state.regions.getRegions().forEach(r => {
        if (r.id !== region.id) r.remove()
      })
      updateToolbar(track, region)
    })

    track.state.regions.on('region-updated', (region) => {
      updateToolbar(track, region)
    })

    track.state.regions.on('region-removed', () => {
      track.state.toolbar = { visible: false, left: 0, region: null }
      track.state.loopEnabled = false
    })
  } else {
    track.state.regions.getRegions().forEach(r => r.remove())
    track.state.regions.disableDragSelection()
    track.state.toolbar = { visible: false, left: 0, region: null }
  }
}

function updateToolbar(track, region) {
  const wrap = wrapRefs[track.id]
  if (!wrap) return
  const W = wrap.getBoundingClientRect().width
  const dur = track.state.duration || 1
  const startX = (region.start / dur) * W
  const endX = (region.end / dur) * W
  track.state.toolbar = {
    visible: true,
    left: startX + (endX - startX) / 2,
    region,
  }
}
```

- [ ] **Step 2: 添加选区操作函数**

```js
function playRegion(track) {
  const region = track.state.toolbar.region
  if (!region || !track.state.ws) return
  track.state.ws.setTime(region.start)
  track.state.ws.play()
  track.state.isPlaying = true

  const stopAtEnd = (time) => {
    if (time >= region.end) {
      track.state.ws.pause()
      track.state.isPlaying = false
      track.state.ws.un('timeupdate', stopAtEnd)
    }
  }
  track.state.ws.on('timeupdate', stopAtEnd)
}

function loopRegion(track) {
  // 切换循环模式（loopEnabled 已在 timeupdate 中处理）
  track.state.loopEnabled = !track.state.loopEnabled
}

async function downloadRegion(track) {
  const region = track.state.toolbar.region
  if (!region) return
  const url = track.state.objectUrl || track.config.src
  if (!url) return

  try {
    const audioCtx = new AudioContext()
    const arrayBuffer = await fetch(url).then(r => r.arrayBuffer())
    const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer)

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

    const wav = audioBufferToWav(clipped)
    const blob = new Blob([wav], { type: 'audio/wav' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `clip_${region.start.toFixed(1)}-${region.end.toFixed(1)}.wav`
    a.click()
    URL.revokeObjectURL(a.href)
    audioCtx.close()
  } catch (err) {
    alert('下载选区失败：' + err.message)
  }
}

function addAnnotation(track) {
  const region = track.state.toolbar.region
  if (!region) return
  const note = prompt('添加批注（双击书签可删除）')
  if (!note) return
  const ann = {
    id: Date.now().toString(),
    start: region.start,
    end: region.end,
    note,
  }
  track.state.annotations.push(ann)
  const key = track.config.src || track.config.file?.name
  if (key) localStorage.setItem(`vp-annotations:${key}`, JSON.stringify(track.state.annotations))
}

function clearRegion(track) {
  track.state.regions.getRegions().forEach(r => r.remove())
  track.state.toolbar = { visible: false, left: 0, region: null }
  track.state.loopEnabled = false
}

// ── WAV 编码 ────────────────────────────────────────────────────────────
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

- [ ] **Step 3: 浏览器验证选区功能**

步骤：
1. 点击控制栏 ⟳ 按钮激活选区模式（按钮高亮）
2. 在波形上拖拽，选区高亮出现
3. 浮动工具条在选区上方居中出现
4. 点击工具条 ▶ — 只播放选区段
5. 点击工具条 ↓ — 下载 WAV 片段（浏览器下载对话框出现）
6. 点击工具条 ✎ — prompt 输入批注
7. 点击工具条 ✕ — 选区消失，工具条消失

- [ ] **Step 4: Commit**

```bash
git add src/components/VoicePlayer.vue
git commit -m "feat: 选区浮动工具条 - 播放/循环/下载WAV/批注/清除"
```

---

## Task 8: 键盘快捷键 + 书签 + 波形缩放

**Files:**
- Modify: `src/components/VoicePlayer.vue`

**Interfaces:**
- Consumes: `track.state.ws`, `track.state.bookmarks`, `waveRefs`
- Produces:
  - `handleKeydown(event, track)`
  - `addBookmark(track, bm)` / `removeBookmark(track, id)`
  - `saveBookmarks(src, bookmarks)`
  - 波形缩放 wheel 事件

- [ ] **Step 1: 添加键盘处理函数**

```js
// ── 键盘快捷键 ──────────────────────────────────────────────────────────
function handleKeydown(e, track) {
  if (!track.state.ws) return
  switch (e.key) {
    case ' ':
      e.preventDefault()
      togglePlay(track)
      break
    case 'ArrowLeft':
      e.preventDefault()
      track.state.ws.setTime(Math.max(0, track.state.currentTime - (e.shiftKey ? 1 : 5)))
      break
    case 'ArrowRight':
      e.preventDefault()
      track.state.ws.setTime(Math.min(track.state.duration, track.state.currentTime + (e.shiftKey ? 1 : 5)))
      break
    case '[': {
      const r = track.state.toolbar.region
      if (r) track.state.ws.setTime(r.start)
      break
    }
    case ']': {
      const r = track.state.toolbar.region
      if (r) track.state.ws.setTime(r.end)
      break
    }
  }
}
```

- [ ] **Step 2: 添加书签功能**

```js
// ── 书签 ────────────────────────────────────────────────────────────────
function addBookmark(track, bm) {
  track.state.bookmarks.push(bm)
  const key = track.config.src || track.config.file?.name
  if (key) localStorage.setItem(`vp-bookmarks:${key}`, JSON.stringify(track.state.bookmarks))
}

function removeBookmark(track, id) {
  track.state.bookmarks = track.state.bookmarks.filter(b => b.id !== id)
  const key = track.config.src || track.config.file?.name
  if (key) localStorage.setItem(`vp-bookmarks:${key}`, JSON.stringify(track.state.bookmarks))
}
```

- [ ] **Step 3: 在 initWaveSurfer 中绑定双击添加书签**

在 `initWaveSurfer` 函数内，`ws` 创建之后添加：

```js
  // 双击波形添加书签
  waveContainer.addEventListener('dblclick', (e) => {
    if (!state.duration) return
    const rect = waveContainer.getBoundingClientRect()
    const time = ((e.clientX - rect.left) / rect.width) * state.duration
    const label = prompt('书签名称', `标记 ${formatTime(time)}`)
    if (label === null) return
    addBookmark(track, { id: Date.now().toString(), time, label })
  })
```

- [ ] **Step 4: 添加滚轮缩放**

在 `initWaveSurfer` 函数内，`ws` 创建之后添加：

```js
  // 滚轮缩放
  waveContainer.addEventListener('wheel', (e) => {
    e.preventDefault()
    const delta = e.deltaY > 0 ? -10 : 10
    state.zoom = Math.max(1, Math.min(200, (state.zoom ?? 1) + delta))
    ws.zoom(state.zoom)
  }, { passive: false })
```

- [ ] **Step 5: 浏览器验证**

键盘测试（点击轨道聚焦后）：
- `空格` → 播放/暂停
- `←` → 后退 5 秒，`Shift+←` → 后退 1 秒
- `→` → 前进 5 秒，`Shift+→` → 前进 1 秒

书签测试：
- 双击波形 → prompt 输入名称 → 书签竖线出现
- hover 书签 → 名称标签出现
- 点击书签 → 跳转到对应时间
- 双击书签 → 删除

缩放测试：
- 向上滚动鼠标滚轮 → 波形放大，出现横向滚动条
- 向下滚动 → 波形缩小回原始

- [ ] **Step 6: Commit**

```bash
git add src/components/VoicePlayer.vue
git commit -m "feat: 键盘快捷键 + 书签标记 + 波形滚轮缩放"
```

---

## Task 9: 导出标注报告

**Files:**
- Modify: `src/components/VoicePlayer.vue`

**Interfaces:**
- Consumes: `track.state.bookmarks`, `track.state.annotations`, `track.state.duration`
- Produces: `exportReport(track)` — 下载 JSON 文件

- [ ] **Step 1: 添加 exportReport 函数**

```js
// ── 导出标注报告 ─────────────────────────────────────────────────────────
function exportReport(track) {
  const report = {
    audio: track.config.src || track.config.file?.name || 'unknown',
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

- [ ] **Step 2: 浏览器验证**

步骤：
1. 双击波形添加 2 个书签
2. 拖拽选区后点击 ✎ 添加批注
3. 点击控制栏 📄 按钮
4. 确认下载文件，打开验证 JSON 格式：

```json
{
  "audio": "https://...",
  "duration": 4.07,
  "exportedAt": "2026-10-10T...",
  "bookmarks": [{ "id": "...", "time": 1.2, "label": "测试书签" }],
  "annotations": [{ "id": "...", "start": 0.5, "end": 2.0, "note": "批注内容" }]
}
```

- [ ] **Step 3: Commit**

```bash
git add src/components/VoicePlayer.vue
git commit -m "feat: 导出标注报告 JSON"
```

---

## Task 10: 完整 Demo 页面

**Files:**
- Modify: `src/App.vue`

**Interfaces:**
- 展示所有功能：单轨、双轨、暗色主题、频谱图配置

- [ ] **Step 1: 更新 App.vue 为完整演示**

```vue
<!-- src/App.vue -->
<template>
  <div style="max-width: 860px; margin: 0 auto; padding: 24px; display: flex; flex-direction: column; gap: 32px;">
    <h1 style="font-size: 20px; font-weight: 700; color: #111827">VoicePlayer Demo</h1>

    <!-- 单轨 URL 模式（默认亮色主题） -->
    <section>
      <h2 style="font-size: 14px; color: #6b7280; margin-bottom: 8px">单轨 · 默认主题 · mirror-bar</h2>
      <VoicePlayer
        :track-a="{ src: AUDIO_URL, label: '主音频' }"
      />
    </section>

    <!-- 单轨 File 上传 -->
    <section>
      <h2 style="font-size: 14px; color: #6b7280; margin-bottom: 8px">单轨 · 本地文件上传</h2>
      <input type="file" accept="audio/*" @change="onFileA" style="margin-bottom: 8px; display: block;" />
      <VoicePlayer v-if="fileTrackA" :track-a="fileTrackA" />
    </section>

    <!-- 双轨 · 暗色主题 -->
    <section>
      <h2 style="font-size: 14px; color: #6b7280; margin-bottom: 8px">双轨 · 暗色主题</h2>
      <VoicePlayer
        :track-a="{ src: AUDIO_URL, label: 'A路' }"
        :track-b="{ src: AUDIO_URL, label: 'B路' }"
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
          --vp-bookmark-color: #fbbf24;
        "
      />
    </section>

    <!-- 频谱图模式 -->
    <section>
      <h2 style="font-size: 14px; color: #6b7280; margin-bottom: 8px">单轨 · 镜像频谱图（热力图配色）</h2>
      <VoicePlayer
        :track-a="{ src: AUDIO_URL, label: '频谱测试' }"
        :options="{ waveformType: 'mirror-spectrogram', spectrogramColorMap: 'heatmap', height: 100 }"
      />
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import VoicePlayer from './components/VoicePlayer.vue'

const AUDIO_URL = 'https://www.w3schools.com/html/horse.ogg'

const fileTrackA = ref(null)
function onFileA(e) {
  const file = e.target.files[0]
  if (file) fileTrackA.value = { file, label: file.name }
}
</script>
```

- [ ] **Step 2: 浏览器全功能验证清单**

- [ ] 单轨 URL：波形渲染、播放、时间显示、音量、速度、下载
- [ ] 单轨 URL：空格/方向键 快捷键
- [ ] 单轨 URL：双击添加书签，hover 显示标签，点击跳转，双击删除
- [ ] 单轨 URL：拖拽选区，浮动工具条出现，播放选区/下载选区/批注/清除
- [ ] 单轨 URL："静"按钮开关跳过空音
- [ ] 单轨 URL：📄 导出报告，验证 JSON
- [ ] 单轨 URL：滚轮缩放，横向滚动
- [ ] 本地文件：上传 mp3，波形渲染正常
- [ ] 双轨：AB 路独立控制，互不干扰
- [ ] 双轨：AB 同步按钮，A 跳转时 B 同步
- [ ] 双轨：音量差条显示（拖动两路音量滑块）
- [ ] 暗色主题：视觉正确
- [ ] 频谱图：热力图配色频谱渲染

- [ ] **Step 3: Commit**

```bash
git add src/App.vue
git commit -m "feat: 完整 Demo 页面 - 覆盖全部功能场景"
```

---

## Task 11: gen-peaks.js 服务器脚本

**Files:**
- Create: `scripts/gen-peaks.js`

**Interfaces:**
- Produces: `<outputBase>.peaks.json` 和 `<outputBase>.silences.json`
- 用法：`ffmpeg -i audio.mp3 -filter:a aformat=channel_layouts=mono -f s16le -ar 8000 pipe:1 | node gen-peaks.js /path/to/output/base`

- [ ] **Step 1: 创建 scripts/gen-peaks.js**

```js
#!/usr/bin/env node
// scripts/gen-peaks.js
// 用法：ffmpeg -i audio.mp3 -filter:a aformat=channel_layouts=mono -f s16le -ar 8000 pipe:1 | node gen-peaks.js /output/base
// 输出：/output/base.peaks.json 和 /output/base.silences.json

'use strict'
const fs = require('fs')
const path = require('path')

const SAMPLES_PER_POINT = 80      // 每点聚合采样数，越大文件越小
const SAMPLE_RATE = 8000          // 与 ffmpeg -ar 保持一致
const SILENCE_THRESHOLD = 0.001   // 低于此 RMS 视为静音
const MIN_SILENCE_DURATION = 0.2  // 静音段短于此秒数不记录

const outputBase = process.argv[2]
if (!outputBase) {
  console.error('Usage: ffmpeg ... pipe:1 | node gen-peaks.js /path/to/output/base')
  process.exit(1)
}

const chunks = []
process.stdin.on('data', chunk => chunks.push(chunk))
process.stdin.on('end', () => {
  const buf = Buffer.concat(chunks)
  const peaks = [[], []]
  const silentRanges = []
  let silenceStart = null
  let sampleIndex = 0
  const totalSamples = Math.floor(buf.length / 2)

  for (let i = 0; i + SAMPLES_PER_POINT * 2 <= buf.length; i += SAMPLES_PER_POINT * 2) {
    let max = 0, min = 0, sumSq = 0

    for (let j = 0; j < SAMPLES_PER_POINT * 2; j += 2) {
      const val = buf.readInt16LE(i + j) / 32768
      if (val > max) max = val
      if (val < min) min = val
      sumSq += val * val
    }

    const rms = Math.sqrt(sumSq / SAMPLES_PER_POINT)
    peaks[0].push(+(max.toFixed(4)))
    peaks[1].push(+(min.toFixed(4)))

    // 静音检测
    const time = sampleIndex / SAMPLE_RATE
    if (rms < SILENCE_THRESHOLD) {
      if (silenceStart === null) silenceStart = time
    } else {
      if (silenceStart !== null) {
        const silenceEnd = time
        if (silenceEnd - silenceStart >= MIN_SILENCE_DURATION) {
          silentRanges.push({
            start: +(silenceStart.toFixed(3)),
            end: +(silenceEnd.toFixed(3)),
          })
        }
        silenceStart = null
      }
    }

    sampleIndex += SAMPLES_PER_POINT
  }

  // 处理末尾静音
  if (silenceStart !== null) {
    const silenceEnd = totalSamples / SAMPLE_RATE
    if (silenceEnd - silenceStart >= MIN_SILENCE_DURATION) {
      silentRanges.push({ start: +(silenceStart.toFixed(3)), end: +(silenceEnd.toFixed(3)) })
    }
  }

  const peaksPath = `${outputBase}.peaks.json`
  const silencesPath = `${outputBase}.silences.json`

  fs.writeFileSync(peaksPath, JSON.stringify(peaks))
  fs.writeFileSync(silencesPath, JSON.stringify(silentRanges))

  const fileSizeKb = (fs.statSync(peaksPath).size / 1024).toFixed(1)
  console.log(`✓ ${path.basename(outputBase)}`)
  console.log(`  peaks:    ${peaks[0].length} points → ${peaksPath} (${fileSizeKb}KB)`)
  console.log(`  silences: ${silentRanges.length} ranges → ${silencesPath}`)
})
```

- [ ] **Step 2: 验证脚本（本地有 ffmpeg 时）**

```bash
# 用 horse.ogg 测试
curl -o /tmp/test.ogg https://www.w3schools.com/html/horse.ogg
ffmpeg -i /tmp/test.ogg -filter:a aformat=channel_layouts=mono \
  -f s16le -ar 8000 pipe:1 2>/dev/null | \
  node scripts/gen-peaks.js /tmp/test
```

Expected:
```
✓ test
  peaks:    XX points → /tmp/test.peaks.json (X.XKB)
  silences: X ranges → /tmp/test.silences.json
```

- [ ] **Step 3: Commit**

```bash
git add scripts/gen-peaks.js
git commit -m "feat: gen-peaks.js 服务器批处理脚本"
```

---

## 自检清单

对照 spec 逐项验证：

- [x] 波形渲染：mirror-bar 默认，可配置为 mirror-spectrogram / bar / line
- [x] 双轨 A/B 独立控制，B 路可选（单轨降级）
- [x] 文件加载：URL / File 对象两种方式
- [x] 超长音频：peaks + silences + duration 模式
- [x] 控制：播放/暂停/时间显示/音量/静音/速度/下载
- [x] 跳过空音开关（默认开启，标准/peaks 双路处理）
- [x] 选区浮动工具条：播放选区/循环/下载WAV/批注/清除
- [x] CSS 变量主题系统（17 个变量，完整覆盖）
- [x] 键盘快捷键（空格/方向键/[]/Shift 组合）
- [x] 书签：双击添加/点击跳转/双击删除/localStorage 持久化
- [x] 波形缩放（滚轮）
- [x] 时间戳点击复制
- [x] AB 路同步模式
- [x] 加载失败处理 + 重试按钮
- [x] 加载进度条
- [x] 批注功能（localStorage 持久化）
- [x] 导出标注报告（JSON）
- [x] AB 路音量差可视化
- [x] gen-peaks.js 服务器脚本
