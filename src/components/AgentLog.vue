<script setup lang="ts">
import { ref, computed } from 'vue'

interface AgentStep {
  id: number
  timestamp: string
  type: 'thinking' | 'tool_call' | 'tool_result' | 'answer'
  content: string
  toolName?: string
  duration?: number
}

const steps = ref<AgentStep[]>([])
const query = ref('')
const loading = ref(false)
const memoryStats = ref({ conversations: 0, experiments: 0, decisions: 0 })

function addStep(type: AgentStep['type'], content: string, toolName?: string) {
  steps.value.push({
    id: Date.now(),
    timestamp: new Date().toLocaleTimeString(),
    type,
    content,
    toolName,
  })
  // 自动滚动到底部
}

async function sendQuery() {
  if (!query.value.trim() || loading.value) return
  loading.value = true
  addStep('thinking', `用户请求: ${query.value}`)

  try {
    const res = await fetch('http://127.0.0.1:8899/api/agent/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify({ query: query.value }),
    })
    const data = await res.json()
    if (data.answer) {
      addStep('answer', data.answer)
    } else if (data.error) {
      addStep('answer', `错误: ${data.error}`)
    }
  } catch (e: unknown) {
    addStep('answer', `连接失败: ${e instanceof Error ? e.message : String(e)}`)
  }

  loading.value = false
  query.value = ''
}

async function loadMemoryStats() {
  try {
    const res = await fetch('http://127.0.0.1:8899/api/agent/status')
    const data = await res.json()
    if (data.memory) memoryStats.value = data.memory
  } catch (_) { /* ignore */ }
}

const typeConfig = computed(() => ({
  thinking: { icon: '🧠', color: '#a78bfa', label: '思考' },
  tool_call: { icon: '🔧', color: '#60a5fa', label: '调用工具' },
  tool_result: { icon: '📊', color: '#4ade80', label: '工具返回' },
  answer: { icon: '💬', color: '#fbbf24', label: '回答' },
}))
</script>

<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <h1 style="font-size:1.4rem;font-weight:700;">Agent 决策日志</h1>
      <div style="display:flex;gap:12px;font-size:12px;color:#71717a;">
        <span>对话: {{ memoryStats.conversations }}</span>
        <span>实验: {{ memoryStats.experiments }}</span>
        <span>决策: {{ memoryStats.decisions }}</span>
        <button @click="loadMemoryStats()" style="background:none;border:1px solid #3f3f46;color:#a1a1aa;padding:2px 8px;border-radius:4px;cursor:pointer;font-size:11px;">刷新</button>
      </div>
    </div>

    <!-- 输入框 -->
    <div style="display:flex;gap:8px;margin-bottom:16px;">
      <input
        v-model="query"
        @keyup.enter="sendQuery()"
        :disabled="loading"
        placeholder="自然语言操作 GPU，例如: 检查所有实例利用率..."
        style="flex:1;padding:10px 14px;background:#18181b;border:1px solid #3f3f46;border-radius:8px;color:#e4e4e7;font-size:14px;outline:none;"
      />
      <button
        @click="sendQuery()"
        :disabled="loading || !query.trim()"
        :style="{
          padding:'10px 20px',background:loading?'#3f3f46':'#2563eb',border:'none',borderRadius:'8px',
          color:'#fff',fontSize:'14px',cursor:loading?'not-allowed':'pointer',fontWeight:'600',
        }"
      >{{ loading ? '执行中...' : '发送' }}</button>
    </div>

    <!-- 决策流 -->
    <div style="background:#09090b;border:1px solid #27272a;border-radius:12px;padding:16px;max-height:500px;overflow-y:auto;min-height:200px;">
      <div v-if="steps.length === 0" style="color:#52525b;text-align:center;padding:40px;">
        输入自然语言请求，观察 Agent 的思考→决策→执行过程
      </div>
      <div v-for="step in steps" :key="step.id" style="margin-bottom:12px;padding:10px 12px;background:#18181b;border-radius:8px;border-left:3px solid v-bind(typeConfig[step.type]?.color || '#52525b');">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
          <span style="font-size:14px;">{{ typeConfig[step.type]?.icon }}</span>
          <span style="font-size:12px;font-weight:600;color:v-bind(typeConfig[step.type]?.color || '#a1a1aa')">
            {{ typeConfig[step.type]?.label }}
          </span>
          <span v-if="step.toolName" style="font-size:12px;color:#60a5fa;background:rgba(96,165,250,0.1);padding:1px 6px;border-radius:4px;">{{ step.toolName }}</span>
          <span style="font-size:11px;color:#52525b;margin-left:auto;">{{ step.timestamp }}</span>
        </div>
        <div style="font-size:13px;color:#d4d4d8;white-space:pre-wrap;line-height:1.6;">{{ step.content }}</div>
      </div>
    </div>
  </div>
</template>
