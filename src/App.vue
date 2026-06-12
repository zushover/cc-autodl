<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import type { Instance, GPUData, ProbeResult, CostData, Alert, Tab, SettingsData } from './types'
import {
  waitForServer, isServerReady,
  loadInstances, setCurrent, getGPU, probeInstance, removeInstance, shutdownInstance,
  syncPro, loadCost, loadAlerts, loadSettings, saveSettings, createSSEStream,
} from './api'
import { useToast } from './composables/useToast'
import Toast from './components/Toast.vue'
import Loading from './components/Loading.vue'
import Sidebar from './components/Sidebar.vue'
import Dashboard from './components/Dashboard.vue'
import InstanceList from './components/InstanceList.vue'
import CostAnalysis from './components/CostAnalysis.vue'
import LogTerminal from './components/LogTerminal.vue'
import SettingsPanel from './components/SettingsPanel.vue'
import RegisterDialog from './components/RegisterDialog.vue'
import AgentLog from './components/AgentLog.vue'
import TopBar from './components/TopBar.vue'

// ── Agent 类型 ──

interface AgentStep {
  id: number; timestamp: string; type: string; content: string; toolName?: string
}
interface AgentConversation {
  id: number; query: string; steps: AgentStep[]
}

// ── State ──

const tabs: Tab[] = [
  { id: 'dashboard', label: '仪表盘', icon: '' },
  { id: 'instances', label: '实例列表', icon: '' },
  { id: 'agent', label: 'AI Agents', icon: '' },
  { id: 'cost', label: '费用分析', icon: '' },
  { id: 'logs', label: '日志终端', icon: '' },
  { id: 'settings', label: '设置', icon: '' },
]

function handleSelectInstance(uuid: string) {
  doSetCurrent(uuid)
}

function handleNavTo(tab: string) {
  currentTab.value = tab
}

const currentTab = ref<string>('dashboard')
const instances = ref<Instance[]>([])
const currentInstance = ref<Instance | null>(null)
const gpuData = ref<GPUData>({})
const probeResult = ref<ProbeResult | null>(null)
const costData = ref<CostData>({} as CostData)
const alerts = ref<Alert[]>([])
const logLines = ref<string[]>([])
const serverOnline = ref(false)
const toastId = ref(0)

// ── 设置状态（在 App.vue 中，永不丢失）──

const settingsData = ref<SettingsData>({ token: '', ssh_key: '', hasToken: false })

async function refreshSettings() {
  const data = await loadSettings()
  if (data && !(data as any).error) {
    data.hasToken = !!(data.token && data.token !== 'your-token-here')
    settingsData.value = data
  }
}

async function doSaveSettings(token: string, sshKey: string, llmApiKey?: string, llmApiBase?: string, llmModel?: string) {
  const data = await saveSettings(token, sshKey, llmApiKey, llmApiBase, llmModel)
  if (data?.ok) {
    await refreshSettings()
    notify('设置已保存')
    refreshCost(true)  // 新 token 可能影响余额查询
  }
}

// ── Agent 状态（在 App.vue 中，永不丢失）──

const agentConversations = ref<AgentConversation[]>([])
const agentQuery = ref('')
const agentLoading = ref(false)
const agentMemoryStats = ref({ conversations: 0, experiments: 0, decisions: 0 })

function agentNow() { return new Date().toLocaleTimeString() }

async function sendAgentQuery(text?: string) {
  const q = text || agentQuery.value.trim()
  if (!q || agentLoading.value) return
  agentLoading.value = true
  agentQuery.value = ''

  const conv: AgentConversation = { id: Date.now(), query: q, steps: [] }
  conv.steps.push({ id: Date.now(), timestamp: agentNow(), type: 'user', content: q })
  agentConversations.value.push(conv)

  // thinking
  const tid = Date.now()
  conv.steps.push({ id: tid, timestamp: agentNow(), type: 'thinking', content: '正在分析请求...' })

  try {
    const res = await fetch('http://127.0.0.1:8899/api/agent/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify({ query: q }),
    })
    const data = await res.json()

    // 移除 thinking
    conv.steps = conv.steps.filter(s => s.id !== tid)

    if (data.steps && Array.isArray(data.steps)) {
      for (const s of data.steps) {
        if (s.type === 'user_input') continue
        if (s.type === 'tool_call') {
          const args = s.tool_args ? JSON.stringify(s.tool_args) : ''
          const shortArgs = args.length > 200 ? args.slice(0, 200) + '...' : args
          conv.steps.push({ id: Date.now(), timestamp: agentNow(), type: 'tool_call', content: shortArgs ? '参数: ' + shortArgs : '', toolName: s.tool_name })
        } else if (s.type === 'tool_result') {
          const c = (s.content || '').length > 500 ? (s.content || '').slice(0, 500) + '...' : (s.content || '')
          conv.steps.push({ id: Date.now(), timestamp: agentNow(), type: 'tool_result', content: c, toolName: s.tool_name })
        } else if (s.type === 'thinking' && s.content) {
          conv.steps.push({ id: Date.now(), timestamp: agentNow(), type: 'thinking', content: s.content })
        }
      }
    }

    if (data.answer) {
      conv.steps.push({ id: Date.now(), timestamp: agentNow(), type: 'answer', content: data.answer })
    } else if (data.error) {
      conv.steps.push({ id: Date.now(), timestamp: agentNow(), type: 'answer', content: '错误: ' + data.error })
    }
  } catch (e: unknown) {
    conv.steps.push({ id: Date.now(), timestamp: agentNow(), type: 'answer', content: '连接失败: 请确认服务已启动 (python sidecar.py)' })
  }

  agentLoading.value = false
  refreshAgentMemory()
}

