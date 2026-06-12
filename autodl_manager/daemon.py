"""后台守护进程 — GPU 监控 + 日志检查 + 空闲检测 + 余额告警。

v2.1: 重写为使用 InstanceRegistry (SQLite) + GPUCollector (支持密钥/密码)。
      作为 FastAPI lifespan 事件运行，通过 SSE 广播实时数据。
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from .autodl_api import AutoDLAPI, AutoDLAPIError
from .db import Database
from .gpu_collector import GPUCollector
from .instance_registry import InstanceRegistry
from .log_parser import parse_training_log, check_anomaly

logger = logging.getLogger("autodl.daemon")

# ─── SSE 广播回调（由 api_server 注入）───

_sse_broadcast = None


def set_broadcaster(fn):
    """注入 SSE 广播函数。api_server 在创建 app 时调用。"""
    global _sse_broadcast
    _sse_broadcast = fn


def _broadcast(event: str, data: dict):
    if _sse_broadcast:
        try:
            _sse_broadcast(event, data)
        except Exception:
            pass


# ─── 守护进程 ───


class DaemonV2:
    """后台监控守护进程。"""

    def __init__(
        self,
        registry: InstanceRegistry,
        db: Database,
        api: Optional[AutoDLAPI] = None,
    ):
        self.reg = registry
        self.db = db
        self.api = api
        self.running = True

        # 定时器
        self._last_gpu_collect = 0.0
        self._last_log_check = 0.0
        self._last_cost_update = 0.0
        self._last_balance_check = 0.0

        # 空闲检测状态
        self._idle_start: float | None = None
        self._idle_state = "NORMAL"

        # 配置
        self.gpu_interval = 120       # GPU 采集间隔（秒）
        self.log_interval = 300       # 日志检查间隔（秒）
        self.cost_interval = 600      # 费用记录间隔（秒）
        self.balance_interval = 1800  # 余额检查间隔（秒）
        self.idle_warn_sec = 900      # 空闲告警阈值（15分钟）
        self.idle_critical_sec = 1800 # 空闲严重告警（30分钟）
        self.low_balance_yuan = 50    # 余额告警阈值

    # ─── GPU 采集 ───

    async def _collect_gpu(self, inst: dict):
        """采集当前实例的 GPU 数据。"""
        host = inst.get("ssh_host", "")
        port = inst.get("ssh_port", 22)
        uuid = inst["uuid"]

        if not host:
            return None

        collector = GPUCollector(
            ssh_key_path=inst.get("ssh_key_path", ""),
            ssh_user=inst.get("ssh_user", "root"),
            ssh_password=inst.get("ssh_password", ""),
        )
        try:
            gpu = await asyncio.to_thread(collector.collect, host, port)
        except Exception as e:
            logger.warning(f"GPU 采集失败 [{uuid[:12]}]: {e}")
            return None

        if gpu:
            self.db.insert_gpu_snapshot(uuid, gpu)
            gpu["uuid"] = uuid
            _broadcast("gpu", gpu)
        return gpu

    # ─── 空闲检测 ───

    def _check_idle(self, inst_uuid: str, gpu_util: int | None):
        """检测 GPU 空闲并生成告警。"""
        now = time.time()
        util = gpu_util or 0

        if util < 5:
            if self._idle_start is None:
                self._idle_start = now
            idle_sec = now - self._idle_start
            if idle_sec > self.idle_critical_sec:
                new_state = "CRITICAL"
            elif idle_sec > self.idle_warn_sec:
                new_state = "WARNING"
            else:
                new_state = self._idle_state
        else:
            self._idle_start = None
            new_state = "NORMAL"

        if new_state != self._idle_state:
            self._idle_state = new_state
            if new_state != "NORMAL":
                idle_min = int((now - (self._idle_start or now)) / 60)
                msg = f"GPU 空闲 {idle_min} 分钟 (利用率 < 5%)"
                if new_state == "CRITICAL":
                    msg += "，建议关机"

                alert = {
                    "id": f"alert-{int(now*1000)}",
                    "instance_uuid": inst_uuid,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "severity": "warning" if new_state == "WARNING" else "critical",
                    "type": "idle",
                    "message": msg,
                    "dismissed": 0,
                }
                self.db.add_alert(alert)
                _broadcast("alert", alert)
                logger.warning(f"[DAEMON] {msg}")

    # ─── 日志检查 ───

    async def _check_log(self, inst: dict):
        """SSH 拉取训练日志，检查异常。"""
        uuid = inst["uuid"]
        host = inst.get("ssh_host", "")
        port = inst.get("ssh_port", 22)

        if not host:
            return

        collector = GPUCollector(
            ssh_key_path=inst.get("ssh_key_path", ""),
            ssh_user=inst.get("ssh_user", "root"),
            ssh_password=inst.get("ssh_password", ""),
        )
        try:
            collector.connect(host, port)
            stdin, stdout, stderr = await asyncio.to_thread(
                collector._client.exec_command,
                "cat /root/autodl-tmp/*/run.log 2>/dev/null | tail -100 || echo ''",
                timeout=15,
            )
            snippet = stdout.read().decode(errors="replace")
            collector.disconnect()

            if not snippet.strip():
                return

            # 解析训练指标
            progress = parse_training_log(snippet)
            if progress:
                _broadcast("training", {"uuid": uuid, **progress})

            # 异常检测
            anomalies = check_anomaly(snippet)
            for a in anomalies:
                alert = {
                    "id": f"alert-{int(time.time()*1000)}",
                    "instance_uuid": uuid,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "severity": a["severity"],
                    "type": a["type"],
                    "message": a["message"],
                    "dismissed": 0,
                }
                self.db.add_alert(alert)
                _broadcast("alert", alert)
                logger.warning(f"[DAEMON] {a['severity'].upper()}: {a['message']}")
        except Exception as e:
            logger.debug(f"日志检查失败 [{uuid[:12]}]: {e}")

    # ─── 余额检查 ───

    async def _check_balance(self):
        """检查余额并生成告警。"""
        if not self.api:
            return
        try:
            bal = await asyncio.to_thread(self.api.get_balance)
            assets = bal.get("assets_yuan", 0)
            _broadcast("balance", {
                "assets_yuan": assets,
                "voucher_balance": bal.get("voucher_balance", 0),
                "accumulate_yuan": bal.get("accumulate_yuan", 0),
            })
            if assets < self.low_balance_yuan:
                alert = {
                    "id": f"alert-{int(time.time()*1000)}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "severity": "critical",
                    "type": "low_balance",
                    "message": f"余额不足 ¥{assets:.2f}",
                    "dismissed": 0,
                }
                self.db.add_alert(alert)
                _broadcast("alert", alert)
                logger.warning(f"[DAEMON] 余额告警: ¥{assets:.2f}")
        except AutoDLAPIError as e:
            logger.warning(f"余额查询失败: {e}")
        except Exception as e:
            logger.debug(f"余额检查异常: {e}")

    # ─── 主循环 ───

    async def run(self):
        """主循环。作为 asyncio Task 运行。"""
        logger.info("[DAEMON] 启动")

        while self.running:
            try:
                current = self.reg.get_current()
                if not current:
                    await asyncio.sleep(10)
                    continue
                if current.get("status") not in ("running", "reachable", "no_gpu"):
                    await asyncio.sleep(10)
                    continue

                now = time.time()
                host = current.get("ssh_host", "")

                # GPU 采集
                if now - self._last_gpu_collect >= self.gpu_interval and host:
                    gpu = await self._collect_gpu(current)
                    self._last_gpu_collect = now
                    if gpu:
                        self._check_idle(current["uuid"], gpu.get("util_percent"))

                # 日志检查
                if now - self._last_log_check >= self.log_interval and host:
                    await self._check_log(current)
                    self._last_log_check = now

                # 余额检查
                if now - self._last_balance_check >= self.balance_interval:
                    await self._check_balance()
                    self._last_balance_check = now

            except Exception as e:
                logger.error(f"[DAEMON] 错误: {e}")

            await asyncio.sleep(10)

        logger.info("[DAEMON] 已停止")

    def stop(self):
        self.running = False
