<!-- src/components/VoicePlayer.vue -->
<template>
  <div class="voice-player" ref="rootEl">
    <!-- 顶部控制栏 -->
    <div class="vp-control-bar">
      <!-- 左侧：主播放控制 -->
      <div class="vp-playback-controls">
        <button class="vp-btn" @click="handlePrev" title="上一条">
          <SvgIcon name="previous" />
        </button>
        <button class="vp-btn" @click="handleRewind" title="回退">
          <SvgIcon name="rewind" />
        </button>
        <button class="vp-btn vp-play-btn" @click="handlePlayPause" :title="isPlayingAll ? '暂停' : '播放'">
          <SvgIcon :name="isPlayingAll ? 'pause' : 'play'" />
        </button>
        <button class="vp-btn" @click="handleForward" title="快进">
          <SvgIcon name="forward" />
        </button>
        <button class="vp-btn" @click="handleNext" title="下一条">
          <SvgIcon name="next" />
        </button>
        <button class="vp-btn vp-volume-btn" @click="handleToggleMute" :title="isAllMuted ? '取消静音' : '静音'">
          <SvgIcon :name="isAllMuted ? 'volume_off' : 'volume_up'" />
        </button>
        <input
          type="range" min="0" max="1" step="0.01"
          :value="currentVolume"
          class="vp-slider vp-ab-volume-slider"
          :style="volumeSliderStyle"
          @input="handleSetVolume($event.target.value)"
        />
      </div>
      <!-- 右侧：辅助控制 -->
      <div class="vp-aux-controls">
        <button class="vp-btn" @click="openSettings" title="设置">
          <SvgIcon name="setting" size="20px" />
        </button>
        <button class="vp-btn" @click="handleDownload" title="下载">
          <SvgIcon name="download" size="20px" />
        </button>
      </div>
    </div>

    <!-- 设置弹窗 -->
    <teleport to="body">
      <div v-if="settingsVisible" class="vp-settings-overlay" @click.self="settingsVisible = false">
        <div class="vp-settings-dialog">
          <div class="vp-settings-header">
            <span class="vp-settings-title">播放设置</span>
            <button class="vp-settings-close" @click="settingsVisible = false">✕</button>
          </div>
          <div class="vp-settings-body">
            <!-- 播放倍数 -->
            <div class="vp-settings-row">
              <label class="vp-settings-label">播放倍数</label>
              <el-select v-model="draftSettings.speed" class="vp-settings-select">
                <el-option v-for="s in SPEED_OPTIONS" :key="s" :label="`${s}x`" :value="s" />
              </el-select>
            </div>
            <!-- 快进/后退秒数 -->
            <div class="vp-settings-row">
              <label class="vp-settings-label">快进 / 后退秒数（秒）</label>
              <el-input-number
                v-model="draftSettings.seekStep"
                :min="1"
                :max="60"
                :step="1"
                controls-position="right"
                class="vp-settings-input-number"
              />
            </div>
            <!-- 播放模式 -->
            <div class="vp-settings-row">
              <label class="vp-settings-label">播放模式</label>
              <el-select v-model="draftSettings.playMode" class="vp-settings-select">
                <el-option label="单条播放" value="single" />
                <el-option label="顺序播放" value="sequence" />
              </el-select>
            </div>
            <!-- 主题 -->
            <div class="vp-settings-row">
              <label class="vp-settings-label">主题</label>
              <el-select v-model="draftSettings.theme" class="vp-settings-select">
                <el-option label="亮色" value="light" />
                <el-option label="深色" value="dark" />
              </el-select>
            </div>
          </div>
          <div class="vp-settings-footer">
            <button class="vp-settings-btn vp-settings-btn--cancel" @click="settingsVisible = false">取消</button>
            <button class="vp-settings-btn vp-settings-btn--confirm" @click="applySettings">确认</button>
          </div>
        </div>
      </div>
    </teleport>

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

          <span class="vp-time">
            {{ formatTime(track.state.currentTime) }} / {{ formatTime(track.state.duration) }}
          </span>

          <button class="vp-btn" @click="toggleMute(track)" :title="track.state.isMuted ? '取消静音' : '静音'">
            <SvgIcon :name="track.state.isMuted ? 'volume_off' : 'volume_up'" size="20px" />
          </button>
          <button class="vp-btn" @click="downloadAudio(track)" title="下载音频">
            <SvgIcon name="download" size="20px" />
          </button>
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
const SPEED_OPTIONS = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]

