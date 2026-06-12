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

    <!-- 总计余额卡片 -->
    <div style="background:var(--text);color:#fff;border-radius:12px;padding:24px 28px;margin-bottom:20px;">
      <div style="font-size:12px;opacity:0.7;margin-bottom:6px;">总计余额</div>
      <div style="display:flex;align-items:baseline;gap:8px;">
        <span style="font-size:2.4rem;font-weight:700;letter-spacing:-1px;">¥{{ y(costData.total_balance) }}</span>
      </div>
    </div>

    <!-- 双栏 -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;">
      <!-- 服务器 -->
      <div class="glass-card" style="padding:20px;">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:16px;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><circle cx="6" cy="6" r="1" fill="currentColor"/><circle cx="6" cy="18" r="1" fill="currentColor"/></svg>
          <span style="font-size:12px;font-weight:600;color:var(--text-secondary);">服务器 · AutoDL</span>
        </div>
        <div style="margin-bottom:14px;">
          <div style="font-size:11px;color:var(--text-dim);margin-bottom:2px;">当前余额</div>
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
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:16px;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
          <span style="font-size:12px;font-weight:600;color:var(--text-secondary);">AI · DeepSeek</span>
        </div>
        <div style="margin-bottom:14px;">
          <div style="font-size:11px;color:var(--text-dim);margin-bottom:2px;">余额</div>
          <div style="font-size:1.5rem;font-weight:700;">{{ costData.ai_balance != null ? '¥' + y(costData.ai_balance) : '未配置' }}</div>
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
  </div>
</template>
