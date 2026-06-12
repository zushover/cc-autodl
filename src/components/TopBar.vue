<script setup lang="ts">
import type { Instance } from '../types'

defineProps<{
  currentInstance: Instance | null
  instances: Instance[]
  stats: { running: number; total: number }
}>()

const emit = defineEmits<{
  selectInstance: [uuid: string]
  navTo: [tab: string]
}>()
</script>

<template>
  <div style="display:flex;align-items:center;justify-content:space-between;padding:0 24px;height:48px;background:var(--bg-card);border-bottom:1px solid var(--border);flex-shrink:0;">
    <!-- 左侧品牌 -->
    <div style="font-weight:700;font-size:14px;letter-spacing:-0.2px;color:var(--text);">
      autodlagents
    </div>

    <!-- 右侧服务器信息 -->
    <div style="display:flex;align-items:center;gap:16px;font-size:12px;">
      <!-- 当前服务器 -->
      <div style="display:flex;align-items:center;gap:6px;">
        <span style="color:var(--text-secondary);">当前服务器</span>
        <select
          :value="currentInstance?.uuid || ''"
          @change="emit('selectInstance', ($event.target as HTMLSelectElement).value)"
          style="padding:3px 8px;font-size:12px;background:var(--bg-input);border:1px solid var(--border);border-radius:5px;color:var(--text);cursor:pointer;max-width:160px;"
        >
          <option value="" disabled>未选择</option>
          <option v-for="i in instances" :key="i.uuid" :value="i.uuid">
            {{ i.alias || i.uuid.slice(0, 8) }}
          </option>
        </select>
      </div>

      <!-- 分隔 -->
      <span style="color:var(--border);">|</span>

      <!-- 服务器状态 → 仪表盘 -->
      <button
        @click="emit('navTo', 'dashboard')"
        style="display:flex;align-items:center;gap:5px;padding:3px 10px;background:var(--bg-hover);border:1px solid var(--border);border-radius:5px;color:var(--text-secondary);font-size:12px;cursor:pointer;font-family:inherit;"
        title="服务器状态 (仪表盘)"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
        <span v-if="stats.running > 0" style="color:var(--green);">运行中 {{ stats.running }}</span>
        <span v-else>无运行</span>
      </button>

      <!-- 服务器切换 → 实例列表 -->
      <button
        @click="emit('navTo', 'instances')"
        style="display:flex;align-items:center;gap:5px;padding:3px 10px;background:var(--bg-card);border:1px solid var(--border);border-radius:5px;color:var(--text-secondary);font-size:12px;cursor:pointer;font-family:inherit;"
        title="切换服务器 (实例列表)"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3H5a2 2 0 00-2 2v3m18 0V5a2 2 0 00-2-2h-3m0 18h3a2 2 0 002-2v-3M3 16v3a2 2 0 002 2h3"/></svg>
        切换
      </button>

      <!-- 实例数 -->
      <span style="color:var(--text-dim);">{{ stats.total }} 台实例</span>
    </div>
  </div>
</template>
