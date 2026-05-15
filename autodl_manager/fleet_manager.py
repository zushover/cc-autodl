import re
from pathlib import Path

from .autodl_api import AutoDLAPI
from .state_manager import StateManager


SSH_CONFIG_HOST = """Host autodl
\tHostName {host}
\tPort {port}
\tUser {user}
\tIdentityFile {key_path}
\tStrictHostKeyChecking no
\tServerAliveInterval 60
"""


class FleetManager:
    def __init__(self, api: AutoDLAPI, state: StateManager, ssh_key: str, ssh_user: str = "root"):
        self.api = api
        self.state = state
        self.ssh_key = ssh_key
        self.ssh_user = ssh_user

    def sync_from_api(self) -> list:
        raw = self.api.list_instances()
        remote = {}
        for inst in raw:
            uid = inst.get("uuid") or inst.get("instance_uuid", "")
            if not uid:
                continue
            inst["instance_uuid"] = uid
            inst["instance_name"] = inst.get("name") or inst.get("instance_name", "")
            inst.setdefault("gpu_type", inst.get("gpu_spec_uuid", ""))
            inst.setdefault("ssh_command", "")
            inst.setdefault("ssh_host", "")
            inst.setdefault("ssh_port", 22)
            inst.setdefault("payg_price", 0)
            inst.setdefault("jupyter_url", "")
            inst.setdefault("jupyter_token", "")

            try:
                detail = self.api.get_instance_detail(uid)
                inst["ssh_command"] = detail.get("ssh_command", "")
                inst["ssh_host"] = detail.get("proxy_host", "")
                inst["ssh_port"] = detail.get("ssh_port", 22)
                inst["jupyter_url"] = detail.get("jupyter_domain", "")
                inst["jupyter_token"] = detail.get("jupyter_token", "")
                inst["root_password"] = detail.get("root_password", "")
                price = detail.get("payg_price", 0)
                inst["payg_price"] = round(price / 100.0, 2) if price > 100 else float(price)
            except Exception:
                pass

            remote[uid] = inst
        local = self.state.read().get("instances", {})

        merged = {}
        for uuid, inst in remote.items():
            prev = local.get(uuid, {})
            inst.setdefault("tags", prev.get("tags", []))
            inst["last_seen"] = inst.get("last_seen", "")
            merged[uuid] = inst

        for uuid, inst in local.items():
            if uuid not in remote:
                inst["status"] = "released"
                inst["last_seen"] = inst.get("last_seen", "")
                merged[uuid] = inst

        self.state.write({"instances": merged})
        return list(merged.values())

    def list_instances(self, filters: dict | None = None) -> list:
        instances = list(self.state.read().get("instances", {}).values())
        if not filters:
            return instances

        result = instances
        if "status" in filters:
            result = [i for i in result if i.get("status") == filters["status"]]
        if "region" in filters:
            result = [i for i in result if filters["region"] in i.get("region_sign", "")]
        if "gpu" in filters:
            spec = filters["gpu"]
            result = [i for i in result if i.get("gpu_spec_uuid") == spec or spec in i.get("gpu_type", "")]
        if "tag" in filters:
            t = filters["tag"]
            result = [i for i in result if t in i.get("tags", [])]
        return result

    def get_current(self) -> dict | None:
        state = self.state.read()
        uuid = state.get("current_instance_uuid")
        if not uuid:
            return None
        return state.get("instances", {}).get(uuid)

    def switch_to(self, identifier: str) -> dict:
        instances = self.state.read().get("instances", {})
        found = None
        for uuid, inst in instances.items():
            if identifier == uuid or identifier == inst.get("instance_name") or identifier in inst.get("tags", []):
                found = inst
                break
        if not found:
            raise ValueError(f"未找到实例: {identifier}")
        self.state.set_current(found["instance_uuid"])
        self.update_ssh_config(found)
        return found

    def create_instance(self, spec: dict) -> str:
        uuid = self.api.create_instance(
            gpu_spec_uuid=spec["gpu_spec_uuid"],
            image_uuid=spec["image_uuid"],
            req_gpu_amount=spec.get("req_gpu_amount", 1),
            expand_system_disk_by_gb=spec.get("expand_system_disk_by_gb", 0),
            cuda_v_from=spec.get("cuda_v_from", 113),
            data_center_list=spec.get("data_center_list"),
            instance_name=spec.get("instance_name"),
            start_command=spec.get("start_command"),
        )
        self.sync_from_api()
        return uuid

    def start_instance(self, uuid: str, mode: str = "gpu") -> None:
        self.api.power_on(uuid)
        self.state.update_instance(uuid, {"status": "powering_on"})

    def stop_instance(self, uuid: str, force: bool = False) -> None:
        self.api.power_off(uuid)
        self.state.update_instance(uuid, {"status": "powering_off"})

    def release_instance(self, uuid: str) -> None:
        self.api.release_instance(uuid)
        self.state.update_instance(uuid, {"status": "released"})

    def update_ssh_config(self, instance: dict) -> None:
        host = instance.get("ssh_host", "")
        port = instance.get("ssh_port", 22)
        if not host:
            return

        ssh_config_path = Path.home() / ".ssh" / "config"
        ssh_config_path.parent.mkdir(mode=0o700, exist_ok=True)

        block = SSH_CONFIG_HOST.format(
            host=host,
            port=port,
            user=self.ssh_user,
            key_path=self.ssh_key.replace("\\", "/"),
        )

        if ssh_config_path.exists():
            content = ssh_config_path.read_text(encoding="utf-8")
            pattern = r"(?:\n)?Host autodl\n(?:\t.*\n?| [^\n]*\n?)*"
            if re.search(pattern, content):
                content = re.sub(pattern, "", content)
            content = content.rstrip("\n") + "\n" + block
            ssh_config_path.write_text(content, encoding="utf-8")
        else:
            ssh_config_path.write_text(block, encoding="utf-8")
