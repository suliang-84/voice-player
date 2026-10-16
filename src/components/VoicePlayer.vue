<!-- src/components/VoicePlayer.vue -->
<template>
  <div class="voice-player" ref="rootEl">
    <!-- AB 路全局控制条（仅双轨时显示） -->
    <div v-if="props.trackB" class="vp-sync-bar">
      <!-- 全局播放/暂停 -->
      <button class="vp-btn" @click="togglePlayBoth" :title="bothPlaying ? '暂停全部' : '播放全部'">
        {{ bothPlaying ? '⏸' : '▶' }} {{ bothPlaying ? '暂停全部' : '播放全部' }}
      </button>
      <!-- AB 全局音量控制 -->
      <button class="vp-btn" @click="toggleMuteBoth" :title="bothMuted ? '取消静音' : '全部静音'">
        {{ bothMuted ? '🔇' : '🔊' }}
      </button>
      <input
        type="range" min="0" max="1" step="0.01"
        :value="bothMuted ? 0 : abVolume"
        class="vp-slider vp-ab-volume-slider"
        @input="setVolumeBoth($event.target.value)"
      />
      <!-- AB 播放速度 -->
      <button class="vp-btn vp-speed-btn" @click="cycleSpeedBoth" title="播放速度（两路同步）">
        {{ abSpeed }}x
      </button>
      <!-- 合并导出标注 -->
      <button class="vp-btn" @click="exportReportBoth" title="合并导出两路标注">📄</button>
      <!-- 下载全部 -->
      <button class="vp-btn" @click="downloadBoth" title="下载全部">↓ 下载全部</button>
    </div>

    <!-- 轨道列表 -->
    <div :class="props.trackB ? 'vp-tracks-dual' : null">
    <div
      v-for="track in tracks"
      :key="track.id"
      class="vp-track"
      :class="{ 'vp-track--dual': props.trackB }"
      tabindex="0"
      @keydown="handleKeydown($event, track)"
    >
      <!-- 头部：标签 + 控制栏 -->
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

          <button v-if="!props.trackB" class="vp-btn vp-play-btn" @click="togglePlay(track)">
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

          <template v-if="!props.trackB">
            <button class="vp-btn" @click="toggleMute(track)" :title="track.state.isMuted ? '取消静音' : '静音'">
              {{ track.state.isMuted ? '🔇' : '🔊' }}
            </button>
            <input
              type="range" min="0" max="1" step="0.01"
              :value="track.state.isMuted ? 0 : track.state.volume"
              class="vp-slider vp-volume-slider"
              @input="setVolume(track, $event.target.value)"
            />
          </template>

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

    </div>
    </div><!-- end vp-tracks-dual wrapper -->

  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import WaveSurfer from 'wavesurfer.js'
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js'

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

// ── AB 进度同步（仅用户主动 seek 时触发，播放中不干预） ─────────────────────────
// 区域边界处理中的持久化锁（异步事件期间全程有效）
const _regionEndLock = { A: false, B: false }

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
// Store rAF IDs for mirror loops keyed by track id
const mirrorRafIds = {}

function setWaveRef(el, id) { if (el) waveRefs[id] = el }
function setMirrorRef(el, id) { if (el) mirrorRefs[id] = el }
function setWrapRef(el, id) { if (el) wrapRefs[id] = el }

