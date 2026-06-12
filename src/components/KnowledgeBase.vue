<script setup lang="ts">
interface Entry { id: string; content: string; timestamp: string }

defineProps<{
  entries: Entry[]
  loading: boolean
  query: string
  stats: { conversations: number; experiments: number; decisions: number }
}>()

defineEmits<{
  search: [q: string]
  refresh: []
  'update:query': [v: string]
}>()

function timeAgo(ts: string) {
  if (!ts) return ''
  try {
    const d = new Date(ts), now = new Date()
    const min = Math.floor((now.getTime() - d.getTime()) / 60000)
    if (min < 1) return '刚刚'
    if (min < 60) return min + 'm'
    const h = Math.floor(min / 60)
    if (h < 24) return h + 'h'
    return Math.floor(h / 24) + 'd'
  } catch { return '' }
}
</script>

<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <h1 style="font-size:1.3rem;font-weight:700;margin:0;">知识库</h1>
      <div style="display:flex;gap:14px;font-size:11px;color:var(--text-dim);">
        <span>对话 {{ stats.conversations }}</span>
        <span>实验 {{ stats.experiments }}</span>
        <span>决策 {{ stats.decisions }}</span>
        <button class="btn btn-ghost" @click="$emit('refresh')" :disabled="loading" style="font-size:11px;padding:2px 8px;">刷新</button>
      </div>
    </div>

    <div style="display:flex;gap:6px;margin-bottom:14px;">
      <input :value="query" @input="$emit('update:query', ($event.target as HTMLInputElement).value)"
        @keyup.enter="$emit('search', query)" placeholder="搜索知识库..."
        style="flex:1;font-size:13px;" />
      <button class="btn" @click="$emit('search', query)" :disabled="loading">搜索</button>
    </div>

    <div v-if="loading" style="text-align:center;padding:40px;color:var(--text-dim);font-size:13px;">加载中...</div>

    <div v-else-if="entries.length === 0" style="text-align:center;padding:40px;color:var(--text-dim);">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" style="margin-bottom:10px;">
        <path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/>
        <line x1="8" y1="7" x2="16" y2="7"/><line x1="8" y1="11" x2="14" y2="11"/>
      </svg>
      <div style="font-size:13px;">暂无内容</div>
      <div style="font-size:11px;margin-top:4px;">Agent 对话和实验记录会自动出现在这里</div>
    </div>

    <div v-else style="display:flex;flex-direction:column;gap:8px;">
      <div v-for="e in entries" :key="e.id" class="glass-card" style="padding:12px 14px;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px;">
          <div style="font-size:13px;color:var(--text);line-height:1.5;flex:1;white-space:pre-wrap;">{{ e.content }}</div>
          <span v-if="e.timestamp" style="font-size:10px;color:var(--text-dim);white-space:nowrap;">{{ timeAgo(e.timestamp) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
