"""Agent Memory — 基于 ChromaDB 的 Agent 共享记忆层。

三层记忆架构：
  短期记忆 — 最近 N 轮对话上下文
  长期记忆 — 向量化的实验记录、文档索引、历史决策
  工作记忆 — 当前任务执行状态（由 SQLite 负责，不在此层）

多 Agent 共享：电脑端 Orchestrator 和服务器端 Executor 可以读写同一份 ChromaDB。
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings


class AgentMemory:
    """Agent 共享记忆系统。

    使用 ChromaDB 持久化存储，支持：
    - 对话历史：可向量检索的对话记录
    - 实验记忆：实验配置/结果的相似检索
    - 决策记忆：Agent 历史决策，用于去重和反模板
    """

    def __init__(self, persist_path: Optional[str] = None):
        if persist_path is None:
            persist_path = str(Path(__file__).parent.parent / "data" / "agent_memory")
        Path(persist_path).mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=persist_path,
            settings=Settings(anonymized_telemetry=False),
        )
        self._ensure_collections()

    def _ensure_collections(self):
        """确保必要的 Collection 存在。"""
        self.conversations = self.client.get_or_create_collection(
            name="conversation_history",
            metadata={"description": "Agent 对话历史，可向量检索"},
        )
        self.experiments = self.client.get_or_create_collection(
            name="experiment_records",
            metadata={"description": "实验记录：配置/指标/经验教训"},
        )
        self.decisions = self.client.get_or_create_collection(
            name="agent_decisions",
            metadata={"description": "Agent 决策历史，用于反循环检测"},
        )

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _make_id(self, prefix: str) -> str:
        return f"{prefix}-{int(datetime.now().timestamp() * 1000)}"

    # ─── 对话记忆 ───

    def add_conversation(self, user_msg: str, agent_response: str, metadata: Optional[dict] = None):
        """存储一轮对话。"""
        meta = metadata or {}
        meta["timestamp"] = self._now()
        self.conversations.add(
            documents=[f"User: {user_msg}\nAgent: {agent_response}"],
            metadatas=[meta],
            ids=[self._make_id("conv")],
        )

    def get_recent_conversations(self, n: int = 10) -> list[str]:
        """获取最近 N 轮对话（按插入顺序）。"""
        results = self.conversations.get()
        if not results["documents"]:
            return []
        return results["documents"][-n:]

    def search_conversations(self, query: str, n: int = 5) -> list[str]:
        """向量搜索相关历史对话。"""
        results = self.conversations.query(query_texts=[query], n_results=n)
        return results["documents"][0] if results["documents"] else []

    # ─── 实验记忆 ───

    def add_experiment(self, exp_id: str, config: dict, results: dict, notes: str = ""):
        """存储一次实验记录，支持后续相似检索。"""
        doc = f"实验ID: {exp_id}\n配置: {json.dumps(config, ensure_ascii=False)}\n结果: {json.dumps(results, ensure_ascii=False)}\n备注: {notes}"
        self.experiments.add(
            documents=[doc],
            metadatas=[{
                "exp_id": exp_id,
                "timestamp": self._now(),
                "gpu_type": config.get("gpu_type", "unknown"),
                "framework": config.get("framework", "unknown"),
                "dataset": config.get("dataset", "unknown"),
            }],
            ids=[f"exp-{exp_id}"],
        )

    def find_similar_experiments(self, query: str, n: int = 5) -> list[str]:
        """查找与查询最相似的 N 个历史实验。"""
        results = self.experiments.query(query_texts=[query], n_results=n)
        return results["documents"][0] if results["documents"] else []

    def get_experiment_count(self) -> int:
        """实验总数。"""
        return self.experiments.count()

    # ─── 决策记忆 — 反循环检测 ───

    def add_decision(self, context: str, chosen_action: str, alternatives: Optional[list[str]] = None):
        """记录一次 Agent 决策：上下文 + 选择的行动 + 备选方案。"""
        doc = f"上下文: {context}\n选择: {chosen_action}\n备选: {json.dumps(alternatives or [], ensure_ascii=False)}"
        self.decisions.add(
            documents=[doc],
            metadatas=[{
                "timestamp": self._now(),
                "action": chosen_action,
            }],
            ids=[self._make_id("dec")],
        )

    def check_loop_risk(self, proposed_action: str, threshold: int = 3) -> bool:
        """检查是否可能陷入循环。

        将拟执行的动作与最近的 N 条决策做相似度比对。
        如果最近 threshold 条中有高度相似（距离 < 0.1）的，判定有循环风险。

        Returns:
            True 表示有循环风险，应该换方案。
        """
        results = self.decisions.query(query_texts=[proposed_action], n_results=threshold)
        if not results["distances"] or not results["distances"][0]:
            return False
        return any(d < 0.1 for d in results["distances"][0] if d is not None)
