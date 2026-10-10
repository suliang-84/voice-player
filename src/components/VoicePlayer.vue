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
import WaveSurfer from 'wavesurfer.js'
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js'
import SpectrogramPlugin from 'wavesurfer.js/dist/plugins/spectrogram.esm.js'

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

  // SkipSilencePlugin not available in wavesurfer.js 7.x — handled in Task 6
  const skipSilencePlugin = null

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

  // loadAudio(track) called in Task 4
}

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

// ── 占位函数（Task 4-9 实现） ───────────────────────────────────────────
function retryLoad(_track) {}
function togglePlay(_track) {}
function toggleMute(_track) {}
function setVolume(_track, _val) {}
function cycleSpeed(_track) {}
function toggleRegionMode(_track) {}
function toggleSkipSilence(_track) {}
function exportReport(_track) {}
function downloadAudio(_track) {}
function handleKeydown(_event, _track) {}
function copyTime(_track) {}
function playRegion(_track) {}
function loopRegion(_track) {}
function downloadRegion(_track) {}
function addAnnotation(_track) {}
function clearRegion(_track) {}
function removeBookmark(_track, _id) {}
function formatTime(seconds) {
  if (!seconds || isNaN(seconds)) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}
const volumeDiffStyle = computed(() => ({ width: '0%', background: 'var(--vp-diff-ok-color)' }))
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
