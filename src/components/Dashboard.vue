<script setup lang="ts">
import type { Instance, GPUData, ProbeResult, GPUProcess } from '../types'
import InstanceCard from './InstanceCard.vue'

defineProps<{
  currentInstance: Instance | null
  instances: Instance[]
  gpuData: GPUData
  probeResult: ProbeResult | null
  loading: { init: boolean; instances: boolean; gpu: boolean; probe: boolean }
}>()

defineEmits<{
  probe: []
  refreshGPU: []
  shutdown: []
  setCurrent: [uuid: string]
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
    <h1 style="font-size:1.4rem;font-weight:700;margin-bottom:20px;">仪表盘</h1>

    <!-- Current Instance Detail -->
    <div v-if="currentInstance" class="glass-card" style="margin-bottom:20px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <div>
          <span :class="'badge badge-' + statusBadge(currentInstance.status)">{{ statusLabel(currentInstance.status) }}</span>
          <span :class="'badge badge-' + currentInstance.source" style="margin-left:6px;">{{ currentInstance.source }}</span>
          <strong style="margin-left:8px;font-size:1.1rem;">{{ currentInstance.alias || currentInstance.uuid?.slice(0, 14) }}</strong>
          <span v-if="currentInstance.gpu_type" style="font-size:13px;color:#71717a;margin-left:8px;">{{ currentInstance.gpu_type }}</span>
        </div>
        <div style="display:flex;gap:6px;">
          <button class="btn" @click="$emit('probe')" :disabled="loading.probe" style="min-width:90px;">
            {{ loading.probe ? '⏳ 探测中...' : '🔍 探测' }}
          </button>
          <button class="btn" @click="$emit('refreshGPU')" :disabled="loading.gpu">{{ loading.gpu ? '⏳' : '🔄' }} 刷新</button>
          <button class="btn btn-danger" @click="$emit('shutdown')" :disabled="loading.probe" style="font-size:12px;">⏻ 关机</button>
        </div>
      </div>

      <!-- GPU Metrics -->
      <div v-if="gpuData.util_percent != null || gpuData.mem_total_gb" style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:12px;">
        <div class="glass" style="padding:16px;text-align:center;">
          <div class="metric-num accent">{{ gpuData.util_percent ?? '--' }}<span style="font-size:0.5em;">%</span></div>
          <div class="metric-label">GPU 利用率</div>
        </div>
        <div class="glass" style="padding:16px;text-align:center;">
          <div class="metric-num">{{ gpuData.mem_used_gb ?? '--' }}<span style="font-size:0.5em;">/{{ gpuData.mem_total_gb ?? '--' }}GB</span></div>
          <div class="metric-label">显存</div>
        </div>
        <div class="glass" style="padding:16px;text-align:center;">
          <div class="metric-num">{{ gpuData.temp_c ?? '--' }}<span style="font-size:0.5em;">°C</span></div>
          <div class="metric-label">温度</div>
        </div>
        <div class="glass" style="padding:16px;text-align:center;">
          <div class="metric-num accent">¥{{ currentInstance.price_per_hour || '--' }}<span style="font-size:0.5em;">/h</span></div>
          <div class="metric-label">单价</div>
        </div>
      </div>

      <!-- No GPU mode -->
      <div v-else-if="currentInstance.status === 'no_gpu'" class="glass" style="text-align:center;padding:16px;margin-bottom:12px;color:#facc15;">
        ⚡ 无卡模式 — 实例运行中但未加载 GPU（¥0.01/h）
      </div>

      <!-- Not probed -->
      <div v-else-if="!loading.probe && !probeResult" class="glass" style="text-align:center;padding:20px;margin-bottom:12px;color:#52525b;">
        💡 点击「🔍 探测」获取实时状态
      </div>

      <!-- GPU Processes -->
      <div v-if="gpuData.processes && gpuData.processes.length" style="margin-bottom:12px;">
        <div style="font-size:12px;color:#71717a;margin-bottom:6px;">🏃 运行中的 GPU 进程</div>
        <div v-for="p in gpuData.processes" :key="p.pid" class="glass" style="padding:8px 12px;margin-bottom:4px;display:flex;justify-content:space-between;align-items:center;">
          <span style="font-size:13px;">{{ p.name }}</span>
          <span style="font-size:11px;color:#71717a;">PID {{ p.pid }} · {{ p.gpu_mem_mb }}MB</span>
        </div>
      </div>

      <!-- System Info -->
      <div v-if="probeResult?.reachable" style="display:flex;gap:16px;font-size:11px;color:#52525b;flex-wrap:wrap;">
        <span v-if="probeResult.hostname">🖥 {{ probeResult.hostname }}</span>
        <span v-if="probeResult.python">{{ probeResult.python }}</span>
        <span v-if="probeResult.disk">💾 {{ probeResult.disk }}</span>
        <span v-if="probeResult.ram">{{ probeResult.ram }}</span>
      </div>

      <!-- SSH info -->
      <div v-if="currentInstance.ssh_host" style="margin-top:8px;font-size:12px;color:#52525b;">
        SSH: {{ currentInstance.ssh_user }}@{{ currentInstance.ssh_host }}:{{ currentInstance.ssh_port }}
      </div>
    </div>

    <!-- No current instance -->
    <div v-if="!currentInstance && !loading.instances" class="glass-card" style="text-align:center;padding:40px;">
      <div style="font-size:2rem;">🖥️</div><div style="color:#a1a1aa;">未设置当前实例</div>
      <div style="font-size:13px;color:#52525b;">在「实例列表」中选择或同步 Pro API</div>
    </div>

    <!-- All Instances Grid -->
    <h2 style="font-size:1.05rem;font-weight:600;margin-bottom:12px;">所有实例</h2>
    <div v-if="instances.length===0" class="glass-card" style="text-align:center;padding:20px;color:#52525b;">暂无实例</div>
    <div v-else style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;">
      <InstanceCard
        v-for="inst in instances"
        :key="inst.uuid"
        :inst="inst"
        @select="(uuid) => $emit('setCurrent', uuid)"
      />
    </div>
  </div>
</template>
