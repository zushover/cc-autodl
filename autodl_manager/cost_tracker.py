import csv
from datetime import datetime, date, timezone, timedelta
from pathlib import Path

from .state_manager import StateManager


COST_LOG_HEADER = ["timestamp", "instance_uuid", "instance_name", "balance_yuan", "price_per_hour", "event"]


class CostTracker:
    def __init__(self, state: StateManager):
        self.state = state
        self._log_path = Path(__file__).parent / "data" / "cost_log.csv"
        self._ensure_log()

    def _ensure_log(self):
        if not self._log_path.exists():
            with open(self._log_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(COST_LOG_HEADER)

    def _read_rows(self) -> list[dict]:
        if not self._log_path.exists():
            return []
        with open(self._log_path, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def _rows_since(self, since: datetime) -> list[dict]:
        rows = []
        for r in self._read_rows():
            try:
                ts = datetime.fromisoformat(r["timestamp"])
                if ts >= since:
                    rows.append(r)
            except (ValueError, KeyError):
                pass
        return rows

    def record_snapshot(self, uuid: str, name: str, price_per_hour: float, event: str = "heartbeat"):
        bal = self.state.read().get("balance") or {}
        balance_yuan = bal.get("assets_yuan", 0)
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "instance_uuid": uuid,
            "instance_name": name,
            "balance_yuan": balance_yuan,
            "price_per_hour": price_per_hour,
            "event": event,
        }
        with open(self._log_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COST_LOG_HEADER)
            writer.writerow(row)

    def estimate_session_cost(self, uuid: str) -> float:
        data = self.state.read()
        session = data.get("session") or {}
        if session.get("instance_uuid") != uuid:
            return 0.0
        started = session.get("started_at", "")
        if not started:
            return 0.0
        try:
            t0 = datetime.fromisoformat(started)
            hours = (datetime.now(timezone.utc) - t0).total_seconds() / 3600.0
        except ValueError:
            return 0.0
        inst = (data.get("instances") or {}).get(uuid, {})
        price = inst.get("payg_price", 0) or 0
        return round(hours * price, 2)

    def _heartbeat_cost(self, rows: list[dict]) -> float:
        """每个 heartbeat 覆盖 ~10 分钟（daemon 默认间隔）。"""
        heartbeats = [r for r in rows if r.get("event") == "heartbeat"]
        if not heartbeats:
            return 0.0
        count = len(heartbeats)
        avg_price = sum(float(r.get("price_per_hour", 0) or 0) for r in heartbeats) / count
        hours = count * 10.0 / 60.0
        return round(hours * avg_price, 2)

    def get_daily_total(self, target_date: str = "") -> float:
        if not target_date:
            target_date = date.today().isoformat()
        d = date.fromisoformat(target_date)
        since = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        until = since + timedelta(days=1)
        rows = [r for r in self._rows_since(since) if r.get("timestamp", "") < until.isoformat()]
        return self._heartbeat_cost(rows)

    def get_weekly_total(self) -> float:
        today = date.today()
        since = datetime(today.year, today.month, today.day, tzinfo=timezone.utc) - timedelta(days=today.weekday())
        return self._heartbeat_cost(self._rows_since(since))

    def predict_runway(self) -> dict:
        bal = self.state.read().get("balance") or {}
        balance = bal.get("assets_yuan", 0)
        week_rows = self._rows_since(datetime.now(timezone.utc) - timedelta(days=7))
        heartbeats = [r for r in week_rows if r.get("event") == "heartbeat"]
        if not heartbeats:
            return {"balance_yuan": balance, "daily_rate_yuan": 0, "runway_days": None}
        total_cost = self._heartbeat_cost(week_rows)
        daily = round(total_cost / 7.0, 2)
        runway = round(balance / daily, 1) if daily > 0 else None
        return {"balance_yuan": round(balance, 2), "daily_rate_yuan": daily, "runway_days": runway}

    def check_budget(self, daily_budget: float) -> list:
        alerts = []
        today_total = self.get_daily_total()
        if today_total > daily_budget:
            alerts.append(f"今日消费 ¥{today_total}，已超预算 ¥{daily_budget}")
        runway = self.predict_runway()
        if runway.get("runway_days") is not None and runway["runway_days"] < 3:
            alerts.append(f"余额仅够 {runway['runway_days']} 天")
        return alerts
