<script setup lang="ts">
import { ref, onMounted } from 'vue'

interface MemoryEntry {
  id: string
  content: string
  timestamp: string
}

const entries = ref<MemoryEntry[]>([])
const results = ref<MemoryEntry[]>([])
const query = ref('')
const loading = ref(false)
const stats = ref({ conversations: 0, experiments: 0, decisions: 0 })
const activeTab = ref<'all' | 'experiments' | 'conversations'>('all')

async function loadStats() {
  try {
    const res = await fetch('http://127.0.0.1:8899/api/agent/status')
    const data = await res.json()
    if (data.memory) stats.value = data.memory
  } catch (_) { /* ignore */ }
}

async function loadAll() {
  loading.value = true
  try {
    const res = await fetch('http://127.0.0.1:8899/api/agent/tasks')
    const data = await res.json()
    if (data.tasks) {
      entries.value = data.tasks.map((t: any) => ({
        id: t.id,
        content: typeof t.content === 'string' ? t.content : JSON.stringify(t.content),
        timestamp: t.meta?.timestamp || '',
      }))
    }
  } catch (_) { /* ignore */ }
  loading.value = false
}

async function search() {
  if (!query.value.trim()) { await loadAll(); return }
  loading.value = true
  try {
    const res = await fetch('http://127.0.0.1:8899/api/memory/experiments?q=' + encodeURIComponent(query.value) + '&n=20')
    const data = await res.json()
    results.value = (data.results || []).map((r: string, i: number) => ({
      id: 'result-' + i,
      content: r,
      timestamp: '',
    }))
  } catch (_) { /* ignore */ }
  loading.value = false
}

function timeAgo(ts: string): string {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    const now = new Date()
    const min = Math.floor((now.getTime() - d.getTime()) / 60000)
    if (min < 1) return '刚刚'
    if (min < 60) return min + ' 分钟前'
    const h = Math.floor(min / 60)
    if (h < 24) return h + ' 小时前'
    return Math.floor(h / 24) + ' 天前'
  } catch { return '' }
}

onMounted(() => { loadStats(); loadAll() })
</script>

<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
      <h1 style="font-size:1.3rem;font-weight:700;margin:0;letter-spacing:-0.3px;">知识库</h1>
      <div style="display:flex;gap:14px;font-size:11px;color:var(--text-dim);">
        <span>对话 {{ stats.conversations }}</span>
        <span>实验 {{ stats.experiments }}</span>
        <span>决策 {{ stats.decisions }}</span>
      </div>
    </div>

    <!-- 搜索 -->
    <div style="display:flex;gap:6px;margin-bottom:14px;">
      <input v-model="query" @keyup.enter="search" placeholder="搜索知识库..." style="flex:1;font-size:13px;" />
      <button class="btn" @click="search" :disabled="loading">{{ loading ? '搜索中' : '搜索' }}</button>
      <button class="btn btn-ghost" @click="loadAll" :disabled="loading" style="font-size:12px;">刷新</button>
    </div>

    <!-- 标签切换 -->
    <div style="display:flex;gap:0;margin-bottom:14px;border-bottom:1px solid var(--border-light);">
      <button v-for="t in [{k:'all',l:'全部'},{k:'experiments',l:'实验'},{k:'conversations',l:'对话'}]" :key="t.k"
        @click="activeTab = t.k as any"
        :style="{
          padding:'6px 14px',fontSize:'12px',fontWeight:activeTab===t.k?600:400,
          background:'none',border:'none',cursor:'pointer',fontFamily:'inherit',
          color:activeTab===t.k?'var(--text)':'var(--text-dim)',
          borderBottom:activeTab===t.k?'2px solid var(--text)':'2px solid transparent',
          marginBottom:'-1px',
        }"
      >{{ t.l }}</button>
    </div>

    <!-- 条目列表 -->
    <div v-if="entries.length === 0 && results.length === 0 && !loading" style="text-align:center;padding:40px;color:var(--text-dim);">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" style="margin-bottom:10px;">
        <path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/><line x1="8" y1="7" x2="16" y2="7"/><line x1="8" y1="11" x2="14" y2="11"/>
      </svg>
      <div style="font-size:13px;">暂无内容</div>
      <div style="font-size:11px;margin-top:4px;">Agent 对话和实验记录会自动出现在这里</div>
    </div>

    <div v-else style="display:flex;flex-direction:column;gap:8px;">
      <div v-for="e in (results.length > 0 ? results : entries)" :key="e.id"
        class="glass-card" style="padding:12px 14px;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px;">
          <div style="font-size:13px;color:var(--text);line-height:1.5;flex:1;white-space:pre-wrap;">{{ e.content }}</div>
          <span v-if="e.timestamp" style="font-size:10px;color:var(--text-dim);white-space:nowrap;">{{ timeAgo(e.timestamp) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
