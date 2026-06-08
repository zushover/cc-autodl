<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'

const API = 'http://127.0.0.1:8899'

const tabs = [
  { id: 'dashboard', label: '仪表盘', icon: '📊' },
  { id: 'instances', label: '实例列表', icon: '🖥' },
  { id: 'cost', label: '费用分析', icon: '💰' },
  { id: 'logs', label: '日志终端', icon: '📋' },
  { id: 'settings', label: '设置', icon: '⚙' },
]

const currentTab = ref('dashboard')
const instances = ref<any[]>([])
const currentInstance = ref<any>(null)
const gpuData = ref<any>({})
const probeResult = ref<any>(null)  // 最近探测结果
const stats = ref({ total: 0, running: 0 })
const costData = ref<any>({})
const alerts = ref<any[]>([])
const logLines = ref<string[]>([])
const toast = reactive({ show: false, msg: '', ok: true, id: 0 })
const showRegister = ref(false)
const loading = reactive({ init: true, instances: false, sync: false, register: false, cost: false, gpu: false, probe: false })
const serverOnline = ref(false)
const gpuTypes = ref<any[]>([])
const regions = ref<string[]>([])

// ── 注册表单 ──
const regForm = reactive({
  source: 'web', uuid: '',
  ssh_string: '',           // SSH 连接字符串，一键解析
  ssh_host: '', ssh_port: 22, ssh_user: 'root',
  ssh_password: '',         // SSH 密码（AutoDL 提供的，如 ppPyRVTCfkGr）
  alias: '', gpu_type: '', region: '', price_per_hour: 0,
  status: 'stopped',        // 实例状态: stopped/running/no_gpu
  tags_str: '',
})

// 选择 GPU 后自动填价
function onGpuSelect() {
  const gpu = gpuTypes.value.find((g: any) => g.name === regForm.gpu_type)
  if (gpu) regForm.price_per_hour = gpu.price
}

function onPasteSsh() {
  setTimeout(() => parseSshString(), 100)
}

// SSH 连接字符串解析
async function parseSshString() {
  if (!regForm.ssh_string.trim()) return
  const resp = await fetch(API + '/api/parse-ssh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify({ ssh_string: regForm.ssh_string }),
  })
  if (!resp.ok) return
  const data = await resp.json()
  if (data.host) {
    regForm.ssh_host = data.host
    regForm.ssh_port = data.port
    regForm.ssh_user = data.user
    notify('✅ 已解析: ' + data.user + '@' + data.host + ':' + data.port)
  }
}

// ── 设置 ──
const settings = reactive({ token: '', ssh_key: '', hasToken: false })

const balanceDisplay = computed(() => {
  if (costData.value.balance_yuan != null) return costData.value.balance_yuan.toFixed(2)
  return '--'
})

function statusBadge(s: string) {
  if (s === 'running' || s === 'reachable') return 'running'
  if (s === 'stopped' || s === 'released' || s === 'shutdown') return 'stopped'
  if (s === 'no_gpu') return 'warning'
  if (s === 'powering_on' || s === 'powering_off') return 'warning'
  return 'stopped'
}

function statusLabel(s: string) {
  const map: any = { running: '运行中', stopped: '已关机', shutdown: '已关机', no_gpu: '无卡模式', reachable: '可达', powering_on: '开机中', powering_off: '关机中' }
  return map[s] || s || '未知'
}

// ── Toast ──
let toastTimer: any = null
function notify(msg: string, ok = true) {
  if (toastTimer) clearTimeout(toastTimer)
  toast.id = Date.now()
  toast.show = true; toast.msg = msg; toast.ok = ok
  toastTimer = setTimeout(() => toast.show = false, 5000)
}

function switchTab(id: string) { currentTab.value = id }

// ── API ──
let serverReady = false
async function waitForServer(maxRetries = 30) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const res = await fetch(API + '/api/stats')
      if (res.ok) { serverReady = true; serverOnline.value = true; return true }
    } catch (_) {}
    await new Promise(r => setTimeout(r, 500))
  }
  serverOnline.value = false
  return false
}

