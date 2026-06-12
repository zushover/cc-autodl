<script setup lang="ts">
import { ref, nextTick, watch, computed, onMounted } from 'vue'

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
const hasSent = computed(() => props.conversations.length > 0)
const showAnim = ref(false)

onMounted(() => {
  // 确保组件挂载后再启动动画，避免首帧卡顿
  requestAnimationFrame(() => {
    showAnim.value = true
  })
})

function doSend(text?: string) {
  emit('send', text || props.query)
}

watch(() => props.conversations.length, () => {
  nextTick(() => { if (logEl.value) logEl.value.scrollTop = logEl.value.scrollHeight })
})

</script>

<template>
  <div style="display:flex;flex-direction:column;height:calc(100vh - 80px);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-shrink:0;">
      <h1 style="font-size:1.3rem;font-weight:700;margin:0;">Triple A</h1>
      <div style="display:flex;gap:14px;font-size:11px;color:var(--text-dim);">
        <span>{{ conversations.length }} 轮对话</span>
      </div>
    </div>

    <div ref="logEl" style="flex:1;overflow-y:auto;min-height:0;">

      <!-- 空状态 -->
      <div v-if="!hasSent && !loading" style="display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px;text-align:center;min-height:100%;">
        <div class="hero-stage" :class="{ active: showAnim }" style="display:flex;align-items:center;justify-content:center;margin-bottom:24px;">
          <div class="final-logo">
            <svg width="56" height="56" viewBox="0 0 48 48" fill="none" stroke="var(--text)" stroke-width="1.3">
              <circle cx="24" cy="24" r="5" stroke-width="2"/>
              <path d="M24 2v6m0 32v6M8.5 8.5l4.2 4.2m22.6 22.6l4.2 4.2M2 24h6m32 0h6M8.5 39.5l4.2-4.2m22.6-22.6l4.2-4.2"/>
            </svg>
          </div>
        </div>

        <div class="brand-text">AutodlAgents</div>
        <div class="brand-sub">自然语言管理 GPU · Agent 自主决策</div>
      </div>

      <!-- 对话 -->
      <div v-if="hasSent" style="padding:0 4px;">
        <template v-for="conv in conversations" :key="conv.id">
          <div v-for="step in conv.steps" :key="step.id" :style="{ marginBottom: step.type === 'user' ? '16px' : '6px' }">
            <div v-if="step.type === 'user'" style="display:flex;justify-content:flex-end;">
              <div style="max-width:75%;background:var(--bg-hover);border:1px solid var(--border);border-radius:12px 12px 4px 12px;padding:10px 14px;">
                <div style="font-size:13px;color:var(--text);line-height:1.5;">{{ step.content }}</div>
              </div>
            </div>
            <div v-else-if="step.type === 'tool_call'" style="display:flex;align-items:center;gap:6px;padding:3px 0 3px 4px;">
              <svg width="12" height="12" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.5" style="color:var(--text-dim);"><circle cx="24" cy="24" r="5"/><path d="M24 2v6m0 32v6M8.46 8.46l4.24 4.24m22.6 22.6l4.24 4.24M2 24h6m32 0h6M8.46 39.54l4.24-4.24m22.6-22.6l4.24-4.24"/></svg>
              <span style="font-size:11px;color:var(--text-dim);">{{ step.toolName || 'tool' }}</span>
              <span v-if="step.content" style="font-size:10px;color:var(--text-dim);opacity:0.5;">{{ step.content.slice(0, 80) }}</span>
            </div>
            <div v-else-if="step.type === 'tool_result'" style="padding:2px 0 2px 4px;">
              <span style="font-size:11px;color:var(--text-dim);opacity:0.4;">{{ (step.content || '').slice(0, 120) }}</span>
            </div>
            <div v-else-if="step.type === 'answer'" style="display:flex;gap:8px;">
              <div style="flex-shrink:0;width:24px;height:24px;display:flex;align-items:center;justify-content:center;">
                <svg width="20" height="20" viewBox="0 0 48 48" fill="none" stroke="var(--text)" stroke-width="1.2">
                  <circle cx="24" cy="24" r="5" stroke-width="1.8"/>
                  <path d="M24 1v6m0 34v6M7.4 7.4l4.2 4.2m24.8 24.8l4.2 4.2M1 24h6m34 0h6M7.4 40.6l4.2-4.2m24.8-24.8l4.2-4.2"/>
                </svg>
              </div>
              <div style="flex:1;font-size:13px;color:var(--text);line-height:1.6;white-space:pre-wrap;">{{ step.content }}</div>
            </div>
            <div v-else-if="step.type === 'thinking'" style="padding:2px 0 2px 4px;">
              <span style="font-size:11px;color:var(--text-dim);font-style:italic;">{{ step.content }}</span>
            </div>
          </div>
          <div style="border-top:1px solid var(--border-light);margin:16px 0;"></div>
        </template>
      </div>

      <div v-if="loading" style="display:flex;align-items:center;gap:8px;padding:12px 4px;">
        <svg width="20" height="20" viewBox="0 0 48 48" fill="none" stroke="var(--text)" stroke-width="1.2" class="pulse-icon">
          <circle cx="24" cy="24" r="5" stroke-width="1.8"/>
          <path d="M24 1v6m0 34v6M7.4 7.4l4.2 4.2m24.8 24.8l4.2 4.2M1 24h6m34 0h6M7.4 40.6l4.2-4.2m24.8-24.8l4.2-4.2"/>
        </svg>
        <span style="font-size:13px;color:var(--text-dim);">思考中...</span>
      </div>
    </div>

    <div style="display:flex;gap:8px;margin-top:10px;flex-shrink:0;">
      <input
        :value="query"
        @input="emit('update:query', ($event.target as HTMLInputElement).value)"
        @keyup.enter="doSend()"
        :disabled="loading"
        placeholder="输入自然语言，例如: 检查GPU利用率..."
        style="flex:1;padding:10px 14px;background:var(--bg-input);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:14px;outline:none;"
      />
      <button @click="doSend()" :disabled="loading || !query.trim()"
        style="padding:10px 20px;background:var(--accent-bg);border:none;border-radius:8px;color:#fff;font-size:14px;cursor:pointer;font-weight:600;"
      >发送</button>
    </div>
  </div>
</template>

<style>
.hero-stage .final-logo { opacity: 0; transform: scale(0.2); }
.hero-stage + .brand-text,
.hero-stage + .brand-text + .brand-sub { opacity: 0; transform: translateY(8px); }

.active .final-logo {
  animation: logoPop 0.45s cubic-bezier(0.34, 1.56, 0.64, 1) 0.05s forwards;
}
@keyframes logoPop {
  0% { opacity: 0; transform: scale(0.15) rotate(-8deg); }
  100% { opacity: 1; transform: scale(1) rotate(0deg); }
}

.active + .brand-text {
  animation: textIn 0.3s ease-out 0.3s forwards;
}
.active + .brand-text + .brand-sub {
  animation: textIn 0.3s ease-out 0.4s forwards;
}
@keyframes textIn { to { opacity: 1; transform: translateY(0); } }

.brand-text { font-size: 1.35rem; font-weight: 600; color: var(--text); }
.brand-sub { font-size: 12px; color: var(--text-dim); margin-top: 6px; }

.pulse-icon { animation: pulse 2s ease-in-out infinite; }
@keyframes pulse { 0%,100%{opacity:.3} 50%{opacity:1} }
</style>
