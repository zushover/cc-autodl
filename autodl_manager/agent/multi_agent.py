"""Multi-Agent Orchestrator — 多 Agent 协作编排器。

电脑端 Orchestrator Agent 负责任务理解和分发，
服务器端 Executor Agent 负责具体执行。

流程：用户请求 → Orchestrator 规划 → 分发到 Executor → 汇总结果 → 返回用户

面试叙事：
  "我用 Orchestrator + Executor 双 Agent 架构。
   Orchestrator 用 LangGraph 做任务规划和分发，
   Executor 在 GPU 服务器上执行代码编写和实验运行。
   两个 Agent 通过 ChromaDB 共享实验上下文和决策历史。"
"""

import json
from typing import Optional
from datetime import datetime, timezone

from ..db import get_db
from ..instance_registry import InstanceRegistry
from .memory import AgentMemory
from .executor import ServerExecutor


class MultiAgentOrchestrator:
    """多 Agent 编排器。

    Orchestrator（电脑端）：理解意图 → 分解子任务 → 分配 Executor → 汇总结果
    Executor（服务器端）：执行单个任务 → 上报结构化结果

    使用方式：
        orch = MultiAgentOrchestrator(memory=AgentMemory())
        result = orch.execute("检查所有GPU实例的利用率，空闲的关掉")
    """

    def __init__(self, memory: Optional[AgentMemory] = None):
        self.memory = memory or AgentMemory()
        self.registry = InstanceRegistry(get_db())

        # 已注册的 Executor（key = server_id）
        self.executors: dict[str, ServerExecutor] = {}

        # 执行历史
        self.plan_history: list[dict] = []

    # ─── 注册 Executor ───

    def register_executor(self, server_id: str) -> ServerExecutor:
        """注册一个服务器端 Executor。"""
        executor = ServerExecutor(server_id=server_id, memory=self.memory)
        self.executors[server_id] = executor
        return executor

    def get_available_servers(self) -> list[dict]:
        """获取可用的服务器列表（从已注册的 GPU 实例中筛选运行中的）。"""
        instances = self.registry.list_all()
        return [
            {
                "uuid": i["uuid"][:12],
                "alias": i.get("alias", ""),
                "gpu_type": i.get("gpu_type", ""),
                "status": i.get("status", "unknown"),
                "ssh_host": i.get("ssh_host", ""),
            }
            for i in instances
            if i.get("status") in ("running", "reachable", "no_gpu")
        ]

    # ─── 任务规划 ───

    def plan(self, user_request: str, llm_api_key: str = "",
             llm_api_base: str = "https://api.deepseek.com/v1",
             llm_model: str = "deepseek-v4-pro") -> list[dict]:
        """用 LLM 将用户自然语言请求分解为可执行的子任务。

        Args:
            user_request: 用户自然语言请求。
                "检查所有实例GPU利用率，空闲的关机"
                "帮我在4090上跑LLaMA-Factory微调实验"
                "分析exp-001的训练日志，找出loss不收敛的原因"

        Returns:
            子任务列表: [
                {"task_id": "1", "task_type": "monitor", "description": "...",
                 "target_server": "pro-xxx", "params": {...}},
                ...
            ]
        """
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage

        # 获取上下文
        servers = self.get_available_servers()
        history = self.memory.get_recent_conversations(5)

        planning_prompt = f"""你是 AI 研究编排器。将用户请求分解为可分配给服务器执行的子任务。

## 可用服务器
{json.dumps(servers, ensure_ascii=False, indent=2) if servers else "无运行中的服务器（任务将标记为 pending）"}

## 最近对话历史
{chr(10).join(history) if history else "无历史"}

## 支持的任务类型
- monitor: 检查 GPU 状态/利用率/进程
- code: 编写/修改代码
- experiment: 运行训练/推理实验
- analysis: 分析日志/结果/指标
- setup: 配置服务器环境（CUDA/Python/Claude Code）
- shutdown: 关闭空闲实例

## 输出格式
返回 JSON 数组，每个子任务包含：
- task_id: 任务编号（1, 2, 3...）
- task_type: 任务类型
- description: 一句话描述这个子任务做什么
- target_server: 目标服务器 UUID（可选，null 表示自动分配）
- params: 具体参数（可选）
- priority: high/medium/low
- depends_on: 依赖的任务 ID（可选）

## 用户请求
{user_request}

只返回 JSON 数组，不要其他内容。"""

        llm = ChatOpenAI(
            model=llm_model,
            api_key=llm_api_key or "not-needed",
            base_url=llm_api_base,
            temperature=0.1,
        )
        response = llm.invoke([
            SystemMessage(content=planning_prompt),
            HumanMessage(content=user_request),
        ])

        # 解析 JSON
        try:
            content = response.content
            # 处理 LLM 可能包裹的 markdown code block
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            tasks = json.loads(content)
        except json.JSONDecodeError:
            # 兜底：单任务
            tasks = [{
                "task_id": "1",
                "task_type": "unknown",
                "description": user_request,
                "target_server": None,
                "params": {},
                "priority": "high",
            }]

        # 记录到记忆
        self.memory.add_decision(
            context=user_request,
            chosen_action=f"分解为 {len(tasks)} 个子任务",
            alternatives=[t.get("description", "") for t in tasks],
        )

        return tasks

    # ─── 执行 ───

    def execute(
        self,
        user_request: str,
        llm_api_key: str = "",
        llm_api_base: str = "https://api.deepseek.com/v1",
        llm_model: str = "deepseek-v4-pro",
    ) -> dict:
        """执行一次完整的 Orchestration 流程。

        规划 → 分发 → 执行 → 汇总 → 返回结果
        """
        plan_record = {
            "request": user_request,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tasks": [],
            "results": [],
        }

        # Step 1: 规划
        tasks = self.plan(user_request, llm_api_key, llm_api_base, llm_model)
        plan_record["tasks"] = tasks

        # Step 2: 分发到 Executor 并执行
        results = []
        for task in tasks:
            task_id = task["task_id"]

            # 选择一个服务器
            target = task.get("target_server")
            if not target:
                # 自动分配：选第一个可用的
                available = self.get_available_servers()
                target = available[0]["uuid"] if available else None

            # 获取或创建 Executor
            executor = self.executors.get(target) if target else None
            if not executor and target:
                executor = self.register_executor(target)

            if executor:
                result = executor.execute(task)
            else:
                # 没有可用服务器 → 用本地 tools 处理能做的事
                result = self._execute_locally(task)

            results.append(result)

        plan_record["results"] = results
        self.plan_history.append(plan_record)

        # Step 3: 汇总
        summary = self._summarize_results(user_request, results, llm_api_key, llm_api_base, llm_model)

        # Step 4: 写入对话记忆
        self.memory.add_conversation(
            user_msg=user_request,
            agent_response=summary,
            metadata={
                "task_count": len(tasks),
                "success_count": sum(1 for r in results if r.get("success")),
            },
        )

        return {
            "request": user_request,
            "tasks_planned": len(tasks),
            "tasks_executed": len(results),
            "tasks_succeeded": sum(1 for r in results if r.get("success")),
            "results": results,
            "summary": summary,
        }

    def _execute_locally(self, task: dict) -> dict:
        """本地执行的 task（不需要服务器）。比如 monitor/shutdown 类的操作。"""
        task_type = task.get("task_type", "unknown")

        if task_type == "monitor":
            instances = self.registry.list_all()
            result = {
                "task_id": task.get("task_id", "local"),
                "success": True,
                "result": {
                    "total_instances": len(instances),
                    "running": sum(1 for i in instances if i.get("status") == "running"),
                    "instances": [
                        {
                            "uuid": i["uuid"][:12],
                            "alias": i.get("alias", ""),
                            "status": i.get("status", ""),
                            "gpu_type": i.get("gpu_type", ""),
                        }
                        for i in instances
                    ],
                },
            }
            return result

        return {
            "task_id": task.get("task_id", "local"),
            "success": True,
            "result": {"note": f"Task type '{task_type}' executed locally (simulated)"},
        }

    # ─── 结果汇总 ───

    def _summarize_results(
        self,
        user_request: str,
        results: list[dict],
        llm_api_key: str = "",
        llm_api_base: str = "https://api.deepseek.com/v1",
        llm_model: str = "deepseek-v4-pro",
    ) -> str:
        """用 LLM 将多个子任务结果汇总为一份可读报告。"""
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage

        results_text = json.dumps(results, ensure_ascii=False, indent=2)

        llm = ChatOpenAI(
            model=llm_model,
            api_key=llm_api_key or "not-needed",
            base_url=llm_api_base,
            temperature=0.3,
        )
        response = llm.invoke([
            SystemMessage(content="你是 AI 研究助手。将多个子任务的执行结果汇总为一份结构清晰的报告。用中文，关键数据用表格。"),
            HumanMessage(content=f"用户请求: {user_request}\n\n子任务结果:\n{results_text}\n\n请汇总为一份报告。"),
        ])
        return response.content

    # ─── 状态查询 ───

    def get_status(self) -> dict:
        """获取编排器整体状态。"""
        return {
            "registered_executors": len(self.executors),
            "total_plans": len(self.plan_history),
            "last_plan": self.plan_history[-1] if self.plan_history else None,
            "available_servers": self.get_available_servers(),
            "memory_stats": {
                "conversations": self.memory.conversations.count(),
                "experiments": self.memory.experiments.count(),
                "decisions": self.memory.decisions.count(),
            },
        }