async function api(url: string, opts: any = {}) {
  if (!serverReady) { const ok = await waitForServer(); if (!ok) { notify('后端未启动', false); return null } }
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 30000)
  try {
    const headers: any = { 'Content-Type': 'application/json; charset=utf-8' }
    if (opts.headers) Object.assign(headers, opts.headers)
    const res = await fetch(API + url, { ...opts, headers, signal: controller.signal })
    clearTimeout(timer)
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      return { error: true, message: err?.error || `服务器错误 (${res.status})` }
    }
    return await res.json()
  } catch (e: any) {
    clearTimeout(timer)
    if (e.name === 'AbortError') { notify('请求超时', false); return { error: true, message: '请求超时' } }
    if (e.name === 'TypeError' && e.message === 'Failed to fetch') serverOnline.value = false
    notify('连接失败: ' + (e.message || ''), false)
    return null
  }
}

// ── 数据加载 ──
async function loadInstances() {
  loading.instances = true
  const data = await api('/api/instances')
  if (data && !data.error) {
    instances.value = data.instances || []
    stats.value = data.stats || { total: 0, running: 0 }
    currentInstance.value = instances.value.find((i: any) => i.is_current) || null
  }
  loading.instances = false
}

async function loadCost(force = false) {
  loading.cost = true
  const data = await api('/api/cost' + (force ? '?refresh=1' : ''))
  if (data && !data.error) costData.value = data
  loading.cost = false
}

async function loadAlerts() {
  const data = await api('/api/alerts')
  if (data && !data.error) alerts.value = data.alerts || []
}

async function loadGpuTypes(source = 'web') {
  const data = await api('/api/gpu-types?source=' + source)
  if (data && !data.error) gpuTypes.value = data.gpu_types || []
}

async function loadRegions() {
  const data = await api('/api/regions')
  if (data && !data.error) regions.value = data.regions || []
}

// ── 操作 ──
async function setCurrent(uuid: string) {
  const data = await api('/api/instances/' + uuid + '/set-current', { method: 'POST' })
  if (data?.ok) { await loadInstances(); notify('已切换当前实例') }
}

async function refreshGPU() {
  if (!currentInstance.value) return notify('请先选择一个实例', false)
  loading.gpu = true
  const data = await api('/api/instances/' + currentInstance.value.uuid + '/gpu')
  if (data && !data.error) { gpuData.value = data }
  else if (data?.error) notify(data.message || 'GPU 采集失败（需要SSH密钥）', false)
  loading.gpu = false
}

async function probeCurrent() { if (currentInstance.value) await probeInstance(currentInstance.value.uuid) }
async function probeInstance(uuid: string) {
  loading.probe = true
  notify('🔍 正在探测实例...')
  const data = await api('/api/instances/' + uuid + '/probe', { method: 'POST' })
  loading.probe = false
  if (!data) return

  probeResult.value = data

  if (data?.reachable) {
    const statusText: any = { running: '运行中', no_gpu: '无卡模式', stopped: '已关机' }
    const s = data.status || 'reachable'
    notify('✅ 可达 · ' + (statusText[s] || s) + (data.gpu ? ' · GPU: ' + data.gpu.gpu_name : ' · 无GPU'))

    // 立即更新当前实例状态（不等列表刷新，避免闪烁）
    if (currentInstance.value && currentInstance.value.uuid === uuid) {
      currentInstance.value.status = s
    }

    // 更新 GPU 数据
    if (data.gpu) {
      gpuData.value = {
        util_percent: data.gpu.util_percent,
        mem_used_gb: data.gpu.mem_used_gb,
        mem_total_gb: data.gpu.mem_total_gb,
        temp_c: data.gpu.temp_c,
        gpu_name: data.gpu.gpu_name,
        processes: data.processes || [],
      }
    } else {
      gpuData.value = {}
    }
    await loadInstances()
  } else {
    // 不可达 → 立即标记为已关机
    if (currentInstance.value && currentInstance.value.uuid === uuid) {
      currentInstance.value.status = 'stopped'
    }
    notify('❌ 不可达: ' + (data?.error || 'SSH连接失败，可能已关机或密码错误'), false)
    await loadInstances()
  }
}