async function refreshAgentMemory() {
  try {
    const res = await fetch('http://127.0.0.1:8899/api/agent/status')
    const data = await res.json()
    if (data.memory) agentMemoryStats.value = data.memory
  } catch (_) { /* ignore */ }
}

const loading = reactive({
  init: true, instances: false, sync: false, register: false,
  cost: false, gpu: false, probe: false,
})

const registerDialog = ref<InstanceType<typeof RegisterDialog> | null>(null)
const { toast, notify, clearToast } = useToast()

// ── Computed ──

const stats = computed(() => ({
  total: instances.value.length,
  running: instances.value.filter(i => i.status === 'running' || i.status === 'reachable').length,
}))

const balanceDisplay = computed(() => {
  if (costData.value.total_balance != null) return costData.value.total_balance.toFixed(2)
  return '--'
})

// ── Data loading ──

async function refreshInstances() {
  loading.instances = true
  const data = await loadInstances()
  if (data && !(data as any).error) {
    instances.value = data.instances || []
    currentInstance.value = instances.value.find(i => i.is_current) || null
  }
  loading.instances = false
}

async function refreshCost(force = false) {
  loading.cost = true
  try {
    const data = await loadCost(force)
    if (data) {
      if ((data as any).error) {
        console.warn('Cost API error:', (data as any).message)
      } else {
        costData.value = data as CostData
      }
    }
  } catch (e) {
    console.warn('Cost fetch failed:', e)
  }
  loading.cost = false
}

async function refreshAlerts() {
  const data = await loadAlerts()
  if (data && !(data as any).error) alerts.value = data.alerts || []
}

// ── Actions ──

async function doSetCurrent(uuid: string) {
  const data = await setCurrent(uuid)
  if (data?.ok) { await refreshInstances(); notify('已切换当前实例') }
}

async function doRefreshGPU() {
  if (!currentInstance.value) { notify('请先选择一个实例', false); return }
  loading.gpu = true
  const data = await getGPU(currentInstance.value.uuid)
  if (data && !(data as any).error) { gpuData.value = data as GPUData }
  else if (data && (data as any).error) notify((data as any).message || 'GPU 采集失败', false)
  loading.gpu = false
}

async function doProbeCurrent() {
  if (currentInstance.value) await doProbe(currentInstance.value.uuid)
}

async function doProbe(uuid: string) {
  loading.probe = true
  notify('🔍 正在探测实例...')
  const data = await probeInstance(uuid)
  loading.probe = false
  if (!data) return

  probeResult.value = data as ProbeResult

  if (data.reachable) {
    const statusLabels: Record<string, string> = { running: '运行中', no_gpu: '无卡模式', stopped: '已关机' }
    const s = data.status || 'reachable'
    notify('✅ 可达 · ' + (statusLabels[s] || s) + (data.gpu ? ' · GPU: ' + data.gpu.gpu_name : ' · 无GPU'))

    if (currentInstance.value && currentInstance.value.uuid === uuid) {
      currentInstance.value.status = s as Instance['status']
    }
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
    await refreshInstances()
  } else {
    if (currentInstance.value && currentInstance.value.uuid === uuid) {
      currentInstance.value.status = 'stopped'
    }
    notify('❌ 不可达: ' + (data.error || 'SSH连接失败'), false)
    await refreshInstances()
  }
}

