<script setup lang="ts">
import { ref } from 'vue'
import type { Instance, GPUData, ProbeResult } from '../types'
import InstanceCard from './InstanceCard.vue'

const props = defineProps<{
  currentInstance: Instance | null
  instances: Instance[]
  gpuData: GPUData
  probeResult: ProbeResult | null
  loading: { init: boolean; instances: boolean; gpu: boolean; probe: boolean }
}>()

const emit = defineEmits<{
  probe: []
  refreshGPU: []
  shutdown: []
  setCurrent: [uuid: string]
}>()

const showSshEdit = ref(false)

function statusBadge(s: string): string {
  if (s === 'running' || s === 'reachable') return 'running'
  if (s === 'stopped' || s === 'released') return 'stopped'
  if (s === 'no_gpu') return 'warning'
  return 'stopped'
}
function statusLabel(s: string): string {
  const m: Record<string, string> = { running:'运行中', stopped:'已关机', no_gpu:'无卡模式', reachable:'可达', powering_on:'开机中', powering_off:'关机中' }
  return m[s] || s || '未知'
}

// 数字格式化 — 限制小数位
function n(v: number | null | undefined, decimals = 1): string {
  if (v == null) return '--'
  return v.toFixed(decimals)
}
function mem(v: number | null | undefined): string {
  if (v == null) return '--'
  if (v < 0.01) return '<0.01'
  return v.toFixed(2)
}
</script>

