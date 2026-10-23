<template>
  <svg
    :class="['svg-icon', className]"
    :style="{ width: size || '1em', height: size || '1em' }"
    aria-hidden="true"
  >
    <use :href="`#icon-${name}`" />
  </svg>
</template>

<script setup>
defineProps({
  name: {
    type: String,
    required: true,
  },
  className: {
    type: String,
    default: '',
  },
  size: {
    type: String,
    default: '',
  },
})
</script>

<style lang="scss" scoped>
.svg-icon {
  fill: currentColor;
  overflow: hidden;
  vertical-align: -0.15em;
  flex-shrink: 0;
}
</style>
