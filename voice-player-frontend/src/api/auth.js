// src/api/auth.js
// token 目前为占位符；宿主系统引入播放器后，通过 configureAuth 注入自己的 token。
let provider = {
  getToken: () => import.meta.env.VITE_PLACEHOLDER_TOKEN || '',
  // 返回新的 token；默认调用 /auth/refresh（见 request.js），宿主可覆盖
  refreshToken: null,
}

export function configureAuth(options = {}) {
  provider = { ...provider, ...options }
}

export function getToken() {
  return provider.getToken?.() || ''
}

export function getRefreshHandler() {
  return provider.refreshToken
}
