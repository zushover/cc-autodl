<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import type { SourceType } from '../types'
import { loadGpuTypes, loadRegions, registerInstance, parseSshString } from '../api'
import { useToast } from '../composables/useToast'

const emit = defineEmits<{ registered: [] }>()

const { notify } = useToast()

const show = ref(false)
const loading = ref(false)
const gpuTypes = ref<{ name: string; vram: string; price: number }[]>([])
const regions = ref<string[]>([])

const form = reactive({
  source: 'web' as SourceType,
  uuid: '',
  ssh_string: '',
  ssh_host: '',
  ssh_port: 22,
  ssh_user: 'root',
  ssh_password: '',
  alias: '',
  gpu_type: '',
  region: '',
  price_per_hour: 0,
  status: 'stopped',
  tags_str: '',
})

function onGpuSelect() {
  const gpu = gpuTypes.value.find(g => g.name === form.gpu_type)
  if (gpu) form.price_per_hour = gpu.price
}

async function onPasteSsh() {
  await new Promise(r => setTimeout(r, 100))
  await parse()
}

async function parse() {
  if (!form.ssh_string.trim()) return
  const resp = await parseSshString(form.ssh_string)
  if (resp && (resp as any).host) {
    form.ssh_host = (resp as any).host
    form.ssh_port = (resp as any).port
    form.ssh_user = (resp as any).user
    notify('✅ 已解析: ' + (resp as any).user + '@' + (resp as any).host + ':' + (resp as any).port)
  }
}

async function open() {
  form.source = 'web'
  const [gpuData, regionData] = await Promise.all([loadGpuTypes('web'), loadRegions()])
  if (gpuData && !(gpuData as any).error) gpuTypes.value = gpuData.gpu_types || []
  if (regionData && !(regionData as any).error) regions.value = regionData.regions || []
  show.value = true
}

function cancel() {
  show.value = false
  loading.value = false
  form.ssh_string = ''; form.ssh_host = ''; form.ssh_port = 22
  form.ssh_user = 'root'; form.ssh_password = ''; form.alias = ''
  form.gpu_type = ''; form.region = ''; form.price_per_hour = 0
  form.status = 'stopped'; form.tags_str = ''
}

async function submit() {
  if (form.source !== 'pro') {
    if (!form.ssh_host.trim()) { notify('请输入 SSH 主机地址', false); return }
    if (!form.alias.trim()) { notify('请输入别名', false); return }
    if (!form.ssh_password.trim()) { notify('请输入 SSH 密码（AutoDL 提供）', false); return }
  } else {
    if (!form.uuid.trim()) { notify('请输入 Pro 实例 UUID', false); return }
  }

  loading.value = true
  const body: Record<string, unknown> = { source: form.source, status: form.status }
  if (form.source === 'pro') {
    body.uuid = form.uuid
  } else {
    body.ssh_host = form.ssh_host; body.ssh_port = form.ssh_port
    body.ssh_user = form.ssh_user; body.ssh_password = form.ssh_password
    body.alias = form.alias
    body.tags = form.tags_str ? form.tags_str.split(',').map(s => s.trim()).filter(Boolean) : []
    if (form.source === 'web') {
      body.gpu_type = form.gpu_type; body.region = form.region
      body.price_per_hour = form.price_per_hour
    }
  }

  const data = await registerInstance(body)
  if (data?.instance) {
    notify('✅ 注册成功: ' + (data.instance.alias || data.instance.uuid?.slice(0, 14)))
    show.value = false
    emit('registered')
  } else if (data && (data as any).error) {
    notify('注册失败: ' + (data as any).message, false)
  }
  loading.value = false
}

watch(() => form.source, async (src) => {
  if (src === 'web') {
    const gpuData = await loadGpuTypes('web')
    if (gpuData && !(gpuData as any).error) gpuTypes.value = gpuData.gpu_types || []
  }
})

defineExpose({ open })
</script>

