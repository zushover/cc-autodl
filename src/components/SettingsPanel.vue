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
  const data = await saveSettings(settings.value.token, settings.value.ssh_key)
  if (data?.ok) {
    settings.value.hasToken = !!(settings.value.token && settings.value.token !== 'your-token-here')
    notify('✅ 设置已保存')
    emit('costUpdated')
  } else if (data && (data as any).error) {
    notify('保存失败: ' + (data as any).message, false)
  }
}

init()
</script>

<template>
  <div>
    <h1 style="font-size:1.4rem;font-weight:700;margin-bottom:20px;">设置</h1>

    <div class="glass-card" style="margin-bottom:12px;">
      <div style="font-weight:600;margin-bottom:12px;">AutoDL 开发者 Token</div>
      <div v-if="settings.hasToken" style="margin-bottom:8px;">
        <span class="badge badge-running">✅ 已配置</span>
      </div>
      <div style="display:flex;gap:8px;">
        <input v-model="settings.token" type="password" placeholder="输入 AutoDL 开发者 Token" style="flex:1;">
        <button class="btn btn-primary" @click="save">保存</button>
      </div>
      <div style="font-size:11px;color:#52525b;margin-top:6px;">获取: autodl.com → 控制台 → 设置 → 开发者 Token</div>
    </div>

    <div class="glass-card" style="margin-bottom:12px;">
      <div style="font-weight:600;margin-bottom:12px;">SSH 登录方式说明</div>
      <div style="font-size:13px;color:#a1a1aa;line-height:1.8;">
        <strong>🔑 密码登录（推荐，简单）</strong><br>
        每个 AutoDL 实例都有独立的 SSH 密码（如 <code style="background:rgba(255,255,255,0.06);padding:2px 6px;">ppPyRVTCfkGr</code>），<br>
        在 AutoDL 控制台 → 实例 → SSH 连接 → 复制密码。<br>
        注册实例时直接填入密码即可。<br><br>
        <strong>🔐 密钥登录（高级，免密）</strong><br>
        1. 终端运行 <code style="background:rgba(255,255,255,0.06);padding:2px 6px;">ssh-keygen -t rsa</code> 生成密钥对<br>
        2. 将公钥上传到 autodl.com → 账号 → SSH 密钥<br>
        3. 配置后所有实例自动生效
      </div>
    </div>

    <div class="glass-card">
      <div style="font-weight:600;margin-bottom:12px;">系统状态</div>
      <p style="font-size:13px;color:#71717a;">
        <span :style="{color: serverOnline ? '#4ade80' : '#f87171'}">
          后端: {{ serverOnline ? '🟢 在线' : '🔴 离线' }}
        </span>
        · GPU采集: 120s · 余额告警: ¥50
      </p>
    </div>
  </div>
</template>
