<script setup lang="ts">
import { ref, reactive } from 'vue'
import { registerInstance, parseSshString, syncPro } from '../api'
import { useToast } from '../composables/useToast'

const emit = defineEmits<{ registered: [] }>()
const { notify } = useToast()

const visible = ref(false)
const tab = ref<'web' | 'pro' | 'local'>('web')
const loading = ref(false)

const webForm = reactive({ alias: '', ssh_string: '', host: '', port: 22, user: 'root', password: '' })
const proSyncing = ref(false)

async function parseSsh() {
  if (!webForm.ssh_string.trim()) return
  const data = await parseSshString(webForm.ssh_string)
  if (data && !(data as any).error) {
    webForm.host = data.host; webForm.port = data.port; webForm.user = data.user
    notify('SSH 已解析')
  }
}

async function registerWeb() {
  if (!webForm.host.trim()) { notify('请输入 SSH 地址', false); return }
  if (!webForm.password.trim()) { notify('请输入 SSH 密码', false); return }
  loading.value = true
  const data = await registerInstance({
    source: 'web', ssh_host: webForm.host, ssh_port: webForm.port,
    ssh_user: webForm.user, ssh_password: webForm.password,
    alias: webForm.alias || undefined, status: 'running',
  })
  loading.value = false
  if (data && !(data as any).error) { notify('实例已注册'); emit('registered'); visible.value = false; resetWeb() }
  else if (data && (data as any).error) notify('注册失败: ' + (data as any).message, false)
}

async function doSyncPro() {
  proSyncing.value = true
  const data = await syncPro()
  proSyncing.value = false
  if (data?.ok) { notify('同步成功 ' + data.synced + ' 个实例'); emit('registered'); visible.value = false }
  else if (data && (data as any).error) notify('同步失败: ' + (data as any).message, false)
}

function resetWeb() { webForm.alias = ''; webForm.ssh_string = ''; webForm.host = ''; webForm.port = 22; webForm.user = 'root'; webForm.password = '' }
function open() { visible.value = true; tab.value = 'web' }
function close() { visible.value = false }
defineExpose({ open, close })
</script>

<template>
  <div v-if="visible" class="dialog-overlay" @click.self="close">
    <div class="dialog">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3 style="margin:0;">注册实例</h3>
        <button class="btn btn-ghost" @click="close" style="font-size:18px;padding:0 4px;">&times;</button>
      </div>

      <div style="display:flex;gap:0;margin-bottom:16px;border-bottom:2px solid var(--border-light);">
        <button v-for="t in [{k:'web',l:'Web 实例'},{k:'pro',l:'Pro API'},{k:'local',l:'本地'}]" :key="t.k"
          @click="tab = t.k as any"
          :style="{
            padding:'8px 16px',fontSize:'13px',fontWeight:tab===t.k?600:400,background:'none',border:'none',
            cursor:'pointer',fontFamily:'inherit',color:tab===t.k?'var(--text)':'var(--text-dim)',
            borderBottom:tab===t.k?'2px solid var(--text)':'2px solid transparent',marginBottom:'-2px',
          }"
        >{{ t.l }}</button>
      </div>

      <!-- Web -->
      <div v-if="tab === 'web'">
        <div class="form-group"><label>名称 <span style="color:var(--text-dim);">可选</span></label><input v-model="webForm.alias" placeholder="如: 3080Ti-训练机" style="width:100%;"></div>
        <div class="form-group"><label>SSH 命令 <span style="font-size:11px;color:var(--text-dim);">粘贴自动解析</span></label>
          <div style="display:flex;gap:6px;"><input v-model="webForm.ssh_string" placeholder="ssh -p 49200 root@host" style="flex:1;" @blur="parseSsh"><button class="btn" @click="parseSsh" style="font-size:12px;">解析</button></div>
        </div>
        <div class="form-row"><div class="form-group"><label>Host</label><input v-model="webForm.host" style="width:100%;"></div><div class="form-group"><label>Port</label><input v-model.number="webForm.port" type="number" style="width:100%;"></div></div>
        <div class="form-group"><label>User</label><input v-model="webForm.user" style="width:100%;"></div>
        <div class="form-group"><label>SSH 密码</label><input v-model="webForm.password" type="password" placeholder="AutoDL 控制台复制" style="width:100%;"></div>
        <button class="btn btn-primary" @click="registerWeb" :disabled="loading" style="width:100%;margin-top:8px;">{{ loading ? '注册中...' : '注册实例' }}</button>
      </div>

      <!-- Pro API -->
      <div v-if="tab === 'pro'">
        <div style="font-size:12px;color:var(--text-dim);margin-bottom:12px;">使用开发者 Token 自动同步 Pro API 创建的所有实例，无需手动输入 SSH 信息。Token 从 autodl.com → 设置 → 开发者 Token 获取。</div>
        <button class="btn btn-primary" @click="doSyncPro" :disabled="proSyncing" style="width:100%;">{{ proSyncing ? '同步中...' : '同步 Pro API 实例' }}</button>
      </div>

      <!-- Local -->
      <div v-if="tab === 'local'">
        <div style="text-align:center;padding:32px;color:var(--text-dim);">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" style="margin-bottom:10px;"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/></svg>
          <div style="font-size:13px;font-weight:600;color:var(--text-secondary);margin-bottom:4px;">本地实例</div>
          <div style="font-size:12px;">局域网 / 本机 GPU 连接，即将推出</div>
        </div>
      </div>
    </div>
  </div>
</template>