// ── WaveSurfer 初始化 ──────────────────────────────────────────────────
async function initWaveSurfer(track) {
  const { config, state } = track
  const waveContainer = waveRefs[track.id]
  if (!waveContainer) return

  const opt = props.options || {}
  const waveformType = opt.waveformType ?? 'mirror-bar'
  const isMirror = waveformType.startsWith('mirror-')

  // ── 构建插件列表 ────────────────────────────────────────────────────
  const regions = RegionsPlugin.create()
  const plugins = [regions]

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
    interact: false,  // 禁用内置 click-to-seek，由下方手动判断点击/拖拽
    plugins,
  })

  state.ws = ws
  state.regions = regions
  state.skipSilencePlugin = skipSilencePlugin

  // ── 点击 seek（区分点击与拖拽：移动 < 5px 才 seek）─────────────────────
  let _mouseDownX = 0
  waveContainer.addEventListener('mousedown', (e) => { _mouseDownX = e.clientX })
  waveContainer.addEventListener('mouseup', (e) => {
    if (Math.abs(e.clientX - _mouseDownX) >= 5) return  // 拖拽，跳过 seek
    if (!state.duration) return
    const rect = waveContainer.getBoundingClientRect()
    const progress = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
    const newTime = progress * state.duration
    ws.seekTo(progress)
    // 用户主动 seek 时精确同步对方轨道
    if (props.trackB) {
      const other = track.id === 'A' ? stateB : stateA
      if (other.ws) other.ws.setTime(newTime)
    }
  })

  // ── 双击波形添加书签 ──────────────────────────────────────────────────
  waveContainer.addEventListener('dblclick', (e) => {
    if (!state.duration) return
    const rect = waveContainer.getBoundingClientRect()
    const time = ((e.clientX - rect.left) / rect.width) * state.duration
    const label = prompt('书签名称', `标记 ${formatTime(time)}`)
    if (label === null) return
    addBookmark(track, { id: Date.now().toString(), time, label })
  })

  // ── 滚轮缩放 ──────────────────────────────────────────────────────────
  waveContainer.addEventListener('wheel', (e) => {
    e.preventDefault()
    const delta = e.deltaY > 0 ? -10 : 10
    state.zoom = Math.max(1, Math.min(200, (state.zoom ?? 1) + delta))
    ws.zoom(state.zoom)
  }, { passive: false })

  // ── 镜像下半：用 requestAnimationFrame 持续 drawImage 复制像素 ──────
  if (isMirror) {
    ws.on('ready', () => {
      const mirrorDiv = mirrorRefs[track.id]
      if (!mirrorDiv) return

      // 取 WaveSurfer shadow DOM 或普通 DOM 中的第一块 canvas
      const sourceCanvas =
        waveContainer.shadowRoot?.querySelector('canvas') ||
        waveContainer.querySelector('canvas')

      if (!sourceCanvas) return

      // 停止旧循环（如重新初始化时）
      if (mirrorRafIds[track.id]) cancelAnimationFrame(mirrorRafIds[track.id])

      // 创建镜像 canvas，尺寸与源 canvas 保持一致
      mirrorDiv.innerHTML = ''
      const mirrorCanvas = document.createElement('canvas')
      mirrorCanvas.width = sourceCanvas.width
      mirrorCanvas.height = sourceCanvas.height
      mirrorCanvas.style.width = '100%'
      mirrorCanvas.style.height = '100%'
      mirrorDiv.appendChild(mirrorCanvas)
      const mirrorCtx = mirrorCanvas.getContext('2d')

      // rAF 持续同步像素
      function drawMirror() {
        if (mirrorCanvas.width !== sourceCanvas.width || mirrorCanvas.height !== sourceCanvas.height) {
          mirrorCanvas.width = sourceCanvas.width
          mirrorCanvas.height = sourceCanvas.height
        }
        try { mirrorCtx.drawImage(sourceCanvas, 0, 0) } catch (_) { /* ignore cross-origin */ }
        mirrorRafIds[track.id] = requestAnimationFrame(drawMirror)
      }
      drawMirror()
    })
  }

  // ── 音频加载（Task 4）──────────────────────────────────────────────
  await loadAudio(track)
}

