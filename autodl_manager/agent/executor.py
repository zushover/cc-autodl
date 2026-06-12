"""Server Executor — 服务器端执行 Agent。

部署在 GPU 服务器上，接收 Orchestrator 分配的任务，执行后上报结果。
有自己独立的 Tool 集合：bash/python/file/git/nvidia_smi。

设计原则：
- 只做被分配的事，不自行扩展范围
- 失败先自查修复（最多2次），然后上报
- 所有结果结构化返回，方便 Orchestrator 汇总
"""

import json
from typing import Optional
from datetime import datetime, timezone


class ServerExecutor:
    """服务器端执行 Agent。

    接收单个任务 → 执行 → 返回结构化结果。
    可运行在 GPU 服务器上（通过 SSH 远程调用或本地进程）。
    """

    # 服务器端可用工具
    AVAILABLE_TOOLS = [
        "bash_exec",        # 执行 Bash 命令
        "python_exec",      # 执行 Python 脚本
        "file_read",        # 读取文件
        "file_write",       # 写入文件
        "file_list",        # 列出目录
        "git_clone",        # 克隆仓库
        "pip_install",      # 安装 Python 包
        "nvidia_smi",       # GPU 状态
        "tmux_session",     # 管理 tmux 会话
        "parse_log",        # 解析训练日志
    ]

    def __init__(self, server_id: str, memory=None):
        self.server_id = server_id
        self.memory = memory
        self.task_history: list[dict] = []

    def execute(self, task: dict) -> dict:
        """执行单个任务。

        Args:
            task: {
                "task_id": str,
                "task_type": "code" | "experiment" | "analysis" | "monitor" | "setup",
                "description": str,          # 人类可读的任务描述
                "params": dict,              # 具体参数
                "working_dir": str,          # 工作目录
                "timeout_minutes": int,      # 超时时间
            }

        Returns:
            {
                "task_id": str,
                "success": bool,
                "result": dict,              # 结构化结果
                "logs": str,                 # 执行日志
                "errors": list[str],         # 错误信息
                "duration_seconds": float,
                "artifacts": list[str],      # 产出的文件路径
            }
        """
        start_time = datetime.now(timezone.utc)
        task_id = task.get("task_id", "unknown")
        task_type = task.get("task_type", "unknown")

        result = {
            "task_id": task_id,
            "server_id": self.server_id,
            "task_type": task_type,
            "success": False,
            "result": {},
            "logs": "",
            "errors": [],
            "duration_seconds": 0,
            "artifacts": [],
        }

        # 记录到历史
        self.task_history.append({
            "task_id": task_id,
            "started_at": start_time.isoformat(),
            "status": "started",
        })

        # 根据任务类型分发
        try:
            if task_type == "code":
                result = self._execute_code_task(task, result)
            elif task_type == "experiment":
                result = self._execute_experiment_task(task, result)
            elif task_type == "analysis":
                result = self._execute_analysis_task(task, result)
            elif task_type == "monitor":
                result = self._execute_monitor_task(task, result)
            elif task_type == "setup":
                result = self._execute_setup_task(task, result)
            else:
                result["errors"].append(f"不支持的任务类型: {task_type}")
        except Exception as e:
            result["errors"].append(f"执行异常: {e}")

        result["duration_seconds"] = (
            datetime.now(timezone.utc) - start_time
        ).total_seconds()

        # 更新历史
        self.task_history[-1]["status"] = "completed" if result["success"] else "failed"
        self.task_history[-1]["duration_seconds"] = result["duration_seconds"]

        # 写入记忆
        if self.memory:
            self.memory.add_decision(
                context=f"执行任务: {task.get('description', task_id)}",
                chosen_action=f"{task_type}: {json.dumps(result['result'], ensure_ascii=False)[:500]}",
            )

        return result

    # ─── 任务类型处理器 ───

    def _execute_code_task(self, task: dict, result: dict) -> dict:
        """代码编写/修改任务。"""
        result["result"] = {
            "action": "code_execution",
            "description": task.get("description", ""),
            "status": "simulated",
            "note": "代码执行需要 SSH 连接到服务器。当前为模拟模式。",
        }
        result["success"] = True
        return result

    def _execute_experiment_task(self, task: dict, result: dict) -> dict:
        """实验运行任务。"""
        params = task.get("params", {})
        result["result"] = {
            "action": "experiment_runner",
            "script": params.get("script", ""),
            "framework": params.get("framework", ""),
            "gpu_type": params.get("gpu_type", ""),
            "expected_hours": params.get("expected_hours", 0),
            "budget_yuan": params.get("budget", 0),
            "status": "simulated",
            "note": "实际运行需要 SSH 连接到服务器并在 tmux 中启动训练脚本。",
        }
        result["success"] = True
        return result

    def _execute_analysis_task(self, task: dict, result: dict) -> dict:
        """日志/结果分析任务。"""
        params = task.get("params", {})
        result["result"] = {
            "action": "analysis",
            "log_path": params.get("log_path", ""),
            "metrics": params.get("metrics", []),
            "status": "simulated",
            "note": "分析需要读取服务器上的训练日志和 checkpoint 文件。",
        }
        result["success"] = True
        return result

    def _execute_monitor_task(self, task: dict, result: dict) -> dict:
        """GPU/训练监控任务。"""
        result["result"] = {
            "action": "monitor",
            "gpu_info": "需要通过 nvidia-smi 采集",
            "training_progress": "需要通过日志解析获取",
            "status": "simulated",
        }
        result["success"] = True
        return result

    def _execute_setup_task(self, task: dict, result: dict) -> dict:
        """服务器环境配置任务。

        检测 CUDA/Python/已安装包 → 装配 Claude Code → 配置开发环境。
        """
        params = task.get("params", {})
        result["result"] = {
            "action": "environment_setup",
            "checks": [
                "CUDA 版本检测",
                "Python 版本检测",
                "pip 已安装包列表",
                "磁盘空间检查",
                "Claude Code 安装",
                "Git 配置",
            ],
            "target_server": params.get("server", ""),
            "status": "simulated",
            "note": "环境检测需要通过 SSH 在服务器上执行命令。",
        }
        result["success"] = True
        return result

    def get_status(self) -> dict:
        """获取执行器当前状态。"""
        return {
            "server_id": self.server_id,
            "total_tasks": len(self.task_history),
            "completed_tasks": sum(
                1 for t in self.task_history if t["status"] == "completed"
            ),
            "failed_tasks": sum(
                1 for t in self.task_history if t["status"] == "failed"
            ),
            "last_task": self.task_history[-1] if self.task_history else None,
        }
