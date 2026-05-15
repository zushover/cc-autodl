import re
from datetime import datetime, timezone

from .state_manager import StateManager


class SessionManager:
    def __init__(self, state: StateManager):
        self.state = state

    def start_session(self, uuid: str, task: str = ""):
        self.state.write({
            "session": {
                "instance_uuid": uuid,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "cost_so_far_yuan": 0.0,
                "task": task,
                "task_progress": "",
                "anomalies": [],
            }
        })

    def end_session(self, uuid: str, reason: str = "manual") -> dict:
        data = self.state.read()
        session = data.get("session") or {}
        if session.get("instance_uuid") != uuid:
            return {}
        started = session.get("started_at", "")
        duration_min = 0.0
        if started:
            try:
                t0 = datetime.fromisoformat(started)
                duration_min = (datetime.now(timezone.utc) - t0).total_seconds() / 60.0
            except ValueError:
                pass
        inst = (data.get("instances") or {}).get(uuid, {})
        price = inst.get("payg_price", 0) or 0
        cost = round(duration_min / 60.0 * price, 2)
        summary = {
            "instance_uuid": uuid,
            "started_at": started,
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "duration_minutes": round(duration_min, 1),
            "cost_yuan": cost,
            "task": session.get("task", ""),
            "reason": reason,
        }
        self.state.write({"session": None})
        return summary

    def get_session_summary(self, uuid: str) -> dict:
        data = self.state.read()
        session = data.get("session") or {}
        gpu = data.get("gpu") or {}
        inst = (data.get("instances") or {}).get(uuid, {})
        price = inst.get("payg_price", 0) or 0

        started = session.get("started_at", "")
        duration_min = 0.0
        if started:
            try:
                t0 = datetime.fromisoformat(started)
                duration_min = (datetime.now(timezone.utc) - t0).total_seconds() / 60.0
            except ValueError:
                pass

        return {
            "instance_uuid": uuid,
            "started_at": started,
            "duration_minutes": round(duration_min, 1),
            "cost_so_far_yuan": round(duration_min / 60.0 * price, 2),
            "task": session.get("task", ""),
            "task_progress": session.get("task_progress", ""),
            "gpu_util": gpu.get("util_percent"),
            "gpu_mem": f"{gpu.get('mem_used_gb','?')}/{gpu.get('mem_total_gb','?')}GB",
            "gpu_temp": gpu.get("temp_c"),
            "anomalies": session.get("anomalies", []),
        }

    def parse_training_log(self, log_snippet: str) -> dict | None:
        step_match = re.search(r"(?:Step|step|Iter|iter)[:\s]*(\d+)", log_snippet)
        loss_match = re.search(r"(?:Loss|loss)[:\s]*([\d.]+(?:e[+-]?\d+)?)", log_snippet)
        lr_match = re.search(r"(?:lr|LR|learning.rate)[:\s]*([\d.e+-]+)", log_snippet)
        throughput_match = re.search(r"(?:samples/sec|it/s|tokens/sec)[:\s]*([\d.]+)", log_snippet)

        result = {}
        if step_match:
            result["current_step"] = int(step_match.group(1))
        if loss_match:
            result["loss"] = float(loss_match.group(1))
        if lr_match:
            result["lr"] = float(lr_match.group(1))
        if throughput_match:
            result["throughput"] = float(throughput_match.group(1))
        return result or None

    def check_anomaly(self, log_snippet: str) -> list:
        anomalies = []
        if re.search(r"\bNaN\b", log_snippet, re.IGNORECASE):
            anomalies.append({"type": "loss_nan", "severity": "critical", "message": "Loss 出现 NaN"})
        if re.search(r"\bInf\b", log_snippet, re.IGNORECASE):
            anomalies.append({"type": "loss_inf", "severity": "critical", "message": "Loss 出现 Inf"})
        if re.search(r"\bOOM\b|out of memory", log_snippet, re.IGNORECASE):
            anomalies.append({"type": "oom", "severity": "critical", "message": "显存溢出 (OOM)"})
        if re.search(r"\bCUDA error\b", log_snippet, re.IGNORECASE):
            anomalies.append({"type": "cuda_error", "severity": "critical", "message": "CUDA 错误"})
        if re.search(r"\bKilled\b", log_snippet):
            anomalies.append({"type": "process_killed", "severity": "critical", "message": "进程被 Kill"})
        return anomalies
