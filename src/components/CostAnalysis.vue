<script setup lang="ts">
import type { CostData } from '../types'

defineProps<{ costData: CostData; loading: boolean }>()
defineEmits<{ refresh: [] }>()

function y(v: number | null | undefined): string {
  if (v == null) return '--'
  return v.toFixed(2)
}
</script>

<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
      <h1 style="font-size:1.3rem;font-weight:700;margin:0;">费用</h1>
      <button class="btn" @click="$emit('refresh')" :disabled="loading">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg>
        {{ loading ? '刷新中' : '刷新' }}
      </button>
    </div>

    <!-- 双栏 -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;">
      <!-- 服务器 -->
      <div class="glass-card" style="padding:20px;">
        <div style="display:flex;align-items:center;gap:7px;margin-bottom:16px;">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><circle cx="6" cy="6" r="1.5" fill="currentColor"/><circle cx="6" cy="18" r="1.5" fill="currentColor"/></svg>
          <span style="font-size:12px;font-weight:600;color:var(--text-secondary);">AutoDL</span>
        </div>
        <div style="margin-bottom:14px;">
          <div style="font-size:11px;color:var(--text-dim);margin-bottom:2px;">余额</div>
          <div style="font-size:1.5rem;font-weight:700;">¥{{ y(costData.server_balance) }}</div>
        </div>
        <div style="border-top:1px solid var(--border-light);padding-top:12px;">
          <div style="display:flex;justify-content:space-between;">
            <span style="font-size:12px;color:var(--text-dim);">累计消费</span>
            <span style="font-weight:600;">¥{{ y(costData.server_spent) }}</span>
          </div>
        </div>
      </div>

      <!-- AI -->
      <div class="glass-card" style="padding:20px;">
        <div style="display:flex;align-items:center;gap:7px;margin-bottom:16px;">
          <!-- 小鲸鱼 SVG -->
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <ellipse cx="12" cy="14" rx="9" ry="5" stroke-linecap="round"/>
            <path d="M3 14c0-3 2-7 7-9 3-1 7 1 8 3 1 2-2 4-4 4" stroke-linecap="round"/>
            <circle cx="17" cy="11" r="1" fill="currentColor" stroke="none"/>
            <path d="M21 12c1 1 1 3 0 4" stroke-linecap="round"/>
          </svg>
          <span style="font-size:12px;font-weight:600;color:var(--text-secondary);">DeepSeek</span>
        </div>
        <div style="margin-bottom:14px;">
          <div style="font-size:11px;color:var(--text-dim);margin-bottom:2px;">余额</div>
          <div style="font-size:1.5rem;font-weight:700;">{{ costData.ai_balance != null ? '¥' + y(costData.ai_balance) : '--' }}</div>
        </div>
        <div style="border-top:1px solid var(--border-light);padding-top:12px;">
          <div v-if="costData.ai_balance != null" style="display:flex;justify-content:space-between;margin-bottom:4px;">
            <span style="font-size:12px;color:var(--text-dim);">充值 / 赠送</span>
            <span style="font-weight:600;">¥{{ y(costData.ai_topped_up) }} / ¥{{ y(costData.ai_granted) }}</span>
          </div>
          <div style="display:flex;justify-content:space-between;">
            <span style="font-size:12px;color:var(--text-dim);">API 调用</span>
            <span style="font-weight:600;">{{ costData.ai_calls || 0 }} 次</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 总计 — 长条 -->
    <div class="glass-card" style="display:flex;justify-content:space-between;align-items:center;padding:14px 20px;">
      <span style="font-size:13px;font-weight:600;">总计余额</span>
      <span style="font-size:1.3rem;font-weight:700;">¥{{ y(costData.total_balance) }}</span>
    </div>
  </div>
</template>
