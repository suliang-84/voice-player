// scripts/mock-server.js
// 仅开发用：按接口设计说明书模拟后端，监听 10090（与 vite 默认代理一致）。
// 用法：node scripts/mock-server.js
import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const PORT = Number(process.env.PORT) || 10090
const PUBLIC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../public')
const DURATION = 1000

const settings = {
  playback: { defaultSpeed: 1, seekStep: 5, playMode: 'single', skipSilence: false },
  ui: { theme: 'light', chatPanelVisible: false },
}
const transcripts = [
  { id: 't1', trackId: 'A', startTime: 0.5, endTime: 3.2, text: '您好，请问是XX客服吗？', confidence: null },
  { id: 't2', trackId: 'B', startTime: 3.8, endTime: 6.1, text: '您好，是的，请问有什么可以帮您？', confidence: null },
  { id: 't3', trackId: 'A', startTime: 12, endTime: 16, text: '我的网络昨天开始一直断线。', confidence: null },
]
const translations = [
  { id: 'tr1', transcriptId: 't1', trackId: 'A', startTime: 0.5, endTime: 3.2, text: 'Hello, is this XX customer service?', confidence: null },
  { id: 'tr2', transcriptId: 't2', trackId: 'B', startTime: 3.8, endTime: 6.1, text: 'Hello, yes. How can I help you?', confidence: null },
]

const peaksOf = (seed, n = 600) =>
  [Array.from({ length: n }, (_, i) => {
    const gap = (i + seed * 7) % 90 > 70
    return gap ? 0 : +(Math.sin(i * 0.7 + seed) * (0.3 + 0.5 * Math.abs(Math.sin(i / 23)))).toFixed(2)
  })]

const sendJson = (res, data, code = 0, message = 'success') => {
  res.writeHead(200, { 'Content-Type': 'application/json' })
  res.end(JSON.stringify({ code, message, data, timestamp: Date.now() }))
}
const readBody = (req) => new Promise((resolve) => {
  let b = ''
  req.on('data', (c) => (b += c))
  req.on('end', () => resolve(b ? JSON.parse(b) : {}))
})

function stream(req, res, track) {
  const file = path.join(PUBLIC, track === 'B' ? 'demo-b.wav' : 'demo-a.wav')
  const { size } = fs.statSync(file)
  const m = /bytes=(\d*)-(\d*)/.exec(req.headers.range || '')
  const start = m && m[1] ? Number(m[1]) : 0
  const end = m && m[2] ? Number(m[2]) : size - 1
  res.writeHead(m ? 206 : 200, {
    'Content-Type': 'audio/wav',
    'Accept-Ranges': 'bytes',
    'Content-Length': end - start + 1,
    ...(m && { 'Content-Range': `bytes ${start}-${end}/${size}` }),
  })
  fs.createReadStream(file, { start, end }).pipe(res)
}

http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x')
  const p = url.pathname.replace(/^\/api\/v1/, '')
  let m
  if ((m = /^\/audios\/([^/]+)\/stream$/.exec(p))) return stream(req, res, url.searchParams.get('track'))
  if (/^\/audios\/[^/]+\/peaks$/.test(p)) {
    const track = (n) => ({ peaks: peaksOf(n), duration: DURATION, pointCount: 600 })
    return sendJson(res, { duration: DURATION, sampleRate: 16000, tracks: { A: track(1), B: track(2) }, generatedAt: new Date().toISOString() })
  }
  if (/^\/audios\/[^/]+\/silences$/.test(p)) {
    return sendJson(res, { tracks: { A: { silences: [{ start: 20, end: 25, duration: 5 }] }, B: { silences: [{ start: 18, end: 27, duration: 9 }] } } })
  }
  if (/^\/audios\/[^/]+\/transcripts$/.test(p)) return sendJson(res, { status: 'completed', language: 'zh-CN', items: transcripts })
  if (/^\/audios\/[^/]+\/translations$/.test(p)) return sendJson(res, { status: 'completed', targetLanguage: 'en', items: translations })
  if (/^\/audios\/[^/]+\/speakers$/.test(p)) {
    return sendJson(res, { speakers: [
      { trackId: 'A', identity: '客户', confidence: 0.9, role: 'customer' },
      { trackId: 'B', identity: null, confidence: null, role: 'customer' },
    ] })
  }
  if (/^\/audios\/[^/]+\/scenes$/.test(p)) {
    return sendJson(res, { scenes: [{ type: 'call_center', subType: 'technical_support', confidence: null, description: '技术支持客服通话', keywords: ['网络'] }], callType: 'unknown', callPurpose: null, callResolution: 'unknown', analysis: null })
  }
  if (p === '/users/settings' && req.method === 'GET') return sendJson(res, settings)
  if (p === '/users/settings' && req.method === 'PUT') {
    const b = await readBody(req)
    for (const k of ['playback', 'ui']) Object.assign(settings[k], b[k])
    return sendJson(res, { ...settings, updatedAt: new Date().toISOString() }, 0, '设置更新成功')
  }
  if ((m = /^\/transcripts\/([^/]+)\/text$/.exec(p)) && req.method === 'PUT') {
    const b = await readBody(req)
    const t = transcripts.find((x) => x.id === m[1])
    if (!t) return sendJson(res, null, 404, '资源不存在')
    t.text = b.text
    return sendJson(res, { ...t, updatedAt: new Date().toISOString() })
  }
  if ((m = /^\/translations\/([^/]+)$/.exec(p)) && req.method === 'PUT') {
    const b = await readBody(req)
    const t = translations.find((x) => x.id === m[1])
    if (!t) return sendJson(res, null, 404, '资源不存在')
    t.text = b.text
    return sendJson(res, { ...t, updatedAt: new Date().toISOString() })
  }
  sendJson(res, null, 404, '资源不存在')
}).listen(PORT, () => console.log(`mock server on http://localhost:${PORT}`))
