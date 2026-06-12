<script setup lang="ts">
defineProps<{ serverOnline: boolean }>()
</script>

<template>
  <div class="glass-card" style="text-align:center;padding:60px;">
    <div style="font-size:1.1rem;color:var(--text);margin-bottom:8px;font-weight:600;"><span style="font-weight:800;">A</span>utodl<span style="font-weight:800;">A</span>gents</div>
    <div v-if="serverOnline" :style="{color:'var(--green)'}">后端已连接，正在加载数据...</div>
    <div v-else :style="{color: 'var(--text-secondary)'}">正在连接后端服务...</div>
    <div v-if="!serverOnline" style="font-size:12px;color:var(--text-dim);margin-top:12px;">
      请确保 python-sidecar.exe 已启动（端口 8899）<br>等待超时后将自动重试
    </div>
  </div>
</template>
