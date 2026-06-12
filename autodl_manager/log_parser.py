"""训练日志解析 — 从 session_manager 提取的独立工具函数。

不依赖任何状态管理，纯函数，可被 CLI、daemon、API server 复用。
"""

import re


def parse_training_log(log_snippet: str) -> dict | None:
    """从训练日志片段中提取 step/loss/lr/throughput。"""
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


def check_anomaly(log_snippet: str) -> list:
    """检测训练日志中的异常（NaN/Inf/OOM/CUDA error/Killed）。"""
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
