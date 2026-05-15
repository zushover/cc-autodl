import os
import sys
import time
import signal
import atexit
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .autodl_api import AutoDLAPI
from .state_manager import StateManager
from .fleet_manager import FleetManager
from .gpu_collector import GPUCollector
from .session_manager import SessionManager
from .cost_tracker import CostTracker


PID_FILE = "data/daemon.pid"


class Daemon:
    def __init__(
        self,
        api: AutoDLAPI,
        fleet: FleetManager,
        state: StateManager,
        collector: GPUCollector,
        session_mgr: SessionManager,
        cost: CostTracker,
    ):
        self.api = api
        self.fleet = fleet
        self.state = state
        self.collector = collector
        self.session = session_mgr
        self.cost = cost
        self.running = True
        self._last_gpu_collect = 0.0
        self._last_log_check = 0.0
        self._last_cost_update = 0.0
        self._last_balance_check = 0.0
        self._idle_start: float | None = None
        self._idle_state = "NORMAL"

    def _pid_path(self) -> Path:
        return Path(__file__).parent / PID_FILE

    def _write_pid(self):
        self._pid_path().write_text(str(os.getpid()))

    def _remove_pid(self):
        path = self._pid_path()
        if path.exists():
            path.unlink()

    def _get_current_instance(self) -> dict | None:
        data = self.state.read()
        uuid = data.get("current_instance_uuid")
        if not uuid:
            return None
        return (data.get("instances") or {}).get(uuid)

    def _collect_gpu(self, instance: dict):
        host = instance.get("ssh_host", "")
        port = instance.get("ssh_port", 22)
        uuid = instance["instance_uuid"]
        gpu = self.collector.collect(host, port)
        if gpu:
            self.state.update_gpu_snapshot(uuid, gpu)
        self._last_gpu_collect = time.time()

    def _check_idle(self, gpu_util: int):
        now = time.time()
        if gpu_util < 5:
            if self._idle_start is None:
                self._idle_start = now
            idle_sec = now - self._idle_start
            if idle_sec > 1800:
                new_state = "CRITICAL"
            elif idle_sec > 900:
                new_state = "WARNING"
            else:
                new_state = self._idle_state
        else:
            self._idle_start = None
            new_state = "NORMAL"

        if new_state != self._idle_state:
            self._idle_state = new_state
            severity = {"NORMAL": "info", "WARNING": "warning", "CRITICAL": "critical"}
            messages = {
                "WARNING": f"GPU 空闲 {int((now - self._idle_start) / 60)} 分钟 (利用率 < 5%)",
                "CRITICAL": f"GPU 空闲 {int((now - self._idle_start) / 60)} 分钟，建议关机",
            }
            if new_state != "NORMAL":
                self.state.add_alert({
                    "severity": severity[new_state],
                    "type": "idle",
                    "message": messages[new_state],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                print(f"[DAEMON] {messages[new_state]}")

        elif self._idle_start is not None and self._idle_state in ("WARNING", "CRITICAL"):
            idle_min = int((now - self._idle_start) / 60)
            if idle_min % 10 == 0:
                print(f"[DAEMON] GPU 持续空闲 {idle_min} 分钟")

    def _check_log(self, instance: dict):
        host = instance.get("ssh_host", "")
        port = instance.get("ssh_port", 22)
        try:
            self.collector.connect(host, port)
            stdin, stdout, stderr = self.collector._client.exec_command(
                "cat /root/autodl-tmp/*/results/run.log 2>/dev/null | tail -100 || echo ''",
                timeout=15,
            )
            snippet = stdout.read().decode(errors="replace")
            if snippet.strip():
                progress = self.session.parse_training_log(snippet)
                if progress:
                    self.state.update_progress(instance["instance_uuid"], progress)
                anomalies = self.session.check_anomaly(snippet)
                for a in anomalies:
                    self.state.add_alert(a)
                    print(f"[DAEMON] {a['severity'].upper()}: {a['message']}")
        except Exception:
            pass
        self._last_log_check = time.time()

    def _update_cost(self, instance: dict):
        price = instance.get("payg_price", 0) or 0
        self.cost.record_snapshot(
            instance["instance_uuid"],
            instance.get("instance_name", ""),
            price,
        )
        self._last_cost_update = time.time()

    def _check_balance_and_expiry(self):
        try:
            bal = self.api.get_balance()
            self.state.write({"balance": {"assets_yuan": bal["assets_yuan"], "updated_at": datetime.now(timezone.utc).isoformat()}})
            if bal["assets_yuan"] < 50:
                self.state.add_alert({
                    "severity": "critical",
                    "type": "low_balance",
                    "message": f"余额不足 ¥{bal['assets_yuan']:.2f}",
                })
                print(f"[DAEMON] 余额告警: ¥{bal['assets_yuan']:.2f}")
        except Exception:
            pass
        self._last_balance_check = time.time()

    def run(self):
        if self._pid_path().exists():
            try:
                old_pid = int(self._pid_path().read_text())
                os.kill(old_pid, 0)
                print(f"守护进程已在运行 (PID {old_pid})")
                return
            except (OSError, ValueError):
                pass

        self._write_pid()
        atexit.register(self._remove_pid)

        def handle_signal(sig, frame):
            self.running = False
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        print(f"[DAEMON] 启动 (PID {os.getpid()})")

        while self.running:
            try:
                instance = self._get_current_instance()
                if not instance or instance.get("status") != "running":
                    time.sleep(30)
                    continue

                now = time.time()
                host = instance.get("ssh_host", "")
                port = instance.get("ssh_port", 22)
                gpu = None

                if now - self._last_gpu_collect >= 120 and host:
                    self._collect_gpu(instance)
                    gpu_data = self.state.read().get("gpu") or {}
                    gpu_util = gpu_data.get("util_percent", 0)
                    self._check_idle(gpu_util)

                if now - self._last_log_check >= 300 and host:
                    self._check_log(instance)

                if now - self._last_cost_update >= 600:
                    self._update_cost(instance)

                if now - self._last_balance_check >= 1800:
                    self._check_balance_and_expiry()

            except Exception as e:
                print(f"[DAEMON] 错误: {e}")

            time.sleep(10)

        print("[DAEMON] 已停止")


def main():
    root = Path(__file__).parent.parent
    config_path = root / "config.yaml"
    if not config_path.exists():
        print("config.yaml 不存在")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    token = config.get("auto_dl", {}).get("token", "")
    if not token or token == "your-token-here":
        print("请在 config.yaml 中填入 AutoDL Token")
        sys.exit(1)

    api = AutoDLAPI(token)
    state = StateManager()
    ssh_key = config.get("ssh", {}).get("key_path", "")
    ssh_user = config.get("ssh", {}).get("user", "root")
    fleet = FleetManager(api, state, ssh_key, ssh_user)
    collector = GPUCollector(ssh_key, ssh_user)
    session_mgr = SessionManager(state)
    cost = CostTracker(state)

    daemon = Daemon(api, fleet, state, collector, session_mgr, cost)
    daemon.run()


if __name__ == "__main__":
    main()
