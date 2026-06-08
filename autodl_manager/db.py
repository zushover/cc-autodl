"""SQLite 数据库层 — 替代 state.json，支持时间序列查询。

借鉴 cc-switch 的 SQLite 选择：零配置、内置支持、适合 GPU 快照和费用记录。
"""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS instances (
    uuid TEXT PRIMARY KEY,
    source TEXT NOT NULL CHECK(source IN ('pro','web','ssh')),
    alias TEXT,
    tags TEXT DEFAULT '[]',

    ssh_host TEXT,
    ssh_port INTEGER DEFAULT 22,
    ssh_user TEXT DEFAULT 'root',
    ssh_key_path TEXT,
	ssh_password TEXT,

    gpu_type TEXT,
    gpu_vram_gb INTEGER,
    region TEXT,
    price_per_hour REAL,

    status TEXT DEFAULT 'unknown',
    is_current INTEGER DEFAULT 0,

    api_detail TEXT DEFAULT '{}',

    created_at TEXT,
    last_seen_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS gpu_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_uuid TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    util_percent INTEGER,
    mem_used_gb REAL,
    mem_total_gb REAL,
    temp_c INTEGER,
    power_w REAL,
    processes TEXT DEFAULT '[]',
    FOREIGN KEY (instance_uuid) REFERENCES instances(uuid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cost_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_uuid TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    balance_yuan REAL,
    price_per_hour REAL,
    event TEXT DEFAULT 'heartbeat',
    FOREIGN KEY (instance_uuid) REFERENCES instances(uuid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    instance_uuid TEXT,
    script_path TEXT,
    config_yaml TEXT,
    status TEXT DEFAULT 'pending',
    started_at TEXT,
    ended_at TEXT,
    duration_minutes REAL,
    total_cost_yuan REAL,
    final_metrics TEXT DEFAULT '{}',
    obsidian_note_path TEXT,
    notes TEXT,
    FOREIGN KEY (instance_uuid) REFERENCES instances(uuid) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    instance_uuid TEXT,
    timestamp TEXT NOT NULL,
    severity TEXT DEFAULT 'info',
    type TEXT,
    message TEXT,
    dismissed INTEGER DEFAULT 0,
    FOREIGN KEY (instance_uuid) REFERENCES instances(uuid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_gpu_snapshots_uuid ON gpu_snapshots(instance_uuid);
CREATE INDEX IF NOT EXISTS idx_gpu_snapshots_ts ON gpu_snapshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_cost_events_uuid ON cost_events(instance_uuid);
CREATE INDEX IF NOT EXISTS idx_cost_events_ts ON cost_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments(status);
CREATE INDEX IF NOT EXISTS idx_alerts_instance ON alerts(instance_uuid);
CREATE INDEX IF NOT EXISTS idx_instances_source ON instances(source);
"""


class Database:
    """线程安全的 SQLite 封装。"""

    def __init__(self, path: Optional[str] = None):
        if path is None:
            path = str(Path(__file__).parent / "data" / "autodl.db")
        self._path = path
        self._local = threading.local()
        self._init_db()

    def _init_db(self):
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(SCHEMA)
        # 迁移：添加 ssh_password 字段（如果不存在）
        try:
            conn.execute("ALTER TABLE instances ADD COLUMN ssh_password TEXT")
        except sqlite3.OperationalError:
            pass  # 字段已存在
        conn.commit()
        conn.close()

    @property
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self._path)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    # ─── 通用 ───

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self._conn.execute(sql, params)

    def executemany(self, sql: str, params_list: list) -> sqlite3.Cursor:
        return self._conn.executemany(sql, params_list)

    def commit(self):
        self._conn.commit()

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[dict]:
        row = self._conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def insert(self, table: str, data: dict) -> int:
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        self._conn.execute(
            f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})",
            tuple(data.values()),
        )
        self._conn.commit()
        return self._conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ─── 实例 ───

    def upsert_instance(self, data: dict) -> None:
        data.setdefault("updated_at", self.now())
        if "created_at" not in data:
            data["created_at"] = self.now()
        self.insert("instances", data)

    def get_instance(self, uuid: str) -> Optional[dict]:
        return self.fetchone("SELECT * FROM instances WHERE uuid = ?", (uuid,))

    def list_instances(self, source: Optional[str] = None) -> list[dict]:
        if source:
            return self.fetchall("SELECT * FROM instances WHERE source = ? ORDER BY alias", (source,))
        return self.fetchall("SELECT * FROM instances ORDER BY is_current DESC, alias")

    def delete_instance(self, uuid: str) -> None:
        self.execute("DELETE FROM instances WHERE uuid = ?", (uuid,))
        self.commit()

    def set_current(self, uuid: str) -> None:
        self.execute("UPDATE instances SET is_current = 0")
        self.execute("UPDATE instances SET is_current = 1 WHERE uuid = ?", (uuid,))
        self.commit()

    def update_instance_status(self, uuid: str, status: str) -> None:
        self.execute(
            "UPDATE instances SET status = ?, last_seen_at = ?, updated_at = ? WHERE uuid = ?",
            (status, self.now(), self.now(), uuid),
        )
        self.commit()

    def update_instance_field(self, uuid: str, field: str, value: Any) -> None:
        self.execute(
            f"UPDATE instances SET {field} = ?, updated_at = ? WHERE uuid = ?",
            (value, self.now(), uuid),
        )
        self.commit()

    # ─── GPU 快照 ───

    def insert_gpu_snapshot(self, instance_uuid: str, snapshot: dict) -> int:
        data = {
            "instance_uuid": instance_uuid,
            "timestamp": snapshot.get("timestamp", self.now()),
            "util_percent": snapshot.get("util_percent"),
            "mem_used_gb": snapshot.get("mem_used_gb"),
            "mem_total_gb": snapshot.get("mem_total_gb"),
            "temp_c": snapshot.get("temp_c"),
            "power_w": snapshot.get("power_w"),
            "processes": json.dumps(snapshot.get("processes", [])),
        }
        return self.insert("gpu_snapshots", data)

    def get_latest_gpu(self, instance_uuid: str) -> Optional[dict]:
        return self.fetchone(
            "SELECT * FROM gpu_snapshots WHERE instance_uuid = ? ORDER BY timestamp DESC LIMIT 1",
            (instance_uuid,),
        )

    def get_gpu_history(self, instance_uuid: str, hours: int = 24) -> list[dict]:
        return self.fetchall(
            "SELECT * FROM gpu_snapshots WHERE instance_uuid = ? "
            "AND timestamp > datetime('now', ?) ORDER BY timestamp",
            (instance_uuid, f"-{hours} hours"),
        )

    # ─── 费用 ───

    def insert_cost_event(self, data: dict) -> int:
        data.setdefault("timestamp", self.now())
        return self.insert("cost_events", data)

    def get_daily_cost(self, date_str: Optional[str] = None) -> float:
        if date_str is None:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = self.fetchone(
            """SELECT COUNT(*) as cnt, AVG(price_per_hour) as avg_price
               FROM cost_events
               WHERE event = 'heartbeat' AND date(timestamp) = ?""",
            (date_str,),
        )
        if not row or row["cnt"] == 0:
            return 0.0
        hours = row["cnt"] * 10.0 / 60.0
        return round(hours * (row["avg_price"] or 0), 2)

    def get_weekly_cost(self) -> float:
        row = self.fetchone(
            """SELECT COUNT(*) as cnt, AVG(price_per_hour) as avg_price
               FROM cost_events
               WHERE event = 'heartbeat'
               AND timestamp > datetime('now', '-7 days')"""
        )
        if not row or row["cnt"] == 0:
            return 0.0
        hours = row["cnt"] * 10.0 / 60.0
        return round(hours * (row["avg_price"] or 0), 2)

    def predict_runway(self, balance_yuan: float) -> dict:
        daily = self.get_daily_cost()
        weekly = self.get_weekly_cost()
        avg_daily = round(weekly / 7.0, 2) if weekly > 0 else 0.0
        runway = round(balance_yuan / avg_daily, 1) if avg_daily > 0 else None
        return {
            "balance_yuan": balance_yuan,
            "daily_rate_yuan": avg_daily,
            "runway_days": runway,
            "today_cost": daily,
            "week_cost": weekly,
        }

    # ─── 告警 ───

    def add_alert(self, data: dict) -> None:
        data.setdefault("id", f"alert-{int(datetime.now(timezone.utc).timestamp() * 1000)}")
        data.setdefault("timestamp", self.now())
        data.setdefault("severity", "info")
        data.setdefault("dismissed", 0)
        self.insert("alerts", data)

    def get_active_alerts(self, instance_uuid: Optional[str] = None) -> list[dict]:
        sql = "SELECT * FROM alerts WHERE dismissed = 0"
        params: tuple = ()
        if instance_uuid:
            sql += " AND instance_uuid = ?"
            params = (instance_uuid,)
        sql += " ORDER BY timestamp DESC LIMIT 20"
        return self.fetchall(sql, params)

    def dismiss_alert(self, alert_id: str) -> None:
        self.execute("UPDATE alerts SET dismissed = 1 WHERE id = ?", (alert_id,))
        self.commit()

    # ─── 实验 ───

    def upsert_experiment(self, data: dict) -> None:
        data.setdefault("id", f"exp-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}")
        self.insert("experiments", data)

    def list_experiments(self, status: Optional[str] = None) -> list[dict]:
        if status:
            return self.fetchall("SELECT * FROM experiments WHERE status = ? ORDER BY started_at DESC", (status,))
        return self.fetchall("SELECT * FROM experiments ORDER BY started_at DESC LIMIT 50")

    def get_experiment(self, exp_id: str) -> Optional[dict]:
        return self.fetchone("SELECT * FROM experiments WHERE id = ?", (exp_id,))

    # ─── 设置 ───

    def get_setting(self, key: str, default: str = "") -> str:
        row = self.fetchone("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.insert("settings", {"key": key, "value": value})

    # ─── 迁移 ───

    def migrate_from_state_json(self, state: dict) -> int:
        """将旧的 state.json 数据迁移到 SQLite。返回迁移的实例数。"""
        count = 0
        instances = state.get("instances", {})
        for uuid, inst in instances.items():
            source = "pro" if uuid.startswith("pro-") else "web"
            self.upsert_instance({
                "uuid": uuid,
                "source": source,
                "alias": inst.get("instance_name", ""),
                "ssh_host": inst.get("ssh_host", ""),
                "ssh_port": inst.get("ssh_port", 22),
                "gpu_type": inst.get("gpu_type", ""),
                "region": inst.get("region_sign", ""),
                "price_per_hour": inst.get("payg_price", 0),
                "status": inst.get("status", "unknown"),
                "is_current": 1 if uuid == state.get("current_instance_uuid") else 0,
            })
            count += 1
        return count


_db_instance: Optional[Database] = None


def get_db(path: Optional[str] = None) -> Database:
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(path)
    return _db_instance