async function removeInstance(uuid: string) {
  if (!confirm('确认注销此实例？')) return
  const data = await api('/api/instances/' + uuid, { method: 'DELETE' })
  if (data?.ok) { await loadInstances(); notify('已注销') }
}

async function shutdownInstance(uuid: string) {
  if (!confirm('确认要关机此实例吗？')) return
  notify('正在发送关机指令...')
  const data = await api('/api/instances/' + uuid + '/shutdown', { method: 'POST' })
  if (data?.ok) { notify('✅ 关机指令已发送'); await loadInstances(); probeResult.value = null; gpuData.value = {} }
  else notify('关机失败: ' + (data?.error || '未知错误'), false)
}

async function dismissAlert(id: string) {
  await api('/api/alerts/' + id + '/dismiss', { method: 'POST' })
  await loadAlerts()
}

async function syncPro() {
  loading.sync = true
  const data = await api('/api/pro/sync', { method: 'POST' })
  if (data?.ok) { await loadInstances(); notify('✅ 同步成功，共 ' + data.synced + ' 个实例') }
  else if (data?.error) notify('同步失败: ' + data.message, false)
  loading.sync = false
}

// ── 注册 ──
function cancelRegister() {
  showRegister.value = false
  loading.register = false
  regForm.ssh_string = ''; regForm.ssh_host = ''; regForm.ssh_port = 22
  regForm.ssh_user = 'root'; regForm.ssh_password = ''; regForm.alias = ''
  regForm.gpu_type = ''; regForm.region = ''; regForm.price_per_hour = 0
  regForm.status = 'stopped'; regForm.tags_str = ''
}

function openRegister() {
  loadGpuTypes(regForm.source)
  loadRegions()
  showRegister.value = true
}

async function doRegister() {
  if (regForm.source !== 'pro') {
    if (!regForm.ssh_host.trim()) { notify('请输入 SSH 主机地址', false); return }
    if (!regForm.alias.trim()) { notify('请输入别名', false); return }
    if (!regForm.ssh_password.trim()) { notify('请输入 SSH 密码（AutoDL 提供）', false); return }
  } else {
    if (!regForm.uuid.trim()) { notify('请输入 Pro 实例 UUID', false); return }
  }

  loading.register = true
  const body: any = { source: regForm.source, status: regForm.status }
  if (regForm.source === 'pro') {
    body.uuid = regForm.uuid
  } else {
    body.ssh_host = regForm.ssh_host; body.ssh_port = regForm.ssh_port
    body.ssh_user = regForm.ssh_user; body.ssh_password = regForm.ssh_password
    body.alias = regForm.alias
    body.tags = regForm.tags_str ? regForm.tags_str.split(',').map((s: string) => s.trim()).filter(Boolean) : []
    if (regForm.source === 'web') {
      body.gpu_type = regForm.gpu_type; body.region = regForm.region
      body.price_per_hour = regForm.price_per_hour
    }
    if (regForm.source === 'ssh') {
      body.host = regForm.ssh_host; body.port = regForm.ssh_port
      body.username = regForm.ssh_user; body.password = regForm.ssh_password
    }
  }
  const data = await api('/api/instances/register', { method: 'POST', body: JSON.stringify(body) })
  if (data?.instance) {
    notify('✅ 注册成功: ' + (data.instance.alias || data.instance.uuid?.slice(0, 14)))
    showRegister.value = false; await loadInstances()
  } else if (data?.error) {
    notify('注册失败: ' + data.message, false)
  }
  loading.register = false
}

// ── 设置 ──
async function loadSettings() {
  const data = await api('/api/settings')
  if (data && !data.error) {
    settings.token = data.token || ''
    settings.ssh_key = data.ssh_key || ''
    settings.hasToken = !!(data.token && data.token !== 'your-token-here')
  }
}

async function saveSetting() {
  const data = await api('/api/settings', {
    method: 'POST',
    body: JSON.stringify({ token: settings.token, ssh_key: settings.ssh_key }),
  })
  if (data?.ok) {
    settings.hasToken = !!(settings.token && settings.token !== 'your-token-here')
    notify('✅ 设置已保存')
    costData.value = {}
    loadCost(true)
  } else if (data?.error) {
    notify('保存失败: ' + data.message, false)
  }
}