async function doShutdownCurrent() {
  if (!currentInstance.value) return
  if (!confirm('确认要关机此实例吗？')) return
  notify('正在发送关机指令...')
  const data = await shutdownInstance(currentInstance.value.uuid)
  if (data?.ok) {
    notify('✅ 关机指令已发送')
    await refreshInstances()
    probeResult.value = null
    gpuData.value = {}
  } else {
    notify('关机失败: ' + ((data as any)?.error || '未知错误'), false)
  }
}

async function doRemove(uuid: string) {
  if (!confirm('确认注销此实例？')) return
  const data = await removeInstance(uuid)
  if (data?.ok) { await refreshInstances(); notify('已注销') }
}

async function doSyncPro() {
  loading.sync = true
  const data = await syncPro()
  if (data?.ok) { await refreshInstances(); notify('✅ 同步成功，共 ' + data.synced + ' 个实例') }
  else if (data && (data as any).error) notify('同步失败: ' + (data as any).message, false)
  loading.sync = false
}

// ── Lifecycle ──

let sseStream: { close: () => void } | null = null
let balanceTimer: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  await waitForServer()
  serverOnline.value = isServerReady()
  // 一次性预加载所有数据——首次费用用 refresh=1 拉实时余额
  await Promise.all([refreshInstances(), refreshCost(true), refreshSettings(), refreshAlerts()])
  loading.init = false
  // 后台再拉一次确保 settings 同步
  refreshAgentMemory()

  sseStream = createSSEStream(
    (gpu) => { if (gpu.uuid === currentInstance.value?.uuid) gpuData.value = gpu },
    () => refreshInstances(),
    () => refreshInstances(),
    () => refreshInstances(),
    () => refreshInstances(),
    () => { refreshInstances(); refreshCost() },
    () => refreshCost(),
  )
  balanceTimer = setInterval(() => refreshCost(), 60000)
})

onUnmounted(() => {
  sseStream?.close()
  if (balanceTimer) clearInterval(balanceTimer)
  clearToast()
})
</script>

<template>
  <Toast :show="toast.show" :msg="toast.msg" :ok="toast.ok" :id="toast.id" @dismiss="toast.show = false" />

  <div style="display:flex;flex-direction:column;height:100vh;">
    <!-- 顶部栏 -->
    <TopBar
      :currentInstance="currentInstance"
      :instances="instances"
      :stats="stats"
      @selectInstance="handleSelectInstance"
      @navTo="handleNavTo"
    />

    <div style="display:flex;flex:1;min-height:0;">
      <Sidebar
        :tabs="tabs"
        :currentTab="currentTab"
        :balanceDisplay="balanceDisplay"
        :stats="stats"
        :loading="loading.init"
        @selectTab="currentTab = $event"
      />

      <!-- MAIN -->
      <div style="flex:1;overflow-y:auto;padding:24px;">
        <Loading v-if="loading.init" :serverOnline="serverOnline" />

        <template v-else>
          <KeepAlive>
          <Dashboard
            v-if="currentTab === 'dashboard'"
            :currentInstance="currentInstance"
            :instances="instances"
            :gpuData="gpuData"
            :probeResult="probeResult"
            :loading="loading"
            @probe="doProbeCurrent"
            @refreshGPU="doRefreshGPU"
            @shutdown="doShutdownCurrent"
            @setCurrent="doSetCurrent"
          />

          <InstanceList
            v-if="currentTab === 'instances'"
            :instances="instances"
            :loading="loading"
            @syncPro="doSyncPro"
            @openRegister="registerDialog?.open()"
            @setCurrent="doSetCurrent"
            @probe="doProbe"
            @remove="doRemove"
          />

          <AgentLog
            v-if="currentTab === 'agent'"
            :conversations="agentConversations"
            :query="agentQuery"
            :loading="agentLoading"
            :memoryStats="agentMemoryStats"
            @send="sendAgentQuery($event)"
            @update:query="agentQuery = $event"
          />

          <CostAnalysis
            v-if="currentTab === 'cost'"
            :costData="costData"
            :loading="loading.cost"
            @refresh="refreshCost(true)"
          />

          <LogTerminal
            v-if="currentTab === 'logs'"
            :currentInstance="currentInstance"
            :logLines="logLines"
          />

          <SettingsPanel
            v-if="currentTab === 'settings'"
            :settings="settingsData"
            @save="doSaveSettings($event.token, $event.sshKey, $event.llmApiKey, $event.llmApiBase, $event.llmModel)"
          />
        </KeepAlive>
      </template>
    </div>
  </div>
  </div>

  <RegisterDialog ref="registerDialog" @registered="refreshInstances()" />
</template>
