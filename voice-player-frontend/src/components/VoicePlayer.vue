<!-- src/components/VoicePlayer.vue -->
<template>
  <div class="voice-player" ref="rootEl">
    <!-- 顶部控制栏 -->
    <div class="vp-control-bar">
      <!-- 左侧：主播放控制 -->
      <div class="vp-playback-controls">
        <button class="vp-btn" @click="handlePrev" title="上一条"
          :disabled="!hasPrev" :class="{ 'vp-btn--disabled': !hasPrev }">
          <SvgIcon name="previous" />
        </button>
        <button class="vp-btn" @click="handleRewind" :title="`回退 ${seekStep} 秒`">
          <SvgIcon name="rewind" />
        </button>
        <button class="vp-btn vp-play-btn" @click="handlePlayPause" :title="isPlayingAll ? '暂停' : '播放'">
          <SvgIcon :name="isPlayingAll ? 'pause' : 'play'" />
        </button>
        <button class="vp-btn" @click="handleForward" :title="`快进 ${seekStep} 秒`">
          <SvgIcon name="forward" />
        </button>
        <button class="vp-btn" @click="handleNext" title="下一条"
          :disabled="!hasNext" :class="{ 'vp-btn--disabled': !hasNext }">
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
        <button class="vp-btn" :class="{ 'vp-btn--active': skipSilence }" @click="toggleSkipSilence"
          :title="skipSilence ? '跳过空音：已开启' : '跳过空音：已关闭'">
          <SvgIcon name="null" size="20px" />
        </button>
        <button v-if="props.trackB" class="vp-btn" :class="{ 'vp-btn--active': stereo }" @click="toggleStereo"
          :title="stereo ? '立体声：已开启（A 路左耳、B 路右耳）' : '立体声：已关闭（混声）'">
          <SvgIcon name="stereo" size="20px" />
        </button>
        <button class="vp-btn" @click="handleDownload"
          :title="props.trackB ? (stereo ? '下载（立体声合并）' : '下载（混声合并）') : '下载'">
          <SvgIcon name="download" size="20px" />
        </button>
        <button class="vp-btn" @click="toggleTheme" title="切换主题">
          <SvgIcon name="theme" size="20px" />
        </button>
        <button class="vp-btn" @click="sceneVisible = true" title="语音场景">
          <SvgIcon name="scene" size="20px" />
        </button>
        <button class="vp-btn" @click="toggleChat" title="转写内容">
          <SvgIcon name="chat" size="20px" />
        </button>
        <button class="vp-btn" @click="openSettings" title="设置">
          <SvgIcon name="setting" size="20px" />
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
          </div>
          <div class="vp-settings-footer">
            <button class="vp-settings-btn vp-settings-btn--cancel" @click="settingsVisible = false">取消</button>
            <button class="vp-settings-btn vp-settings-btn--confirm" @click="applySettings">确认</button>
          </div>
        </div>
      </div>
    </teleport>

    <!-- 轨道列表 + 聊天面板 -->
    <div class="vp-main-area">
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
        <span class="vp-label">
          <SvgIcon name="doubble_triangle" size="16px" :class="['vp-track-icon', `vp-track-icon--${track.id}`]" />
          {{ track.config.label || `${track.id}路` }}
          <span v-if="speakerIdentity(track.id)" class="vp-identity">（疑似{{ speakerIdentity(track.id) }}）</span>
        </span>
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
          <button @click="clearRegion(track)" title="清除选区">✕</button>
        </div>

        <!-- 上半波形（WaveSurfer 渲染） -->
        <div :ref="el => setWaveRef(el, track.id)" class="vp-waveform-top"></div>

      </div>

    </div>

    <!-- 统一滚动条（仅放大时显示，限制在波形区域内） -->
    <div v-if="unifiedScrollMax > 0" class="vp-unified-scroll">
      <input
        type="range"
        min="0"
        :max="unifiedScrollMax"
        step="1"
        :value="unifiedScrollLeft"
        class="vp-unified-scrollbar"
        @input="onUnifiedScroll($event.target.value)"
      />
    </div>

    </div><!-- end vp-tracks-dual wrapper -->

    <!-- 聊天面板 -->
    <transition name="vp-chat-slide">
      <div v-if="chatVisible" class="vp-chat-panel"
        ref="chatEl"
        @mouseenter="chatHovered = true"
        @mouseleave="chatHovered = false"
      >
        <div v-if="transcriptState.transcriptStatus === 'processing'" class="vp-chat-empty">
          转写中 {{ transcriptState.transcriptProgress }}%
        </div>
        <div v-else-if="transcriptState.transcriptStatus === 'failed'" class="vp-chat-empty">
          转写失败{{ transcriptState.errors.transcripts ? `：${transcriptState.errors.transcripts}` : '' }}
        </div>
        <div v-else-if="!chatItems.length" class="vp-chat-empty">暂无转写内容</div>
        <template v-else>
          <div
            v-for="(item, idx) in chatItems"
            :key="item.id"
            class="vp-chat-msg"
            :class="[`vp-chat-msg--${item.trackId}`, { 'vp-chat-msg--active': idx === activeTranscriptIdx }]"
            @dblclick="seekToTranscript(item)"
          >
            <SvgIcon :name="`admin_${item.trackId}`" size="24px" class="vp-chat-avatar" />
            <div class="vp-chat-bubble" @contextmenu.stop="onBubbleContextMenu($event, item)">
              <span class="vp-chat-text">{{ item.text }}</span>
              <template v-if="item.translation">
                <div class="vp-chat-divider"></div>
                <span class="vp-chat-translation">{{ item.translation }}</span>
              </template>
            </div>
          </div>
        </template>
      </div>
    </transition>

    </div><!-- end vp-main-area -->

  </div>

  <!-- 右键菜单 -->
  <teleport to="body">
    <div
      v-if="ctxMenu.visible"
      class="vp-ctx-menu"
      :style="{ top: ctxMenu.y + 'px', left: ctxMenu.x + 'px' }"
      @click.stop
    >
      <button class="vp-ctx-menu-item" @click="editTranscript">编辑转写内容</button>
      <button class="vp-ctx-menu-item" @click="editTranslation">编辑翻译内容</button>
    </div>
  </teleport>

  <!-- 编辑转写 / 翻译 -->
  <el-dialog
    v-model="editDialog.visible"
    :title="editDialog.kind === 'transcript' ? '编辑转写内容' : '编辑翻译内容'"
    width="480px"
    append-to-body
  >
    <el-input v-model="editDialog.text" type="textarea" :rows="5" />
    <template #footer>
      <el-button @click="editDialog.visible = false">取消</el-button>
      <el-button type="primary" :loading="editDialog.saving" @click="submitEdit">保存</el-button>
    </template>
  </el-dialog>

  <!-- 语音场景 -->
  <el-dialog v-model="sceneVisible" title="语音场景" width="520px" append-to-body>
    <div v-if="transcriptState.errors.scenes" class="vp-scene-empty">{{ transcriptState.errors.scenes }}</div>
    <div v-else-if="!transcriptState.scenes" class="vp-scene-empty">暂无场景数据</div>
    <template v-else>
      <div v-for="(sc, i) in transcriptState.scenes.scenes" :key="i" class="vp-scene-item">
        <div class="vp-scene-title">
          {{ sc.description || sc.type }}
          <span v-if="sc.confidence != null" class="vp-scene-conf">{{ Math.round(sc.confidence * 100) }}%</span>
        </div>
        <div v-if="sc.type || sc.subType" class="vp-scene-sub">{{ [sc.type, sc.subType].filter(Boolean).join(' / ') }}</div>
        <div v-if="sc.keywords?.length" class="vp-scene-tags">
          <el-tag v-for="k in sc.keywords" :key="k" size="small">{{ k }}</el-tag>
        </div>
      </div>
      <el-descriptions :column="1" size="small" border class="vp-scene-desc">
        <el-descriptions-item v-if="known(transcriptState.scenes.callType)" label="通话方向">{{ transcriptState.scenes.callType }}</el-descriptions-item>
        <el-descriptions-item v-if="known(transcriptState.scenes.callPurpose)" label="通话目的">{{ transcriptState.scenes.callPurpose }}</el-descriptions-item>
        <el-descriptions-item v-if="known(transcriptState.scenes.callResolution)" label="通话结果">{{ transcriptState.scenes.callResolution }}</el-descriptions-item>
        <template v-if="transcriptState.scenes.analysis">
          <el-descriptions-item label="投诉倾向">
            {{ transcriptState.scenes.analysis.hasComplaint ? '是' : '否' }}（{{ transcriptState.scenes.analysis.complaintScore }}）
          </el-descriptions-item>
          <el-descriptions-item label="表扬">{{ transcriptState.scenes.analysis.hasPraise ? '是' : '否' }}</el-descriptions-item>
          <el-descriptions-item label="已升级">{{ transcriptState.scenes.analysis.isEscalated ? '是' : '否' }}</el-descriptions-item>
        </template>
      </el-descriptions>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import WaveSurfer from 'wavesurfer.js'
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js'
import { ElMessage } from 'element-plus'
import { getUserSettings, updateUserSettings, streamUrl, downloadUrl } from '../api'
import { useAudioData } from '../composables/useAudioData'

