<script setup lang="ts">
import type { Instance } from '../types'

defineProps<{ inst: Instance }>()
defineEmits<{ select: [uuid: string] }>()

function statusBadge(s: string): string {
  if (s === 'running' || s === 'reachable') return 'running'
  if (s === 'stopped' || s === 'released' || s === 'shutdown') return 'stopped'
  if (s === 'no_gpu') return 'warning'
  return 'stopped'
}

function statusLabel(s: string): string {
  const map: Record<string, string> = {
    running: '运行中', stopped: '已关机', shutdown: '已关机',
    no_gpu: '无卡模式', reachable: '可达', powering_on: '开机中', powering_off: '关机中',
  }
  return map[s] || s || '未知'
}
</script>

<template>
  <div
    :class="'glass-card' + (inst.is_current ? ' glass-card-active' : '')"
    style="cursor:pointer;"
    @click="$emit('select', inst.uuid)"
  >
    <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">
      <span
        style="width:8px;height:8px;border-radius:50%;"
        :style="{background: inst.status==='running'||inst.status==='reachable'?'#4ade80':inst.status==='no_gpu'?'#facc15':'var(--text-secondary)'}"
      ></span>
      <span style="font-weight:600;font-size:13px;">{{ inst.alias || inst.uuid.slice(0, 14) }}</span>
    </div>
    <div style="font-size:12px;color:var(--text-secondary);">
      {{ inst.gpu_type || 'GPU' }} · {{ inst.source }} · {{ statusLabel(inst.status) }}
    </div>
  </div>
</template>
