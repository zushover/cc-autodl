<script setup lang="ts">
</script>

<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
      <h1 style="font-size:1.3rem;font-weight:700;margin:0;letter-spacing:-0.3px;">知识库</h1>
    </div>

    <div style="text-align:center;padding:60px 20px;background:var(--bg-card);border:1px solid var(--border);border-radius:12px;">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" style="color:var(--text-dim);margin-bottom:12px;">
        <path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/>
        <line x1="8" y1="7" x2="16" y2="7"/><line x1="8" y1="11" x2="14" y2="11"/>
      </svg>
      <div style="font-weight:600;margin-bottom:4px;">实验记录 & 文档索引</div>
      <div style="font-size:12px;color:var(--text-dim);">ChromaDB 驱动的 Agent 共享知识库，即将推出</div>
    </div>
  </div>
</template>
