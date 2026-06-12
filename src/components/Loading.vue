<script setup lang="ts">
defineProps<{ serverOnline: boolean }>()
</script>

<template>
  <div class="glass-card" style="text-align:center;padding:60px;">
    <div style="font-size:3rem;margin-bottom:16px;">⚡</div>
    <div style="font-size:1.1rem;font-weight:600;color:#e4e4e7;margin-bottom:8px;">AutoDL Manager</div>
    <div v-if="serverOnline" style="color:#4ade80;">后端已连接，正在加载数据...</div>
    <div v-else style="color:#facc15;">正在连接后端服务...</div>
    <div v-if="!serverOnline" style="font-size:12px;color:#52525b;margin-top:12px;">
      请确保 python-sidecar.exe 已启动（端口 8899）<br>等待超时后将自动重试
    </div>
  </div>
</template>