<template>
  <div v-if="show" class="dialog-overlay" @click.self="cancel">
    <div class="dialog" style="width:540px;max-height:85vh;">
      <h3>注册实例</h3>

      <!-- Source type -->
      <div class="form-group">
        <label>来源</label>
        <div style="display:flex;gap:8px;">
          <button :class="'btn'+(form.source==='web'?' btn-primary':'')" @click="form.source='web'" style="flex:1;">Web 控制台</button>
          <button :class="'btn'+(form.source==='ssh'?' btn-primary':'')" @click="form.source='ssh'" style="flex:1;">自定义 SSH</button>
          <button :class="'btn'+(form.source==='pro'?' btn-primary':'')" @click="form.source='pro'" style="flex:1;">Pro API</button>
        </div>
      </div>

      <!-- Pro mode -->
      <template v-if="form.source==='pro'">
        <div class="form-group"><label>Pro 实例 UUID <span style="color:#f87171;">*</span></label><input v-model="form.uuid" placeholder="pro-xxxxxxxx"></div>
      </template>

      <!-- Web/SSH mode -->
      <template v-else>
        <div class="form-group">
          <label>SSH 连接命令 <span style="font-size:11px;color:#71717a;">（粘贴自动解析）</span></label>
          <div style="display:flex;gap:6px;">
            <input v-model="form.ssh_string" placeholder="例如: ssh -p 50479 root@connect.bjb2.seetacloud.com" style="flex:1;font-size:12px;" @paste="onPasteSsh">
            <button class="btn" @click="parse" style="white-space:nowrap;">🔍 解析</button>
          </div>
        </div>

        <div class="form-row">
          <div class="form-group"><label>主机 <span style="color:#f87171;">*</span></label><input v-model="form.ssh_host" placeholder="connect.xxx.autodl.com"></div>
          <div class="form-group"><label>端口</label><input v-model.number="form.ssh_port" type="number" style="width:80px;"></div>
          <div class="form-group"><label>用户</label><input v-model="form.ssh_user" style="width:80px;"></div>
        </div>

        <div class="form-group">
          <label>SSH 密码 <span style="color:#f87171;">*</span> <span style="font-size:11px;color:#71717a;">（AutoDL 控制台复制）</span></label>
          <input v-model="form.ssh_password" type="password" placeholder="例如: ppPyRVTCfkGr">
          <div style="font-size:11px;color:#52525b;margin-top:4px;">AutoDL 实例页 → SSH 连接 → 复制密码（非密钥文件）</div>
        </div>

        <div class="form-row" v-if="form.source==='web'">
          <div class="form-group">
            <label>GPU 型号</label>
            <select v-model="form.gpu_type" @change="onGpuSelect">
              <option value="">-- 选择 GPU --</option>
              <option v-for="g in gpuTypes" :key="g.name" :value="g.name">{{ g.name }} ({{ g.vram }})</option>
            </select>
          </div>
          <div class="form-group">
            <label>区域</label>
            <select v-model="form.region">
              <option value="">-- 选择区域 --</option>
              <option v-for="r in regions" :key="r" :value="r">{{ r }}</option>
            </select>
          </div>
        </div>

        <div class="form-row">
          <div class="form-group"><label>别名 <span style="color:#f87171;">*</span></label><input v-model="form.alias" placeholder="北京3090-训练"></div>
          <div class="form-group">
            <label>初始状态</label>
            <select v-model="form.status">
              <option value="stopped">已关机</option>
              <option value="running">运行中</option>
              <option value="no_gpu">无卡模式</option>
            </select>
          </div>
        </div>

        <div class="form-group" v-if="form.source==='web'"><label>单价 (¥/h)</label><input v-model.number="form.price_per_hour" type="number" step="0.01"></div>
        <div class="form-group"><label>标签</label><input v-model="form.tags_str" placeholder="微调, Qwen (逗号分隔)"></div>
      </template>

      <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:16px;">
        <button class="btn" @click="cancel">取消</button>
        <button class="btn btn-primary" @click="submit" :disabled="loading">{{ loading ? '⏳ 注册中...' : '注册' }}</button>
      </div>
    </div>
  </div>
</template>

