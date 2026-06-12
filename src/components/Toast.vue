<script setup lang="ts">
defineProps<{ show: boolean; msg: string; ok: boolean; id: number }>()
defineEmits<{ dismiss: [] }>()
</script>

<template>
  <div
    v-if="show"
    :key="id"
    :class="'toast ' + (ok ? 'toast-ok' : 'toast-err')"
    @click="$emit('dismiss')"
  >{{ msg }}</div>
</template>
