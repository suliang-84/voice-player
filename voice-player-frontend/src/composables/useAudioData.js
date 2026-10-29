// src/composables/useAudioData.js
// 按 audioId 拉取波形、静音、转写、译文、说话人、场景；各接口独立容错。
import { reactive, computed, watch, onBeforeUnmount } from 'vue'
import * as api from '../api'
import { connectWs } from '../api/ws'
import { normalizePeaks } from '../api/peaks'

const POLL_INTERVAL = 5000
const TASK_NOT_DONE = 40002

export function useAudioData(getAudioId, { onPeaksGenerated } = {}) {
  const state = reactive({
    peaks: null,            // { duration, tracks: { A: {peaks}, B: {peaks} } }
    skipRanges: [],         // 两路同时静音、可跳过的区间 [{start,end}]
    activeRanges: [],       // 与之互补的有声部分 [{start,end}]，用于在波形上标记
    transcriptStatus: '',   // completed | processing | failed | ''
    transcriptProgress: 0,
    transcriptItems: [],
    translationItems: [],
    speakers: [],
    scenes: null,
    errors: {},
  })

  const setError = (key, err) => { state.errors[key] = err?.message || '加载失败' }
  const clearError = (key) => { delete state.errors[key] }

  async function loadPeaks() {
    try {
      const id = getAudioId()
      const data = await api.getPeaks(id)
      if (id !== getAudioId()) return  // 已切换到别的音频，丢弃过期结果
      state.peaks = data
      clearError('peaks')
    } catch (e) { setError('peaks', e) }
  }

  async function loadSilences() {
    try {
      const id = getAudioId()
      const data = await api.getSilences(id)
      if (id !== getAudioId()) return
      state.skipRanges = data.both?.silences || []
      state.activeRanges = data.both?.activeSegments || []
      clearError('silences')
    } catch (e) { setError('silences', e) }
  }

  async function loadTranscripts() {
    try {
      const data = await api.getTranscripts(getAudioId())
      state.transcriptStatus = data.status
      state.transcriptItems = data.items || []
      if (data.status === 'failed') setError('transcripts', { message: data.error })
      else clearError('transcripts')
    } catch (e) {
      if (e.code === TASK_NOT_DONE) {
        state.transcriptStatus = 'processing'
        state.transcriptProgress = e.data?.progress ?? 0
      } else {
        state.transcriptStatus = 'failed'
        setError('transcripts', e)
      }
    }
  }

  async function loadTranslations() {
    try {
      const data = await api.getTranslations(getAudioId())
      state.translationItems = data.items || []
      clearError('translations')
    } catch (e) { setError('translations', e) }
  }

  async function loadSpeakers() {
    try {
      state.speakers = (await api.getSpeakers(getAudioId())).speakers || []
      clearError('speakers')
    } catch (e) { setError('speakers', e) }
  }

  async function loadScenes() {
    try {
      state.scenes = await api.getScenes(getAudioId())
      clearError('scenes')
    } catch (e) { setError('scenes', e) }
  }

  const loadTexts = () => Promise.all([loadTranscripts(), loadTranslations(), loadSpeakers()])

  // 渲染波形所需的数据：必须先于 WaveSurfer 创建
  const loadWaveData = () => Promise.all([loadPeaks(), loadSilences()])

  // 重置并加载播放所需的数据（波形、静音）。转写类数据与播放无关，由 loadDetails 单独加载，
  // 避免耗时的转写/译文请求与音频流抢占浏览器同一主机的并发连接
  function loadAll() {
    resetData()
    return loadWaveData()
  }

  // 转写、译文、说话人、场景：在音频就绪后再加载，失败或缓慢都不影响播放
  function loadDetails() {
    loadTexts()
    loadScenes()
  }

  function resetData() {
    state.peaks = null
    rejectedPeaks.clear()
    state.skipRanges = []
    state.activeRanges = []
    state.transcriptStatus = ''
    state.transcriptProgress = 0
    state.transcriptItems = []
    state.translationItems = []
    state.speakers = []
    state.scenes = null
    state.errors = {}
  }

  // 转写 + 译文合并为聊天面板条目
  const transcripts = computed(() => {
    const byTranscript = new Map(state.translationItems.map(t => [t.transcriptId, t]))
    return state.transcriptItems.map(item => {
      const tr = byTranscript.get(item.id)
      return { ...item, translation: tr?.text || '', translationId: tr?.id || null }
    })
  })

  const identities = computed(() => {
    const map = {}
    for (const s of state.speakers) {
      if (s.identity && s.identity !== 'unknown') map[s.trackId] = s.identity
    }
    return map
  })

  // 与音频实际时长不符的 peaks 会被拒绝，该轨道回退为浏览器解码
  const rejectedPeaks = new Set()
  const rejectPeaks = (trackId) => rejectedPeaks.add(trackId)

  function peaksOf(trackId) {
    const t = state.peaks?.tracks?.[trackId]
    if (!t || rejectedPeaks.has(trackId)) return null
    const peaks = normalizePeaks(t.peaks, t.pointCount)
    return peaks ? { peaks, duration: t.duration || state.peaks.duration } : null
  }

  // 编辑：用接口返回的完整片段更新本地列表
  async function editTranscript(item, text) {
    const res = await api.updateTranscriptText(item.id, { text })
    const target = state.transcriptItems.find(t => t.id === item.id)
    if (target) Object.assign(target, { text: res.text, startTime: res.startTime, endTime: res.endTime })
  }

  async function editTranslation(item, text) {
    const res = await api.updateTranslation(item.translationId, { text })
    const target = state.translationItems.find(t => t.id === item.translationId)
    if (target) target.text = res.text
  }

  // ── 异步任务通知：WebSocket；未配置时对处理中的转写做轮询兜底 ──────────────
  const disconnect = connectWs((msg) => {
    if (msg.audioId !== getAudioId()) return
    if (msg.type === 'transcription_progress') {
      state.transcriptStatus = msg.status
      state.transcriptProgress = msg.progress
    } else if (msg.type === 'transcription_completed') {
      loadTexts()
    } else if (msg.type === 'peaks_generated') {
      const hadPeaks = !!state.peaks
      loadPeaks().then(() => { if (!hadPeaks && state.peaks) onPeaksGenerated?.() })
    }
  })

  let pollTimer = null
  watch(() => state.transcriptStatus, (status) => {
    clearInterval(pollTimer)
    pollTimer = null
    if (status === 'processing' && !import.meta.env.VITE_WS_URL) {
      pollTimer = setInterval(loadTexts, POLL_INTERVAL)
    }
  })

  onBeforeUnmount(() => {
    disconnect()
    clearInterval(pollTimer)
  })

  return {
    state, transcripts, identities,
    loadAll, loadDetails, loadWaveData, peaksOf, rejectPeaks,
    editTranscript, editTranslation,
  }
}