// ── 设置弹窗 ────────────────────────────────────────────────────────────────
const settingsVisible = ref(false)
const seekStep = ref(5)
const playMode = ref('single')
const theme = ref('light')

const DARK_THEME = {
  '--vp-bg': '#0f172a',
  '--vp-border-color': '#312e81',
  '--vp-progress-color': '#a5b4fc',
  '--vp-cursor-color': '#c7d2fe',
  '--vp-region-color': 'rgba(165,180,252,0.2)',
  '--vp-btn-color': '#a5b4fc',
  '--vp-btn-hover-bg': '#1e1b4b',
  '--vp-label-color': '#e0e7ff',
  '--vp-time-color': '#94a3b8',
  '--vp-slider-color': '#a5b4fc',
  '--vp-bookmark-color': '#fbbf24',
  '--vp-progress-bar-color': '#a5b4fc',
}

const draftSettings = reactive({
  speed: 1,
  seekStep: 5,
  playMode: 'single',
  theme: 'light',
})

function openSettings() {
  draftSettings.speed = currentSpeed.value
  draftSettings.seekStep = seekStep.value
  draftSettings.playMode = playMode.value
  draftSettings.theme = theme.value
  settingsVisible.value = true
}

function applySettings() {
  // 应用播放倍数
  if (props.trackB) {
    abSpeed.value = draftSettings.speed
    for (const track of tracks.value) {
      track.state.speed = draftSettings.speed
      track.state.ws?.setPlaybackRate(draftSettings.speed)
    }
  } else {
    stateA.speed = draftSettings.speed
    stateA.ws?.setPlaybackRate(draftSettings.speed)
  }
  // 应用快进/后退秒数
  seekStep.value = draftSettings.seekStep || 5
  // 应用播放模式
  playMode.value = draftSettings.playMode
  // 应用主题
  theme.value = draftSettings.theme
  if (rootEl.value) {
    const vars = draftSettings.theme === 'dark' ? DARK_THEME : {}
    // 清除旧变量
    Object.keys(DARK_THEME).forEach(k => rootEl.value.style.removeProperty(k))
    Object.entries(vars).forEach(([k, v]) => rootEl.value.style.setProperty(k, v))
  }
  settingsVisible.value = false
}

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
    ws: null,
    regions: null,
    skipSilencePlugin: null,
    objectUrl: null,
    toolbar: { visible: false, left: 0, region: null },
    regionEnded: false,
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
const wrapRefs = {}

function setWaveRef(el, id) { if (el) waveRefs[id] = el }
function setWrapRef(el, id) { if (el) wrapRefs[id] = el }

// ── 选区颜色（按轨道 ID） ──────────────────────────────────────────────
function regionColor(trackId) {
  if (props.trackB) return trackId === 'A' ? 'rgba(44,145,228,0.1)' : 'rgba(15,171,157,0.1)'
  return rootEl.value
    ? getComputedStyle(rootEl.value).getPropertyValue('--vp-region-color').trim() || 'rgba(99,102,241,0.15)'
    : 'rgba(99,102,241,0.15)'
}

