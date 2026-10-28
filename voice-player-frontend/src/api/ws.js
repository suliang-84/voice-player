// src/api/ws.js
// 订阅 WebSocket 事件；断线后指数退避重连。未配置 VITE_WS_URL 时不连接。
import { getToken } from './auth'

export function connectWs(onMessage) {
  const base = import.meta.env.VITE_WS_URL
  if (!base) return () => {}

  let ws = null
  let closed = false
  let retry = 0
  let timer = null

  function open() {
    ws = new WebSocket(`${base}?token=${encodeURIComponent(getToken())}`)
    ws.onopen = () => { retry = 0 }
    ws.onmessage = (e) => {
      try { onMessage(JSON.parse(e.data)) } catch { /* 忽略非 JSON 消息 */ }
    }
    ws.onclose = () => {
      if (closed) return
      timer = setTimeout(open, Math.min(30000, 1000 * 2 ** retry++))
    }
    ws.onerror = () => ws.close()
  }
  open()

  return () => {
    closed = true
    clearTimeout(timer)
    ws?.close()
  }
}
