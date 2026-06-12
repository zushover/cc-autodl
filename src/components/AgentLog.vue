<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'

interface ApiStep {
  step: number; type: string; content?: string; tool_name?: string; tool_args?: Record<string, unknown>
}

interface DisplayStep {
  id: number; timestamp: string; type: 'user' | 'thinking' | 'tool_call' | 'tool_result' | 'answer'
  content: string; toolName?: string
}

interface Conversation {
  id: number; query: string; steps: DisplayStep[]
}

const conversations = ref<Conversation[]>([])
const query = ref('')
const loading = ref(false)
const memoryStats = ref({ conversations: 0, experiments: 0, decisions: 0 })
const logEl = ref<HTMLElement | null>(null)

// 快捷指令
const quickActions = [
  { label: 'GPU概况', query: '列出所有GPU实例' },
  { label: '查余额', query: '查询我的账户余额' },
  { label: '查利用率', query: '检查westb那台3080Ti的GPU利用率' },
]

function scrollBottom() {
  nextTick(() => {
    if (logEl.value) logEl.value.scrollTop = logEl.value.scrollHeight
  })
}

async function sendQuery(text?: string) {
  const q = text || query.value.trim()
  if (!q || loading.value) return
  loading.value = true
  query.value = ''

  const conv: Conversation = { id: Date.now(), query: q, steps: [] }
  conv.steps.push({ id: Date.now(), timestamp: now(), type: 'user', content: q })
  conversations.value.push(conv)
  scrollBottom()

  try {
    const res = await fetch('http://127.0.0.1:8899/api/agent/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify({ query: q }),
    })

    // 先加一个 thinking 步骤表示等待
    const thinkingId = Date.now()
    conv.steps.push({ id: thinkingId, timestamp: now(), type: 'thinking', content: '正在分析请求...' })
    scrollBottom()

    const data = await res.json()

    // 移除 thinking
    conv.steps = conv.steps.filter(s => s.id !== thinkingId)

    if (data.steps && Array.isArray(data.steps)) {
      for (const s of data.steps as ApiStep[]) {
        if (s.type === 'user_input') continue
        if (s.type === 'tool_call') {
          const args = s.tool_args ? JSON.stringify(s.tool_args) : ''
          const shortArgs = args.length > 200 ? args.slice(0, 200) + '...' : args
          conv.steps.push({ id: Date.now(), timestamp: now(), type: 'tool_call', content: shortArgs ? `参数: ${shortArgs}` : '', toolName: s.tool_name })
        } else if (s.type === 'tool_result') {
          const content = (s.content || '').length > 500 ? (s.content || '').slice(0, 500) + '...' : (s.content || '')
          conv.steps.push({ id: Date.now(), timestamp: now(), type: 'tool_result', content, toolName: s.tool_name })
        } else if (s.type === 'thinking' && s.content) {
          conv.steps.push({ id: Date.now(), timestamp: now(), type: 'thinking', content: s.content })
        }
      }
    }

    if (data.answer) {
      conv.steps.push({ id: Date.now(), timestamp: now(), type: 'answer', content: data.answer })
    } else if (data.error) {
      conv.steps.push({ id: Date.now(), timestamp: now(), type: 'answer', content: `错误: ${data.error}` })
    }
  } catch (e: unknown) {
    conv.steps.push({ id: Date.now(), timestamp: now(), type: 'answer', content: `连接失败: 请确认服务已启动 (python sidecar.py)` })
  }

  loading.value = false
  loadMemoryStats()
  scrollBottom()
}

async function loadMemoryStats() {
  try {
    const res = await fetch('http://127.0.0.1:8899/api/agent/status')
    const data = await res.json()
    if (data.memory) memoryStats.value = data.memory
  } catch (_) { /* ignore */ }
}

function now() { return new Date().toLocaleTimeString() }

const typeCfg: Record<string, { icon: string; color: string; label: string; bg: string }> = {
  user:      { icon: '👤', color: '#a1a1aa', label: '你', bg: '#27272a' },
  thinking:  { icon: '🧠', color: '#a78bfa', label: '思考', bg: 'rgba(167,139,250,0.06)' },
  tool_call: { icon: '🔧', color: '#60a5fa', label: '调用工具', bg: 'rgba(96,165,250,0.06)' },
  tool_result:{ icon: '📊', color: '#4ade80', label: '工具返回', bg: 'rgba(74,222,128,0.06)' },
  answer:    { icon: '🤖', color: '#fbbf24', label: 'Agent', bg: 'rgba(251,191,36,0.04)' },
}

