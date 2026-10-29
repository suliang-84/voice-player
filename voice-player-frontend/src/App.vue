<!-- src/App.vue -->
<template>
  <div class="app-container">
    <section>
      <VoicePlayer
        :audio-id="playlist[current].audioId"
        :track-a="playlist[current].trackA"
        :track-b="playlist[current].trackB"
        :has-prev="current > 0"
        :has-next="current < playlist.length - 1"
        @prev="current--"
        @next="current++"
      />
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import VoicePlayer from './components/VoicePlayer.vue'

// 演示数据：真实场景中 audioId 列表由业务系统提供并通过 props 传入。
// 不传 src 时，音频通过后端 /audios/{audioId}/stream 获取；也可传 src/file 覆盖
const playlist = [
  {
    audioId: 'audio_003',
    trackA: { label: 'A路' },
    trackB: { label: 'B路' },
  },
]

const current = ref(0)
</script>

<style lang="scss" scoped>
.app-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}
</style>