// ── Props ──────────────────────────────────────────────────────────────────
const props = defineProps({
  audioId: { type: String, required: true },
  // 轨道配置：src / file / label。未提供 src 与 file 时，按 audioId 使用后端音频流接口
  trackA: { type: Object, default: () => ({}) },
  trackB: { type: Object, default: null },
  options: { type: Object, default: () => ({}) },
  hasPrev: { type: Boolean, default: false },
  hasNext: { type: Boolean, default: false },
})

const emit = defineEmits([
  'prev', 'next',
  // 波形
  'ready', 'load-progress', 'load-error',
  // 播放
  'play', 'pause', 'finish', 'timeupdate',
  // 交互
  'seek', 'volume-change', 'speed-change', 'zoom-change',
  // 选区
  'region-created', 'region-cleared',
])

// ── 后端数据 ───────────────────────────────────────────────────────────────
const audioData = useAudioData(() => props.audioId, {
  // 首次没有 peaks（后端仍在生成）时，波形生成完成后重新初始化
  onPeaksGenerated: () => { for (const track of tracks.value) retryLoad(track) },
})
const chatItems = audioData.transcripts
const transcriptState = audioData.state

const speakerIdentity = (trackId) => audioData.identities.value[trackId]

// ── 常量 ───────────────────────────────────────────────────────────────────
const SPEED_OPTIONS = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]

// ── 设置弹窗 ────────────────────────────────────────────────────────────────
const settingsVisible = ref(false)
const seekStep = ref(5)
const playMode = ref('single')
const theme = ref('light')
const skipSilence = ref(false)
const stereo = ref(false)  // false 混声（两路居中）；true 立体声（A 左 B 右）

const DARK_THEME = {
  '--vp-bg': '#0f172a',
  '--vp-control-bar-bg': '#1a2340',
  '--vp-border-color': '#312e81',
  '--vp-progress-color': '#a5b4fc',
  '--vp-cursor-color': '#c7d2fe',
  '--vp-region-color': 'rgba(123,156,239,0.2)',
  '--vp-btn-color': '#7b9cef',
  '--vp-btn-hover-bg': '#1e1b4b',
  '--vp-label-color': '#e0e7ff',
  '--vp-time-color': '#94a3b8',
  '--vp-slider-color': '#7b9cef',
  '--vp-progress-bar-color': '#a5b4fc',
}

const draftSettings = reactive({
  speed: 1,
  seekStep: 5,
  playMode: 'single',
  theme: 'light',
})

function applyTheme(name) {
  theme.value = name
  draftSettings.theme = name
  if (!rootEl.value) return
  const vars = name === 'dark' ? DARK_THEME : {}
  Object.keys(DARK_THEME).forEach(k => rootEl.value.style.removeProperty(k))
  Object.entries(vars).forEach(([k, v]) => rootEl.value.style.setProperty(k, v))
}

function applySpeed(speed) {
  if (props.trackB) abSpeed.value = speed
  for (const track of tracks.value) {
    track.state.speed = speed
    track.state.ws?.setPlaybackRate(speed)
  }
}

// ── 用户设置：服务端读取 / 保存 ────────────────────────────────────────────
// 修改后合并到 pending，防抖 300ms 后以部分更新（merge）提交
let _saveTimer = null
let _pending = {}

function saveSettings(patch) {
  for (const key of ['playback', 'ui']) {
    if (patch[key]) _pending[key] = { ..._pending[key], ...patch[key] }
  }
  clearTimeout(_saveTimer)
  _saveTimer = setTimeout(async () => {
    const body = _pending
    _pending = {}
    try {
      await updateUserSettings(body)
    } catch (e) {
      ElMessage.error(`设置保存失败：${e.message}`)
    }
  }, 300)
}

