<script setup lang="ts">
import { ref, watch } from 'vue'
import type { SettingsData } from '../types'

const props = defineProps<{ settings: SettingsData }>()
const emit = defineEmits<{ save: [payload: { token: string; sshKey: string; llmApiKey?: string; llmApiBase?: string; llmModel?: string }] }>()

const token = ref('')
const llmApiKey = ref('')
const llmApiBase = ref('')
const llmModel = ref('')
const saved = ref(false)

// 从 props 同步到本地编辑状态（App.vue 数据回来时自动填充）
watch(() => props.settings, (s) => {
  if (s.token && s.token !== 'your-token-here') token.value = s.token
  if (s.llm_api_key) llmApiKey.value = s.llm_api_key
  if (s.llm_api_base) llmApiBase.value = s.llm_api_base
  if (s.llm_model) llmModel.value = s.llm_model
}, { immediate: true })

function save() {
  emit('save', {
    token: token.value,
    sshKey: props.settings?.ssh_key || '',
    llmApiKey: llmApiKey.value,
    llmApiBase: llmApiBase.value,
    llmModel: llmModel.value,
  })
  saved.value = true
  setTimeout(() => { saved.value = false }, 2000)
}
</script>

<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
      <h1 style="font-size:1.3rem;font-weight:700;margin:0;">设置</h1>
      <span v-if="saved" style="font-size:11px;color:var(--green);">已保存</span>
    </div>

    <!-- AutoDL Token -->
    <div class="glass-card" style="margin-bottom:12px;">
      <div style="font-weight:600;font-size:13px;margin-bottom:4px;">AutoDL 开发者 Token</div>
      <div style="font-size:11px;color:var(--text-dim);margin-bottom:10px;">用于同步实例、查询余额、开关机操作</div>
      <div style="display:flex;gap:8px;align-items:center;">
        <input v-model="token" type="password" placeholder="输入 Token" style="flex:1;">
        <span v-if="settings.hasToken" class="badge badge-running">已配置</span>
      </div>
    </div>

    <!-- AI API -->
    <div class="glass-card" style="margin-bottom:14px;">
      <div style="font-weight:600;font-size:13px;margin-bottom:4px;">AI API 接口</div>
      <div style="font-size:11px;color:var(--text-dim);margin-bottom:10px;">Agent 使用的 LLM 接口（OpenAI 兼容协议）</div>
      <div style="display:flex;flex-direction:column;gap:8px;">
        <div style="display:flex;gap:8px;">
          <div style="flex:1;">
            <div style="font-size:11px;color:var(--text-secondary);margin-bottom:3px;">API Key</div>
            <input v-model="llmApiKey" type="password" placeholder="sk-..." style="width:100%;">
          </div>
          <div style="flex:1;">
            <div style="font-size:11px;color:var(--text-secondary);margin-bottom:3px;">API 地址</div>
            <input v-model="llmApiBase" placeholder="https://api.deepseek.com/v1" style="width:100%;">
          </div>
        </div>
        <div style="width:50%;padding-right:4px;">
          <div style="font-size:11px;color:var(--text-secondary);margin-bottom:3px;">模型</div>
          <input v-model="llmModel" placeholder="deepseek-v4-pro" style="width:100%;">
        </div>
      </div>
    </div>

    <button class="btn btn-primary" @click="save">保存设置</button>
  </div>
</template>
