<script setup lang="ts">
import { ref } from 'vue'
import type { SettingsData } from '../types'
import { loadSettings, saveSettings } from '../api'
import { useToast } from '../composables/useToast'

const emit = defineEmits<{ costUpdated: [] }>()
const { notify } = useToast()
const settings = ref<SettingsData>({ token: '', ssh_key: '', hasToken: false })
const serverOnline = ref(true)

async function init() {
  const data = await loadSettings()
  if (data && !(data as any).error) {
    settings.value = data
    settings.value.hasToken = !!(data.token && data.token !== 'your-token-here')
  }
}

async function save() {
  const data = await saveSettings(
    settings.value.token,
    settings.value.ssh_key,
    settings.value.llm_api_key,
    settings.value.llm_api_base,
    settings.value.llm_model,
  )
  if (data?.ok) {
    settings.value.hasToken = !!(settings.value.token && settings.value.token !== 'your-token-here')
    notify('设置已保存')
    emit('costUpdated')
  } else if (data && (data as any).error) {
    notify('保存失败: ' + (data as any).message, false)
  }
}

init()
</script>

<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
      <h1 style="font-size:1.3rem;font-weight:700;margin:0;">设置</h1>
      <span style="font-size:11px;" :style="{ color: serverOnline ? 'var(--green)' : 'var(--red)' }">
        后端 {{ serverOnline ? '在线' : '离线' }}
      </span>
    </div>

    <!-- AutoDL -->
    <div class="glass-card" style="margin-bottom:12px;">
      <div style="font-weight:600;font-size:13px;margin-bottom:4px;">AutoDL 开发者 Token</div>
      <div style="font-size:11px;color:var(--text-dim);margin-bottom:10px;">用于同步实例、查询余额、开关机操作</div>
      <div style="display:flex;gap:8px;align-items:center;">
        <input v-model="settings.token" type="password" placeholder="输入 AutoDL 开发者 Token" style="flex:1;">
        <span v-if="settings.hasToken" class="badge badge-running" style="font-size:11px;">已配置</span>
      </div>
    </div>

    <!-- AI API -->
    <div class="glass-card" style="margin-bottom:12px;">
      <div style="font-weight:600;font-size:13px;margin-bottom:4px;">AI API 接口</div>
      <div style="font-size:11px;color:var(--text-dim);margin-bottom:10px;">Agent 功能使用的 LLM 接口，支持 OpenAI 兼容协议</div>

      <div style="display:flex;flex-direction:column;gap:8px;">
        <div style="display:flex;gap:8px;">
          <div style="flex:1;">
            <div style="font-size:11px;color:var(--text-secondary);margin-bottom:3px;">API Key</div>
            <input v-model="settings.llm_api_key" type="password" placeholder="sk-..." style="width:100%;">
          </div>
          <div style="flex:1;">
            <div style="font-size:11px;color:var(--text-secondary);margin-bottom:3px;">API 地址</div>
            <input v-model="settings.llm_api_base" placeholder="https://api.deepseek.com/v1" style="width:100%;">
          </div>
        </div>
        <div style="width:50%;padding-right:4px;">
          <div style="font-size:11px;color:var(--text-secondary);margin-bottom:3px;">模型</div>
          <input v-model="settings.llm_model" placeholder="deepseek-v4-pro" style="width:100%;">
        </div>
      </div>
    </div>

    <button class="btn btn-primary" @click="save" style="margin-bottom:20px;">保存设置</button>

    <!-- SSH 说明 -->
    <div class="glass-card">
      <div style="font-weight:600;font-size:13px;margin-bottom:8px;">SSH 登录方式</div>
      <div style="font-size:12px;color:var(--text-secondary);line-height:1.8;">
        <div style="margin-bottom:6px;"><strong>密码登录（推荐）</strong> — 每个实例有独立密码，AutoDL 控制台 → SSH 连接 → 复制密码</div>
        <div><strong>密钥登录（免密）</strong> — ssh-keygen 生成密钥对，公钥上传 AutoDL → 账号 → SSH 密钥</div>
      </div>
    </div>
  </div>
</template>