async function loadSettings() {
  try {
    const { playback = {}, ui = {} } = await getUserSettings()
    if (playback.defaultSpeed) applySpeed(playback.defaultSpeed)
    if (playback.seekStep) seekStep.value = playback.seekStep
    if (playback.playMode) playMode.value = playback.playMode
    if (playback.skipSilence != null) skipSilence.value = playback.skipSilence
    if (playback.stereo != null) stereo.value = playback.stereo
    if (ui.theme) applyTheme(ui.theme)
    if (ui.chatPanelVisible != null) chatVisible.value = ui.chatPanelVisible
  } catch (e) {
    ElMessage.warning(`用户设置加载失败，已使用默认值：${e.message}`)
  }
}

function toggleTheme() {
  const name = theme.value === 'light' ? 'dark' : 'light'
  applyTheme(name)
  saveSettings({ ui: { theme: name } })
}

function toggleChat() {
  chatVisible.value = !chatVisible.value
  saveSettings({ ui: { chatPanelVisible: chatVisible.value } })
}

function toggleSkipSilence() {
  skipSilence.value = !skipSilence.value
  saveSettings({ playback: { skipSilence: skipSilence.value } })
}

function toggleStereo() {
  stereo.value = !stereo.value
  saveSettings({ playback: { stereo: stereo.value } })
}

function openSettings() {
  draftSettings.speed = currentSpeed.value
  draftSettings.seekStep = seekStep.value
  draftSettings.playMode = playMode.value
  draftSettings.theme = theme.value
  settingsVisible.value = true
}

function applySettings() {
  applySpeed(draftSettings.speed)
  emit('speed-change', { speed: draftSettings.speed })
  seekStep.value = draftSettings.seekStep || 5
  playMode.value = draftSettings.playMode
  applyTheme(draftSettings.theme)
  settingsVisible.value = false
  saveSettings({
    playback: { defaultSpeed: draftSettings.speed, seekStep: seekStep.value, playMode: playMode.value },
    ui: { theme: draftSettings.theme },
  })
}

// ── 根元素 ref ─────────────────────────────────────────────────────────────
const rootEl = ref(null)

// ── 聊天面板 ────────────────────────────────────────────────────────────────
const chatVisible = ref(false)
const chatHovered = ref(false)
const chatEl = ref(null)

// ── 右键菜单 ─────────────────────────────────────────────────────────────────
const ctxMenu = reactive({ visible: false, x: 0, y: 0, item: null })

function onBubbleContextMenu(e, item) {
  e.preventDefault()
  ctxMenu.visible = true
  ctxMenu.x = e.clientX
  ctxMenu.y = e.clientY
  ctxMenu.item = item
}

function closeCtxMenu() {
  ctxMenu.visible = false
  ctxMenu.item = null
}

// 编辑转写 / 翻译：kind 为 'transcript' | 'translation'
const editDialog = reactive({ visible: false, kind: '', item: null, text: '', saving: false })

function openEdit(kind) {
  const item = ctxMenu.item
  closeCtxMenu()
  if (!item) return
  if (kind === 'translation' && !item.translationId) {
    ElMessage.warning('该条暂无译文，无法编辑')
    return
  }
  editDialog.kind = kind
  editDialog.item = item
  editDialog.text = kind === 'transcript' ? item.text : item.translation
  editDialog.visible = true
}

const editTranscript = () => openEdit('transcript')
const editTranslation = () => openEdit('translation')

async function submitEdit() {
  const text = editDialog.text.trim()
  if (!text) { ElMessage.warning('内容不能为空'); return }
  editDialog.saving = true
  try {
    if (editDialog.kind === 'transcript') await audioData.editTranscript(editDialog.item, text)
    else await audioData.editTranslation(editDialog.item, text)
    editDialog.visible = false
    ElMessage.success('保存成功')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    editDialog.saving = false
  }
}

// ── 场景弹窗 ───────────────────────────────────────────────────────────────
const sceneVisible = ref(false)
const known = (v) => !!v && v !== 'unknown'

onMounted(() => {
  window.addEventListener('click', closeCtxMenu)
  window.addEventListener('contextmenu', closeCtxMenu)
})

onBeforeUnmount(() => {
  window.removeEventListener('click', closeCtxMenu)
  window.removeEventListener('contextmenu', closeCtxMenu)
})

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
    duration: 0,       // 显示用真实时长，对齐后不变
    realDuration: 0,   // 音频文件实际时长
    volume: 1,
    isMuted: false,
    speed: 1,
    zoom: 1,
    loopEnabled: false,
    ws: null,
    regions: null,
    objectUrl: null,
    toolbar: { visible: false, left: 0, region: null },
    regionEnded: false,
  })
}

const stateA = createTrackState('A')
const stateB = createTrackState('B')

// ── 聊天面板 computed（依赖 stateA，必须在 stateA 声明后定义）────────────────
const activeTranscriptIdx = computed(() => {
  if (!chatItems.value.length) return -1
  const t = stateA.currentTime
  let idx = -1
  for (let i = 0; i < chatItems.value.length; i++) {
    if (chatItems.value[i].startTime <= t) idx = i
    else break
  }
  return idx
})

watch(activeTranscriptIdx, (idx) => {
  if (chatHovered.value || idx < 0 || !chatEl.value) return
  const el = chatEl.value.querySelectorAll('.vp-chat-msg')[idx]
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
})

function resolveConfig(id, cfg) {
  return cfg.src || cfg.file ? cfg : { ...cfg, src: streamUrl(props.audioId, id) }
}

const tracks = computed(() => {
  const result = [{ id: 'A', config: resolveConfig('A', props.trackA), state: stateA }]
  if (props.trackB) result.push({ id: 'B', config: resolveConfig('B', props.trackB), state: stateB })
  return result
})

// ── DOM refs ───────────────────────────────────────────────────────────────
const waveRefs = {}
const wrapRefs = {}

function setWaveRef(el, id) { if (el) waveRefs[id] = el }
function setWrapRef(el, id) { if (el) wrapRefs[id] = el }

// ── 统一滚动条 ──────────────────────────────────────────────────────────────
const unifiedScrollLeft = ref(0)
const unifiedScrollMax = ref(0)
let _scrollRaf = null

// ── 双轨时长对齐 ────────────────────────────────────────────────────────────
let _durationsAligned = false

