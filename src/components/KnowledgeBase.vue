<script setup lang="ts">
import { ref, computed } from 'vue'

interface Entry { id: string; content: string; timestamp: string; type?: string }

const props = defineProps<{
  entries: Entry[]
  loading: boolean
  query: string
  stats: { conversations: number; experiments: number; decisions: number }
}>()

const emit = defineEmits(['search', 'refresh', 'update:query'])

const activeCategory = ref('all')
const activeAgent = ref('all')

const categories = computed(() => [
  { key: 'all', label: '全部', count: props.entries.length },
  { key: 'conversation', label: '对话', count: props.stats.conversations },
  { key: 'experiment', label: '实验', count: props.stats.experiments },
  { key: 'decision', label: '决策', count: props.stats.decisions },
  { key: 'document', label: '文档', count: 0 },
])

const agents = [
  { key: 'all', label: '全部 Agent' },
  { key: 'triple-a', label: 'Triple A (Master)' },
  { key: 'server-3080ti', label: 'Server · 3080Ti' },
  { key: 'server-4090d', label: 'Server · 4090D' },
]

const filtered = computed(() => {
  let items = props.entries
  if (activeCategory.value !== 'all') {
    items = items.filter(e => (e.type || '').includes(activeCategory.value))
  }
  return items
})

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

function typeIcon(t: string) {
  return t === 'experiment' ? '🧪' : t === 'decision' ? '📋' : t === 'conversation' ? '💬' : '📄'
}
</script>

<template>
  <div style="display:flex;gap:16px;height:calc(100vh - 80px);">
    <!-- 左侧面板 -->
    <div style="width:180px;flex-shrink:0;display:flex;flex-direction:column;gap:16px;">
      <!-- Agent 选择器 -->
      <div>
        <div style="font-size:10px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">Agent</div>
        <select v-model="activeAgent"
          style="width:100%;font-size:12px;padding:5px 8px;">
          <option v-for="a in agents" :key="a.key" :value="a.key">{{ a.label }}</option>
        </select>
      </div>

      <!-- 分类 -->
      <div>
        <div style="font-size:10px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">分类</div>
        <div style="display:flex;flex-direction:column;gap:1px;">
          <button v-for="c in categories" :key="c.key" @click="activeCategory = c.key"
            :style="{
              padding:'5px 8px',fontSize:'12px',textAlign:'left',background:activeCategory===c.key?'var(--bg-hover)':'transparent',
              border:'none',borderRadius:'4px',cursor:'pointer',fontFamily:'inherit',
              color:activeCategory===c.key?'var(--text)':'var(--text-dim)',fontWeight:activeCategory===c.key?600:400,
              display:'flex',justifyContent:'space-between',
            }"
          ><span>{{ c.label }}</span><span style="color:var(--text-dim);font-size:10px;">{{ c.count }}</span></button>
        </div>
      </div>

      <!-- Agent 记忆占位 -->
      <div v-if="activeAgent !== 'all'" class="glass-card" style="padding:10px;font-size:11px;color:var(--text-dim);text-align:center;">
        <div style="font-size:10px;font-weight:600;margin-bottom:4px;">专属记忆</div>
        <div>该 Agent 的对话和实验结果会单独归档</div>
        <div style="margin-top:6px;font-size:10px;color:var(--text-dim);opacity:0.5;">即将推出</div>
      </div>
    </div>

    <!-- 右侧主内容 -->
    <div style="flex:1;min-width:0;display:flex;flex-direction:column;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
        <h1 style="font-size:1.3rem;font-weight:700;margin:0;">知识库</h1>
        <div style="display:flex;gap:10px;font-size:11px;color:var(--text-dim);">
          <button class="btn btn-ghost" @click="$emit('refresh')" :disabled="loading" style="font-size:11px;padding:2px 8px;">刷新</button>
        </div>
      </div>

      <div style="display:flex;gap:6px;margin-bottom:14px;">
        <input :value="query" @input="$emit('update:query', ($event.target as HTMLInputElement).value)"
          @keyup.enter="$emit('search', query)" placeholder="搜索知识库..."
          style="flex:1;font-size:13px;" />
        <button class="btn" @click="$emit('search', query)" :disabled="loading">搜索</button>
      </div>

      <div v-if="loading" style="text-align:center;padding:40px;color:var(--text-dim);">加载中...</div>

      <div v-else-if="filtered.length === 0" style="text-align:center;padding:40px;color:var(--text-dim);flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" style="margin-bottom:10px;">
          <path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/>
          <line x1="8" y1="7" x2="16" y2="7"/><line x1="8" y1="11" x2="14" y2="11"/>
        </svg>
        <div style="font-size:13px;">暂无内容</div>
        <div style="font-size:11px;margin-top:4px;">Agent 对话和实验结果会自动归档</div>
      </div>

      <div v-else style="flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:8px;">
        <div v-for="e in filtered" :key="e.id" class="glass-card" style="padding:10px 14px;">
          <div style="display:flex;align-items:flex-start;gap:8px;">
            <span style="font-size:14px;flex-shrink:0;">{{ typeIcon(e.type || '') }}</span>
            <div style="flex:1;min-width:0;">
              <div style="font-size:12px;color:var(--text);line-height:1.5;white-space:pre-wrap;">{{ e.content }}</div>
              <div style="display:flex;justify-content:space-between;margin-top:4px;">
                <span style="font-size:10px;color:var(--text-dim);">{{ e.type || 'doc' }}</span>
                <span v-if="e.timestamp" style="font-size:10px;color:var(--text-dim);">{{ timeAgo(e.timestamp) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
