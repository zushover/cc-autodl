<script setup lang="ts">
import type { Instance } from '../types'

defineProps<{
  instances: Instance[]
  loading: { sync: boolean }
}>()

defineEmits<{
  syncPro: []
  openRegister: []
  setCurrent: [uuid: string]
  probe: [uuid: string]
  remove: [uuid: string]
}>()

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
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
      <h1 style="font-size:1.4rem;font-weight:700;">实例列表</h1>
      <div style="display:flex;gap:8px;">
        <button class="btn" @click="$emit('syncPro')" :disabled="loading.sync">{{ loading.sync ? '⏳ 同步中...' : '🔄 同步 Pro API' }}</button>
        <button class="btn btn-primary" @click="$emit('openRegister')">+ 注册实例</button>
      </div>
    </div>

    <div v-if="instances.length===0" class="glass-card" style="text-align:center;padding:40px;color:#52525b;">
      暂无实例<br><small>点击「同步 Pro API」或「注册实例」</small>
    </div>

    <div v-else class="glass" style="overflow:hidden;">
      <table>
        <thead>
          <tr>
            <th>状态</th><th>来源</th><th>名称</th><th>GPU</th><th>区域</th><th>单价</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="inst in instances" :key="inst.uuid" :style="{background: inst.is_current ? 'rgba(212,116,74,0.04)' : ''}">
            <td><span :class="'badge badge-' + statusBadge(inst.status)">{{ statusLabel(inst.status) }}</span></td>
            <td><span :class="'badge badge-' + inst.source">{{ inst.source }}</span></td>
            <td>
              <span style="font-weight:600;">{{ inst.alias || inst.uuid.slice(0, 14) }}</span>
              <span v-if="inst.is_current" style="color:#d4744a;"> ★</span>
            </td>
            <td>{{ inst.gpu_type || '--' }}</td>
            <td>{{ inst.region || '--' }}</td>
            <td>{{ inst.price_per_hour ? '¥' + inst.price_per_hour + '/h' : '免费' }}</td>
            <td>
              <div style="display:flex;gap:4px;">
                <button v-if="!inst.is_current" class="btn" style="font-size:11px;padding:4px 8px;" @click="$emit('setCurrent', inst.uuid)">切换</button>
                <button class="btn" style="font-size:11px;padding:4px 8px;" @click="$emit('probe', inst.uuid)">探测</button>
                <button class="btn btn-danger" style="font-size:11px;padding:4px 8px;" @click="$emit('remove', inst.uuid)">注销</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