async function alignDurations() {
  if (!props.trackB) return
  if (!stateA.realDuration || !stateB.realDuration) return  // 等两路都 ready
  if (_durationsAligned) return
  _durationsAligned = true

  const maxDur = Math.max(stateA.realDuration, stateB.realDuration)

  for (const track of tracks.value) {
    if (track.state.realDuration >= maxDur - 0.5) continue  // 跳过较长的轨道

    const ws = track.state.ws
    if (!ws) continue

    // 导出当前已渲染的峰值数据
    const exported = ws.exportPeaks({ channels: 1, maxLength: 8000, precision: 2 })
    const real = exported[0] || []
    const ratio = maxDur / track.state.realDuration
    const newLen = Math.ceil(real.length * ratio)

    // 补零：zeros 代表静音，WaveSurfer 会渲染为平线
    const padded = new Array(newLen).fill(0)
    for (let i = 0; i < real.length; i++) padded[i] = real[i]

    // 用新的峰值数据 + maxDuration 重渲染（不重新加载音频）
    const url = track.state.objectUrl || track.config.src || ''
    await ws.load(url, [padded], maxDur)

    // ── 关键修复 ────────────────────────────────────────────────────────────
    // WaveSurfer.getDuration() 优先返回 media.duration（真实音频时长），
    // 即使 ws.load() 传入了 maxDur，进度条依然用 realDuration 计算 → 不同步。
    // 通过 monkey-patch 强制返回 maxDur，使两路进度条以相同基准渲染。
    ws.getDuration = () => maxDur
  }
  // 对齐后时长基准变了，有声标记按新基准重画
  for (const track of tracks.value) renderActiveMarks(track)
}

// WaveSurfer v7 结构：waveRefs[id] → firstElementChild (shadow host) → shadowRoot → .scroll
function getWsScrollEl(trackId) {
  const container = waveRefs[trackId]
  if (!container) return null
  const shadowHost = container.firstElementChild
  if (!shadowHost?.shadowRoot) return null
  return shadowHost.shadowRoot.querySelector('.scroll') || null
}

function updateUnifiedScrollMax() {
  const el = getWsScrollEl('A') || getWsScrollEl('B')
  if (!el) return
  const max = el.scrollWidth - el.clientWidth
  unifiedScrollMax.value = Math.max(0, max)
}

function onUnifiedScroll(val) {
  const left = Number(val)
  unifiedScrollLeft.value = left
  for (const track of tracks.value) {
    track.state.ws?.setScroll(left)
  }
}

function startScrollSync() {
  if (_scrollRaf) return
  function tick() {
    // 优先用 DOM 读取 scrollWidth/clientWidth，计算最大滚动量
    const el = getWsScrollEl('A') || getWsScrollEl('B')
    if (el) {
      const max = el.scrollWidth - el.clientWidth
      if (unifiedScrollMax.value !== max) unifiedScrollMax.value = Math.max(0, max)
    }
    // 用 WaveSurfer API 读取当前滚动位置（更可靠）
    const ws = stateA.ws || stateB.ws
    if (ws) unifiedScrollLeft.value = ws.getScroll()
    _scrollRaf = requestAnimationFrame(tick)
  }
  _scrollRaf = requestAnimationFrame(tick)
}

function stopScrollSync() {
  if (_scrollRaf) { cancelAnimationFrame(_scrollRaf); _scrollRaf = null }
}

// ── 选区颜色（按轨道 ID） ──────────────────────────────────────────────
function regionColor(trackId) {
  if (props.trackB) return trackId === 'A' ? 'rgba(44,145,228,0.2)' : 'rgba(15,171,157,0.2)'
  return rootEl.value
    ? getComputedStyle(rootEl.value).getPropertyValue('--vp-region-color').trim() || 'rgba(69,98,189,0.2)'
    : 'rgba(69,98,189,0.2)'
}

// 倍数不超过 FIT_EPS 视为铺满（触控板的小幅滚动会累积出接近 1 的值，不能在单个事件里吸附回 1）
const FIT_EPS = 1.02

// 把"相对铺满的倍数"换算成 WaveSurfer 的 px/s：铺满 = 容器宽度 / 时长；视为铺满时传 0 恢复自适应
function applyZoom(factor) {
  const duration = props.trackB ? Math.max(stateA.realDuration, stateB.realDuration) : stateA.realDuration
  for (const t of tracks.value) {
    const width = waveRefs[t.id]?.clientWidth
    t.state.ws?.zoom(factor <= FIT_EPS || !duration || !width ? 0 : (width / duration) * factor)
    if (t.state.toolbar.region) updateToolbar(t, t.state.toolbar.region)
  }
}

