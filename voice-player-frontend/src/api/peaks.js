// src/api/peaks.js
// 把后端返回的 peaks 统一成 WaveSurfer 需要的单声道一维数组 [[...]]。
// 约定格式见接口文档 2.1：外层为声道，内层为带符号振幅点，长度等于 pointCount。
// 无法识别 / 校验失败时返回 null，由调用方回退到浏览器解码。

const isNumArray = (a) => Array.isArray(a) && a.every(v => typeof v === 'number' && Number.isFinite(v))

// 逐点取绝对值最大者（保留符号）
const pickMax = (a, b) => (Math.abs(a) >= Math.abs(b) ? a : b)

export function normalizePeaks(raw, pointCount) {
  if (!Array.isArray(raw) || !raw.length || !raw.every(isNumArray) || raw.some(a => !a.length)) {
    return null
  }

  let flat
  let format

  const inner = raw[0].length
  if (raw.length === 1) {
    flat = raw[0]
    format = 'contract'
  } else if (raw.length > 2 && raw.length === pointCount && raw.every(a => a.length <= 4)) {
    // [[min,max], ...]：每段一个小数组
    flat = raw.map(seg => seg.reduce(pickMax, 0))
    format = 'segments'
  } else if (raw.every(a => a.length === inner)) {
    // 多声道或 [max[], min[]]：逐点合并为一路
    flat = raw[0].map((_, i) => raw.reduce((m, ch) => pickMax(m, ch[i]), 0))
    format = 'channels-merged'
  } else {
    return null
  }

  if (flat.every(v => v === 0)) return null

  if (format !== 'contract') {
    console.warn(`[peaks] 后端返回的 peaks 不是约定格式，已按 "${format}" 适配（见接口文档 2.1）`)
  } else if (pointCount && flat.length !== pointCount) {
    console.warn(`[peaks] 内层长度 ${flat.length} 与 pointCount ${pointCount} 不一致`)
  }
  return [flat]
}
