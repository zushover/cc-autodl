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
</script>

<template>
  <div style="width:220px;background:#0d0d10;border-right:1px solid rgba(255,255,255,0.04);display:flex;flex-direction:column;padding:16px 12px;flex-shrink:0;">
    <div style="padding:8px 16px 20px;font-weight:800;font-size:15px;letter-spacing:-0.3px;color:#e4e4e7;">⚡ AutoDL Manager</div>
    <nav style="flex:1;">
      <div
        v-for="tab in tabs"
        :key="tab.id"
        :class="'sidebar-link' + (currentTab === tab.id ? ' active' : '')"
        @click="$emit('selectTab', tab.id)"
      >
        <span style="width:20px;text-align:center;">{{ tab.icon }}</span> {{ tab.label }}
      </div>
    </nav>
    <div class="glass-card" style="margin-top:auto;font-size:12px;">
      <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
        <span class="text-dim">余额</span>
        <span style="font-weight:700;">{{ loading ? '...' : '¥' + balanceDisplay }}</span>
      </div>
      <div style="display:flex;justify-content:space-between;">
        <span class="text-dim">实例</span>
        <span>
          <span v-if="loading">...</span>
          <span v-else><span style="color:#4ade80;">{{ stats.running }}</span> / {{ stats.total }}</span>
        </span>
      </div>
    </div>
  </div>
</template>