// ── WaveSurfer 初始化 ──────────────────────────────────────────────────
async function initWaveSurfer(track) {
  const { config, state } = track
  const waveContainer = waveRefs[track.id]
  if (!waveContainer) return

  const opt = props.options || {}

  // 同一路不允许并存两个播放器，残留的旧实例先销毁
  if (state.ws) { state.ws.destroy(); state.ws = null }

  // ── 创建原生 audio 元素，交由浏览器流式播放，避免 WaveSurfer 完整下载解码 ──
  const url = config.file
    ? (state.objectUrl = URL.createObjectURL(config.file))
    : config.src
  const mediaEl = document.createElement('audio')
  mediaEl.crossOrigin = 'anonymous'  // 必须先于 src：立体声要用 WebAudio 处理，跨域音频没有 CORS 就只有静音
  mediaEl.src = url || ''
  mediaEl.preload = 'auto'

  // ── 构建插件列表 ────────────────────────────────────────────────────
  const regions = RegionsPlugin.create()
  const plugins = [regions]

  const pk = audioData.peaksOf(track.id)

  // peaks 时长与音频实际时长相差过大（如对应了别的文件）：放弃 peaks，回退为浏览器解码
  if (pk) {
    mediaEl.addEventListener('loadedmetadata', () => {
      if (Math.abs(mediaEl.duration - pk.duration) > 1) {
        console.warn(`[peaks] track ${track.id} 的 peaks 时长 ${pk.duration}s 与音频 ${mediaEl.duration}s 不符，已回退解码`)
        audioData.rejectPeaks(track.id)
        retryLoad(track)
      }
    }, { once: true })
  }

  // ── 创建 WaveSurfer 实例（传入 media，跳过内部 fetch+decode）────────
  const ws = WaveSurfer.create({
    container: waveContainer,
    media: mediaEl,
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
    barHeight: 0.8,
    normalize: true,
    interact: false,
    autoCenter: true,
    autoScroll: true,
    hideScrollbar: true,
    cursorWidth: 2,
    plugins,
    // 后端预计算的峰值：传入后不再由浏览器解码整个文件
    ...(pk && { peaks: pk.peaks, duration: pk.duration }),
  })

  state.ws = ws
  state.regions = regions
  wirePan(track)
  ws.setPlaybackRate(state.speed)  // 设置可能先于波形创建加载完成

  // ── 点击 seek（区分点击与拖拽：移动 < 5px 才 seek）─────────────────────
  let _mouseDownX = 0
  waveContainer.addEventListener('mousedown', (e) => { _mouseDownX = e.clientX })
  waveContainer.addEventListener('mouseup', (e) => {
    if (Math.abs(e.clientX - _mouseDownX) >= 5) return  // 拖拽，跳过 seek
    if (!state.realDuration) return
    const rect = waveContainer.getBoundingClientRect()
    // 放大时需要加上已滚动的偏移量，再除以总宽度，才能得到正确进度
    const clickX = e.clientX - rect.left
    const scrollEl = getWsScrollEl(track.id)
    const scrollLeft = scrollEl ? scrollEl.scrollLeft : 0
    const totalWidth = scrollEl ? scrollEl.scrollWidth : rect.width
    const progress = Math.max(0, Math.min(1, (scrollLeft + clickX) / totalWidth))
    // 用对齐后的最大时长计算绝对时间，确保两路 seek 基准一致
    const alignedDuration = props.trackB
      ? Math.max(stateA.realDuration, stateB.realDuration)
      : state.realDuration
    const newTime = progress * alignedDuration
    ws.seekTo(progress)
    emit('seek', { trackId: track.id, currentTime: newTime })
    // 用户主动 seek 时精确同步对方轨道
    if (props.trackB) {
      const other = track.id === 'A' ? stateB : stateA
      if (other.ws) other.ws.setTime(newTime)
    }
  })

  // ── 滚轮缩放（上滚放大，下滚缩小；双击恢复铺满，同步所有轨道）────
  // state.zoom 是相对"刚好铺满容器"的倍数：1 = 铺满，上限 maxZoom（默认 10，
  // 即 1000 秒的音频最多放大到屏幕显示约 100 秒）
  const maxZoom = Math.max(1, opt.maxZoom ?? 10)
  let _zoomTimer = null
  waveContainer.addEventListener('wheel', (e) => {
    e.preventDefault()
    // 按滚轮幅度连续缩放：鼠标一格 deltaY≈100 → 约 ×1.22，触控板的小幅滑动则平滑变化
    const dy = Math.max(-200, Math.min(200, e.deltaY))
    const newZoom = Math.max(1, Math.min(maxZoom, (state.zoom ?? 1) * Math.exp(-dy * 0.002)))
    for (const t of tracks.value) t.state.zoom = newZoom
    if (_zoomTimer) clearTimeout(_zoomTimer)
    _zoomTimer = setTimeout(() => {
      applyZoom(newZoom)
      emit('zoom-change', { zoom: newZoom })
      _zoomTimer = null
    }, 150)
  }, { passive: false })

  waveContainer.addEventListener('dblclick', (e) => {
    if (state.zoom > FIT_EPS) {
      e.stopImmediatePropagation()
      for (const t of tracks.value) t.state.zoom = 1
      applyZoom(1)
      emit('zoom-change', { zoom: 1 })
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
  // 使用 mediaEl 原生事件追踪缓冲进度（替代 ws loading 事件）
  const mediaEl = ws.getMediaElement()
  if (mediaEl) {
    mediaEl.addEventListener('progress', () => {
      if (mediaEl.duration && mediaEl.buffered.length) {
        const progress = Math.round(mediaEl.buffered.end(mediaEl.buffered.length - 1) / mediaEl.duration * 100)
        state.loadProgress = progress
        emit('load-progress', { trackId: track.id, progress })
      }
    })
    mediaEl.addEventListener('canplay', () => {
      state.isLoading = false
      state.loadProgress = 100
    })
    mediaEl.addEventListener('error', () => {
      state.isLoading = false
      state.loadError = '音频加载失败，请检查文件路径或网络'
      emit('load-error', { trackId: track.id, message: state.loadError })
    })
  }

  // 防止 alignDurations 触发的二次 ready 重复初始化事件监听
  let _wsReadyOnce = false

  ws.on('ready', () => {
    if (!_wsReadyOnce) {
      _wsReadyOnce = true

      // 记录真实音频时长（对齐后不再修改）
      state.realDuration = ws.getDuration()
      state.duration = state.realDuration
      state.isLoading = false
      state.loadProgress = 100
      state.loadError = null
      emit('ready', { trackId: track.id, duration: state.realDuration })

      // 始终启用拖拽选区
      state.regions.enableDragSelection({ color: regionColor(track.id) })

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
        if (!_syncingRegion) {
          syncRegionToOther(track, region)
          emit('region-created', { trackId: track.id, start: region.start, end: region.end })
        }
      })
      const unsubUpdated = state.regions.on('region-updated', (region) => {
        updateToolbar(track, region)
        syncRegionToOther(track, region)
      })
      const unsubRemoved = state.regions.on('region-removed', () => {
        if (_syncingRegion) return
        if (state.regions.getRegions().length === 0) {
          state.toolbar = { visible: false, left: 0, region: null }
        }
      })
      regionListeners[track.id] = [unsubCreated, unsubUpdated, unsubRemoved]
    }

    // 每次 ready（含对齐后触发的）都尝试对齐，_durationsAligned 保证只执行一次
    renderActiveMarks(track)
    alignDurations()
  })

  ws.on('finish', () => {
    state.isPlaying = false
    emit('finish', { trackId: track.id })
    // 顺序播放：以主轨结束为准，进入下一条
    if (playMode.value === 'sequence' && props.hasNext && track.id === tracks.value[0].id) {
      emit('next')
    }
  })

  // currentTime 节流：每 250ms 才更新响应式状态，避免高频触发 Vue 重渲染
  let _lastTimeUpdate = 0
  ws.on('timeupdate', (time) => {
    // 边界检测与静音跳过用局部时间，不依赖响应式
    // 跳过空音：由主轨驱动；落在联合静音区间（双轨即两路都静音）内就跳，并同步 seek
    if (skipSilence.value && track.id === tracks.value[0].id) {
      const target = findSkipTarget(time)
      if (target != null) {
        for (const t of tracks.value) t.state.ws?.setTime(target)
        return
      }
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
      emit('timeupdate', { trackId: track.id, currentTime: time, duration: state.realDuration })
    }
  })

  state.isLoading = true
  state.loadProgress = 0
}

// ── 空音查找 ────────────────────────────────────────────────────────────
// silences 按时间升序，二分查找包含 time 的区间
function findSilence(list, time) {
  let lo = 0, hi = list.length - 1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    const r = list[mid]
    if (time < r.start) hi = mid - 1
    else if (time >= r.end) lo = mid + 1
    else return r
  }
  return null
}