// ── SSE ──
let sseSource: EventSource | null = null
let sseTimer: any = null
function connectSSE() {
  if (sseSource) sseSource.close()
  sseSource = new EventSource(API + '/api/stream')
  sseSource.addEventListener('gpu', (e: any) => { try { const d = JSON.parse(e.data); if (d.uuid === currentInstance.value?.uuid) gpuData.value = d } catch (_) {} })
  sseSource.addEventListener('instance_registered', () => { loadInstances() })
  sseSource.addEventListener('instance_status', () => { loadInstances() })
  sseSource.addEventListener('instance_removed', () => { loadInstances() })
  sseSource.addEventListener('current_changed', () => { loadInstances() })
  sseSource.addEventListener('pro_synced', () => { loadInstances(); loadCost() })
  sseSource.addEventListener('settings_updated', () => { loadCost() })
  sseSource.onerror = () => { if (sseTimer) clearTimeout(sseTimer); sseTimer = setTimeout(connectSSE, 5000) }
}

let balanceTimer: any = null

onMounted(async () => {
  await waitForServer()
  await Promise.all([loadInstances(), loadCost(), loadAlerts(), loadSettings(), loadGpuTypes(), loadRegions()])
  loading.init = false
  connectSSE()
  balanceTimer = setInterval(() => loadCost(), 60000)
})

onUnmounted(() => {
  if (sseSource) sseSource.close()
  if (sseTimer) clearTimeout(sseTimer)
  if (toastTimer) clearTimeout(toastTimer)
  if (balanceTimer) clearInterval(balanceTimer)
})
</script>

