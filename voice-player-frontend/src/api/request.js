// src/api/request.js
import axios from 'axios'
import { getToken, getRefreshHandler } from './auth'

export class ApiError extends Error {
  constructor(code, message, data) {
    super(message || '请求失败')
    this.code = code
    this.data = data ?? null
  }
}

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api/v1',
  timeout: 30000,
})

http.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  config.headers['X-Request-ID'] = crypto.randomUUID()
  return config
})

// 并发 401 共用一次刷新
let refreshing = null
async function refreshToken() {
  if (!refreshing) {
    const handler = getRefreshHandler()
    refreshing = (handler ? handler() : defaultRefresh()).finally(() => { refreshing = null })
  }
  return refreshing
}

async function defaultRefresh() {
  const res = await axios.post(`${http.defaults.baseURL}/auth/refresh`, null, {
    headers: { Authorization: `Bearer ${getToken()}` },
  })
  if (res.data?.code !== 0) throw new ApiError(res.data?.code, res.data?.message)
  return res.data.data.token
}

// 业务码优先于 HTTP 状态码：code !== 0 一律抛 ApiError
http.interceptors.response.use(
  (res) => {
    const body = res.data
    if (body && typeof body.code === 'number') {
      if (body.code !== 0) throw new ApiError(body.code, body.message, body.data)
      return body.data
    }
    return body
  },
  async (err) => {
    const { response, config } = err
    if (response?.status === 401 && config && !config._retried && !config.url?.includes('/auth/refresh')) {
      config._retried = true
      try {
        const token = await refreshToken()
        if (token) config.headers.Authorization = `Bearer ${token}`
        return http(config)
      } catch {
        // 刷新失败，落到下面的统一错误
      }
    }
    const body = response?.data
    if (body && typeof body.code === 'number') {
      throw new ApiError(body.code, body.message, body.data)
    }
    throw new ApiError(response?.status || -1, err.message || '网络错误')
  },
)

export default http