// 后端已按「A、B 两路同时低于阈值」算好联合静音区间（两端留有余量）：time 落在区间内就返回区间结束点
function findSkipTarget(time) {
  return findSilence(transcriptState.skipRanges, time)?.end ?? null
}

// ── 波形上标出有声（非静音）部分 ────────────────────────────────────────
// 色块画在 WaveSurfer 的 wrapper 里（随缩放、滚动一起走），位置用占总时长的百分比。
// WaveSurfer 在 shadow DOM 内，页面样式作用不到，所以全部用行内样式；z-index:-1 让色块垫在波形下面。
const ACTIVE_MARKS_ATTR = 'data-vp-active-marks'

function renderActiveMarks(track) {
  const ws = track.state.ws
  if (!ws) return
  const wrapper = ws.getWrapper()
  wrapper.querySelector(`[${ACTIVE_MARKS_ATTR}]`)?.remove()
  if (!skipSilence.value) return  // 只在开启「跳过空音」时显示
  // 双轨以对齐后的最大时长为基准，与 seek 的计算一致
  const duration = props.trackB ? Math.max(stateA.realDuration, stateB.realDuration) : track.state.realDuration
  const ranges = transcriptState.activeRanges
  if (!duration || !transcriptState.skipRanges.length) return
  const rgb = track.id === 'B' ? '15,171,157' : '44,145,228'
  const layer = document.createElement('div')
  layer.setAttribute(ACTIVE_MARKS_ATTR, '')
  layer.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:-1'
  for (const r of ranges) {
    const seg = document.createElement('div')
    seg.style.cssText = `position:absolute;top:0;bottom:0;left:${(r.start / duration) * 100}%;` +
      `width:${((r.end - r.start) / duration) * 100}%;background:rgba(${rgb},.12);border-bottom:3px solid rgba(${rgb},.5)`
    layer.appendChild(seg)
  }
  wrapper.appendChild(layer)
}

// ── 混声 / 立体声 ────────────────────────────────────────────────────────
// 混声：两路用原生 <audio> 播放，各自居中。立体声：A 路只进左耳、B 路只进右耳，要经 WebAudio 声像节点。
// createMediaElementSource 之后声音只走节点图，而 AudioContext 必须在用户操作后才会运行，
// 所以从未开启过立体声时不建图（保持原生播放）；建图和 resume 都放在用户操作里（点开关、点播放）。
let audioCtx = null
const panGraph = {}  // trackId → { media, source, panner }

function trackPan(id) { return stereo.value && props.trackB ? (id === 'A' ? -1 : 1) : 0 }

function wirePan(track) {
  const media = track.state.ws?.getMediaElement()
  if (!audioCtx || !media) return
  const old = panGraph[track.id]
  if (old?.media === media) {
    old.panner.pan.value = trackPan(track.id)
    return
  }
  old?.source.disconnect()
  old?.panner.disconnect()
  const source = audioCtx.createMediaElementSource(media)
  const panner = audioCtx.createStereoPanner()
  panner.pan.value = trackPan(track.id)
  source.connect(panner).connect(audioCtx.destination)
  panGraph[track.id] = { media, source, panner }
}

function resumeAudio() {
  if (audioCtx?.state === 'suspended') audioCtx.resume()
}

function applyStereo() {
  if (!audioCtx) {
    if (!stereo.value) return
    audioCtx = new AudioContext()
  }
  resumeAudio()
  for (const track of tracks.value) wirePan(track)
}
watch(stereo, applyStereo)

// 开关切换（含启动时从设置恢复）：标记随之显示或消失
watch(skipSilence, () => { for (const track of tracks.value) renderActiveMarks(track) })

// ── 重试加载 ─────────────────────────────────────────────────────────────
async function retryLoad(track) {
  if (!audioData.state.peaks) await audioData.loadWaveData()
  track.state.loadError = null
  track.state.ws?.destroy()
  track.state.ws = null
  await nextTick()
  await initWaveSurfer(track)
}

// ── 生命周期 ────────────────────────────────────────────────────────────
onMounted(async () => {
  await nextTick()
  // 波形/静音数据先于 WaveSurfer 创建；音频就绪后再加载转写、说话人、场景（与播放无关，不阻塞）
  loadSettings()
  await audioData.loadAll()
  for (const track of tracks.value) {
    await initWaveSurfer(track)
  }
  startScrollSync()
  audioData.loadDetails()
})

