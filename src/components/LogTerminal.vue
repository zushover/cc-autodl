<script setup lang="ts">
import type { Instance } from '../types'

defineProps<{ currentInstance: Instance | null; logLines: string[] }>()
</script>

<template>
  <div>
    <h1 style="font-size:1.4rem;font-weight:700;margin-bottom:12px;">日志终端</h1>
    <div v-if="!currentInstance" class="glass-card" style="text-align:center;padding:40px;">请先选择一个实例</div>
    <div v-else class="glass" style="background:#000;padding:16px;font-family:monospace;font-size:13px;max-height:500px;overflow-y:auto;">
      <div v-if="logLines.length===0" style="color:#52525b;">等待日志...</div>
      <div
        v-for="(line, i) in logLines"
        :key="i"
        style="line-height:1.6;"
        :style="{color: line.includes('NaN') ? '#f87171' : line.includes('loss') ? '#60a5fa' : line.includes('Step') ? '#4ade80' : '#a1a1aa'}"
      >{{ line }}</div>
    </div>
  </div>
</template>
