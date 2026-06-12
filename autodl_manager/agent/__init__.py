"""Agent 模块 — 为 cc-autodl 提供 LLM 驱动的自主决策能力。

模块结构：
  tools.py        — LangChain Tool 定义，把现有 REST API 包装为 LLM 可调用的工具
  agent_loop.py   — LangGraph ReAct 循环，LLM 自主决策 → 调 Tool → 观察 → 再决策
  memory.py       — ChromaDB 记忆层，短期/长期/工作记忆
  prompts.py      — System Prompt 模板
  executor.py     — 服务器端执行 Agent（代码/实验/分析/监控/环境配置）
  multi_agent.py  — 多 Agent 编排器（Orchestrator + Executor + ChromaDB 共享记忆）

使用示例：
  # 单 Agent 模式
  from autodl_manager.agent import run_agent_query
  result = await run_agent_query("检查所有GPU实例，哪些利用率低于10%？")

  # 多 Agent 模式
  from autodl_manager.agent import MultiAgentOrchestrator, AgentMemory
  orch = MultiAgentOrchestrator(memory=AgentMemory())
  result = orch.execute("检查所有GPU，空闲的关机")
"""

from .tools import ALL_TOOLS
from .agent_loop import create_agent_loop, run_agent_query
from .memory import AgentMemory
from .prompts import SYSTEM_PROMPT
from .executor import ServerExecutor
from .multi_agent import MultiAgentOrchestrator

__all__ = [
    "ALL_TOOLS",
    "create_agent_loop",
    "run_agent_query",
    "AgentMemory",
    "SYSTEM_PROMPT",
    "ServerExecutor",
    "MultiAgentOrchestrator",
]
