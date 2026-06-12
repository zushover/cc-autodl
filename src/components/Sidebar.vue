<script setup lang="ts">
import type { Tab } from '../types'

defineProps<{
  tabs: Tab[]
  currentTab: string
  balanceDisplay: string
  stats: { running: number; total: number }
  loading: boolean
}>()

defineEmits<{ selectTab: [id: string] }>()

// 每个 tab 对应的 SVG 图标
const icons: Record<string, string> = {
  dashboard:  'dashboard',
  instances:  'server',
  agent:      'agent',
  cost:       'cost',
  logs:       'logs',
  settings:   'settings',
}
</script>

<template>
  <div style="width:180px;background:var(--bg-sidebar);border-right:1px solid var(--border);display:flex;flex-direction:column;padding:14px 10px;flex-shrink:0;">
    <div style="padding:6px 10px 18px;font-weight:700;font-size:14px;letter-spacing:-0.2px;color:var(--text);">
      autodlagents
    </div>

    <nav style="flex:1;">
      <div
        v-for="tab in tabs"
        :key="tab.id"
        :class="'sidebar-link' + (currentTab === tab.id ? ' active' : '')"
        @click="$emit('selectTab', tab.id)"
      >
        <!-- Dashboard -->
        <svg v-if="tab.id === 'dashboard'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
        <!-- Instances -->
        <svg v-else-if="tab.id === 'instances'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><circle cx="6" cy="6" r="1" fill="currentColor"/><circle cx="6" cy="18" r="1" fill="currentColor"/></svg>
        <!-- Agent -->
        <svg v-else-if="tab.id === 'agent'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
        <!-- Cost -->
        <svg v-else-if="tab.id === 'cost'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>
        <!-- Logs -->
        <svg v-else-if="tab.id === 'logs'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
        <!-- Settings -->
        <svg v-else-if="tab.id === 'settings'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"/></svg>
        {{ tab.label }}
      </div>
    </nav>

    <!-- 底部信息 -->
    <div class="glass-card" style="font-size:11px;padding:12px;">
      <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
        <span class="text-dim">余额</span>
        <span style="font-weight:600;">{{ loading ? '...' : '¥' + balanceDisplay }}</span>
      </div>
      <div style="display:flex;justify-content:space-between;">
        <span class="text-dim">实例</span>
        <span>
          <span v-if="loading">...</span>
          <span v-else><span :style="{ color: stats.running > 0 ? 'var(--green)' : 'var(--text-secondary)' }">{{ stats.running }}</span> / {{ stats.total }}</span>
        </span>
      </div>
    </div>
  </div>
</template>
