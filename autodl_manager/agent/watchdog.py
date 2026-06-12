"""服务器端任务监听器 (watchdog)。

部署到 GPU 服务器后，在 tmux 中运行。
每 10 秒扫描 tasks/ 目录，发现新任务自动调 Claude Code 执行，
结果写回 results/ 目录，并上报面板 ChromaDB。

部署方式（已集成到 deploy.py 中）:
  tmux new -d -s watchdog "python3 ~/autodl-workspace/watchdog.py"
"""

import json
import os
import time
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# ─── 配置（deploy 时写入）───
TASKS_DIR = Path(os.environ.get("WATCHDOG_TASKS_DIR", "/root/autodl-workspace/tasks"))
RESULTS_DIR = Path(os.environ.get("WATCHDOG_RESULTS_DIR", "/root/autodl-workspace/results"))
PANEL_HOST = os.environ.get("WATCHDOG_PANEL_HOST", "http://127.0.0.1:8899")
SERVER_ID = os.environ.get("WATCHDOG_SERVER_ID", "unknown")
POLL_INTERVAL = int(os.environ.get("WATCHDOG_POLL_INTERVAL", "10"))


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str):
    print(f"[watchdog {SERVER_ID[:8]}] {msg}", flush=True)


def report_to_panel(task_id: str, status: str, result: Optional[dict] = None):
    """上报任务状态到面板 ChromaDB。"""
    try:
        body = json.dumps({
            "task_id": task_id,
            "server_id": SERVER_ID,
            "status": status,
            "result": result or {},
            "timestamp": now(),
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{PANEL_HOST}/api/agent/report",
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        log(f"上报失败: {e}")


def execute_task(task: dict) -> dict:
    """调 Claude Code 执行任务。返回结果字典。"""
    task_id = task.get("task_id", "unknown")
    description = task.get("description", "")
    task_type = task.get("task_type", "general")

    log(f"开始执行 [{task_id}] {task_type}: {description[:100]}")

    # 构造 Claude Code prompt
    prompt = f"""执行以下研究任务。

任务ID: {task_id}
类型: {task_type}
描述: {description}

参数: {json.dumps(task.get('params', {}), ensure_ascii=False)}

完成后，输出 JSON 格式的结果：
{{"task_id": "{task_id}", "success": true/false, "summary": "...", "data": {{...}}}}
"""

    try:
        # 调 Claude Code（非交互模式）
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=task.get("timeout_seconds", 600),  # 默认10分钟
            cwd=str(RESULTS_DIR.parent),
        )
        output = result.stdout.strip()
        log(f"[{task_id}] 完成 (exit {result.returncode}), output: {output[:200]}")

        # 尝试解析 JSON
        try:
            parsed = json.loads(output) if output else {}
        except json.JSONDecodeError:
            parsed = {"raw_output": output[:2000]}

        return {"success": result.returncode == 0, "output": parsed, "task_id": task_id}
    except subprocess.TimeoutExpired:
        log(f"[{task_id}] 超时")
        return {"success": False, "error": "timeout", "task_id": task_id}
    except FileNotFoundError:
        log(f"[{task_id}] Claude Code 未安装")
        return {"success": False, "error": "claude not found", "task_id": task_id}


def run():
    """主循环：扫描 tasks/ → 执行 → 写 results/ → 上报面板。"""
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    processed = set()

    log(f"启动: tasks={TASKS_DIR}, results={RESULTS_DIR}, panel={PANEL_HOST}")

    while True:
        try:
            for f in sorted(TASKS_DIR.glob("*.yaml")):
                if f.name in processed:
                    continue
                processed.add(f.name)

                # 读任务
                import yaml
                try:
                    with open(f, "r") as fh:
                        task = yaml.safe_load(fh)
                except Exception:
                    log(f"跳过无效文件: {f.name}")
                    continue

                if not task or not task.get("task_id"):
                    continue

                # 上报 started
                report_to_panel(task.get("task_id", ""), "started")

                # 执行
                result = execute_task(task)

                # 写结果
                result_path = RESULTS_DIR / f"{task.get('task_id', f.stem)}.json"
                with open(result_path, "w") as fh:
                    json.dump(result, fh, ensure_ascii=False, indent=2)

                # 写实验记忆
                report_to_panel(task.get("task_id", ""),
                               "completed" if result.get("success") else "failed",
                               result)

                log(f"[{task.get('task_id', '?')}] 结果已保存: {result_path.name}")

        except Exception as e:
            log(f"循环异常: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