onMounted(() => { loadMemoryStats() })
</script>

<template>
  <div style="display:flex;flex-direction:column;height:calc(100vh - 80px);">
    <!-- 顶栏 -->
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-shrink:0;">
      <h1 style="font-size:1.3rem;font-weight:700;">AI Agent</h1>
      <div style="display:flex;gap:14px;font-size:11px;color:#71717a;">
        <span title="对话轮数">💬 {{ conversations.length }}</span>
        <span title="记忆条数">🧠 {{ memoryStats.conversations }}</span>
        <span title="决策记录">📋 {{ memoryStats.decisions }}</span>
      </div>
    </div>

    <!-- 快捷指令 -->
    <div style="display:flex;gap:6px;margin-bottom:10px;flex-shrink:0;flex-wrap:wrap;">
      <button v-for="a in quickActions" :key="a.label" @click="sendQuery(a.query)" :disabled="loading"
        style="padding:5px 12px;background:#18181b;border:1px solid #27272a;border-radius:16px;color:#a1a1aa;font-size:12px;cursor:pointer;white-space:nowrap;"
      >{{ a.label }}</button>
    </div>

    <!-- 对话区 -->
    <div ref="logEl" style="flex:1;overflow-y:auto;background:#09090b;border:1px solid #1f1f23;border-radius:12px;padding:16px;min-height:0;">
      <div v-if="conversations.length === 0" style="color:#3f3f46;text-align:center;padding:60px 20px;">
        <div style="font-size:40px;margin-bottom:12px;">🤖</div>
        <div style="font-size:14px;margin-bottom:4px;">自然语言管理 GPU</div>
        <div style="font-size:12px;">试试上方快捷指令，或输入 "检查GPU利用率"</div>
      </div>

      <template v-for="conv in conversations" :key="conv.id">
        <div v-for="step in conv.steps" :key="step.id"
          style="margin-bottom:8px;padding:8px 12px;border-radius:8px;"
          :style="{ background: typeCfg[step.type]?.bg || '#18181b' }">
          <!-- 步骤头 -->
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:2px;">
            <span style="font-size:13px;">{{ typeCfg[step.type]?.icon }}</span>
            <span style="font-size:11px;font-weight:600;" :style="{ color: typeCfg[step.type]?.color }">{{ typeCfg[step.type]?.label }}</span>
            <span v-if="step.toolName" style="font-size:10px;color:#60a5fa;background:rgba(96,165,250,0.1);padding:0px 5px;border-radius:3px;">{{ step.toolName }}</span>
            <span style="font-size:10px;color:#3f3f46;margin-left:auto;">{{ step.timestamp }}</span>
          </div>
          <!-- 内容 -->
          <div v-if="step.content" style="font-size:13px;color:#d4d4d8;white-space:pre-wrap;line-height:1.55;">{{ step.content }}</div>
        </div>
        <!-- 分隔线 -->
        <div style="border-top:1px solid #1f1f23;margin:12px 0;"></div>
      </template>

      <!-- loading -->
      <div v-if="loading" style="display:flex;align-items:center;gap:8px;padding:8px 12px;color:#71717a;font-size:12px;">
        <span style="display:inline-block;width:8px;height:8px;background:#a78bfa;border-radius:50%;animation:pulse 1s infinite;"></span>
        正在调用 LLM + 工具...
      </div>
    </div>

    <!-- 输入栏 -->
    <div style="display:flex;gap:8px;margin-top:10px;flex-shrink:0;">
      <input v-model="query" @keyup.enter="sendQuery()" :disabled="loading"
        placeholder="输入自然语言，例如: 检查所有GPU利用率..."
        style="flex:1;padding:10px 14px;background:#18181b;border:1px solid #27272a;border-radius:10px;color:#e4e4e7;font-size:14px;outline:none;"
      />
      <button @click="sendQuery()" :disabled="loading || !query.trim()"
        style="padding:10px 24px;background:linear-gradient(135deg,#2563eb,#7c3aed);border:none;border-radius:10px;color:#fff;font-size:14px;cursor:pointer;font-weight:600;white-space:nowrap;"
      >{{ loading ? '⏳' : '发送' }}</button>
    </div>
  </div>
</template>

<style scoped>
@keyframes pulse {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 1; }
}
</style>
