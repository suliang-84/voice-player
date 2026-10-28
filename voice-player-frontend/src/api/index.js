// src/api/index.js
import http from './request'
import { getToken } from './auth'

const audio = (id) => `/audios/${encodeURIComponent(id)}`
const params = (p) => ({ params: p })

// 音频流：按轨道返回单声道 WAV，支持 Range
// <audio> 无法携带 Authorization 头，token 通过 query 传递
export const streamUrl = (audioId, track) => {
  const token = getToken()
  return `${http.defaults.baseURL}${audio(audioId)}/stream?track=${track}${token ? `&token=${encodeURIComponent(token)}` : ''}`
}

// 后端每次都重新下载并推理，耗时较长，放宽超时
const SLOW = { timeout: 120000 }
const slow = (p) => ({ ...SLOW, ...params(p) })

export const getPeaks = (audioId, query) => http.get(`${audio(audioId)}/peaks`, slow(query))
export const getSilences = (audioId, query) => http.get(`${audio(audioId)}/silences`, slow(query))
export const getTranscripts = (audioId, query) => http.get(`${audio(audioId)}/transcripts`, slow(query))
export const getTranslations = (audioId, query) => http.get(`${audio(audioId)}/translations`, slow(query))
export const getSpeakers = (audioId) => http.get(`${audio(audioId)}/speakers`, SLOW)
export const getScenes = (audioId) => http.get(`${audio(audioId)}/scenes`, SLOW)

export const updateTranscriptText = (id, body) =>
  http.put(`/transcripts/${encodeURIComponent(id)}/text`, body)
export const updateTranslation = (id, body) =>
  http.put(`/translations/${encodeURIComponent(id)}`, body)

export const getUserSettings = () => http.get('/users/settings')
export const updateUserSettings = (body) => http.put('/users/settings', body)

export { ApiError } from './request'
export { configureAuth } from './auth'
