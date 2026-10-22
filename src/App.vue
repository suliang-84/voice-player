<!-- src/App.vue -->
<template>
  <div class="app-container">
    <section>
      <VoicePlayer
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

const playlist = [
  {
    trackA: { src: '/demo-a.wav', label: 'A路' },
    trackB: { src: '/demo-b.wav', label: 'B路' },
  },
  {
    trackA: { src: '/demo-a.wav', label: 'A路' },
    trackB: { src: '/demo-b.wav', label: 'B路' },
  },
]

const current = ref(0)
</script>

<style lang="scss" scoped>
.app-container {
  max-width: 860px;
  margin: 0 auto;
  padding: 24px;
}
</style>
