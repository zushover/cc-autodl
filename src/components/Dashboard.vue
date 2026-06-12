<script setup lang="ts">
import { ref, watch } from 'vue'
import type { Instance, GPUData, ProbeResult } from '../types'
import InstanceCard from './InstanceCard.vue'

const props = defineProps<{
  currentInstance: Instance | null
  instances: Instance[]
  gpuData: GPUData
  probeResult: ProbeResult | null
  loading: { init: boolean; instances: boolean; gpu: boolean; probe: boolean; sync: boolean }
}>()

const emit = defineEmits<{
  probe: []; refreshGPU: []; shutdown: []; setCurrent: [uuid: string]
  syncPro: []; remove: [uuid: string]; openRegister: []; probeInstance: [uuid: string]
}>()

// 探测动画状态
const probePhase = ref<'idle' | 'breathing' | 'reveal'>('idle')

watch(() => props.loading.probe, (v) => {
  if (v) probePhase.value = 'breathing'
})
watch(() => props.probeResult, (r) => {
  if (r) probePhase.value = 'reveal'
})
watch(() => props.loading.probe, (v) => {
  if (!v && props.probeResult) probePhase.value = 'reveal'
})

function statusBadge(s: string) {
  return s === 'running' || s === 'reachable' ? 'running' : s === 'no_gpu' ? 'warning' : 'stopped'
}
function statusLabel(s: string) {
  const m: Record<string, string> = { running:'运行中', stopped:'已关机', no_gpu:'无卡模式', reachable:'可达' }
  return m[s] || s
}
function n(v: number | null | undefined, d = 1) {
  if (v == null) return '--'
  return v.toFixed(d)
}
function fmtMem(v: number | null | undefined) {
  if (v == null) return '--'
  if (v < 0.01) return '<0.01'
  return v.toFixed(2)
}
</script>

