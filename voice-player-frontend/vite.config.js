import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { createSvgIconsPlugin } from 'vite-plugin-svg-icons'
import path from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [
      vue(),
      createSvgIconsPlugin({
        iconDirs: [path.resolve(process.cwd(), 'src/icons')],
        symbolId: 'icon-[name]',
      }),
    ],
    server: {
      // 后端地址通过 VITE_PROXY_TARGET 配置，默认本机 10090（voice_ai 默认端口）
      proxy: {
        '/api': { target: env.VITE_PROXY_TARGET || 'http://localhost:10090', changeOrigin: true },
        '/ws': { target: env.VITE_PROXY_TARGET || 'http://localhost:10090', changeOrigin: true, ws: true },
      },
    },
  }
})
