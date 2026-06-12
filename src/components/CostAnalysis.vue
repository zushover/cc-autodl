<script setup lang="ts">
import type { CostData } from '../types'

defineProps<{ costData: CostData; loading: boolean }>()
defineEmits<{ refresh: [] }>()

function fmt(v: number | null | undefined): string {
  if (v == null) return '--'
  return v.toFixed(2)
}
function fmtToken(n: number | undefined): string {
  if (!n) return '0'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return n.toString()
}
</script>

<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
      <h1 style="font-size:1.3rem;font-weight:700;margin:0;">费用分析</h1>
      <button class="btn" @click="$emit('refresh')" :disabled="loading">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 102.13-9.36L1 10"/></svg>
        {{ loading ? '刷新中' : '刷新' }}
      </button>
    </div>

    <!-- 服务器费用 -->
    <div style="margin-bottom:24px;">
      <div style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:10px;">服务器费用 · AutoDL GPU</div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:10px;">
        <div class="glass-card" style="text-align:center;padding:16px 12px;">
          <div class="metric-num" style="font-size:1.6rem;">{{ costData.balance_yuan != null ? '¥' + fmt(costData.balance_yuan) : '--' }}</div>
          <div class="metric-label">当前余额</div>
        </div>
        <div class="glass-card" style="text-align:center;padding:16px 12px;">
          <div class="metric-num" style="font-size:1.6rem;">{{ costData.runway_days ?? '--' }}</div>
          <div class="metric-label">预估天数</div>
        </div>
        <div class="glass-card" style="text-align:center;padding:16px 12px;">
          <div class="metric-num" style="font-size:1.6rem;">¥{{ fmt(costData.total_spent) }}</div>
          <div class="metric-label">累计消费</div>
        </div>
        <div class="glass-card" style="text-align:center;padding:16px 12px;">
          <div class="metric-num" style="font-size:1.6rem;">¥{{ fmt(costData.voucher_balance) }}</div>
          <div class="metric-label">代金券</div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;">
        <div class="glass-card" style="display:flex;justify-content:space-between;align-items:center;padding:12px 16px;">
          <span style="font-size:12px;color:var(--text-secondary);">今日</span>
          <span style="font-weight:600;">¥{{ fmt(costData.today_cost) }}</span>
        </div>
        <div class="glass-card" style="display:flex;justify-content:space-between;align-items:center;padding:12px 16px;">
          <span style="font-size:12px;color:var(--text-secondary);">本周</span>
          <span style="font-weight:600;">¥{{ fmt(costData.week_cost) }}</span>
        </div>
        <div class="glass-card" style="display:flex;justify-content:space-between;align-items:center;padding:12px 16px;">
          <span style="font-size:12px;color:var(--text-secondary);">日均</span>
          <span style="font-weight:600;">¥{{ fmt(costData.daily_rate_yuan) }}</span>
        </div>
      </div>
    </div>

    <!-- AI 费用 -->
    <div>
      <div style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:10px;">AI 费用 · DeepSeek API</div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;">
        <div class="glass-card" style="text-align:center;padding:16px 12px;">
          <div class="metric-num" style="font-size:1.3rem;">{{ costData.ai_total_calls || 0 }}</div>
          <div class="metric-label">API 调用次数</div>
        </div>
        <div class="glass-card" style="text-align:center;padding:16px 12px;">
          <div class="metric-num" style="font-size:1.3rem;">{{ fmtToken(costData.ai_total_tokens) }}</div>
          <div class="metric-label">Token 用量</div>
        </div>
        <div class="glass-card" style="text-align:center;padding:16px 12px;">
          <div class="metric-num" style="font-size:1.3rem;">¥{{ fmt(costData.ai_estimated_cost_yuan) }}</div>
          <div class="metric-label">预估费用</div>
        </div>
      </div>
      <div style="font-size:11px;color:var(--text-dim);margin-top:8px;">
        * DeepSeek 定价约 ¥1/百万 token，实际费用以 API 账单为准
      </div>
    </div>
  </div>
</template>