<template>
  <div v-if="toast.show" :key="toast.id" :class="'toast ' + (toast.ok ? 'toast-ok' : 'toast-err')" @click="toast.show=false">{{ toast.msg }}</div>

  <div style="display:flex;height:100vh;">
    <!-- SIDEBAR -->
    <div style="width:220px;background:#0d0d10;border-right:1px solid rgba(255,255,255,0.04);display:flex;flex-direction:column;padding:16px 12px;flex-shrink:0;">
      <div style="padding:8px 16px 20px;font-weight:800;font-size:15px;letter-spacing:-0.3px;color:#e4e4e7;">⚡ AutoDL Manager</div>
      <nav style="flex:1;">
        <div v-for="tab in tabs" :key="tab.id" :class="'sidebar-link' + (currentTab === tab.id ? ' active' : '')" @click="switchTab(tab.id)">
          <span style="width:20px;text-align:center;">{{ tab.icon }}</span> {{ tab.label }}
        </div>
      </nav>
      <div class="glass-card" style="margin-top:auto;font-size:12px;">
        <div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span class="text-dim">余额</span><span style="font-weight:700;">{{ loading.init ? '...' : '¥'+balanceDisplay }}</span></div>
        <div style="display:flex;justify-content:space-between;"><span class="text-dim">实例</span><span><span v-if="loading.init">...</span><span v-else><span style="color:#4ade80;">{{ stats.running }}</span> / {{ stats.total }}</span></span></div>
      </div>
    </div>

    <!-- MAIN -->
    <div style="flex:1;overflow-y:auto;padding:24px;">
      <div v-if="loading.init" class="glass-card" style="text-align:center;padding:60px;"><div style="font-size:2rem;">⏳</div><div style="color:#a1a1aa;">加载中...</div></div>

      <template v-else>

      <!-- DASHBOARD -->
      <div v-if="currentTab === 'dashboard'">
        <h1 style="font-size:1.4rem;font-weight:700;margin-bottom:20px;">仪表盘</h1>

        <!-- 当前实例详情卡片 -->
        <div v-if="currentInstance" class="glass-card" style="margin-bottom:20px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
            <div>
              <span :class="'badge badge-' + statusBadge(currentInstance.status)">{{ statusLabel(currentInstance.status) }}</span>
              <span :class="'badge badge-' + currentInstance.source" style="margin-left:6px;">{{ currentInstance.source }}</span>
              <strong style="margin-left:8px;font-size:1.1rem;">{{ currentInstance.alias || currentInstance.uuid?.slice(0,14) }}</strong>
              <span v-if="currentInstance.gpu_type" style="font-size:13px;color:#71717a;margin-left:8px;">{{ currentInstance.gpu_type }}</span>
            </div>
            <div style="display:flex;gap:6px;">
              <button class="btn" @click="probeCurrent" :disabled="loading.probe" style="min-width:90px;">
                {{ loading.probe ? '⏳ 探测中...' : '🔍 探测' }}
              </button>
              <button class="btn" @click="refreshGPU" :disabled="loading.gpu">{{ loading.gpu?'⏳':'🔄' }} 刷新</button>
              <button class="btn btn-danger" @click="shutdownInstance(currentInstance.uuid)" :disabled="loading.probe" style="font-size:12px;">⏻ 关机</button>
            </div>
          </div>

          <!-- GPU 有数据时显示指标 -->
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

          <!-- 探测过但无 GPU（无卡模式） -->
          <div v-else-if="currentInstance.status === 'no_gpu'" class="glass" style="text-align:center;padding:16px;margin-bottom:12px;color:#facc15;">
            ⚡ 无卡模式 — 实例运行中但未加载 GPU（¥0.01/h）
          </div>

          <!-- 未探测时提示 -->
          <div v-else-if="!loading.probe && !probeResult" class="glass" style="text-align:center;padding:20px;margin-bottom:12px;color:#52525b;">
            💡 点击「🔍 探测」获取实时状态
          </div>

          <!-- 运行进程列表 -->
          <div v-if="gpuData.processes && gpuData.processes.length" style="margin-bottom:12px;">
            <div style="font-size:12px;color:#71717a;margin-bottom:6px;">🏃 运行中的 GPU 进程</div>
            <div v-for="p in gpuData.processes" :key="p.pid" class="glass" style="padding:8px 12px;margin-bottom:4px;display:flex;justify-content:space-between;align-items:center;">
              <span style="font-size:13px;">{{ p.name }}</span>
              <span style="font-size:11px;color:#71717a;">PID {{ p.pid }} · {{ p.gpu_mem_mb }}MB</span>
            </div>
          </div>

          <!-- 系统信息 -->
          <div v-if="probeResult?.reachable" style="display:flex;gap:16px;font-size:11px;color:#52525b;flex-wrap:wrap;">
            <span v-if="probeResult.hostname">🖥 {{ probeResult.hostname }}</span>
            <span v-if="probeResult.python">{{ probeResult.python }}</span>
            <span v-if="probeResult.disk">💾 {{ probeResult.disk }}</span>
            <span v-if="probeResult.ram">{{ probeResult.ram }}</span>
          </div>

          <!-- SSH 信息 -->
          <div v-if="currentInstance.ssh_host" style="margin-top:8px;font-size:12px;color:#52525b;">
            SSH: {{ currentInstance.ssh_user }}@{{ currentInstance.ssh_host }}:{{ currentInstance.ssh_port }}
          </div>
        </div>

        <!-- 无当前实例 -->
        <div v-if="!currentInstance && !loading.instances" class="glass-card" style="text-align:center;padding:40px;">
          <div style="font-size:2rem;">🖥️</div><div style="color:#a1a1aa;">未设置当前实例</div>
          <div style="font-size:13px;color:#52525b;">在「实例列表」中选择或同步 Pro API</div>
        </div>

        <!-- 所有实例 -->
        <h2 style="font-size:1.05rem;font-weight:600;margin-bottom:12px;">所有实例</h2>
        <div v-if="instances.length===0" class="glass-card" style="text-align:center;padding:20px;color:#52525b;">暂无实例</div>
        <div v-else style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;">
          <div v-for="inst in instances" :key="inst.uuid" :class="'glass-card'+(inst.is_current?' glass-card-active':'')" style="cursor:pointer;" @click="setCurrent(inst.uuid)">
            <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;"><span style="width:8px;height:8px;border-radius:50%;" :style="{background: inst.status==='running'||inst.status==='reachable'?'#4ade80':inst.status==='no_gpu'?'#facc15':'#71717a'}"></span><span style="font-weight:600;font-size:13px;">{{ inst.alias || inst.uuid.slice(0,14) }}</span></div>
            <div style="font-size:12px;color:#71717a;">{{ inst.gpu_type||'GPU' }} · {{ inst.source }} · {{ statusLabel(inst.status) }}</div>
          </div>
        </div>
      </div>

      <!-- INSTANCES -->
      <div v-if="currentTab === 'instances'">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
          <h1 style="font-size:1.4rem;font-weight:700;">实例列表</h1>
          <div style="display:flex;gap:8px;">
            <button class="btn" @click="syncPro" :disabled="loading.sync">{{ loading.sync?'⏳ 同步中...':'🔄 同步 Pro API' }}</button>
            <button class="btn btn-primary" @click="openRegister">+ 注册实例</button>
          </div>
        </div>
        <div v-if="instances.length===0" class="glass-card" style="text-align:center;padding:40px;color:#52525b;">暂无实例<br><small>点击「同步 Pro API」或「注册实例」</small></div>
        <div v-else class="glass" style="overflow:hidden;">
          <table><thead><tr><th>状态</th><th>来源</th><th>名称</th><th>GPU</th><th>区域</th><th>单价</th><th>操作</th></tr></thead>
            <tbody><tr v-for="inst in instances" :key="inst.uuid" :style="{background:inst.is_current?'rgba(212,116,74,0.04)':''}">
              <td><span :class="'badge badge-'+statusBadge(inst.status)">{{ statusLabel(inst.status) }}</span></td>
              <td><span :class="'badge badge-'+inst.source">{{ inst.source }}</span></td>
              <td><span style="font-weight:600;">{{ inst.alias||inst.uuid.slice(0,14) }}</span><span v-if="inst.is_current" style="color:#d4744a;"> ★</span></td>
              <td>{{ inst.gpu_type||'--' }}</td><td>{{ inst.region||'--' }}</td><td>{{ inst.price_per_hour?'¥'+inst.price_per_hour+'/h':'免费' }}</td>
              <td><div style="display:flex;gap:4px;">
                <button v-if="!inst.is_current" class="btn" style="font-size:11px;padding:4px 8px;" @click="setCurrent(inst.uuid)">切换</button>
                <button class="btn" style="font-size:11px;padding:4px 8px;" @click="probeInstance(inst.uuid)">探测</button>
                <button class="btn btn-danger" style="font-size:11px;padding:4px 8px;" @click="removeInstance(inst.uuid)">注销</button>
              </div></td>
            </tr></tbody>
          </table>
        </div>
      </div>

      <!-- COST -->
      <div v-if="currentTab === 'cost'">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
          <h1 style="font-size:1.4rem;font-weight:700;">费用分析</h1>
          <button class="btn" @click="loadCost(true)" :disabled="loading.cost">{{ loading.cost?'⏳':'🔄' }} 刷新</button>
        </div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px;">
          <div class="glass-card" style="text-align:center;"><div class="metric-num">¥{{ costData.today_cost||'0.00' }}</div><div class="metric-label">今日消费</div></div>
          <div class="glass-card" style="text-align:center;"><div class="metric-num">¥{{ costData.week_cost||'0.00' }}</div><div class="metric-label">本周消费</div></div>
          <div class="glass-card" style="text-align:center;"><div class="metric-num accent">¥{{ costData.balance_yuan!=null?costData.balance_yuan:'--' }}</div><div class="metric-label">当前余额</div></div>
          <div class="glass-card" style="text-align:center;"><div class="metric-num">{{ costData.runway_days??'--' }}</div><div class="metric-label">预估可用天数</div></div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:20px;">
          <div class="glass-card"><div style="color:#71717a;font-size:12px;">累计消费</div><div style="font-size:1.3rem;font-weight:700;">¥{{ costData.total_spent?.toFixed(2)||'--' }}</div></div>
          <div class="glass-card"><div style="color:#71717a;font-size:12px;">代金券</div><div style="font-size:1.3rem;font-weight:700;">¥{{ costData.voucher_balance?.toFixed(2)||'0.00' }}</div></div>
          <div class="glass-card"><div style="color:#71717a;font-size:12px;">日均消费</div><div style="font-size:1.3rem;font-weight:700;">¥{{ costData.daily_rate_yuan||'0.00' }}</div></div>
        </div>
      </div>

      <!-- LOGS -->
      <div v-if="currentTab === 'logs'">
        <h1 style="font-size:1.4rem;font-weight:700;margin-bottom:12px;">日志终端</h1>
        <div v-if="!currentInstance" class="glass-card" style="text-align:center;padding:40px;">请先选择一个实例</div>
        <div v-else class="glass" style="background:#000;padding:16px;font-family:monospace;font-size:13px;max-height:500px;overflow-y:auto;">
          <div v-if="logLines.length===0" style="color:#52525b;">等待日志...</div>
          <div v-for="(line,i) in logLines" :key="i" style="line-height:1.6;" :style="{color:line.includes('NaN')?'#f87171':line.includes('loss')?'#60a5fa':line.includes('Step')?'#4ade80':'#a1a1aa'}">{{ line }}</div>
        </div>
      </div>

      <!-- SETTINGS -->
      <div v-if="currentTab === 'settings'">
        <h1 style="font-size:1.4rem;font-weight:700;margin-bottom:20px;">设置</h1>
        <div class="glass-card" style="margin-bottom:12px;">
          <div style="font-weight:600;margin-bottom:12px;">AutoDL 开发者 Token</div>
          <div v-if="settings.hasToken" style="margin-bottom:8px;"><span class="badge badge-running">✅ 已配置</span></div>
          <div style="display:flex;gap:8px;"><input v-model="settings.token" type="password" placeholder="输入 AutoDL 开发者 Token" style="flex:1;"><button class="btn btn-primary" @click="saveSetting">保存</button></div>
          <div style="font-size:11px;color:#52525b;margin-top:6px;">获取: autodl.com → 控制台 → 设置 → 开发者 Token</div>
        </div>

        <div class="glass-card" style="margin-bottom:12px;">
          <div style="font-weight:600;margin-bottom:12px;">SSH 登录方式说明</div>
          <div style="font-size:13px;color:#a1a1aa;line-height:1.8;">
            <strong>🔑 密码登录（推荐，简单）</strong><br>
            每个 AutoDL 实例都有独立的 SSH 密码（如 <code style="background:rgba(255,255,255,0.06);padding:2px 6px;">ppPyRVTCfkGr</code>），<br>
            在 AutoDL 控制台 → 实例 → SSH 连接 → 复制密码。<br>
            注册实例时直接填入密码即可。<br><br>
            <strong>🔐 密钥登录（高级，免密）</strong><br>
            1. 终端运行 <code style="background:rgba(255,255,255,0.06);padding:2px 6px;">ssh-keygen -t rsa</code> 生成密钥对<br>
            2. 将公钥 <code style="background:rgba(255,255,255,0.06);padding:2px 6px;">id_rsa.pub</code> 上传到 autodl.com → 账号 → SSH 密钥<br>
            3. 此处填入私钥路径 <code style="background:rgba(255,255,255,0.06);padding:2px 6px;">C:\\Users\\24860\\.ssh\\id_rsa</code><br>
            4. 已有实例需重启生效
          </div>
        </div>

        <div class="glass-card"><div style="font-weight:600;margin-bottom:12px;">系统状态</div>
          <p style="font-size:13px;color:#71717a;"><span :style="{color:serverOnline?'#4ade80':'#f87171'}">后端: {{ serverOnline?'🟢 在线':'🔴 离线' }}</span> · GPU采集: 120s · 余额告警: ¥50</p>
        </div>
      </div>
      </template>
    </div>
  </div>

  <!-- REGISTER DIALOG -->
  <div v-if="showRegister" class="dialog-overlay" @click.self="cancelRegister">
    <div class="dialog" style="width:540px;max-height:85vh;">
      <h3>注册实例</h3>

      <!-- 来源类型 -->
      <div class="form-group">
        <label>来源</label>
        <div style="display:flex;gap:8px;">
          <button :class="'btn'+(regForm.source==='web'?' btn-primary':'')" @click="regForm.source='web'; loadGpuTypes('web')" style="flex:1;">Web 控制台</button>
          <button :class="'btn'+(regForm.source==='ssh'?' btn-primary':'')" @click="regForm.source='ssh'" style="flex:1;">自定义 SSH</button>
          <button :class="'btn'+(regForm.source==='pro'?' btn-primary':'')" @click="regForm.source='pro'" style="flex:1;">Pro API</button>
        </div>
      </div>

      <!-- Pro 模式 -->
      <template v-if="regForm.source==='pro'">
        <div class="form-group"><label>Pro 实例 UUID <span style="color:#f87171;">*</span></label><input v-model="regForm.uuid" placeholder="pro-xxxxxxxx"></div>
      </template>

      <!-- Web/SSH 模式 -->
      <template v-else>
        <!-- SSH 连接字符串解析 -->
        <div class="form-group">
          <label>SSH 连接命令 <span style="font-size:11px;color:#71717a;">（粘贴自动解析）</span></label>
          <div style="display:flex;gap:6px;">
            <input v-model="regForm.ssh_string" placeholder="例如: ssh -p 50479 root@connect.bjb2.seetacloud.com" style="flex:1;font-size:12px;" @paste="onPasteSsh">
            <button class="btn" @click="parseSshString" style="white-space:nowrap;">🔍 解析</button>
          </div>
        </div>

        <div class="form-row">
          <div class="form-group"><label>主机 <span style="color:#f87171;">*</span></label><input v-model="regForm.ssh_host" placeholder="connect.xxx.autodl.com"></div>
          <div class="form-group"><label>端口</label><input v-model.number="regForm.ssh_port" type="number" style="width:80px;"></div>
          <div class="form-group"><label>用户</label><input v-model="regForm.ssh_user" style="width:80px;"></div>
        </div>

        <div class="form-group">
          <label>SSH 密码 <span style="color:#f87171;">*</span> <span style="font-size:11px;color:#71717a;">（AutoDL 控制台复制）</span></label>
          <input v-model="regForm.ssh_password" type="password" placeholder="例如: ppPyRVTCfkGr">
          <div style="font-size:11px;color:#52525b;margin-top:4px;">AutoDL 实例页 → SSH 连接 → 复制密码（非密钥文件）</div>
        </div>

        <!-- GPU 下拉 -->
        <div class="form-row" v-if="regForm.source==='web'">
          <div class="form-group"><label>GPU 型号</label>
            <select v-model="regForm.gpu_type" @change="onGpuSelect"><option value="">-- 选择 GPU --</option><option v-for="g in gpuTypes" :key="g.name" :value="g.name">{{ g.name }} ({{ g.vram }})</option></select>
          </div>
          <div class="form-group"><label>区域</label>
            <select v-model="regForm.region"><option value="">-- 选择区域 --</option><option v-for="r in regions" :key="r" :value="r">{{ r }}</option></select>
          </div>
        </div>

        <div class="form-row">
          <div class="form-group"><label>别名 <span style="color:#f87171;">*</span></label><input v-model="regForm.alias" placeholder="北京3090-训练"></div>
          <div class="form-group"><label>初始状态</label>
            <select v-model="regForm.status"><option value="stopped">已关机</option><option value="running">运行中</option><option value="no_gpu">无卡模式</option></select>
          </div>
        </div>

        <div class="form-group" v-if="regForm.source==='web'"><label>单价 (¥/h)</label><input v-model.number="regForm.price_per_hour" type="number" step="0.01"></div>
        <div class="form-group"><label>标签</label><input v-model="regForm.tags_str" placeholder="微调, Qwen (逗号分隔)"></div>
      </template>

      <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:16px;">
        <button class="btn" @click="cancelRegister">取消</button>
        <button class="btn btn-primary" @click="doRegister" :disabled="loading.register">{{ loading.register?'⏳ 注册中...':'注册' }}</button>
      </div>
    </div>
  </div>
</template>
