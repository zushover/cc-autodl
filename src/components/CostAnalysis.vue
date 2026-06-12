<script setup lang="ts">
import type { CostData } from '../types'

defineProps<{ costData: CostData; loading: boolean }>()
defineEmits<{ refresh: [] }>()
</script>

<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
      <h1 style="font-size:1.4rem;font-weight:700;">费用分析</h1>
      <button class="btn" @click="$emit('refresh')" :disabled="loading">{{ loading ? '⏳' : '🔄' }} 刷新</button>
    </div>

    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px;">
      <div class="glass-card" style="text-align:center;">
        <div class="metric-num">¥{{ costData.today_cost || '0.00' }}</div>
        <div class="metric-label">今日消费</div>
      </div>
      <div class="glass-card" style="text-align:center;">
        <div class="metric-num">¥{{ costData.week_cost || '0.00' }}</div>
        <div class="metric-label">本周消费</div>
      </div>
      <div class="glass-card" style="text-align:center;">
        <div class="metric-num accent">¥{{ costData.balance_yuan != null ? costData.balance_yuan : '--' }}</div>
        <div class="metric-label">当前余额</div>
      </div>
      <div class="glass-card" style="text-align:center;">
        <div class="metric-num">{{ costData.runway_days ?? '--' }}</div>
        <div class="metric-label">预估可用天数</div>
      </div>
    </div>

    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:20px;">
      <div class="glass-card">
        <div style="color:#71717a;font-size:12px;">累计消费</div>
        <div style="font-size:1.3rem;font-weight:700;">¥{{ costData.total_spent?.toFixed(2) || '--' }}</div>
      </div>
      <div class="glass-card">
        <div style="color:#71717a;font-size:12px;">代金券</div>
        <div style="font-size:1.3rem;font-weight:700;">¥{{ costData.voucher_balance?.toFixed(2) || '0.00' }}</div>
      </div>
      <div class="glass-card">
        <div style="color:#71717a;font-size:12px;">日均消费</div>
        <div style="font-size:1.3rem;font-weight:700;">¥{{ costData.daily_rate_yuan || '0.00' }}</div>
      </div>
    </div>
  </div>
</template>
