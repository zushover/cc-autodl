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

// 光芒环 — 每层是竖线（太阳光芒），缓慢旋转
const rings = [
  { r: 120, rays: 24, speed: 40, w: 1.5, h: 14, alpha: 0.2 },
  { r: 90, rays: 20, speed: 35, w: 1.5, h: 12, alpha: 0.3 },
  { r: 60, rays: 16, speed: 30, w: 2, h: 10, alpha: 0.45 },
  { r: 34, rays: 12, speed: 25, w: 2, h: 8, alpha: 0.65 },
]
</script>

<template>
  <div style="display:flex;flex-direction:column;height:calc(100vh - 80px);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-shrink:0;">
      <h1 style="font-size:1.3rem;font-weight:700;margin:0;">AI Agents</h1>
      <div style="display:flex;gap:14px;font-size:11px;color:var(--text-dim);">
        <span>{{ conversations.length }} 轮对话</span>
      </div>
    </div>

    <div ref="logEl" style="flex:1;overflow-y:auto;min-height:0;">

      <!-- 空状态 -->
      <div v-if="!hasSent && !loading" style="display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px;text-align:center;min-height:100%;">
        <div class="hero-stage" :class="{ active: showAnim }" style="position:relative;width:300px;height:300px;flex-shrink:0;margin-bottom:28px;">

          <!-- 光芒环 -->
          <div v-for="(ring, ri) in rings" :key="'r'+ri"
            :class="'orbit ring-'+ri"
            :style="{
              position:'absolute',
              top:'50%', left:'50%',
              width: ring.r*2+'px', height: ring.r*2+'px',
              marginLeft: -ring.r+'px', marginTop: -ring.r+'px',
            }"
          >
            <div v-for="i in ring.rays" :key="'d'+ri+'-'+i"
              class="ray"
              :style="{
                position:'absolute',
                width: ring.w+'px', height: ring.h+'px',
                borderRadius: ring.w+'px',
                background: 'var(--text)',
                opacity: ring.alpha,
                top: '50%', left: '50%',
                marginLeft: -(ring.w/2)+'px',
                marginTop: -ring.r+'px',
                transformOrigin: 'center ' + ring.r + 'px',
                transform: `rotate(${(360/ring.rays)*i}deg)`,
              }"
            />
          </div>

          <!-- logo -->
          <div class="final-logo" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;">
            <svg width="52" height="52" viewBox="0 0 48 48" fill="none" stroke="var(--text)" stroke-width="1.3">
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
/* === scoped 外的全局动画样式（因为 orbit ring 由 v-for 动态生成） === */

/* 默认隐藏，.active 触发后显示 */
.hero-stage .orbit { opacity: 0; }
.hero-stage .final-logo { opacity: 0; transform: scale(0.3); }
.hero-stage + .brand-text,
.hero-stage + .brand-text + .brand-sub { opacity: 0; transform: translateY(10px); }

.hero-stage.active .orbit { opacity: 1; }
.hero-stage.active .final-logo { opacity: 1; }

/* GPU 加速 */
.orbit { will-change: transform; backface-visibility: hidden; }

/* 慢速旋转 — 所有环缓慢顺时针 */
.ring-0 { animation: spin40 40s linear infinite; }
.ring-1 { animation: spin35 35s linear infinite; }
.ring-2 { animation: spin30 30s linear infinite; }
.ring-3 { animation: spin25 25s linear infinite; }

@keyframes spin40 { to { transform: rotate(360deg); } }
@keyframes spin35 { to { transform: rotate(360deg); } }
@keyframes spin30 { to { transform: rotate(360deg); } }
@keyframes spin25 { to { transform: rotate(360deg); } }

/* 汇聚 — 0.1s后收缩到0 */
.active .ring-0 { animation: spin40 40s linear infinite, c0 0.4s ease-in 0.1s forwards; }
.active .ring-1 { animation: spin35 35s linear infinite, c1 0.35s ease-in 0.12s forwards; }
.active .ring-2 { animation: spin30 30s linear infinite, c2 0.3s ease-in 0.14s forwards; }
.active .ring-3 { animation: spin25 25s linear infinite, c3 0.25s ease-in 0.16s forwards; }

@keyframes c0 { to { width:0; height:0; margin-left:0; margin-top:0; opacity:0; } }
@keyframes c1 { to { width:0; height:0; margin-left:0; margin-top:0; opacity:0; } }
@keyframes c2 { to { width:0; height:0; margin-left:0; margin-top:0; opacity:0; } }
@keyframes c3 { to { width:0; height:0; margin-left:0; margin-top:0; opacity:0; } }

/* logo — 0.4s 弹入 */
.active .final-logo {
  animation: popIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) 0.35s forwards;
}
@keyframes popIn {
  0% { opacity: 0; transform: scale(0.1) rotate(-8deg); }
  100% { opacity: 1; transform: scale(1) rotate(0deg); }
}

/* 文字 — 0.6s */
.active + .brand-text {
  animation: fadeIn 0.3s ease-out 0.55s forwards;
}
.active + .brand-text + .brand-sub {
  animation: fadeIn 0.3s ease-out 0.65s forwards;
}
@keyframes fadeIn { to { opacity: 1; transform: translateY(0); } }

.brand-text { font-size: 1.35rem; font-weight: 600; color: var(--text); }
.brand-sub { font-size: 12px; color: var(--text-dim); margin-top: 6px; }

.pulse-icon { animation: pulse 2s ease-in-out infinite; }
@keyframes pulse { 0%,100%{opacity:.3} 50%{opacity:1} }
</style>
