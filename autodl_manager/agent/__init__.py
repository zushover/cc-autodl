"""Agent 模块 — 为 cc-autodl 提供 LLM 驱动的自主决策能力。

模块结构：
  tools.py        — LangChain Tool 定义（5个Tool）
  agent_loop.py   — LangGraph ReAct 单Agent循环
  memory.py       — ChromaDB 三层记忆（对话/实验/决策）
  prompts.py      — System Prompt 模板
  executor.py     — 服务器端执行Agent（5种任务类型）
  multi_agent.py  — 多Agent编排器（Orchestrator + Executor）
  mcp_server.py   — MCP Server（GPU监控标准化为MCP协议）
  observability.py — LangFuse 全链路trace

使用示例：
  # 单 Agent
  from autodl_manager.agent import run_agent_query
  result = await run_agent_query("检查所有GPU")

  # 多 Agent
  from autodl_manager.agent import MultiAgentOrchestrator, AgentMemory
  orch = MultiAgentOrchestrator(memory=AgentMemory())
  result = orch.execute("检查GPU，空闲的关机")

  # MCP Server
  from autodl_manager.agent.mcp_server import MCPServer
  server = MCPServer()
  server.call_tool("list_gpu_instances", {})
"""

from .tools import ALL_TOOLS
from .agent_loop import create_agent_loop, run_agent_query
from .memory import AgentMemory
from .prompts import SYSTEM_PROMPT
from .executor import ServerExecutor
from .multi_agent import MultiAgentOrchestrator
from .mcp_server import MCPServer
from .observability import AgentTracer, get_tracer

__all__ = [
    "ALL_TOOLS",
    "create_agent_loop",
    "run_agent_query",
    "AgentMemory",
    "SYSTEM_PROMPT",
    "ServerExecutor",
    "MultiAgentOrchestrator",
    "MCPServer",
    "AgentTracer",
    "get_tracer",
]
