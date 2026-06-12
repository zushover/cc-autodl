<script setup lang="ts">
import { ref, watch } from 'vue'
import type { Instance, GPUData, ProbeResult } from '../types'

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

const probeAnim = ref(false)
const deploying = ref(false)
watch(() => props.loading.probe, v => { if (v) probeAnim.value = true })

async function doDeploy() {
  if (!props.currentInstance || deploying.value) return
  deploying.value = true
  try {
    const res = await fetch(`http://127.0.0.1:8899/api/instances/${props.currentInstance.uuid}/deploy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify({}),
    })
    const data = await res.json()
    if (data.success) {
      alert(`Claude Code 已部署到服务器!\n\n连接: tmux attach -t claude-code\n\n${data.log?.join('\n') || ''}`)
    } else {
      alert('部署失败: ' + (data.error || '未知错误'))
    }
  } catch (e: unknown) {
    alert('部署请求失败: ' + (e instanceof Error ? e.message : '网络错误'))
  }
  deploying.value = false
}

function sb(s: string) { return s==='running'||s==='reachable'?'running':s==='no_gpu'?'warning':'stopped' }
function sl(s: string) { const m: Record<string,string>={running:'运行中',stopped:'已关机',no_gpu:'无卡',reachable:'可达'}; return m[s]||s }
function f(v: number|null|undefined, d=1) { return v==null?'--':v.toFixed(d) }
function fm(v: number|null|undefined) { return v==null?'--':v<0.01?'<0.01':v.toFixed(2) }
function memPercent(used: number|null|undefined, total: number|null|undefined): string {
  if (!total || !used) return '0%'
  return Math.min(100, (used/total)*100).toFixed(0) + '%'
}
</script>

<template>
  <div>
    <!-- 顶栏 -->
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
      <h1 style="font-size:1.3rem;font-weight:700;margin:0;letter-spacing:-0.3px;">服务器</h1>
      <div style="display:flex;gap:6px;">
        <button class="btn" @click="emit('syncPro')" :disabled="loading.sync" style="font-size:12px;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg>
          同步
        </button>
        <button class="btn btn-primary" @click="emit('openRegister')" style="font-size:12px;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          注册
        </button>
      </div>
    </div>

    <!-- ====== 有实例 ====== -->
    <div v-if="currentInstance" style="display:flex;flex-direction:column;gap:12px;">

      <!-- 实例选择 + 操作 -->
      <div style="display:flex;justify-content:space-between;align-items:center;background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:14px 18px;">
        <div style="display:flex;align-items:center;gap:10px;">
          <select :value="currentInstance.uuid" @change="emit('setCurrent', ($event.target as HTMLSelectElement).value)"
            style="font-size:13px;font-weight:600;padding:6px 10px;min-width:180px;border:none;background:var(--bg-hover);border-radius:6px;">
            <option v-for="i in instances" :key="i.uuid" :value="i.uuid">{{ i.alias || i.uuid.slice(0,10) }} · {{ i.gpu_type||'?' }}</option>
          </select>
          <span :class="'badge badge-'+sb(currentInstance.status)">{{ sl(currentInstance.status) }}</span>
          <span v-if="currentInstance.gpu_type" style="font-size:12px;color:var(--text-dim);">{{ currentInstance.gpu_type }}</span>
          <span v-if="currentInstance.price_per_hour" style="font-size:12px;color:var(--text-dim);">¥{{ currentInstance.price_per_hour }}/h</span>
        </div>
        <div style="display:flex;gap:5px;">
          <!-- ☀️ 一键部署 Claude Code -->
          <button class="btn btn-primary" @click="doDeploy" :disabled="deploying" style="font-size:12px;" title="一键部署 Claude Code 到服务器">
            <svg width="14" height="14" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="24" cy="24" r="5"/><path d="M24 2v6m0 32v6M8.5 8.5l4.2 4.2m22.6 22.6l4.2 4.2M2 24h6m32 0h6M8.5 39.5l4.2-4.2m22.6-22.6l4.2-4.2"/></svg>
            {{ deploying ? '部署中' : '部署 CC' }}
          </button>
          <button class="btn" @click="emit('probe')" :disabled="loading.probe" style="font-size:12px;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.35-4.35"/></svg>
            {{ loading.probe ? '探测中' : '探测' }}
          </button>
          <button class="btn" @click="emit('refreshGPU')" :disabled="loading.gpu" style="font-size:12px;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg>
          </button>
          <button class="btn btn-danger" @click="emit('shutdown')" style="font-size:12px;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v10"/><path d="M18.36 5.64a9 9 0 11-12.72 0"/></svg>
            关机
          </button>
        </div>
      </div>

      <!-- 探测中：呼吸动画 -->
      <div v-if="loading.probe" style="display:flex;align-items:center;justify-content:center;padding:32px;background:var(--bg-card);border:1px solid var(--border);border-radius:12px;">
        <div :class="probeAnim ? 'pulse-sun' : ''">
          <svg width="44" height="44" viewBox="0 0 48 48" fill="none" stroke="var(--text)" stroke-width="1.3">
            <circle cx="24" cy="24" r="5" stroke-width="2"/><path d="M24 2v5m0 34v5M8.5 8.5l3.5 3.5m24 24l3.5 3.5M2 24h5m34 0h5M8.5 39.5l3.5-3.5m24-24l3.5-3.5"/>
          </svg>
        </div>
      </div>

      <!-- 探测结果 -->
      <div v-else-if="probeResult?.reachable" style="display:flex;flex-direction:column;gap:10px;">

        <!-- GPU 概览卡 -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
          <!-- 利用率大数字 -->
          <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px;display:flex;flex-direction:column;align-items:center;justify-content:center;">
            <div style="font-size:10px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.8px;margin-bottom:12px;">GPU 利用率</div>
            <div style="font-size:3rem;font-weight:700;letter-spacing:-1.5px;line-height:1;">{{ f(gpuData.util_percent, 0) }}</div>
            <div style="font-size:13px;color:var(--text-dim);margin-top:4px;">%</div>
          </div>
          <!-- 显存 + 温度 + 进程 -->
          <div style="display:flex;flex-direction:column;gap:10px;">
            <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:16px;flex:1;">
              <div style="font-size:10px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.8px;margin-bottom:8px;">显存</div>
              <div style="font-size:1.5rem;font-weight:700;">{{ fm(gpuData.mem_used_gb) }}<span style="font-size:0.5em;font-weight:500;color:var(--text-dim);"> / {{ f(gpuData.mem_total_gb) }} GB</span></div>
              <div style="margin-top:8px;height:4px;background:var(--bg-hover);border-radius:2px;overflow:hidden;">
                <div :style="{width: memPercent(gpuData.mem_used_gb, gpuData.mem_total_gb), height:'100%', background:'var(--text)', borderRadius:'2px'}"></div>
              </div>
              <div v-if="gpuData.gpu_name" style="font-size:11px;color:var(--text-dim);margin-top:8px;">{{ gpuData.gpu_name }}</div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
              <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:14px;text-align:center;">
                <div style="font-size:10px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px;">温度</div>
                <div style="font-size:1.3rem;font-weight:700;">{{ f(gpuData.temp_c,0) }}<span style="font-size:0.5em;color:var(--text-dim);">°C</span></div>
              </div>
              <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:14px;text-align:center;">
                <div style="font-size:10px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px;">进程</div>
                <div style="font-size:1.3rem;font-weight:700;">{{ gpuData.processes?.length || 0 }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 系统信息 + 资源 双栏 -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
          <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:16px;">
            <div style="font-size:10px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.8px;margin-bottom:10px;">系统</div>
            <div style="font-size:12px;color:var(--text-secondary);line-height:2;">
              <div v-if="probeResult.hostname">{{ probeResult.hostname }}</div>
              <div v-if="probeResult.os" style="color:var(--text-dim);">{{ probeResult.os }}</div>
              <div v-if="probeResult.python" style="color:var(--text-dim);">{{ probeResult.python }}</div>
            </div>
          </div>
          <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:16px;">
            <div style="font-size:10px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.8px;margin-bottom:10px;">资源</div>
            <div style="font-size:12px;color:var(--text-secondary);line-height:2;">
              <div v-if="probeResult.disk">磁盘 {{ probeResult.disk }}</div>
              <div v-if="probeResult.ram">内存 {{ probeResult.ram }}</div>
            </div>
          </div>
        </div>

        <!-- SSH -->
        <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:14px 18px;">
          <div style="font-size:10px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px;">SSH</div>
          <code style="font-size:12px;color:var(--text-secondary);background:var(--bg-hover);padding:6px 10px;border-radius:6px;display:block;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;">
            ssh -p {{ currentInstance.ssh_port }} {{ currentInstance.ssh_user }}@{{ currentInstance.ssh_host }}
          </code>
        </div>

        <!-- GPU 进程列表 -->
        <div v-if="gpuData.processes?.length" style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:16px;">
          <div style="font-size:10px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.8px;margin-bottom:8px;">GPU 进程</div>
          <div v-for="p in gpuData.processes" :key="p.pid" style="display:flex;justify-content:space-between;font-size:12px;padding:4px 0;color:var(--text-secondary);border-bottom:1px solid var(--border-light);">
            <span>{{ p.name }}</span><span style="color:var(--text-dim);">PID {{ p.pid }} · {{ p.gpu_mem_mb }}MB</span>
          </div>
        </div>
      </div>

      <!-- 未探测 -->
      <div v-else-if="!loading.probe && !probeResult?.reachable" style="text-align:center;padding:28px;color:var(--text-dim);font-size:13px;background:var(--bg-card);border:1px solid var(--border);border-radius:12px;">
        {{ probeResult ? '不可达' : '点击「探测」获取实时 GPU 数据' }}
      </div>

    </div>

    <!-- ====== 无实例 ====== -->
    <div v-else style="text-align:center;padding:56px 20px;background:var(--bg-card);border:1px solid var(--border);border-radius:12px;">
      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" style="color:var(--text-dim);margin-bottom:12px;">
        <rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><circle cx="6" cy="6" r="1" fill="currentColor"/><circle cx="6" cy="18" r="1" fill="currentColor"/>
      </svg>
      <div style="font-weight:600;margin-bottom:6px;">暂无服务器</div>
      <div style="font-size:12px;color:var(--text-dim);margin-bottom:16px;">注册 GPU 实例开始使用</div>
      <button class="btn btn-primary" @click="emit('openRegister')">注册实例</button>
    </div>

    <!-- ====== 全部实例 ====== -->
    <div v-if="instances.length > 0" style="margin-top:20px;">
      <div style="font-size:10px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.8px;margin-bottom:8px;">全部实例 · {{ instances.length }}</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:8px;">
        <div v-for="inst in instances" :key="inst.uuid"
          :class="'glass-card' + (inst.uuid === currentInstance?.uuid ? ' glass-card-active' : '')"
          style="cursor:pointer;padding:12px;"
          @click="emit('setCurrent', inst.uuid)"
        >
          <div style="display:flex;align-items:center;gap:5px;margin-bottom:3px;">
            <span style="width:6px;height:6px;border-radius:50%;flex-shrink:0;"
              :style="{background:inst.status==='running'||inst.status==='reachable'?'var(--green)':inst.status==='no_gpu'?'#eab308':'var(--text-dim)'}"
            ></span>
            <span style="font-weight:600;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{{ inst.alias || inst.uuid.slice(0,10) }}</span>
            <span v-if="inst.uuid===currentInstance?.uuid" style="font-size:9px;color:var(--text-dim);margin-left:auto;border:1px solid var(--border);border-radius:3px;padding:0 4px;">当前</span>
          </div>
          <div style="font-size:11px;color:var(--text-dim);">{{ inst.gpu_type||'未知' }} · {{ sl(inst.status) }}</div>
          <div style="display:flex;gap:4px;margin-top:6px;">
            <button class="btn btn-ghost" style="font-size:10px;padding:2px 6px;" @click.stop="emit('probeInstance', inst.uuid)">探测</button>
            <button class="btn btn-ghost" style="font-size:10px;padding:2px 6px;color:var(--red);" @click.stop="emit('remove', inst.uuid)">删除</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pulse-sun { animation: pulseSun 1.4s ease-in-out infinite; }
@keyframes pulseSun {
  0%, 100% { transform: scale(1); opacity: 0.45; }
  50% { transform: scale(1.35); opacity: 1; }
}
</style>
