import json
import os
import sys
import time
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_STATE = {
    "version": "1.0",
    "updated_at": "",
    "current_instance_uuid": None,
    "instances": {},
    "session": None,
    "gpu": None,
    "balance": None,
    "alerts": [],
}


def _deep_merge(base: dict, overlay: dict) -> dict:
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


class StateManager:
    def __init__(self, data_dir: str = "data"):
        root = Path(__file__).parent
        self.state_path = root / data_dir / "state.json"
        self.backup_path = root / data_dir / "state.json.bak"
        self._ensure_state()

    def _ensure_state(self):
        if self.state_path.exists():
            try:
                self.read()
                return
            except (json.JSONDecodeError, KeyError):
                if self.backup_path.exists():
                    shutil.copy2(self.backup_path, self.state_path)
        self._write_raw(DEFAULT_STATE)

    @contextmanager
    def _file_lock(self, mode: str = "r"):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, mode, encoding="utf-8") as f:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                op = fcntl.LOCK_SH if "r" in mode else fcntl.LOCK_EX
                fcntl.flock(f.fileno(), op)
            try:
                yield f
            finally:
                if sys.platform == "win32":
                    import msvcrt
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def read(self) -> dict:
        with self._file_lock("r") as f:
            return json.load(f)

    def _write_raw(self, data: dict):
        temp = self.state_path.with_suffix(".tmp")
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        if self.state_path.exists():
            shutil.copy2(self.state_path, self.backup_path)
        temp.replace(self.state_path)

    def write(self, partial: dict):
        with self._file_lock("r") as f:
            current = json.load(f)
        merged = _deep_merge(current, partial)
        merged["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write_raw(merged)

    def update_instance(self, uuid: str, fields: dict):
        self.write({
            "instances": {uuid: fields}
        })

    def set_current(self, uuid: str):
        self.write({"current_instance_uuid": uuid})

    def update_gpu_snapshot(self, uuid: str, snapshot: dict):
        snapshot["collected_at"] = datetime.now(timezone.utc).isoformat()
        self.write({"gpu": snapshot})

    def update_progress(self, uuid: str, progress: dict):
        session = self.read().get("session") or {}
        session.update(progress)
        self.write({"session": session})

    def add_alert(self, alert: dict):
        alert.setdefault("id", f"alert-{int(time.time()*1000)}")
        alert["dismissed"] = False
        state = self.read()
        state.setdefault("alerts", []).append(alert)
        self._write_raw(state)

    def dismiss_alert(self, alert_id: str):
        state = self.read()
        for a in state.get("alerts", []):
            if a["id"] == alert_id:
                a["dismissed"] = True
        self._write_raw(state)
