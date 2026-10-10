<!-- src/App.vue -->
<template>
  <div style="max-width: 860px; margin: 0 auto; padding: 24px; display: flex; flex-direction: column; gap: 32px;">
    <h1 style="font-size: 20px; font-weight: 700; color: #111827">VoicePlayer Demo</h1>

    <!-- 单轨 URL 模式（默认亮色主题） -->
    <section>
      <h2 style="font-size: 14px; color: #6b7280; margin-bottom: 8px">单轨 · 默认主题 · mirror-bar</h2>
      <VoicePlayer
        :track-a="{ src: AUDIO_URL, label: '主音频' }"
      />
    </section>

    <!-- 单轨 File 上传 -->
    <section>
      <h2 style="font-size: 14px; color: #6b7280; margin-bottom: 8px">单轨 · 本地文件上传</h2>
      <input type="file" accept="audio/*" @change="onFileA" style="margin-bottom: 8px; display: block;" />
      <VoicePlayer v-if="fileTrackA" :track-a="fileTrackA" />
    </section>

    <!-- 双轨 · 暗色主题 -->
    <section>
      <h2 style="font-size: 14px; color: #6b7280; margin-bottom: 8px">双轨 · 暗色主题</h2>
      <VoicePlayer
        :track-a="{ src: AUDIO_URL, label: 'A路' }"
        :track-b="{ src: AUDIO_URL, label: 'B路' }"
        style="
          --vp-bg: #0f172a;
          --vp-border-color: #1e293b;
          --vp-wave-color: #4f46e5;
          --vp-progress-color: #818cf8;
          --vp-cursor-color: #a5b4fc;
          --vp-region-color: rgba(129,140,248,0.25);
          --vp-btn-color: #818cf8;
          --vp-btn-hover-bg: #1e293b;
          --vp-label-color: #e2e8f0;
          --vp-time-color: #94a3b8;
          --vp-slider-color: #818cf8;
          --vp-bookmark-color: #fbbf24;
        "
      />
    </section>

    <!-- 频谱图模式 -->
    <section>
      <h2 style="font-size: 14px; color: #6b7280; margin-bottom: 8px">单轨 · 镜像频谱图（热力图配色）</h2>
      <VoicePlayer
        :track-a="{ src: AUDIO_URL, label: '频谱测试' }"
        :options="{ waveformType: 'mirror-spectrogram', spectrogramColorMap: 'heatmap', height: 100 }"
      />
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import VoicePlayer from './components/VoicePlayer.vue'

const AUDIO_URL = 'https://www.w3schools.com/html/horse.ogg'

const fileTrackA = ref(null)
function onFileA(e) {
  const file = e.target.files[0]
  if (file) fileTrackA.value = { file, label: file.name }
}
</script>