// ── 音频加载 ────────────────────────────────────────────────────────────
async function loadAudio(track) {
  const { config, state } = track
  const ws = state.ws

  // ── 绑定加载事件 ──────────────────────────────────────────────────────
  ws.on('loading', (percent) => {
    state.loadProgress = percent
  })

  ws.on('ready', () => {
    state.duration = ws.getDuration()
    state.isLoading = false
    state.loadProgress = 100
    state.loadError = null
    // 从 localStorage 恢复书签与批注
    const storageKey = config.src || config.file?.name
    if (storageKey) {
      const saved = localStorage.getItem(`vp-bookmarks:${storageKey}`)
      if (saved) {
        try { state.bookmarks = JSON.parse(saved) } catch (_) {}
      }
      const savedAnn = localStorage.getItem(`vp-annotations:${storageKey}`)
      if (savedAnn) {
        try { state.annotations = JSON.parse(savedAnn) } catch (_) {}
      }
    }
    // 标准模式：静音检测在首次播放时懒初始化（需要用户手势才能让 AudioContext 以 running 状态启动）

    // 始终启用拖拽选区（无需开关按钮）
    state.regions.enableDragSelection({
      color: rootEl.value
        ? getComputedStyle(rootEl.value).getPropertyValue('--vp-region-color').trim() || 'rgba(37,99,235,0.2)'
        : 'rgba(37,99,235,0.2)',
    })
    const unsubCreated = state.regions.on('region-created', (region) => {
      state.regions.getRegions().forEach(r => { if (r.id !== region.id) r.remove() })
      updateToolbar(track, region)
      ws.setTime(region.start)
      if (!_syncingRegion) syncRegionToOther(track, region)
    })
    const unsubUpdated = state.regions.on('region-updated', (region) => {
      updateToolbar(track, region)
      syncRegionToOther(track, region)
    })
    const unsubRemoved = state.regions.on('region-removed', () => {
      // 同步中或还有选区时不清空 toolbar
      if (_syncingRegion) return
      if (state.regions.getRegions().length === 0) {
        state.toolbar = { visible: false, left: 0, region: null }
      }
    })
    regionListeners[track.id] = [unsubCreated, unsubUpdated, unsubRemoved]
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

    // 选区边界检测：用持久化锁防止异步事件重复触发
    if (state.toolbar.region && !_regionEndLock[track.id]) {
      const region = state.toolbar.region
      if (time >= region.end) {
        _regionEndLock[track.id] = true
        if (state.loopEnabled) {
          ws.pause()
          ws.setTime(region.start)
          ws.play().finally(() => { _regionEndLock[track.id] = false })
        } else {
          ws.pause()
          ws.setTime(region.end)
          state.isPlaying = false
          // 锁短暂保持，防止 pause 触发的 timeupdate 再次进入
          setTimeout(() => { _regionEndLock[track.id] = false }, 200)
        }
      }
    }
    // AB 同步已移至用户 seek 时触发，播放中不干预，保证进度条丝滑
  })

  // ── 解析 URL ──────────────────────────────────────────────────────────
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
    // peaks 模式：跳过解码，直接渲染；第三参数为时长（秒）
    ws.load(url, config.peaks, config.duration)
  } else {
    // 标准模式：WaveSurfer Web Worker 解码
    ws.load(url)
  }
}

