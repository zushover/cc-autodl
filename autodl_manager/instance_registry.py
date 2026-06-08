"""实例注册表 — 统一管理 Pro API / Web 控制台 / 自定义 SSH 三种来源的实例。

三种来源：
  pro-xxx  — AutoDL Pro API 创建，通过 API 管理生命周期
  web-xxx  — AutoDL Web 控制台创建，通过 SSH 管理
  ssh-xxx  — 任意可 SSH 的机器，通过 SSH 管理

所有实例统一存储在 SQLite 中，统一在面板中展示。
"""

import re
import uuid as _uuid_mod
from pathlib import Path
from typing import Optional

import paramiko
import yaml

from .db import Database, get_db


SSH_CONFIG_BLOCK = """Host autodl-{alias}
\tHostName {host}
\tPort {port}
\tUser {user}
\tIdentityFile {key_path}
\tStrictHostKeyChecking no
\tServerAliveInterval 60
"""


class InstanceRegistry:
    """统一实例注册表。"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_db()

    # ─── 注册 ───

    def register_pro(self, instance_uuid: str, detail: Optional[dict] = None) -> dict:
        """注册一个 Pro API 实例（从 API 同步或手动添加）。"""
        inst = {
            "uuid": instance_uuid,
            "source": "pro",
            "alias": "",
            "tags": "[]",
            "status": detail.get("status", "unknown") if detail else "unknown",
            "api_detail": yaml.dump(detail) if detail else "{}",
            "region": detail.get("region_sign", "") if detail else "",
            "gpu_type": detail.get("gpu_type", "") if detail else "",
            "price_per_hour": detail.get("payg_price", 0) if detail else 0,
            "ssh_host": detail.get("proxy_host", "") if detail else "",
            "ssh_port": detail.get("ssh_port", 22) if detail else 22,
        }
        self.db.upsert_instance(inst)
        return inst

    def register_web(
        self,
        ssh_host: str,
        ssh_port: int = 22,
        ssh_user: str = "root",
        ssh_key_path: str = "",
        ssh_password: str = "",
        alias: str = "",
        gpu_type: str = "",
        region: str = "",
        price_per_hour: float = 0.0,
        tags: Optional[list] = None,
        status: str = "stopped",
    ) -> dict:
        """注册一个 Web 控制台实例（用户手动在 autodl.com 创建的）。"""
        instance_uuid = f"web-{_uuid_mod.uuid4().hex[:12]}"
        inst = {
            "uuid": instance_uuid,
            "source": "web",
            "alias": alias or f"{gpu_type or 'GPU'}-{region or ssh_host[:8]}",
            "tags": _to_json(tags or []),
            "ssh_host": ssh_host,
            "ssh_port": ssh_port,
            "ssh_user": ssh_user,
            "ssh_key_path": ssh_key_path,
            "ssh_password": ssh_password,
            "gpu_type": gpu_type,
            "region": region,
            "price_per_hour": price_per_hour,
            "status": status,
        }
        self.db.upsert_instance(inst)
        return inst

    def register_ssh(
        self,
        host: str,
        port: int = 22,
        username: str = "root",
        key_filename: str = "",
        password: str = "",
        alias: str = "",
        gpu_type: str = "",
        tags: Optional[list] = None,
    ) -> dict:
        """注册一个自定义 SSH 实例（实验室机器等）。"""
        instance_uuid = f"ssh-{_uuid_mod.uuid4().hex[:12]}"
        inst = {
            "uuid": instance_uuid,
            "source": "ssh",
            "alias": alias or f"{username}@{host}:{port}",
            "tags": _to_json(tags or []),
            "ssh_host": host,
            "ssh_port": port,
            "ssh_user": username,
            "ssh_key_path": key_filename,
            "gpu_type": gpu_type,
            "price_per_hour": 0.0,
            "status": "unknown",
        }
        self.db.upsert_instance(inst)
        if key_filename:
            self._update_ssh_config(inst)
        return inst

    # ─── 查询 ───

    def get(self, uuid: str) -> Optional[dict]:
        return self.db.get_instance(uuid)

    def list_all(self, source: Optional[str] = None) -> list[dict]:
        return self.db.list_instances(source)

    def get_current(self) -> Optional[dict]:
        instances = self.db.list_instances()
        for inst in instances:
            if inst.get("is_current"):
                return inst
        return None

    def get_running(self) -> list[dict]:
        return [i for i in self.db.list_instances() if i.get("status") == "running"]

    def get_by_alias(self, alias: str) -> Optional[dict]:
        for inst in self.db.list_instances():
            if inst.get("alias") == alias:
                return inst
        return None

    def search(self, query: str) -> list[dict]:
        q = query.lower()
        return [
            i for i in self.db.list_instances()
            if q in (i.get("alias") or "").lower()
            or q in (i.get("uuid") or "").lower()
            or q in (i.get("gpu_type") or "").lower()
            or q in (i.get("tags") or "[]").lower()
        ]

    # ─── 操作 ───

    def set_current(self, uuid: str) -> None:
        inst = self.db.get_instance(uuid)
        if not inst:
            raise ValueError(f"实例不存在: {uuid}")
        self.db.set_current(uuid)

    def update_status(self, uuid: str, status: str) -> None:
        self.db.update_instance_status(uuid, status)

    def update_gpu_info(self, uuid: str, gpu_type: str, price: float, region: str = "") -> None:
        inst = self.db.get_instance(uuid)
        if inst:
            if gpu_type:
                self.db.update_instance_field(uuid, "gpu_type", gpu_type)
            if price:
                self.db.update_instance_field(uuid, "price_per_hour", price)
            if region:
                self.db.update_instance_field(uuid, "region", region)

    def update_alias(self, uuid: str, alias: str, tags: Optional[list] = None) -> None:
        self.db.update_instance_field(uuid, "alias", alias)
        if tags is not None:
            self.db.update_instance_field(uuid, "tags", _to_json(tags))

    def unregister(self, uuid: str) -> bool:
        """注销实例。返回是否成功。"""
        inst = self.db.get_instance(uuid)
        if not inst:
            return False
        self.db.delete_instance(uuid)
        return True

    # ─── SSH 探测 ───

    def probe_ssh(self, uuid: str) -> dict:
        """SSH 连接探测：智能识别实例状态 + 获取 GPU/系统信息。"""
        inst = self.db.get_instance(uuid)
        if not inst:
            return {"reachable": False, "error": "实例不存在"}

        host = inst.get("ssh_host", "")
        port = inst.get("ssh_port", 22)
        user = inst.get("ssh_user", "root")
        key = inst.get("ssh_key_path", "") or ""
        password = inst.get("ssh_password", "") or ""

        if not host:
            return {"reachable": False, "error": "SSH host 未配置"}

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            connect_kwargs: dict = {"hostname": host, "port": port, "username": user, "timeout": 10, "banner_timeout": 10}
            if key:
                connect_kwargs["key_filename"] = key
            elif password:
                connect_kwargs["password"] = password
            else:
                return {"reachable": False, "error": "需要 SSH 密码或密钥，请在实例中配置"}

            client.connect(**connect_kwargs)

            # 一次性获取所有信息
            cmd = (
                "HAS_GPU=0; "
                "GPU_DATA=$(nvidia-smi --query-gpu=name,memory.total,memory.free,utilization.gpu,temperature.gpu --format=csv,noheader 2>/dev/null); "
                "if [ -n \"$GPU_DATA\" ]; then HAS_GPU=1; fi; "
                "echo \"GPU_PRESENT=$HAS_GPU\"; "
                "echo \"$GPU_DATA\"; "
                "echo '---GPU_PROC---'; "
                "if [ $HAS_GPU -eq 1 ]; then "
                "  nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>/dev/null; "
                "fi; "
                "echo '---SYS---'; "
                "hostname; "
                "(python3 --version 2>/dev/null || python --version 2>/dev/null || which python3 2>/dev/null || which python 2>/dev/null || echo 'Python: N/A'); "
                "df -h /root/autodl-tmp 2>/dev/null | tail -1; "
                "free -h 2>/dev/null | grep Mem; "
                "echo '---OS---'; "
                "cat /etc/os-release 2>/dev/null | head -1"
            )
            stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
            output = stdout.read().decode(errors="replace").strip()
            client.close()

            # 解析结果
            lines = output.split("\n")
            gpu_present = False
            gpu_name = ""; gpu_mem_total = 0; gpu_mem_free = 0
            gpu_util = 0; gpu_temp = 0; gpu_mem_total_mb = 0; gpu_mem_free_mb = 0
            hostname = ""; python_ver = ""; disk_info = ""; ram_info = ""; os_info = ""
            processes = []
            section = "gpu"

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("GPU_PRESENT="):
                    gpu_present = line.split("=", 1)[1] == "1"
                elif line == "---GPU_PROC---":
                    section = "proc"
                elif line == "---SYS---":
                    section = "sys"
                elif line == "---OS---":
                    section = "os"
                elif section == "gpu" and "," in line:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 5:
                        gpu_name = parts[0]
                        gpu_mem_total_mb = int(parts[1].split()[0])
                        gpu_mem_free_mb = int(parts[2].split()[0])
                        gpu_util = int(parts[3])
                        gpu_temp = int(parts[4])
                elif section == "proc" and "," in line:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 3:
                        processes.append({"pid": parts[0], "name": parts[1], "gpu_mem_mb": parts[2]})
                elif section == "sys":
                    if not hostname: hostname = line
                    elif ("Python" in line or "python" in line) and not python_ver: python_ver = line
                    elif "/root" in line and not disk_info: disk_info = line
                    elif "Mem:" in line and not ram_info: ram_info = line
                elif section == "os":
                    if not os_info: os_info = line

            # 智能判断状态
            if not gpu_present:
                new_status = "no_gpu"  # SSH通了但没GPU → 无卡模式
            else:
                new_status = "running"  # 有GPU → 运行中

            # 更新数据库
            if gpu_name:
                self.db.update_instance_field(uuid, "gpu_type", gpu_name)
            self.db.update_instance_field(uuid, "status", new_status)

            # 写 GPU 快照
            if gpu_present:
                gpu_mem_total_gb = round(gpu_mem_total_mb / 1024.0, 1)
                gpu_mem_used_gb = round((gpu_mem_total_mb - gpu_mem_free_mb) / 1024.0, 1)
                from datetime import datetime, timezone
                self.db.insert_gpu_snapshot(uuid, {
                    "util_percent": gpu_util,
                    "mem_used_gb": gpu_mem_used_gb,
                    "mem_total_gb": gpu_mem_total_gb,
                    "temp_c": gpu_temp,
                    "processes": processes,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            return {
                "reachable": True,
                "status": new_status,
                "gpu_present": gpu_present,
                "gpu": {
                    "gpu_name": gpu_name,
                    "util_percent": gpu_util,
                    "mem_total_gb": round(gpu_mem_total_mb / 1024.0, 1) if gpu_mem_total_mb else 0,
                    "mem_used_gb": round((gpu_mem_total_mb - gpu_mem_free_mb) / 1024.0, 1) if gpu_mem_total_mb else 0,
                    "mem_free_gb": round(gpu_mem_free_mb / 1024.0, 1) if gpu_mem_free_mb else 0,
                    "temp_c": gpu_temp,
                } if gpu_present else None,
                "processes": processes,
                "hostname": hostname,
                "python": python_ver,
                "disk": disk_info,
                "ram": ram_info,
                "os": os_info,
            }
        except Exception as e:
            # SSH 连不上 → 标记为 stopped
            self.db.update_instance_field(uuid, "status", "stopped")
            return {"reachable": False, "error": str(e), "status": "stopped"}
        finally:
            try:
                client.close()
            except Exception:
                pass

    # ─── SSH Config ───

    def _update_ssh_config(self, inst: dict) -> None:
        host = inst.get("ssh_host", "")
        port = inst.get("ssh_port", 22)
        alias = inst.get("alias", inst["uuid"][:12])
        key = inst.get("ssh_key_path", "")

        if not host or not key:
            return

        ssh_config_path = Path.home() / ".ssh" / "config"
        ssh_config_path.parent.mkdir(mode=0o700, exist_ok=True)

        safe_alias = re.sub(r"[^a-zA-Z0-9_-]", "-", alias)
        block = SSH_CONFIG_BLOCK.format(
            alias=safe_alias, host=host, port=port,
            user=inst.get("ssh_user", "root"), key_path=key.replace("\\", "/"),
        )

        if ssh_config_path.exists():
            content = ssh_config_path.read_text(encoding="utf-8")
            pattern = rf"(?:\n)?Host autodl-{re.escape(safe_alias)}\n(?:\t.*\n?| [^\n]*\n?)*"
            content = re.sub(pattern, "", content).rstrip("\n") + "\n" + block
            ssh_config_path.write_text(content, encoding="utf-8")
        else:
            ssh_config_path.write_text(block)

    # ─── 统计 ───

    def stats(self) -> dict:
        all_inst = self.db.list_instances()
        running = [i for i in all_inst if i.get("status") == "running"]
        web_count = sum(1 for i in all_inst if i.get("source") == "web")
        pro_count = sum(1 for i in all_inst if i.get("source") == "pro")
        ssh_count = sum(1 for i in all_inst if i.get("source") == "ssh")
        return {
            "total": len(all_inst),
            "running": len(running),
            "stopped": len(all_inst) - len(running),
            "by_source": {"web": web_count, "pro": pro_count, "ssh": ssh_count},
        }


def _to_json(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)
