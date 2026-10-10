<!-- src/App.vue -->
<template>
  <div style="max-width: 800px; margin: 0 auto; padding: 24px">
    <h1 style="margin-bottom: 24px; font-size: 18px; color: #374151">VoicePlayer Demo</h1>
    <VoicePlayer :track-a="{ src: 'https://www.w3schools.com/html/horse.ogg', label: 'A路测试' }" />
  </div>
</template>

<script setup>
import VoicePlayer from './components/VoicePlayer.vue'
</script>
