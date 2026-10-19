<!-- src/App.vue -->
<template>
  <div class="app-container">
    <div class="app-header">
      <h1 class="app-title">VoicePlayer Demo</h1>
      <button class="app-theme-btn" @click="isDark = !isDark">
        {{ isDark ? '☀ 亮主题' : '☾ 暗主题' }}
      </button>
    </div>

    <section>
      <VoicePlayer
        :track-a="{ src: AUDIO_URL, label: 'A路' }"
        :track-b="{ src: AUDIO_URL, label: 'B路' }"
        :style="isDark ? darkTheme : {}"
      />
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import VoicePlayer from './components/VoicePlayer.vue'

const AUDIO_URL = '/demo.mp3'
const isDark = ref(false)

const darkTheme = {
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
</script>

<style lang="scss" scoped>
.app-container {
  max-width: 860px;
  margin: 0 auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.app-title {
  font-size: 20px;
  font-weight: 700;
  color: #111827;
}

.app-theme-btn {
  padding: 6px 14px;
  border-radius: 6px;
  border: 1px solid #d1d5db;
  background: #f9fafb;
  cursor: pointer;
  font-size: 13px;
  color: #374151;
}
</style>
