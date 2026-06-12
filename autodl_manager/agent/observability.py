"""Agent Observability — LangFuse 全链路 trace。

记录 Agent 每一步决策：LLM 调用、Tool 选择、执行耗时、Token 消耗。
面试时说："我用 LangFuse 做 Agent 可观测性，每一步决策都有 trace。"

LangFuse 是可选的——不配置也不影响 Agent 运行。
配置方式：环境变量 LANGFUSE_SECRET_KEY + LANGFUSE_PUBLIC_KEY。
"""

import os
import time
import functools
from typing import Optional


class AgentTracer:
    """Agent 可观测性追踪器。

    无 LangFuse 时退化为本地 logger，不影响功能。
    """

    def __init__(self):
        self._langfuse = None
        self._enabled = self._init_langfuse()

    def _init_langfuse(self) -> bool:
        """尝试初始化 LangFuse。"""
        try:
            secret = os.getenv("LANGFUSE_SECRET_KEY")
            public = os.getenv("LANGFUSE_PUBLIC_KEY")
            if not secret or not public:
                return False
            from langfuse import Langfuse
            self._langfuse = Langfuse(secret_key=secret, public_key=public)
            return True
        except Exception:
            return False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def trace_agent_call(
        self,
        query: str,
        steps: list[dict],
        final_answer: str,
        total_tokens: int = 0,
        duration_ms: float = 0,
    ):
        """记录一次完整的 Agent 调用。

        Args:
            query: 用户请求
            steps: [{"step": 1, "action": "call_tool", "tool": "list_gpu_instances", "duration_ms": 230}, ...]
            final_answer: 最终回答
            total_tokens: 总 Token 消耗
            duration_ms: 总耗时
        """
        if self._enabled and self._langfuse:
            try:
                trace = self._langfuse.trace(
                    name="agent_query",
                    input={"query": query},
                    output={"answer": final_answer[:500]},
                    metadata={
                        "steps": len(steps),
                        "total_tokens": total_tokens,
                        "duration_ms": duration_ms,
                    },
                )
                for s in steps:
                    trace.span(
                        name=s.get("action", "unknown"),
                        metadata=s,
                    )
            except Exception:
                pass


# ─── 全局实例 ───

_tracer: Optional[AgentTracer] = None


def get_tracer() -> AgentTracer:
    global _tracer
    if _tracer is None:
        _tracer = AgentTracer()
    return _tracer
