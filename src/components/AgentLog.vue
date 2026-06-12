<script setup lang="ts">
import { ref, nextTick, watch, computed } from 'vue'

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

function doSend(text?: string) {
  emit('send', text || props.query)
}

watch(() => props.conversations.length, () => {
  nextTick(() => { if (logEl.value) logEl.value.scrollTop = logEl.value.scrollHeight })
})
</script>

<template>
  <div style="display:flex;flex-direction:column;height:calc(100vh - 80px);">
    <!-- 顶栏 -->
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-shrink:0;">
      <h1 style="font-size:1.3rem;font-weight:700;margin:0;">AI Agent</h1>
      <div style="display:flex;gap:14px;font-size:11px;color:var(--text-dim);">
        <span>{{ conversations.length }} 轮对话</span>
      </div>
    </div>

    <!-- 对话区 -->
    <div ref="logEl" style="flex:1;overflow-y:auto;min-height:0;">

      <!-- 空状态 — 产品 logo 动画 -->
      <div v-if="!hasSent && !loading" style="display:flex;flex-direction:column;align-items:center;justify-content:center;padding:60px 20px;text-align:center;">
        <!-- 产品 logo — 太阳射线 -->
        <div class="logo-spin">
          <svg width="64" height="64" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.2" style="color:var(--text);">
            <circle cx="24" cy="24" r="6" stroke-width="1.5"/>
            <path d="M24 2v6m0 32v6M8.46 8.46l4.24 4.24m22.6 22.6l4.24 4.24M2 24h6m32 0h6M8.46 39.54l4.24-4.24m22.6-22.6l4.24-4.24"/>
            <circle cx="24" cy="24" r="18" stroke-width="0.4" opacity="0.3"/>
            <circle cx="24" cy="24" r="14" stroke-width="0.6" opacity="0.5"/>
          </svg>
        </div>
        <div style="font-size:1.2rem;font-weight:700;margin-top:20px;margin-bottom:6px;color:var(--text);">autodlagents</div>
        <div style="font-size:13px;color:var(--text-dim);max-width:260px;line-height:1.6;">
          自然语言管理 GPU 实例<br>Agent 自主决策 · 工具调用 · 实时监控
        </div>
      </div>

      <!-- 对话列表 -->
      <div v-if="hasSent" style="padding:0 4px;">
        <template v-for="conv in conversations" :key="conv.id">
          <!-- 用户消息 -->
          <div v-for="step in conv.steps" :key="step.id" :style="{ marginBottom: step.type === 'user' ? '16px' : '6px' }">
            <!-- 用户 — 右对齐 -->
            <div v-if="step.type === 'user'" style="display:flex;justify-content:flex-end;">
              <div style="max-width:75%;background:var(--bg-hover);border:1px solid var(--border);border-radius:12px 12px 4px 12px;padding:10px 14px;">
                <div style="font-size:13px;color:var(--text);line-height:1.5;">{{ step.content }}</div>
              </div>
            </div>

            <!-- 工具调用 — 小标签 -->
            <div v-else-if="step.type === 'tool_call'" style="display:flex;align-items:center;gap:6px;padding:3px 0 3px 4px;">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--text-dim);"><circle cx="12" cy="12" r="3"/><path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
              <span style="font-size:11px;color:var(--text-dim);">{{ step.toolName || 'tool' }}</span>
              <span v-if="step.content" style="font-size:10px;color:var(--text-dim);opacity:0.6;">{{ step.content.slice(0, 80) }}</span>
            </div>

            <!-- 工具结果 — 灰色小字 -->
            <div v-else-if="step.type === 'tool_result'" style="padding:2px 0 2px 4px;">
              <span style="font-size:11px;color:var(--text-dim);opacity:0.5;">{{ (step.content || '').slice(0, 120) }}</span>
            </div>

            <!-- Agent 回答 — 左对齐 -->
            <div v-else-if="step.type === 'answer'" style="display:flex;gap:8px;">
              <!-- logo 小头像 -->
              <div style="flex-shrink:0;width:24px;height:24px;display:flex;align-items:center;justify-content:center;">
                <svg width="20" height="20" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.2" style="color:var(--text);">
                  <circle cx="24" cy="24" r="5" stroke-width="1.8"/>
                  <path d="M24 1v6m0 34v6M7.4 7.4l4.2 4.2m24.8 24.8l4.2 4.2M1 24h6m34 0h6M7.4 40.6l4.2-4.2m24.8-24.8l4.2-4.2"/>
                </svg>
              </div>
              <div style="flex:1;font-size:13px;color:var(--text);line-height:1.6;white-space:pre-wrap;">{{ step.content }}</div>
            </div>

            <!-- 思考 — 小字 -->
            <div v-else-if="step.type === 'thinking'" style="padding:2px 0 2px 4px;">
              <span style="font-size:11px;color:var(--text-dim);font-style:italic;">{{ step.content }}</span>
            </div>
          </div>

          <!-- 分隔 -->
          <div style="border-top:1px solid var(--border-light);margin:16px 0;"></div>
        </template>
      </div>

      <!-- loading -->
      <div v-if="loading" style="display:flex;align-items:center;gap:8px;padding:12px 4px;">
        <div style="flex-shrink:0;width:24px;height:24px;display:flex;align-items:center;justify-content:center;">
          <svg width="20" height="20" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.2" class="logo-pulse" style="color:var(--text);">
            <circle cx="24" cy="24" r="5" stroke-width="1.8"/>
            <path d="M24 1v6m0 34v6M7.4 7.4l4.2 4.2m24.8 24.8l4.2 4.2M1 24h6m34 0h6M7.4 40.6l4.2-4.2m24.8-24.8l4.2-4.2"/>
          </svg>
        </div>
        <span style="font-size:13px;color:var(--text-dim);">思考中...</span>
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
        style="flex:1;padding:10px 14px;background:var(--bg-input);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:14px;outline:none;"
      />
      <button @click="doSend()" :disabled="loading || !query.trim()"
        style="padding:10px 20px;background:var(--accent-bg);border:none;border-radius:8px;color:#fff;font-size:14px;cursor:pointer;font-weight:600;"
      >发送</button>
    </div>
  </div>
</template>

<style scoped>
.logo-spin {
  animation: logoEnter 0.8s ease-out;
}
@keyframes logoEnter {
  from { opacity: 0; transform: scale(0.8) rotate(-10deg); }
  to { opacity: 1; transform: scale(1) rotate(0deg); }
}
.logo-pulse {
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}
</style>