// ── 重试加载 ─────────────────────────────────────────────────────────────
async function retryLoad(track) {
  stopSilenceDetection(track)
  // 停止镜像循环
  if (mirrorRafIds[track.id]) {
    cancelAnimationFrame(mirrorRafIds[track.id])
    delete mirrorRafIds[track.id]
  }
  track.state.loadError = null
  track.state.ws?.destroy()
  track.state.ws = null
  await nextTick()
  await initWaveSurfer(track)
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
    // 停止静音检测
    stopSilenceDetection(track)
    // 停止镜像 rAF 循环
    if (mirrorRafIds[track.id]) {
      cancelAnimationFrame(mirrorRafIds[track.id])
      delete mirrorRafIds[track.id]
    }
    // 清理区间事件监听器
    if (regionListeners[track.id]) {
      regionListeners[track.id].forEach(unsub => unsub?.())
      delete regionListeners[track.id]
    }
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

// ── AB 全局控制 ──────────────────────────────────────────────────────────
const bothPlaying = computed(() => stateA.isPlaying || stateB.isPlaying)
const bothMuted = computed(() => stateA.isMuted && stateB.isMuted)
const abVolume = ref(1)
const abSpeed = ref(1)

function setVolumeBoth(val) {
  const v = parseFloat(val)
  abVolume.value = v
  for (const track of tracks.value) {
    if (!track.state.ws) continue
    track.state.volume = v
    track.state.isMuted = v === 0
    track.state.ws.setVolume(v)
  }
}

function togglePlayBoth() {
  const playing = bothPlaying.value
  if (!playing) {
    // 开始播放前先对齐两轨起始位置
    const refTrack = tracks.value[0]
    if (refTrack?.state.ws) {
      const isEnded = refTrack.state.ws.getMediaElement()?.ended ?? false
      const region = refTrack.state.toolbar.region
      let startTime
      if (isEnded) {
        // 音频自然结束：从头（或选区起点）重播
        startTime = region ? region.start : 0
      } else {
        startTime = refTrack.state.currentTime
        if (region && startTime >= region.end) startTime = region.start
      }
      // 所有轨道对齐到同一起点，清除 regionEndLock
      for (const track of tracks.value) {
        _regionEndLock[track.id] = false
        track.state.ws?.setTime(startTime)
      }
    }
  }
  for (const track of tracks.value) {
    if (!track.state.ws) continue
    if (track.state.skipSilence && !track.config?.silences && !analyserNodes[track.id]) {
      startSilenceDetection(track)
    }
    if (playing && track.state.isPlaying) {
      track.state.ws.pause()
      track.state.isPlaying = false
    } else if (!playing && !track.state.isPlaying) {
      track.state.ws.play()
      track.state.isPlaying = true
    }
  }
}

function toggleMuteBoth() {
  const mute = !bothMuted.value
  for (const track of tracks.value) {
    if (!track.state.ws) continue
    if (mute) {
      track.state.ws.setVolume(0)
      track.state.isMuted = true
    } else {
      const v = track.state.volume || 0.8
      track.state.ws.setVolume(v)
      track.state.isMuted = false
    }
  }
}

function cycleSpeedBoth() {
  const idx = SPEEDS.indexOf(abSpeed.value)
  const next = SPEEDS[(idx + 1) % SPEEDS.length]
  abSpeed.value = next
  for (const track of tracks.value) {
    track.state.speed = next
    track.state.ws?.setPlaybackRate(next)
  }
}

function exportReportBoth() {
  const report = {
    exportedAt: new Date().toISOString(),
    tracks: tracks.value.map(track => ({
      id: track.id,
      audio: track.config.src || track.config.file?.name || 'unknown',
      duration: track.state.duration,
      bookmarks: track.state.bookmarks,
      annotations: track.state.annotations,
    })),
  }
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `report_AB_${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(a.href)
}

function downloadBoth() {
  for (const track of tracks.value) {
    downloadAudio(track)
  }
}

// ── 播放控制 ────────────────────────────────────────────────────────────
function togglePlay(track) {
  if (!track.state.ws) return
  // 首次播放时在用户手势内懒创建 AudioContext（保证以 running 状态启动，避免挂起导致音频路由失效）
  if (track.state.skipSilence && !track.config?.silences && !analyserNodes[track.id]) {
    startSilenceDetection(track)
  }
  if (track.state.isPlaying) {
    track.state.ws.pause()
    track.state.isPlaying = false
    return
  }
  // 以底层 media.ended 为权威判断音频是否已播完，不依赖 currentTime 推断
  const ended = track.state.ws.getMediaElement()?.ended ?? false
  const atEnd = track.state.duration > 0 && track.state.currentTime >= track.state.duration - 0.1
  const region = track.state.toolbar.region
  if (region) {
    if (ended || track.state.currentTime >= region.end) {
      track.state.ws.setTime(region.start)
    }
    _regionEndLock[track.id] = false
  } else if (ended || atEnd) {
    track.state.ws.setTime(0)
  }
  track.state.ws.play()
  track.state.isPlaying = true
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


// ── 跳过空音 ────────────────────────────────────────────────────────────
// Store analyser nodes per track
const analyserNodes = {}
const silenceTimers = {}

// ── 选区事件监听器管理 ──────────────────────────────────────────────────
// Store unsubscribe functions per track to prevent listener accumulation
const regionListeners = {}
let _syncingRegion = false

function syncRegionToOther(track, region) {
  if (!props.trackB || _syncingRegion) return
  const otherState = track.id === 'A' ? stateB : stateA
  if (!otherState.regions) return
  _syncingRegion = true
  // 清除对方旧选区，新建同范围选区
  otherState.regions.getRegions().forEach(r => r.remove())
  const newRegion = otherState.regions.addRegion({
    start: region.start,
    end: region.end,
    color: rootEl.value
      ? getComputedStyle(rootEl.value).getPropertyValue('--vp-region-color').trim() || 'rgba(37,99,235,0.2)'
      : 'rgba(37,99,235,0.2)',
    drag: false,
    resize: false,
  })
  _syncingRegion = false
  // 用 addRegion 返回值直接更新对方 toolbar，不依赖事件链时序
  const otherTrack = tracks.value.find(t => t.id !== track.id)
  if (otherTrack && newRegion) updateToolbar(otherTrack, newRegion)
}

function startSilenceDetection(track) {
  // Guard: prevent duplicate AudioContext on same track
  if (analyserNodes[track.id]) return
  if (!track.state.ws) return
  const mediaEl = track.state.ws.getMediaElement()
  if (!mediaEl) return

  const audioCtx = new AudioContext()
  const source = audioCtx.createMediaElementSource(mediaEl)
  const analyser = audioCtx.createAnalyser()
  analyser.fftSize = 512
  source.connect(analyser)
  source.connect(audioCtx.destination)  // still play audio

  analyserNodes[track.id] = { audioCtx, analyser }

  const dataArray = new Float32Array(analyser.fftSize)
  let silenceStart = null
  const THRESHOLD = 0.001
  const MARGIN = 0.2

  function checkSilence() {
    if (!track.state.skipSilence || !track.state.isPlaying) {
      silenceStart = null
      silenceTimers[track.id] = requestAnimationFrame(checkSilence)
      return
    }
    analyser.getFloatTimeDomainData(dataArray)
    const rms = Math.sqrt(dataArray.reduce((s, v) => s + v * v, 0) / dataArray.length)

    if (rms < THRESHOLD) {
      if (silenceStart === null) silenceStart = track.state.currentTime
      else if (track.state.currentTime - silenceStart > MARGIN) {
        // Jump forward 0.5s to escape silence
        const newTime = Math.min(track.state.duration, track.state.currentTime + 0.5)
        track.state.ws.setTime(newTime)
        silenceStart = null
      }
    } else {
      silenceStart = null
    }
    silenceTimers[track.id] = requestAnimationFrame(checkSilence)
  }
  silenceTimers[track.id] = requestAnimationFrame(checkSilence)
}

function stopSilenceDetection(track) {
  if (silenceTimers[track.id]) {
    cancelAnimationFrame(silenceTimers[track.id])
    delete silenceTimers[track.id]
  }
  if (analyserNodes[track.id]) {
    analyserNodes[track.id].audioCtx.close()
    delete analyserNodes[track.id]
  }
}

function toggleSkipSilence(track) {
  track.state.skipSilence = !track.state.skipSilence

  if (track.state.skipSilence) {
    startSilenceDetection(track)
  } else {
    stopSilenceDetection(track)
  }
}

// ── 选区与浮动工具条 ─────────────────────────────────────────────────────

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
  // 双轨模式同步清除对方选区
  if (props.trackB) {
    const otherState = track.id === 'A' ? stateB : stateA
    otherState.regions?.getRegions().forEach(r => r.remove())
    otherState.toolbar = { visible: false, left: 0, region: null }
  }
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
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.vp-ab-volume-slider { width: 90px; }

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

/* 双轨模式：轨道包裹层无间隙，轨道无边框 */
.vp-tracks-dual {
  display: flex;
  flex-direction: column;
}
.vp-track--dual {
  border: none;
  border-radius: 0;
}

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

</style>