onBeforeUnmount(() => {
  audioCtx?.close()
  stopScrollSync()
  for (const track of tracks.value) {
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

// 切换音频（上一条/下一条）：重新拉取数据并重建 A/B 两路波形。
// switchSeq 防止连续点击时多次切换交叠执行；过期的切换在每个 await 之后直接放弃。
let switchSeq = 0
watch(() => props.audioId, async () => {
  const seq = ++switchSeq
  stopScrollSync()
  for (const track of tracks.value) {
    track.state.ws?.destroy()
    track.state.ws = null
    Object.assign(track.state, { currentTime: 0, duration: 0, realDuration: 0, isPlaying: false })
    track.state.toolbar = { visible: false, left: 0, region: null }
  }
  _durationsAligned = false
  await audioData.loadAll()
  await nextTick()
  if (seq !== switchSeq) return
  for (const track of tracks.value) {
    // 一路失败不能影响另一路
    try { await initWaveSurfer(track) } catch (e) { console.error(`[switch] track ${track.id} 初始化失败`, e) }
    if (seq !== switchSeq) return
  }
  startScrollSync()
  audioData.loadDetails()
})

// trackB 从无到有时初始化。切换音频时 trackB 对象也会变，但那由 audioId 的 watch 统一重建，这里不能插手
watch(() => props.trackB, async (newVal, oldVal) => {
  if (newVal && !oldVal && !stateB.ws) {
    await nextTick()
    await initWaveSurfer({ id: 'B', config: resolveConfig('B', newVal), state: stateB })
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
  const maxDur = props.trackB
    ? Math.max(stateA.realDuration, stateB.realDuration)
    : stateA.realDuration
  for (const track of tracks.value) {
    if (!track.state.ws) continue
    track.state.ws.setTime(Math.min(maxDur, track.state.currentTime + seekStep.value))
  }
}

function handlePrev() {
  if (props.hasPrev) {
    // 暂停当前播放
    for (const track of tracks.value) {
      if (track.state.isPlaying) {
        track.state.ws?.pause()
        track.state.isPlaying = false
      }
    }
    emit('prev')
  } else {
    // 没有上一条则回到开头
    for (const track of tracks.value) {
      track.state.ws?.setTime(0)
    }
  }
}

function handleNext() {
  if (props.hasNext) {
    // 暂停当前播放
    for (const track of tracks.value) {
      if (track.state.isPlaying) {
        track.state.ws?.pause()
        track.state.isPlaying = false
      }
    }
    emit('next')
  } else {
    // 没有下一条则跳到结尾
    for (const track of tracks.value) {
      if (!track.state.ws) continue
      track.state.ws.setTime(track.state.duration)
    }
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

// 有 audioId 且轨道没有用 src / file 覆盖时，下载交给后端（单路、合并、选区都在后端处理）；
// 否则（外部文件、本地文件）退回浏览器本地处理
function usesBackend(track) {
  const cfg = track.id === 'A' ? props.trackA : props.trackB
  return !(cfg?.src || cfg?.file)
}

function startDownload(url) {
  const a = document.createElement('a')
  a.href = url
  a.click()
}

// 顶部下载：双轨按当前模式合并（混声 → 单声道混音；立体声 → A 左 B 右）
function handleDownload() {
  if (!props.trackB) return downloadAudio(tracks.value[0])
  if (tracks.value.every(usesBackend)) {
    return startDownload(downloadUrl(props.audioId, { track: stereo.value ? 'stereo' : 'mix' }))
  }
  downloadBoth()
}

function setVolumeBoth(val) {
  const v = parseFloat(val)
  abVolume.value = v
  for (const track of tracks.value) {
    if (!track.state.ws) continue
    track.state.volume = v
    track.state.isMuted = v === 0
    emit('volume-change', { volume: v, muted: v === 0 })
    track.state.ws.setVolume(v)
  }
}

function togglePlayBoth() {
  resumeAudio()
  const playing = bothPlaying.value
  if (playing) {
    for (const track of tracks.value) {
      if (!track.state.ws || !track.state.isPlaying) continue
      track.state.ws.pause()
      track.state.isPlaying = false
      emit('pause', { trackId: track.id, currentTime: track.state.currentTime })
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
    track.state.regionEnded = false
    _regionEndLock[track.id] = false
    // 在同一同步帧内完成 setTime + play，确保 play 调用时 media.currentTime 已就位
    track.state.ws.setTime(startTime)
    track.state.ws.play()
    track.state.isPlaying = true
    emit('play', { trackId: track.id, currentTime: startTime })
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

function downloadBoth() {
  for (const track of tracks.value) {
    downloadAudio(track)
  }
}

// ── 播放控制 ────────────────────────────────────────────────────────────
function togglePlay(track) {
  resumeAudio()
  if (!track.state.ws) return
  if (track.state.isPlaying) {
    track.state.ws.pause()
    track.state.isPlaying = false
    emit('pause', { trackId: track.id, currentTime: track.state.currentTime })
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
  emit('play', { trackId: track.id, currentTime: startTime })
}

function setVolume(track, val) {
  const v = parseFloat(val)
  track.state.volume = v
  track.state.isMuted = v === 0
  track.state.ws?.setVolume(v)
  emit('volume-change', { volume: v, muted: v === 0 })
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

function downloadAudio(track) {
  if (usesBackend(track)) return startDownload(downloadUrl(props.audioId, { track: track.id }))
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

// ── 选区与浮动工具条 ─────────────────────────────────────────────────────

function updateToolbar(track, region) {
  const wrap = wrapRefs[track.id]
  if (!wrap) return
  const dur = track.state.duration || 1
  // 缩放时需用总滚动宽度和当前偏移量计算工具条的可见位置
  const scrollEl = getWsScrollEl(track.id)
  const totalWidth = scrollEl ? scrollEl.scrollWidth : wrap.getBoundingClientRect().width
  const scrollLeft = scrollEl ? scrollEl.scrollLeft : 0
  const startX = (region.start / dur) * totalWidth - scrollLeft
  const endX = (region.end / dur) * totalWidth - scrollLeft
  track.state.toolbar = {
    visible: true,
    left: startX + (endX - startX) / 2,
    region,
  }
}

async function downloadRegion(track) {
  const region = track.state.toolbar.region
  if (!region) return
  if (usesBackend(track)) {
    return startDownload(downloadUrl(props.audioId, { track: track.id, start: region.start, end: region.end }))
  }
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


function clearRegion(track) {
  track.state.regions.getRegions().forEach(r => r.remove())
  track.state.toolbar = { visible: false, left: 0, region: null }
  emit('region-cleared', { trackId: track.id })
  // 双轨模式同步清除对方选区
  if (props.trackB) {
    const otherState = track.id === 'A' ? stateB : stateA
    otherState.regions?.getRegions().forEach(r => r.remove())
    otherState.toolbar = { visible: false, left: 0, region: null }
    emit('region-cleared', { trackId: otherState.id })
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

// ── 转写内容双击定位 ────────────────────────────────────────────────────────
function seekToTranscript(item) {
  for (const track of tracks.value) {
    track.state.ws?.setTime(item.startTime)
  }
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

</script>

<style lang="scss" scoped>
button { cursor: pointer !important; }

/* ── CSS 变量默认值 ────────────────────────────────────────────────────── */
.voice-player {
  --vp-bg: #ffffff;
  --vp-control-bar-bg: #f6f7ff;
  --vp-border-color: #e0e7ff;
  --vp-wave-color: #818cf8;
  --vp-progress-color: #6366f1;
  --vp-cursor-color: #4f46e5;
  --vp-region-color: rgba(69, 98, 189, 0.2);
  --vp-btn-color: #4562bd;
  --vp-btn-hover-bg: #eef2ff;
  --vp-label-color: #374151;
  --vp-time-color: #6b7280;
  --vp-slider-color: #4562bd;
  --vp-radius: 8px;
  --vp-error-color: #ef4444;
  --vp-progress-bar-color: #6366f1;

  background: var(--vp-bg);
  border-radius: var(--vp-radius);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  padding: 0;
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
  background: var(--vp-control-bar-bg);
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
  margin-right: 10px;
}

.vp-ab-volume-slider { width: 90px; }

/* ── 双轨模式包裹层 & 轨道 ───────────────────────────────────────────── */
.vp-tracks-dual {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  padding: 5px 10px;
}

.vp-track {
  border: 1px solid var(--vp-border-color);
  border-radius: calc(var(--vp-radius) - 2px);
  display: flex;
  flex-direction: column;
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
  display: flex;
  align-items: center;
  gap: 4px;

  .vp-identity {
    font-weight: 400;
    font-size: 12px;
    color: var(--vp-time-color);
    margin-left: 2px;
  }
}

.vp-track-icon {
  transform: rotate(90deg);
  flex-shrink: 0;

  &--A { color: #2c91e4; }
  &--B { color: #0fab9d; }
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

  &--disabled {
    opacity: 0.3;
    cursor: not-allowed !important;
  }
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

/* ── 隐藏 WaveSurfer 每路自带滚动条 ─────────────────────────────────── */
:deep(.scroll) {
  overflow: hidden !important;
  scrollbar-width: none;
  &::-webkit-scrollbar { display: none; }
}

/* ── 主区域（波形 + 聊天并排） ───────────────────────────────────────── */
.vp-main-area {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* ── 聊天面板 ────────────────────────────────────────────────────────── */
.vp-chat-panel {
  width: 35%;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  border-left: 1px solid var(--vp-border-color);
  background: var(--vp-bg);
  padding: 12px 8px;
  gap: 10px;
  scrollbar-width: thin;

  &::-webkit-scrollbar { width: 4px; }
  &::-webkit-scrollbar-thumb { background: var(--vp-border-color); border-radius: 2px; }
}

.vp-chat-empty {
  text-align: center;
  color: var(--vp-time-color);
  font-size: 13px;
  margin-top: 20px;
}

.vp-chat-msg {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  cursor: pointer;
  user-select: none;

  // A路：左对齐（蓝色），头像在左
  &--A {
    justify-content: flex-start;
    .vp-chat-avatar { order: 0; }
    .vp-chat-bubble {
      order: 1;
      background: #d6eaf8;
      color: #1a5276;
      border-radius: 4px 4px 4px 4px;
    }
  }

  // B路：右对齐（绿色），头像在右
  &--B {
    justify-content: flex-end;
    .vp-chat-avatar { order: 1; }
    .vp-chat-bubble {
      order: 0;
      background: #d5f5e3;
      color: #1e8449;
      border-radius: 4px 4px 4px 4px;
    }
  }

  // 高亮当前播放条目：A路用蓝色，B路用绿色，文字白色
  &--active.vp-chat-msg--A .vp-chat-bubble {
    background: #2c91e4;
    color: #ffffff;
  }
  &--active.vp-chat-msg--B .vp-chat-bubble {
    background: #0fab9d;
    color: #ffffff;
  }
}

.vp-chat-avatar {
  flex-shrink: 0;
  align-self: flex-start;
  margin-top: 1px;
}

.vp-chat-bubble {
  position: relative;
  max-width: 75%;
  padding: 8px 12px;
  font-size: 13px;
  line-height: 1.5;
  word-break: break-all;
  transition: background 0.2s, color 0.2s;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.vp-chat-text {
  display: block;
}

.vp-chat-divider {
  height: 1px;
  background: currentColor;
  opacity: 0.2;
}

.vp-chat-translation {
  display: block;
  font-size: 12px;
  opacity: 0.75;
  font-style: italic;
}

.vp-chat-msg--A .vp-chat-bubble::before {
  content: '';
  position: absolute;
  top: 8px;
  left: -6px;
  border-width: 5px 6px 5px 0;
  border-style: solid;
  border-color: transparent #d6eaf8 transparent transparent;
}
.vp-chat-msg--active.vp-chat-msg--A .vp-chat-bubble::before {
  border-color: transparent #2c91e4 transparent transparent;
}

.vp-chat-msg--B .vp-chat-bubble::before {
  content: '';
  position: absolute;
  top: 8px;
  right: -6px;
  border-width: 5px 0 5px 6px;
  border-style: solid;
  border-color: transparent transparent transparent #d5f5e3;
}
.vp-chat-msg--active.vp-chat-msg--B .vp-chat-bubble::before {
  border-color: transparent transparent transparent #0fab9d;
}

// 聊天面板滑入动画
.vp-chat-slide-enter-active,
.vp-chat-slide-leave-active {
  transition: width 0.25s ease, opacity 0.25s ease;
  overflow: hidden;
}
.vp-chat-slide-enter-from,
.vp-chat-slide-leave-to {
  width: 0 !important;
  opacity: 0;
}

/* ── 统一滚动条 ──────────────────────────────────────────────────────── */
.vp-unified-scroll {
  padding: 4px 0 0;
}

.vp-unified-scrollbar {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 6px;
  border-radius: 3px;
  background: #f6f7ff;
  outline: none;
  cursor: pointer;
  display: block;

  &::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 40px;
    height: 6px;
    border-radius: 3px;
    background: var(--vp-slider-color);
    cursor: pointer;
  }

  &::-moz-range-thumb {
    width: 40px;
    height: 6px;
    border-radius: 3px;
    background: var(--vp-slider-color);
    cursor: pointer;
    border: none;
  }
}

/* ── 右键菜单 ────────────────────────────────────────────────────────────── */
:global(.vp-ctx-menu) {
  position: fixed;
  z-index: 9999;
  background: #ffffff;
  border: 1px solid #e0e7ff;
  border-radius: 6px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  padding: 4px 0;
  min-width: 140px;
  user-select: none;
}

:global(.vp-ctx-menu-item) {
  display: block;
  width: 100%;
  padding: 8px 16px;
  background: none;
  border: none;
  text-align: left;
  font-size: 13px;
  color: #374151;
  cursor: pointer;
  line-height: 1.4;

  &:hover {
    background: #f0f4ff;
    color: #4562bd;
  }
}

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

.vp-btn--active {
  background: var(--vp-btn-hover-bg, #eef2ff);
  border-radius: 4px;
}
.vp-scene-empty { text-align: center; color: #94a3b8; padding: 24px 0; }
.vp-scene-item { margin-bottom: 12px; }
.vp-scene-title { font-weight: 600; }
.vp-scene-conf { margin-left: 8px; font-weight: 400; color: #94a3b8; font-size: 12px; }
.vp-scene-sub { color: #94a3b8; font-size: 12px; margin: 2px 0 6px; }
.vp-scene-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.vp-scene-desc { margin-top: 12px; }
</style>