<template>
  <div>
    <h1 style="font-size:1.3rem;font-weight:700;margin:0 0 18px;">仪表盘</h1>

    <!-- 当前实例 -->
    <div v-if="currentInstance" class="glass-card" style="margin-bottom:18px;padding:20px 22px;">

      <!-- 顶行：状态 + 名称 + 按钮 -->
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:18px;">
        <div>
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
            <span :class="'badge badge-' + statusBadge(currentInstance.status)">{{ statusLabel(currentInstance.status) }}</span>
            <span :class="'badge badge-' + currentInstance.source" style="font-size:10px;">{{ currentInstance.source }}</span>
          </div>
          <div style="font-size:1.1rem;font-weight:700;">{{ currentInstance.alias || currentInstance.uuid?.slice(0, 14) }}</div>
          <div style="font-size:12px;color:var(--text-dim);">{{ currentInstance.gpu_type || '未知GPU' }} · ¥{{ currentInstance.price_per_hour || '--' }}/h</div>
        </div>

        <!-- 按钮组 -->
        <div style="display:flex;gap:6px;align-items:center;">
          <!-- 太阳logo按钮 — 服务器Agent预留 -->
          <button class="btn btn-ghost" title="服务器 Agent（即将推出）" style="padding:6px 10px;opacity:0.5;">
            <svg width="18" height="18" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5">
              <circle cx="24" cy="24" r="5" stroke-width="2.2"/>
              <path d="M24 2v5m0 34v5M8.5 8.5l3.5 3.5m24 24l3.5 3.5M2 24h5m34 0h5M8.5 39.5l3.5-3.5m24-24l3.5-3.5"/>
            </svg>
          </button>

          <!-- 探测 -->
          <button class="btn" @click="emit('probe')" :disabled="loading.probe" title="探测实例状态">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
              <circle cx="11" cy="11" r="7"/><path d="M21 21l-4.35-4.35"/><path d="M11 8v3l2 2" stroke-width="1.2"/>
            </svg>
            {{ loading.probe ? '探测中' : '探测' }}
          </button>

          <!-- 刷新GPU -->
          <button class="btn" @click="emit('refreshGPU')" :disabled="loading.gpu" title="刷新 GPU 数据">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
              <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/>
            </svg>
            {{ loading.gpu ? '刷新中' : '刷新' }}
          </button>

          <!-- 关机 -->
          <button class="btn btn-danger" @click="emit('shutdown')" :disabled="loading.probe" title="关闭实例">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
              <path d="M12 2v10"/><path d="M18.36 5.64a9 9 0 11-12.72 0"/>
            </svg>
            关机
          </button>
        </div>
      </div>

      <!-- GPU 指标 — 4列 -->
      <div v-if="gpuData.util_percent != null || gpuData.mem_total_gb" style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:14px;">
        <div class="glass" style="padding:14px;text-align:center;">
          <div style="font-size:1.5rem;font-weight:700;letter-spacing:-0.5px;">{{ n(gpuData.util_percent, 0) }}<span style="font-size:0.45em;font-weight:500;">%</span></div>
          <div style="font-size:11px;color:var(--text-dim);margin-top:2px;">GPU 利用率</div>
        </div>
        <div class="glass" style="padding:14px;text-align:center;">
          <div style="font-size:1.5rem;font-weight:700;letter-spacing:-0.5px;">{{ mem(gpuData.mem_used_gb) }}<span style="font-size:0.45em;font-weight:500;"> / {{ n(gpuData.mem_total_gb) }} GB</span></div>
          <div style="font-size:11px;color:var(--text-dim);margin-top:2px;">显存</div>
        </div>
        <div class="glass" style="padding:14px;text-align:center;">
          <div style="font-size:1.5rem;font-weight:700;letter-spacing:-0.5px;">{{ n(gpuData.temp_c, 0) }}<span style="font-size:0.45em;font-weight:500;">°C</span></div>
          <div style="font-size:11px;color:var(--text-dim);margin-top:2px;">温度</div>
        </div>
        <div class="glass" style="padding:14px;text-align:center;">
          <div style="font-size:1.5rem;font-weight:700;letter-spacing:-0.5px;">{{ gpuData.processes?.length || 0 }}</div>
          <div style="font-size:11px;color:var(--text-dim);margin-top:2px;">GPU 进程</div>
        </div>
      </div>

      <!-- 无GPU/未探测提示 -->
      <div v-else-if="currentInstance.status === 'no_gpu'" class="glass" style="text-align:center;padding:16px;margin-bottom:12px;color:var(--text-dim);">
        无卡模式 — 实例运行中但未加载 GPU
      </div>
      <div v-else-if="!loading.probe && !probeResult" class="glass" style="text-align:center;padding:16px;margin-bottom:12px;color:var(--text-dim);">
        点击「探测」获取实时 GPU 数据
      </div>

      <!-- GPU 进程 -->
      <div v-if="gpuData.processes && gpuData.processes.length" style="margin-bottom:14px;">
        <div style="font-size:11px;font-weight:600;color:var(--text-dim);margin-bottom:6px;">GPU 进程</div>
        <div v-for="p in gpuData.processes" :key="p.pid" class="glass" style="padding:6px 12px;margin-bottom:3px;display:flex;justify-content:space-between;align-items:center;font-size:12px;">
          <span>{{ p.name }}</span>
          <span style="color:var(--text-dim);">PID {{ p.pid }} · {{ p.gpu_mem_mb }}MB</span>
        </div>
      </div>

      <!-- 系统信息 -->
      <div v-if="probeResult?.reachable" style="display:flex;gap:14px;font-size:11px;color:var(--text-dim);flex-wrap:wrap;margin-bottom:14px;padding:10px 14px;background:var(--bg-hover);border-radius:8px;">
        <span v-if="probeResult.hostname">{{ probeResult.hostname }}</span>
        <span v-if="probeResult.python">{{ probeResult.python }}</span>
        <span v-if="probeResult.disk">磁盘: {{ probeResult.disk }}</span>
        <span v-if="probeResult.ram">内存: {{ probeResult.ram }}</span>
        <span v-if="probeResult.os">{{ probeResult.os }}</span>
      </div>

      <!-- SSH 连接信息 + 编辑 -->
      <div v-if="currentInstance.ssh_host" style="border-top:1px solid var(--border-light);padding-top:14px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
          <span style="font-size:11px;font-weight:600;color:var(--text-dim);">SSH 连接</span>
          <button class="btn btn-ghost" @click="showSshEdit = !showSshEdit" style="font-size:11px;padding:2px 8px;">
            {{ showSshEdit ? '收起' : '编辑' }}
          </button>
        </div>
        <code style="font-size:12px;color:var(--text-secondary);background:var(--bg-input);padding:4px 8px;border-radius:4px;">
          ssh -p {{ currentInstance.ssh_port }} {{ currentInstance.ssh_user }}@{{ currentInstance.ssh_host }}
        </code>
        <div v-if="currentInstance.ssh_password" style="font-size:11px;color:var(--text-dim);margin-top:4px;">
          密码: {{ currentInstance.ssh_password }}
        </div>

        <!-- 编辑面板 -->
        <div v-if="showSshEdit" style="margin-top:10px;display:flex;flex-direction:column;gap:6px;">
          <div style="display:flex;gap:6px;">
            <input :value="currentInstance.ssh_host" placeholder="Host" style="flex:1;font-size:12px;" readonly>
            <input :value="currentInstance.ssh_port" placeholder="Port" style="width:70px;font-size:12px;" readonly>
          </div>
          <div style="display:flex;gap:6px;">
            <input :value="currentInstance.ssh_user" placeholder="User" style="width:80px;font-size:12px;" readonly>
            <input :value="currentInstance.ssh_password || ''" placeholder="密码" type="password" style="flex:1;font-size:12px;" readonly>
          </div>
          <span style="font-size:10px;color:var(--text-dim);">修改 SSH 信息请在「实例列表」中注销后重新注册</span>
        </div>
      </div>

    </div>

    <!-- 无当前实例 -->
    <div v-if="!currentInstance && !loading.instances" class="glass-card" style="text-align:center;padding:40px;">
      <div style="margin-bottom:8px;">
        <svg width="40" height="40" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.2" style="color:var(--text-dim);">
          <rect x="2" y="2" width="44" height="32" rx="3"/><circle cx="24" cy="18" r="6"/><path d="M14 42l4-14h12l4 14"/>
        </svg>
      </div>
      <div style="color:var(--text-secondary);font-weight:600;margin-bottom:4px;">未设置当前实例</div>
      <div style="font-size:12px;color:var(--text-dim);">在「实例列表」中选择或同步 Pro API</div>
    </div>

    <!-- 全部实例 -->
    <h2 style="font-size:1rem;font-weight:600;margin:0 0 10px;">所有实例</h2>
    <div v-if="instances.length===0" class="glass-card" style="text-align:center;padding:20px;color:var(--text-dim);font-size:13px;">暂无实例</div>
    <div v-else style="display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:8px;">
      <InstanceCard
        v-for="inst in instances"
        :key="inst.uuid"
        :inst="inst"
        @select="(uuid: string) => emit('setCurrent', uuid)"
      />
    </div>
  </div>
</template>
