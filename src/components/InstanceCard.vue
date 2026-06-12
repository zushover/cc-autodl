<script setup lang="ts">
import type { Instance } from '../types'

defineProps<{ inst: Instance; isCurrent?: boolean }>()
defineEmits<{ select: [uuid: string]; probe: [uuid: string]; remove: [uuid: string] }>()

function statusBadge(s: string): string {
  if (s === 'running' || s === 'reachable') return 'running'
  if (s === 'no_gpu') return 'warning'
  return 'stopped'
}
function statusLabel(s: string): string {
  const m: Record<string, string> = { running:'运行中', stopped:'已关机', no_gpu:'无卡模式', reachable:'可达', powering_on:'开机中', powering_off:'关机中' }
  return m[s] || s || '未知'
}
</script>

<template>
  <div
    :class="'glass-card' + (isCurrent ? ' glass-card-active' : '')"
    style="cursor:pointer;padding:14px;"
    @click="$emit('select', inst.uuid)"
  >
    <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
      <span style="width:7px;height:7px;border-radius:50%;flex-shrink:0;"
        :style="{background: inst.status==='running'||inst.status==='reachable'?'var(--green)':inst.status==='no_gpu'?'#eab308':'var(--text-dim)'}"
      ></span>
      <span style="font-weight:600;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{{ inst.alias || inst.uuid.slice(0, 14) }}</span>
      <span v-if="isCurrent" style="font-size:9px;color:var(--text-dim);border:1px solid var(--border);border-radius:3px;padding:0 4px;margin-left:auto;">当前</span>
    </div>
    <div style="font-size:11px;color:var(--text-dim);">
      {{ inst.gpu_type || '未知GPU' }} · {{ inst.source.toUpperCase() }} · {{ statusLabel(inst.status) }}
    </div>
    <div style="font-size:11px;color:var(--text-dim);margin-top:1px;">¥{{ inst.price_per_hour || '--' }}/h</div>

    <!-- 操作 -->
    <div style="display:flex;gap:4px;margin-top:8px;" @click.stop>
      <button class="btn btn-ghost" style="font-size:10px;padding:2px 6px;" @click.stop="$emit('probe', inst.uuid)">探测</button>
      <button class="btn btn-ghost" style="font-size:10px;padding:2px 6px;color:var(--red);" @click.stop="$emit('remove', inst.uuid)">删除</button>
    </div>
  </div>
</template>
