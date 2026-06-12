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
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 102.13-9.36L1 10"/></svg>
        {{ loading ? '刷新中' : '刷新' }}
      </button>
    </div>

    <!-- 总计 -->
    <div class="glass-card" style="text-align:center;padding:20px;margin-bottom:20px;">
      <div style="font-size:12px;color:var(--text-secondary);margin-bottom:4px;">总计余额</div>
      <div style="font-size:2.2rem;font-weight:700;letter-spacing:-1px;">¥{{ y(costData.total_balance) }}</div>
    </div>

    <!-- 双栏 -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
      <!-- 服务器费用 -->
      <div class="glass-card" style="padding:20px;">
        <div style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:16px;">服务器 · AutoDL</div>
        <div style="margin-bottom:16px;">
          <div style="font-size:12px;color:var(--text-secondary);margin-bottom:4px;">当前余额</div>
          <div style="font-size:1.6rem;font-weight:700;">¥{{ y(costData.server_balance) }}</div>
        </div>
        <div>
          <div style="font-size:12px;color:var(--text-secondary);margin-bottom:4px;">累计消费</div>
          <div style="font-size:1.3rem;font-weight:600;">¥{{ y(costData.server_spent) }}</div>
        </div>
      </div>

      <!-- AI 费用 -->
      <div class="glass-card" style="padding:20px;">
        <div style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:16px;">AI · DeepSeek</div>
        <div style="margin-bottom:16px;">
          <div style="font-size:12px;color:var(--text-secondary);margin-bottom:4px;">余额</div>
          <div style="font-size:1.6rem;font-weight:700;">{{ costData.ai_balance != null ? '¥' + y(costData.ai_balance) : '未配置' }}</div>
        </div>
        <div v-if="costData.ai_balance != null" style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px;">
          <div>
            <div style="font-size:11px;color:var(--text-dim);">充值</div>
            <div style="font-weight:600;">¥{{ y(costData.ai_topped_up) }}</div>
          </div>
          <div>
            <div style="font-size:11px;color:var(--text-dim);">赠送</div>
            <div style="font-weight:600;">¥{{ y(costData.ai_granted) }}</div>
          </div>
        </div>
        <div>
          <div style="font-size:12px;color:var(--text-secondary);margin-bottom:4px;">API 调用</div>
          <div style="font-weight:600;">{{ costData.ai_calls || 0 }} 次</div>
        </div>
      </div>
    </div>
  </div>
</template>
