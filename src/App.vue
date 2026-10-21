<!-- src/App.vue -->
<template>
  <div class="app-container">
    <section>
      <VoicePlayer
        :track-a="{ src: AUDIO_URL_A, label: 'A路' }"
        :track-b="{ src: AUDIO_URL_B, label: 'B路' }"
      />
    </section>
  </div>
</template>

<script setup>
import VoicePlayer from './components/VoicePlayer.vue'

const AUDIO_URL_A = '/demo-a.wav'
const AUDIO_URL_B = '/demo-b.wav'
</script>

<style lang="scss" scoped>
.app-container {
  max-width: 860px;
  margin: 0 auto;
  padding: 24px;
}
</style>
