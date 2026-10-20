<!-- src/App.vue -->
<template>
  <div class="app-container">
    <section>
      <VoicePlayer
        :track-a="{ src: AUDIO_URL_A, label: '主动方' }"
        :track-b="{ src: AUDIO_URL_B, label: '接收方' }"
      />
    </section>
  </div>
</template>

<script setup>
import VoicePlayer from './components/VoicePlayer.vue'

const AUDIO_URL_A = '/demo-a.mp3'
const AUDIO_URL_B = '/demo-b.mp3'
</script>

<style lang="scss" scoped>
.app-container {
  max-width: 860px;
  margin: 0 auto;
  padding: 24px;
}
</style>
