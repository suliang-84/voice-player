<!-- src/App.vue -->
<template>
  <div class="app-container">
    <section>
      <VoicePlayer
        :track-a="playlist[current].trackA"
        :track-b="playlist[current].trackB"
        :has-prev="current > 0"
        :has-next="current < playlist.length - 1"
        :transcripts="playlist[current].transcripts"
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
    trackA: { src: '/demo-a.wav', label: 'A路', identity: '运营商运维人员' },
    trackB: { src: '/demo-b.wav', label: 'B路', identity: '客户' },
    transcripts: [
      { trackId: 'A', startTime: 0.5,  endTime: 3.2,  text: '您好，请问是XX客服吗？',                                 translation: 'Hello, is this XX customer service?' },
      { trackId: 'B', startTime: 3.8,  endTime: 6.1,  text: '您好，是的，请问有什么可以帮您？',                     translation: 'Hello, yes. How can I help you?' },
      { trackId: 'A', startTime: 6.5,  endTime: 10.0, text: '我这边网络一直有问题，已经持续好几天了。',             translation: 'My network has been having issues for several days.' },
      { trackId: 'B', startTime: 10.5, endTime: 14.2, text: '好的，我这边帮您查一下，请稍等。',                     translation: 'Alright, let me check that for you. Please hold on.' },
      { trackId: 'A', startTime: 14.8, endTime: 17.3, text: '好的，谢谢。',                                         translation: 'Okay, thank you.' },
      { trackId: 'B', startTime: 18.0, endTime: 23.5, text: '查到了，您所在区域目前有基站维护，预计明天上午恢复正常。', translation: 'There is base station maintenance in your area, expected to resume tomorrow morning.' },
      { trackId: 'A', startTime: 24.0, endTime: 27.1, text: '那请问大概什么时候可以恢复？',                         translation: 'So when approximately will it be restored?' },
      { trackId: 'B', startTime: 27.5, endTime: 31.0, text: '预计明天上午十点之前可以恢复，给您带来不便非常抱歉。', translation: 'It should be restored before 10 AM tomorrow. We apologize for the inconvenience.' },
    ],
  },
  {
    trackA: { src: '/demo-a.wav', label: 'A路' },
    trackB: { src: '/demo-b.wav', label: 'B路' },
    transcripts: [],
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
