<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'

interface AgentStep {
  id: number; timestamp: string; type: string; content: string; toolName?: string
}
interface AgentConversation {
  id: number; query: string; steps: AgentStep[]
}

const props = defineProps<{
  conversations: AgentConversation[]
  query: string
  loading: boolean
  memoryStats: { conversations: number; experiments: number; decisions: number }
}>()

const emit = defineEmits<{
  send: [text: string]
  'update:query': [value: string]
}>()

const logEl = ref<HTMLElement | null>()

const quickActions = [
  { label: 'GPU概况', query: '列出所有GPU实例' },
  { label: '查余额', query: '查询我的账户余额' },
  { label: '查利用率', query: '检查westb那台3080Ti的GPU利用率' },
]

const typeCfg: Record<string, { icon: string; color: string; label: string; bg: string }> = {
  user:       { icon: '👤', color: '#a1a1aa', label: '你',    bg: '#27272a' },
  thinking:   { icon: '🧠', color: '#a78bfa', label: '思考',  bg: 'rgba(167,139,250,0.06)' },
  tool_call:  { icon: '🔧', color: '#60a5fa', label: '调用',  bg: 'rgba(96,165,250,0.06)' },
  tool_result:{ icon: '📊', color: '#4ade80', label: '结果',  bg: 'rgba(74,222,128,0.06)' },
  answer:     { icon: '🤖', color: '#fbbf24', label: 'Agent', bg: 'rgba(251,191,36,0.04)' },
}

function doSend(text?: string) {
  emit('send', text || props.query)
}

// 新对话时自动滚到底部
watch(() => props.conversations.length, () => {
  nextTick(() => { if (logEl.value) logEl.value.scrollTop = logEl.value.scrollHeight })
})
</script>

<template>
  <div style="display:flex;flex-direction:column;height:calc(100vh - 80px);">
    <!-- 顶栏 -->
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-shrink:0;">
      <h1 style="font-size:1.3rem;font-weight:700;margin:0;">AI Agent</h1>
      <div style="display:flex;gap:14px;font-size:11px;color:#71717a;">
        <span>💬 {{ conversations.length }}</span>
        <span>🧠 {{ memoryStats.conversations }}</span>
        <span>📋 {{ memoryStats.decisions }}</span>
      </div>
    </div>

    <!-- 快捷指令 -->
    <div style="display:flex;gap:6px;margin-bottom:10px;flex-shrink:0;flex-wrap:wrap;">
      <button v-for="a in quickActions" :key="a.label" @click="doSend(a.query)" :disabled="loading"
        style="padding:5px 12px;background:#18181b;border:1px solid #27272a;border-radius:16px;color:#a1a1aa;font-size:12px;cursor:pointer;"
      >{{ a.label }}</button>
    </div>

    <!-- 对话区 -->
    <div ref="logEl" style="flex:1;overflow-y:auto;background:#09090b;border:1px solid #1f1f23;border-radius:12px;padding:16px;min-height:0;">
      <div v-if="conversations.length === 0 && !loading" style="color:#3f3f46;text-align:center;padding:60px 20px;">
        <div style="font-size:40px;margin-bottom:12px;">🤖</div>
        <div style="font-size:14px;margin-bottom:4px;">自然语言管理 GPU</div>
        <div style="font-size:12px;">试试上方快捷指令，或输入 "检查GPU利用率"</div>
      </div>

      <template v-for="conv in conversations" :key="conv.id">
        <div v-for="step in conv.steps" :key="step.id"
          style="margin-bottom:8px;padding:8px 12px;border-radius:8px;"
          :style="{ background: (typeCfg[step.type] || typeCfg.answer!).bg }">
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:2px;">
            <span style="font-size:13px;">{{ (typeCfg[step.type] || typeCfg.answer!).icon }}</span>
            <span style="font-size:11px;font-weight:600;" :style="{ color: (typeCfg[step.type] || typeCfg.answer!).color }">
              {{ (typeCfg[step.type] || typeCfg.answer!).label }}
            </span>
            <span v-if="step.toolName" style="font-size:10px;color:#60a5fa;background:rgba(96,165,250,0.1);padding:0px 5px;border-radius:3px;">
              {{ step.toolName }}
            </span>
            <span style="font-size:10px;color:#3f3f46;margin-left:auto;">{{ step.timestamp }}</span>
          </div>
          <div v-if="step.content" style="font-size:13px;color:#d4d4d8;white-space:pre-wrap;line-height:1.55;">{{ step.content }}</div>
        </div>
        <div style="border-top:1px solid #1f1f23;margin:12px 0;"></div>
      </template>

      <div v-if="loading" style="display:flex;align-items:center;gap:8px;padding:8px 12px;color:#71717a;font-size:12px;">
        <span style="display:inline-block;width:8px;height:8px;background:#a78bfa;border-radius:50%;animation:pulse 1s infinite;"></span>
        正在调用 LLM + 工具...
      </div>
    </div>

    <!-- 输入栏 -->
    <div style="display:flex;gap:8px;margin-top:10px;flex-shrink:0;">
      <input
        :value="query"
        @input="emit('update:query', ($event.target as HTMLInputElement).value)"
        @keyup.enter="doSend()"
        :disabled="loading"
        placeholder="输入自然语言，例如: 检查GPU利用率..."
        style="flex:1;padding:10px 14px;background:#18181b;border:1px solid #27272a;border-radius:10px;color:#e4e4e7;font-size:14px;outline:none;"
      />
      <button @click="doSend()" :disabled="loading || !query.trim()"
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
