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
import CostAnalysis from './components/CostAnalysis.vue'
import KnowledgeBase from './components/KnowledgeBase.vue'
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
  { id: 'dashboard', label: '服务器', icon: '' },
  { id: 'agent', label: 'AI Agents', icon: '' },
  { id: 'knowledge', label: '知识库', icon: '' },
  { id: 'cost', label: '费用', icon: '' },
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

// ── 知识库状态（在 App.vue 中，永不丢失）──
const kbEntries = ref<{ id: string; content: string; timestamp: string }[]>([])
const kbLoading = ref(false)
const kbQuery = ref('')

async function loadKnowledgeBase() {
  kbLoading.value = true
  try {
    const res = await fetch('http://127.0.0.1:8899/api/knowledge/all')
    const data = await res.json()
    kbEntries.value = (data.items || []).map((item: any) => ({
      id: item.id || 'kb-' + Math.random(),
      content: `[${item.type}] ${item.content || ''}`,
      timestamp: item.timestamp || '',
    }))
  } catch (_) { /* ignore */ }
  kbLoading.value = false
}

async function kbSearch(q: string) {
  kbQuery.value = q
  if (!q.trim()) { await loadKnowledgeBase(); return }
  kbLoading.value = true
  try {
    const res = await fetch('http://127.0.0.1:8899/api/memory/experiments?q=' + encodeURIComponent(q) + '&n=20')
    const data = await res.json()
    kbEntries.value = (data.results || []).map((r: string, i: number) => ({
      id: 'sr-' + i, content: r, timestamp: ''
    }))
  } catch (_) { /* ignore */ }
  kbLoading.value = false
}

function agentNow() { return new Date().toLocaleTimeString() }

async function sendAgentQuery(text?: string) {
  const q = text || agentQuery.value.trim()
  if (!q || agentLoading.value) return
  agentLoading.value = true
  agentQuery.value = ''

  const conv: AgentConversation = { id: Date.now(), query: q, steps: [] }
  conv.steps.push({ id: Date.now(), timestamp: agentNow(), type: 'user', content: q })
  agentConversations.value.push(conv)

  // 等待指示器
  const tid = Date.now()
  conv.steps.push({ id: tid, timestamp: agentNow(), type: 'thinking', content: '正在分析...' })

  try {
    const res = await fetch('http://127.0.0.1:8899/api/agent/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify({ query: q }),
    })

    if (!res.ok) throw new Error('Server error')

    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let answerText = ''

    // 移除等待指示器
    conv.steps = conv.steps.filter(s => s.id !== tid)

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const data = JSON.parse(line.slice(6))
          const now = agentNow()

          if (data.type === 'tool_call' || data.type === 'tool_start') {
            conv.steps = [...conv.steps, { id: Date.now(), timestamp: now, type: 'tool_call', toolName: data.tool, content: data.args ? JSON.stringify(data.args).slice(0, 100) : '' }]
          } else if (data.type === 'tool_result') {
            conv.steps = [...conv.steps, { id: Date.now(), timestamp: now, type: 'tool_result', toolName: data.tool, content: (data.output || '').slice(0, 300) }]
          } else if (data.type === 'text') {
            answerText += data.content
            const lastIdx = conv.steps.length - 1
            if (lastIdx >= 0 && conv.steps[lastIdx].type === 'answer') {
              const updated = [...conv.steps]
              updated[lastIdx] = { ...updated[lastIdx], content: answerText }
              conv.steps = updated
            } else {
              conv.steps = [...conv.steps, { id: Date.now(), timestamp: now, type: 'answer', content: answerText }]
            }
            // 每个 text 事件后让 Vue 渲染
            await new Promise(r => requestAnimationFrame(r))
          } else if (data.type === 'done') {
            if (data.answer) {
              const lastIdx2 = conv.steps.length - 1
              if (lastIdx2 >= 0 && conv.steps[lastIdx2].type === 'answer') {
                const updated2 = [...conv.steps]
                updated2[lastIdx2] = { ...updated2[lastIdx2], content: data.answer }
                conv.steps = updated2
              } else if (data.answer) {
                conv.steps = [...conv.steps, { id: Date.now(), timestamp: now, type: 'answer', content: data.answer }]
              }
            }
          } else if (data.type === 'error') {
            conv.steps = [...conv.steps, { id: Date.now(), timestamp: now, type: 'answer', content: 'Error: ' + data.message }]
          }
        } catch (_) { /* skip */ }
      }
    }
  } catch (e: unknown) {
    conv.steps = conv.steps.filter(s => s.id !== tid)
    conv.steps.push({ id: Date.now(), timestamp: agentNow(), type: 'answer', content: '连接失败: 请确认服务已启动' })
  }

  agentLoading.value = false
  refreshAgentMemory()

  // 对话自动存入 ChromaDB 共享记忆
  const finalAnswer = conv.steps.find(s => s.type === 'answer')?.content || ''
  if (finalAnswer) {
    try {
      await fetch('http://127.0.0.1:8899/api/memory/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
        body: JSON.stringify({ user_msg: q, agent_response: finalAnswer, metadata: { source: 'ai-agents-panel' } }),
      })
    } catch (_) { /* ignore */ }
  }
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
  // 一次性预加载所有数据
  await Promise.all([refreshInstances(), refreshCost(true), refreshSettings(), refreshAlerts()])
  loading.init = false
  refreshAgentMemory()
  loadKnowledgeBase()  // 预加载知识库

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
            @syncPro="doSyncPro"
            @remove="doRemove"
            @openRegister="registerDialog?.open()"
            @probeInstance="doProbe"
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

          <KnowledgeBase
            v-if="currentTab === 'knowledge'"
            :entries="kbEntries"
            :loading="kbLoading"
            :query="kbQuery"
            :stats="agentMemoryStats"
            @search="kbSearch($event)"
            @refresh="loadKnowledgeBase()"
            @update:query="kbQuery = $event"
          />

          <CostAnalysis
            v-if="currentTab === 'cost'"
            :costData="costData"
            :loading="loading.cost"
            @refresh="refreshCost(true)"
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