// ── WaveSurfer 初始化 ──────────────────────────────────────────────────
async function initWaveSurfer(track) {
  const { config, state } = track
  const waveContainer = waveRefs[track.id]
  if (!waveContainer) return

  const opt = props.options || {}

  // ── 构建插件列表 ────────────────────────────────────────────────────
  const regions = RegionsPlugin.create()
  const plugins = [regions]

  // SkipSilencePlugin not available in wavesurfer.js 7.x — handled in Task 6
  const skipSilencePlugin = null

  // ── 创建 WaveSurfer 实例 ────────────────────────────────────────────
  const ws = WaveSurfer.create({
    container: waveContainer,
    waveColor: opt.waveColor || (props.trackB
      ? (track.id === 'A' ? '#bfdef7' : '#b7e6e1')
      : (rootEl.value ? getComputedStyle(rootEl.value).getPropertyValue('--vp-wave-color').trim() : '') || '#bfdef7'),
    progressColor: opt.progressColor || (props.trackB
      ? (track.id === 'A' ? '#2c91e4' : '#0fab9d')
      : (rootEl.value ? getComputedStyle(rootEl.value).getPropertyValue('--vp-progress-color').trim() : '') || '#6366f1'),
    cursorColor: opt.cursorColor || (props.trackB
      ? (track.id === 'A' ? '#2c91e4' : '#0fab9d')
      : (rootEl.value ? getComputedStyle(rootEl.value).getPropertyValue('--vp-cursor-color').trim() : '') || '#4f46e5'),
    height: opt.height ?? 'auto',
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

  // ── 滚轮缩放（上滚放大，下滚缩小；双击恢复原比例，同步所有轨道）────
  waveContainer.addEventListener('wheel', (e) => {
    e.preventDefault()
    const delta = e.deltaY > 0 ? -10 : 10
    const newZoom = Math.max(1, Math.min(200, (state.zoom ?? 1) + delta))
    for (const t of tracks.value) {
      t.state.zoom = newZoom
      t.state.ws?.zoom(newZoom)
    }
  }, { passive: false })

  waveContainer.addEventListener('dblclick', (e) => {
    if (state.zoom > 1) {
      e.stopImmediatePropagation()
      for (const t of tracks.value) {
        t.state.zoom = 1
        t.state.ws?.zoom(1)
      }
    }
  })



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
      color: regionColor(track.id),
    })
    // region-initialized：拖拽开始时元素刚创建，此时清除 handle border
    state.regions.on('region-initialized', (region) => {
      if (region.element) {
        region.element.querySelectorAll('[part~="region-handle-left"],[part~="region-handle-right"]')
          .forEach(el => { el.style.borderLeft = 'none'; el.style.borderRight = 'none' })
      }
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

  // currentTime 节流：每 250ms 才更新响应式状态，避免高频触发 Vue 重渲染
  let _lastTimeUpdate = 0
  ws.on('timeupdate', (time) => {
    // 边界检测与静音跳过用局部时间，不依赖响应式
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
          state.regionEnded = true
          setTimeout(() => { _regionEndLock[track.id] = false }, 200)
        }
      }
    }

    // 节流：250ms 更新一次显示用的响应式 currentTime
    const now = Date.now()
    if (now - _lastTimeUpdate >= 250) {
      _lastTimeUpdate = now
      state.currentTime = time
    }
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

// ── 顶部控制栏统一 computed ────────────────────────────────────────────────
const isPlayingAll = computed(() =>
  props.trackB ? bothPlaying.value : stateA.isPlaying
)
const isAllMuted = computed(() =>
  props.trackB ? bothMuted.value : stateA.isMuted
)
const currentVolume = computed(() =>
  props.trackB ? (isAllMuted.value ? 0 : abVolume.value)
               : (stateA.isMuted ? 0 : stateA.volume)
)
const currentSpeed = computed(() =>
  props.trackB ? abSpeed.value : stateA.speed
)

const volumeSliderStyle = computed(() => {
  const pct = Math.round(currentVolume.value * 100)
  return {
    background: `linear-gradient(to right, var(--vp-slider-color) ${pct}%, var(--vp-border-color) ${pct}%)`,
  }
})

// ── 顶部控制栏操作函数 ────────────────────────────────────────────────────
function handlePlayPause() {
  if (props.trackB) togglePlayBoth()
  else togglePlay(tracks.value[0])
}

function handleRewind() {
  for (const track of tracks.value) {
    if (!track.state.ws) continue
    track.state.ws.setTime(Math.max(0, track.state.currentTime - seekStep.value))
  }
}

function handleForward() {
  for (const track of tracks.value) {
    if (!track.state.ws) continue
    track.state.ws.setTime(Math.min(track.state.duration, track.state.currentTime + seekStep.value))
  }
}

function handlePrev() {
  for (const track of tracks.value) {
    track.state.ws?.setTime(0)
  }
}

function handleNext() {
  for (const track of tracks.value) {
    if (!track.state.ws) continue
    track.state.ws.setTime(track.state.duration)
  }
}

function handleToggleMute() {
  if (props.trackB) toggleMuteBoth()
  else toggleMute(tracks.value[0])
}

function handleSetVolume(val) {
  if (props.trackB) setVolumeBoth(val)
  else setVolume(tracks.value[0], val)
}

function handleCycleSpeed() {
  if (props.trackB) cycleSpeedBoth()
  else cycleSpeed(tracks.value[0])
}

function handleExport() {
  if (props.trackB) exportReportBoth()
  else exportReport(tracks.value[0])
}

function handleDownload() {
  if (props.trackB) downloadBoth()
  else downloadAudio(tracks.value[0])
}

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
  if (playing) {
    for (const track of tracks.value) {
      if (!track.state.ws || !track.state.isPlaying) continue
      track.state.ws.pause()
      track.state.isPlaying = false
    }
    return
  }

  // 计算两轨共同起始位置
  const refTrack = tracks.value[0]
  let startTime = 0
  if (refTrack?.state.ws) {
    const isEnded = refTrack.state.ws.getMediaElement()?.ended ?? false
    const region = refTrack.state.toolbar.region
    if (isEnded || refTrack.state.regionEnded) {
      // 自然结束或区域边界触发暂停：回到区域起点（或头部）
      startTime = region ? region.start : 0
    } else {
      startTime = refTrack.state.currentTime
      if (region && startTime >= region.end) startTime = region.start
    }
  }

  for (const track of tracks.value) {
    if (!track.state.ws || track.state.isPlaying) continue
    if (track.state.skipSilence && !track.config?.silences && !analyserNodes[track.id]) {
      startSilenceDetection(track)
    }
    track.state.regionEnded = false
    _regionEndLock[track.id] = false
    // 在同一同步帧内完成 setTime + play，确保 play 调用时 media.currentTime 已就位
    track.state.ws.setTime(startTime)
    track.state.ws.play()
    track.state.isPlaying = true
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
  const ended = track.state.ws.getMediaElement()?.ended ?? false
  const atEnd = track.state.duration > 0 && track.state.currentTime >= track.state.duration - 0.1
  const region = track.state.toolbar.region
  let startTime = track.state.currentTime
  if (region) {
    if (ended || track.state.regionEnded || track.state.currentTime >= region.end) {
      startTime = region.start
    }
    track.state.regionEnded = false
    _regionEndLock[track.id] = false
  } else if (ended || atEnd) {
    startTime = 0
  }
  track.state.ws.setTime(startTime)
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
    color: regionColor(otherState.id),
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

<style lang="scss" scoped>
button { cursor: pointer !important; }

/* ── CSS 变量默认值 ────────────────────────────────────────────────────── */
.voice-player {
  --vp-bg: #ffffff;
  --vp-border-color: #e0e7ff;
  --vp-wave-color: #818cf8;
  --vp-progress-color: #6366f1;
  --vp-cursor-color: #4f46e5;
  --vp-region-color: rgba(99, 102, 241, 0.15);
  --vp-btn-color: #6366f1;
  --vp-btn-hover-bg: #eef2ff;
  --vp-label-color: #374151;
  --vp-time-color: #6b7280;
  --vp-slider-color: #6366f1;
  --vp-radius: 8px;
  --vp-bookmark-color: #f59e0b;
  --vp-error-color: #ef4444;
  --vp-progress-bar-color: #6366f1;

  background: var(--vp-bg);
  border-radius: var(--vp-radius);
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  font-family: system-ui, sans-serif;
  height: 400px;
  overflow: hidden;
}

/* ── 顶部控制栏 ──────────────────────────────────────────────────────── */
.vp-control-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.vp-playback-controls {
  display: flex;
  align-items: center;
  gap: 4px;

  .vp-btn {
    font-size: 35px;
    padding: 4px 1px;
    height: 43px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .vp-volume-btn {
    font-size: 25px;
  }
}

.vp-aux-controls {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.vp-ab-volume-slider { width: 90px; }

/* ── 双轨模式包裹层 & 轨道 ───────────────────────────────────────────── */
.vp-tracks-dual {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
}

.vp-track {
  border: 1px solid var(--vp-border-color);
  border-radius: calc(var(--vp-radius) - 2px);
  display: flex;
  flex-direction: column;
  gap: 8px;
  outline: none;
  flex: 1;
  min-height: 0;
  overflow: hidden;

  &:focus-within { border-color: var(--vp-btn-color); }

  /* 双轨模式：轨道无边框 */
  &--dual {
    border: none;
    border-radius: 0;
  }
}

/* ── 头部 ────────────────────────────────────────────────────────────── */
.vp-track-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 20px;
}

.vp-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--vp-label-color);
}

.vp-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.vp-loading-text {
  font-size: 12px;
  color: var(--vp-time-color);
}

.vp-error-text {
  font-size: 12px;
  color: var(--vp-error-color);
  display: flex;
  align-items: center;
  gap: 6px;
}

.vp-retry-btn {
  font-size: 11px;
  padding: 2px 6px;
}

/* ── 加载进度条 ───────────────────────────────────────────────────────── */
.vp-load-progress {
  height: 4px;
  background: var(--vp-border-color);
  border-radius: 2px;
  overflow: hidden;

  &-fill {
    height: 100%;
    background: var(--vp-progress-bar-color);
    transition: width 0.2s;
  }
}

/* ── 波形区域 ────────────────────────────────────────────────────────── */
.vp-waveform {
  &-wrap {
    position: relative;
    cursor: pointer;
    overflow: hidden;
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  &-top {
    width: 100%;
    height: 100%;
    overflow: hidden;
  }
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
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  z-index: 20;
  white-space: nowrap;

  button {
    background: none;
    border: none;
    color: var(--vp-btn-color);
    cursor: pointer;
    font-size: 13px;
    padding: 2px 5px;
    border-radius: 4px;
    line-height: 1.4;
  }
}

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

  &-line {
    width: 2px;
    height: 100%;
    background: var(--vp-bookmark-color);
    margin: 0 auto;
  }

  &-label {
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

  &:hover .vp-bookmark-label { opacity: 1; }
}

/* ── 通用按钮 ────────────────────────────────────────────────────────── */
.vp-btn {
  background: none;
  border: 1px solid transparent;
  border-radius: 6px;
  color: var(--vp-btn-color);
  cursor: pointer;
  font-size: 15px;
  line-height: 1;
  transition: background 0.15s;
  white-space: nowrap;

  &--active { background: var(--vp-btn-hover-bg); border-color: var(--vp-btn-color); }
}

.vp-speed-btn {
  font-size: 12px;
  font-weight: 600;
  min-width: 36px;
}

/* ── 时间 ────────────────────────────────────────────────────────────── */
.vp-time {
  font-size: 13px;
  color: var(--vp-time-color);
  font-variant-numeric: tabular-nums;
  min-width: 90px;
  cursor: pointer;
  user-select: none;

}

/* ── 滑块 ────────────────────────────────────────────────────────────── */
.vp-slider {
  -webkit-appearance: none;
  appearance: none;
  height: 4px;
  border-radius: 2px;
  background: var(--vp-border-color);
  outline: none;
  cursor: pointer;

  &::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--vp-slider-color);
    cursor: pointer;
  }
}

.vp-volume-slider { width: 70px; }

/* ── 设置弹窗 ────────────────────────────────────────────────────────────── */
.vp-settings-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.vp-settings-dialog {
  background: #fff;
  border-radius: 12px;
  width: 360px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.18);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.vp-settings-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px 12px;
  border-bottom: 1px solid #e0e7ff;
}

.vp-settings-title {
  font-size: 15px;
  font-weight: 600;
  color: #111827;
}

.vp-settings-close {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  color: #6b7280;
  padding: 2px 6px;
  border-radius: 4px;
}

.vp-settings-body {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.vp-settings-row {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.vp-settings-label {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}

.vp-settings-select {
  width: 100%;
}

.vp-settings-input-number {
  width: 100%;
}

.vp-settings-input-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.vp-settings-input {
  width: 80px;
  padding: 6px 10px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  color: #111827;
  outline: none;

  &:focus { border-color: #6366f1; }
}

.vp-settings-unit {
  font-size: 13px;
  color: #6b7280;
}

.vp-settings-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 12px 20px 16px;
  border-top: 1px solid #e0e7ff;
}

.vp-settings-btn {
  padding: 7px 20px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: background 0.15s;

  &--cancel {
    background: #f3f4f6;
    color: #374151;
    border-color: #d1d5db;

  }

  &--confirm {
    background: #6366f1;
    color: #fff;
  }
}
</style>
