#!/usr/bin/env node
// scripts/gen-peaks.js
// 用法：ffmpeg -i audio.mp3 -filter:a aformat=channel_layouts=mono -f s16le -ar 8000 pipe:1 | node gen-peaks.js /output/base
// 输出：/output/base.peaks.json 和 /output/base.silences.json

'use strict'
const fs = require('fs')
const path = require('path')

const SAMPLES_PER_POINT = 80      // 每点聚合采样数，越大文件越小
const SAMPLE_RATE = 8000          // 与 ffmpeg -ar 保持一致
const SILENCE_THRESHOLD = 0.001   // 低于此 RMS 视为静音
const MIN_SILENCE_DURATION = 0.2  // 静音段短于此秒数不记录

const outputBase = process.argv[2]
if (!outputBase) {
  console.error('Usage: ffmpeg ... pipe:1 | node gen-peaks.js /path/to/output/base')
  process.exit(1)
}

const chunks = []
process.stdin.on('data', chunk => chunks.push(chunk))
process.stdin.on('end', () => {
  const buf = Buffer.concat(chunks)
  const peaks = [[], []]
  const silentRanges = []
  let silenceStart = null
  let sampleIndex = 0
  const totalSamples = Math.floor(buf.length / 2)

  for (let i = 0; i + SAMPLES_PER_POINT * 2 <= buf.length; i += SAMPLES_PER_POINT * 2) {
    let max = 0, min = 0, sumSq = 0

    for (let j = 0; j < SAMPLES_PER_POINT * 2; j += 2) {
      const val = buf.readInt16LE(i + j) / 32768
      if (val > max) max = val
      if (val < min) min = val
      sumSq += val * val
    }

    const rms = Math.sqrt(sumSq / SAMPLES_PER_POINT)
    peaks[0].push(+(max.toFixed(4)))
    peaks[1].push(+(min.toFixed(4)))

    // 静音检测
    const time = sampleIndex / SAMPLE_RATE
    if (rms < SILENCE_THRESHOLD) {
      if (silenceStart === null) silenceStart = time
    } else {
      if (silenceStart !== null) {
        const silenceEnd = time
        if (silenceEnd - silenceStart >= MIN_SILENCE_DURATION) {
          silentRanges.push({
            start: +(silenceStart.toFixed(3)),
            end: +(silenceEnd.toFixed(3)),
          })
        }
        silenceStart = null
      }
    }

    sampleIndex += SAMPLES_PER_POINT
  }

  // 处理末尾静音
  if (silenceStart !== null) {
    const silenceEnd = totalSamples / SAMPLE_RATE
    if (silenceEnd - silenceStart >= MIN_SILENCE_DURATION) {
      silentRanges.push({ start: +(silenceStart.toFixed(3)), end: +(silenceEnd.toFixed(3)) })
    }
  }

  const peaksPath = `${outputBase}.peaks.json`
  const silencesPath = `${outputBase}.silences.json`

  fs.writeFileSync(peaksPath, JSON.stringify(peaks))
  fs.writeFileSync(silencesPath, JSON.stringify(silentRanges))

  const fileSizeKb = (fs.statSync(peaksPath).size / 1024).toFixed(1)
  console.log(`✓ ${path.basename(outputBase)}`)
  console.log(`  peaks:    ${peaks[0].length} points → ${peaksPath} (${fileSizeKb}KB)`)
  console.log(`  silences: ${silentRanges.length} ranges → ${silencesPath}`)
})