<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <h1 style="font-size:1.3rem;font-weight:700;margin:0;">服务器</h1>
      <div style="display:flex;gap:6px;">
        <button class="btn" @click="emit('syncPro')" :disabled="loading.sync" title="同步 Pro API">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg>
          {{ loading.sync ? '同步中' : '同步' }}
        </button>
        <button class="btn btn-primary" @click="emit('openRegister')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          注册
        </button>
      </div>
    </div>

    <!-- ===== 当前实例详情 ===== -->
    <div v-if="currentInstance" class="glass-card" style="padding:20px;margin-bottom:16px;">

      <!-- 实例选择器 + 操作按钮 -->
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <div style="display:flex;align-items:center;gap:10px;">
          <select
            :value="currentInstance.uuid"
            @change="emit('setCurrent', ($event.target as HTMLSelectElement).value)"
            style="font-size:13px;font-weight:600;padding:6px 10px;min-width:180px;"
          >
            <option v-for="i in instances" :key="i.uuid" :value="i.uuid">
              {{ i.alias || i.uuid.slice(0, 10) }} · {{ i.gpu_type || '?' }}
            </option>
          </select>
          <span :class="'badge badge-' + statusBadge(currentInstance.status)">{{ statusLabel(currentInstance.status) }}</span>
          <span v-if="currentInstance.gpu_type" style="font-size:12px;color:var(--text-dim);">{{ currentInstance.gpu_type }}</span>
        </div>

        <div style="display:flex;gap:5px;">
          <button class="btn" @click="emit('probe')" :disabled="loading.probe" title="探测">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.35-4.35"/></svg>
            {{ loading.probe ? '探测中' : '探测' }}
          </button>
          <button class="btn" @click="emit('refreshGPU')" :disabled="loading.gpu" title="刷新GPU">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg>
          </button>
          <button class="btn btn-danger" @click="emit('shutdown')" :disabled="loading.probe" title="关机">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 2v10"/><path d="M18.36 5.64a9 9 0 11-12.72 0"/></svg>
          </button>
        </div>
      </div>

      <!-- ===== 探测呼吸动画 / 结果面板 ===== -->

      <!-- 呼吸中 -->
      <div v-if="probePhase === 'breathing'" style="display:flex;align-items:center;justify-content:center;padding:40px;">
        <div class="sun-breathe">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="var(--text)" stroke-width="1.2">
            <circle cx="24" cy="24" r="5" stroke-width="2"/>
            <path d="M24 2v5m0 34v5M8.5 8.5l3.5 3.5m24 24l3.5 3.5M2 24h5m34 0h5M8.5 39.5l3.5-3.5m24-24l3.5-3.5"/>
          </svg>
        </div>
      </div>

      <!-- 结果面板 -->
      <div v-else-if="probeResult?.reachable" style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">

        <!-- GPU 卡片 -->
        <div class="glass" style="padding:14px;grid-column:1/-1;">
          <div style="font-size:10px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:10px;">GPU</div>
          <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;">
            <div style="text-align:center;">
              <div style="font-size:1.4rem;font-weight:700;">{{ n(gpuData.util_percent, 0) }}<span style="font-size:0.4em;">%</span></div>
              <div style="font-size:10px;color:var(--text-dim);">利用率</div>
            </div>
            <div style="text-align:center;">
              <div style="font-size:1.4rem;font-weight:700;">{{ fmtMem(gpuData.mem_used_gb) }}<span style="font-size:0.4em;"> / {{ n(gpuData.mem_total_gb) }}G</span></div>
              <div style="font-size:10px;color:var(--text-dim);">显存</div>
            </div>
            <div style="text-align:center;">
              <div style="font-size:1.4rem;font-weight:700;">{{ n(gpuData.temp_c, 0) }}<span style="font-size:0.4em;">°C</span></div>
              <div style="font-size:10px;color:var(--text-dim);">温度</div>
            </div>
            <div style="text-align:center;">
              <div style="font-size:1.4rem;font-weight:700;">{{ gpuData.processes?.length || 0 }}</div>
              <div style="font-size:10px;color:var(--text-dim);">进程</div>
            </div>
          </div>
          <!-- GPU 名称 -->
          <div v-if="gpuData.gpu_name" style="margin-top:8px;font-size:11px;color:var(--text-dim);text-align:center;">{{ gpuData.gpu_name }}</div>
        </div>

        <!-- 系统信息 -->
        <div class="glass" style="padding:12px;">
          <div style="font-size:10px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">系统</div>
          <div style="font-size:12px;color:var(--text-secondary);line-height:1.7;">
            <div v-if="probeResult.hostname">{{ probeResult.hostname }}</div>
            <div v-if="probeResult.os">{{ probeResult.os }}</div>
            <div v-if="probeResult.python">{{ probeResult.python }}</div>
          </div>
        </div>

        <!-- 资源 -->
        <div class="glass" style="padding:12px;">
          <div style="font-size:10px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">资源</div>
          <div style="font-size:12px;color:var(--text-secondary);line-height:1.7;">
            <div v-if="probeResult.disk">磁盘 {{ probeResult.disk }}</div>
            <div v-if="probeResult.ram">内存 {{ probeResult.ram }}</div>
          </div>
        </div>

        <!-- SSH -->
        <div class="glass" style="padding:12px;grid-column:1/-1;">
          <div style="font-size:10px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">SSH</div>
          <code style="font-size:12px;background:var(--bg-input);padding:4px 8px;border-radius:4px;display:block;">
            ssh -p {{ currentInstance.ssh_port }} {{ currentInstance.ssh_user }}@{{ currentInstance.ssh_host }}
          </code>
        </div>

        <!-- GPU 进程 -->
        <div v-if="gpuData.processes?.length" class="glass" style="padding:12px;grid-column:1/-1;">
          <div style="font-size:10px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">GPU 进程</div>
          <div v-for="p in gpuData.processes" :key="p.pid" style="font-size:12px;color:var(--text-secondary);display:flex;justify-content:space-between;padding:3px 0;">
            <span>{{ p.name }}</span><span>PID {{ p.pid }} · {{ p.gpu_mem_mb }}MB</span>
          </div>
        </div>
      </div>

      <!-- 未探测 / 不可达 -->
      <div v-else-if="!loading.probe" style="text-align:center;padding:20px;color:var(--text-dim);">
        {{ probeResult ? '不可达: ' + (probeResult.error || 'SSH连接失败') : '点击「探测」获取实时 GPU 数据' }}
      </div>

    </div>

    <!-- 无实例 -->
    <div v-if="!currentInstance && instances.length === 0" class="glass-card" style="text-align:center;padding:48px;">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" style="color:var(--text-dim);margin-bottom:12px;">
        <rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><circle cx="6" cy="6" r="1" fill="currentColor"/><circle cx="6" cy="18" r="1" fill="currentColor"/>
      </svg>
      <div style="font-weight:600;color:var(--text-secondary);margin-bottom:6px;">暂无服务器</div>
      <div style="font-size:12px;color:var(--text-dim);margin-bottom:14px;">注册 GPU 实例或同步 Pro API</div>
      <button class="btn btn-primary" @click="emit('openRegister')">注册实例</button>
    </div>

    <div v-if="!currentInstance && instances.length > 0" class="glass-card" style="text-align:center;padding:32px;">
      <div style="font-weight:600;color:var(--text-secondary);margin-bottom:6px;">选择一台服务器</div>
      <div style="font-size:12px;color:var(--text-dim);">{{ instances.length }} 台实例已注册，从下方选择一台</div>
    </div>

    <!-- ===== 全部实例列表 ===== -->
    <div v-if="instances.length > 0" style="margin-top:16px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
        <span style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.5px;">全部实例 · {{ instances.length }}</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px;">
        <InstanceCard
          v-for="inst in instances"
          :key="inst.uuid"
          :inst="inst"
          :isCurrent="inst.uuid === currentInstance?.uuid"
          @select="(uuid: string) => emit('setCurrent', uuid)"
          @probe="(uuid: string) => emit('probeInstance', uuid)"
          @remove="(uuid: string) => emit('remove', uuid)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.sun-breathe {
  animation: breathe 1.5s ease-in-out infinite;
}
@keyframes breathe {
  0%, 100% { transform: scale(1); opacity: 0.5; }
  50% { transform: scale(1.3); opacity: 1; }
}
</style>
