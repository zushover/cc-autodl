import time
import sys
from pathlib import Path

import requests
import yaml


class AutoDLAPIError(Exception):
    def __init__(self, code: str, msg: str, request_id: str = ""):
        self.code = code
        self.msg = msg
        self.request_id = request_id
        super().__init__(f"[{code}] {msg}" + (f" (request_id={request_id})" if request_id else ""))


class AutoDLAPI:
    BASE_URL = "https://api.autodl.com"

    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers["Authorization"] = token
        self.session.timeout = 30

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.BASE_URL}{path}"
        backoff = 1.0

        for attempt in range(3):
            try:
                resp = self.session.request(method, url, timeout=30, **kwargs)
                break
            except requests.exceptions.RequestException as e:
                if attempt == 2:
                    raise AutoDLAPIError("NetworkError", str(e))
                time.sleep(backoff)
                backoff *= 2

        body = resp.json()
        if body.get("code") != "Success":
            raise AutoDLAPIError(
                body.get("code", "Unknown"),
                body.get("msg", "Unknown error"),
                body.get("request_id", ""),
            )

        return body.get("data", {})

    def _paginate(self, method: str, path: str, **kwargs) -> list:
        params = kwargs.pop("params", {})
        params.setdefault("page_index", 1)
        params.setdefault("page_size", 50)

        all_items = []
        while True:
            data = self._request(method, path, params={**params}, **kwargs)
            items = data.get("list") or [] if isinstance(data, dict) else []
            all_items.extend(items)
            max_page = data.get("max_page", 1) if isinstance(data, dict) else 1
            if params["page_index"] >= max_page:
                break
            params["page_index"] += 1

        return all_items


    def create_instance(
        self,
        gpu_spec_uuid: str,
        image_uuid: str,
        req_gpu_amount: int = 1,
        expand_system_disk_by_gb: int = 0,
        cuda_v_from: int = 113,
        data_center_list: list | None = None,
        instance_name: str | None = None,
        start_command: str | None = None,
    ) -> str:
        payload = {
            "gpu_spec_uuid": gpu_spec_uuid,
            "image_uuid": image_uuid,
            "req_gpu_amount": req_gpu_amount,
            "expand_system_disk_by_gb": expand_system_disk_by_gb,
            "cuda_v_from": cuda_v_from,
        }
        if data_center_list:
            payload["data_center_list"] = data_center_list
        if instance_name:
            payload["instance_name"] = instance_name
        if start_command:
            payload["start_command"] = start_command

        data = self._request("POST", "/api/v1/dev/instance/pro/create", json=payload)
        return data.get("instance_uuid", "")

    def list_instances(self) -> list:
        return self._paginate("POST", "/api/v1/dev/instance/pro/list")

    def get_instance_detail(self, uuid: str) -> dict:
        return self._request("GET", "/api/v1/dev/instance/pro/snapshot", params={"instance_uuid": uuid})

    def get_instance_status(self, uuid: str) -> str:
        data = self._request("GET", "/api/v1/dev/instance/pro/status", params={"instance_uuid": uuid})
        return data.get("status", "unknown")

    def power_on(self, uuid: str, start_command: str | None = None) -> None:
        payload: dict = {"instance_uuid": uuid, "payload": "gpu"}
        if start_command:
            payload["start_command"] = start_command
        self._request("POST", "/api/v1/dev/instance/pro/power_on", json=payload)

    def power_off(self, uuid: str) -> None:
        self._request("POST", "/api/v1/dev/instance/pro/power_off", json={"instance_uuid": uuid})

    def release_instance(self, uuid: str) -> None:
        status = self.get_instance_status(uuid)
        if status == "running":
            self.power_off(uuid)
            for _ in range(60):
                time.sleep(5)
                if self.get_instance_status(uuid) == "stopped":
                    break
        self._request("POST", "/api/v1/dev/instance/pro/release", json={"instance_uuid": uuid})


    def save_image(self, uuid: str, name: str) -> str:
        data = self._request(
            "POST",
            "/api/v1/dev/instance/pro/image/save",
            json={"instance_uuid": uuid, "image_name": name},
        )
        return data.get("image_uuid", "")

    def list_private_images(self) -> list:
        return self._paginate("POST", "/api/v1/dev/instance/pro/image/private/list")


    def get_balance(self) -> dict:
        data = self._request("POST", "/api/v1/dev/wallet/balance")
        assets = data.get("assets", 0)
        return {
            "assets": assets,
            "assets_yuan": assets / 1000.0,
            "voucher_balance": data.get("voucher_balance", 0),
            "accumulate": data.get("accumulate", 0),
            "accumulate_yuan": data.get("accumulate", 0) / 1000.0,
        }


    def mount_nfs(self, data_center: str, mount: bool = True) -> None:
        self._request(
            "POST",
            "/api/v1/dev/exclusive_nfs/mount",
            json={"data_center": data_center, "mountable": 1 if mount else -1},
        )


def _load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.yaml"
    if not config_path.exists():
        print("config.yaml 不存在，跳过测试")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test():
    config = _load_config()
    token = config.get("auto_dl", {}).get("token", "")
    if not token or token == "your-token-here":
        print("请在 config.yaml 中填入 AutoDL Token")
        sys.exit(1)

    api = AutoDLAPI(token)
    passed = 0
    failed = 0

    def run(name: str, fn, *args):
        nonlocal passed, failed
        try:
            result = fn(*args)
            print(f"  PASS  {name}")
            passed += 1
            return result
        except Exception as e:
            print(f"  FAIL  {name}: {e}")
            failed += 1
            return None

    print("AutoDL API 自检\n")

    print("[余额]")
    bal = run("get_balance", api.get_balance)
    if bal:
        print(f"        assets_yuan={bal['assets_yuan']}, accumulate_yuan={bal['accumulate_yuan']}")

    print("[实例列表]")
    instances = run("list_instances", api.list_instances)
    uuids = []
    if instances:
        for inst in instances[:5]:
            u = inst.get("instance_uuid", "")
            s = inst.get("status", "?")
            name = inst.get("instance_name", u[:12])
            print(f"        {u}  {s:10s}  {name}")
            uuids.append(u)

    if uuids:
        test_uuid = uuids[0]
        print(f"\n[实例详情] uuid={test_uuid}")
        run("get_instance_detail", api.get_instance_detail, test_uuid)

        print(f"\n[实例状态]")
        status = run("get_instance_status", api.get_instance_status, test_uuid)
        if status:
            print(f"        status={status}")

    print(f"\n[镜像]")
    images = run("list_private_images", api.list_private_images)
    if images:
        for img in images[:3]:
            print(f"        {img.get('image_uuid','?')[:20]}  {img.get('image_name','?')}")

    print(f"\n{'='*40}")
    print(f"通过: {passed}/{passed+failed}")
    if failed:
        print(f"失败: {failed}")
    print(f"{'='*40}")


if __name__ == "__main__":
    test()
