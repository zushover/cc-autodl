"""MCP Server — GPU Monitor。

将 cc-autodl 的 GPU 监控能力以 Model Context Protocol 暴露。
任何 MCP Client（Claude Code、Cursor、自定义 Agent）都可以发现并调用。

MCP 协议三个原语：
  Tool — 可调用的原子能力（例如 gpu_status(uuid)）
  Resource — 可读取的数据（例如 instances://list）
  Prompt — 可复用的提示模板（例如 idle-detection）

面试叙事：
  "我把 GPU 监控做成了 MCP Server。其他 Agent 通过 MCP 协议
   发现我的 GPU 监控工具，标准化的 Tool/Resource/Prompt 三原语。"
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml


class MCPServer:
    """GPU Monitor MCP Server。

    提供标准 MCP 协议接口：list_tools / call_tool / list_resources / read_resource。
    底层复用 InstanceRegistry + GPUCollector。
    """

    def __init__(self):
        from ..db import get_db
        from ..instance_registry import InstanceRegistry
        self.registry = InstanceRegistry(get_db())
        self._tools = self._define_tools()
        self._resources = self._define_resources()
        self._prompts = self._define_prompts()

    # ─── Tool 定义 ───

    def _define_tools(self) -> list[dict]:
        return [
            {
                "name": "gpu_status",
                "description": "获取指定 GPU 实例的实时状态：利用率、显存、温度、功耗、运行进程。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "uuid": {
                            "type": "string",
                            "description": "实例 UUID（可只提供前12位）",
                        },
                    },
                    "required": ["uuid"],
                },
            },
            {
                "name": "gpu_history",
                "description": "获取指定实例最近 N 小时的 GPU 利用率历史。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "uuid": {"type": "string", "description": "实例 UUID"},
                        "hours": {"type": "integer", "description": "查询最近多少小时，默认24", "default": 24},
                    },
                    "required": ["uuid"],
                },
            },
            {
                "name": "list_gpu_instances",
                "description": "列出所有已注册的 GPU 实例及其状态。",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "probe_instance",
                "description": "对实例执行健康检测：SSH 连接测试 + GPU 信息采集 + 系统信息收集。自动更新实例状态。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "uuid": {"type": "string", "description": "实例 UUID"},
                    },
                    "required": ["uuid"],
                },
            },
            {
                "name": "get_balance",
                "description": "查询 AutoDL 账户余额和费用概览。",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]

    # ─── Resource 定义 ───

    def _define_resources(self) -> list[dict]:
        return [
            {
                "uri": "instances://list",
                "name": "GPU Instance List",
                "description": "所有已注册 GPU 实例的实时列表",
                "mimeType": "application/json",
            },
            {
                "uri": "gpu://{uuid}/latest",
                "name": "Latest GPU Snapshot",
                "description": "指定实例的最新 GPU 快照数据。用实际 UUID 替换 {uuid}。",
                "mimeType": "application/json",
            },
            {
                "uri": "balance://overview",
                "name": "Account Balance Overview",
                "description": "当前账户余额和费用概览",
                "mimeType": "application/json",
            },
        ]

    # ─── Prompt 定义 ───

    def _define_prompts(self) -> list[dict]:
        return [
            {
                "name": "idle_detection",
                "description": "检测空闲 GPU 实例并建议关机",
                "arguments": [
                    {"name": "idle_threshold_percent", "description": "GPU 利用率低于此值视为空闲", "required": False},
                ],
            },
            {
                "name": "cost_optimization",
                "description": "分析费用并提供优化建议",
                "arguments": [],
            },
        ]

    # ─── MCP 协议方法 ───

    def list_tools(self) -> list[dict]:
        """MCP: 返回所有可用 Tool。"""
        return self._tools

    def call_tool(self, name: str, arguments: dict) -> str:
        """MCP: 调用指定 Tool 并返回结果。"""
        if name == "gpu_status":
            return self._handle_gpu_status(arguments.get("uuid", ""))
        elif name == "gpu_history":
            return self._handle_gpu_history(arguments.get("uuid", ""), arguments.get("hours", 24))
        elif name == "list_gpu_instances":
            return self._handle_list_instances()
        elif name == "probe_instance":
            return self._handle_probe(arguments.get("uuid", ""))
        elif name == "get_balance":
            return self._handle_balance()
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})

    def list_resources(self) -> list[dict]:
        """MCP: 返回所有可用 Resource。"""
        return self._resources

    def read_resource(self, uri: str) -> str:
        """MCP: 读取指定 Resource。"""
        if uri == "instances://list":
            return self._handle_list_instances()
        elif uri.startswith("gpu://") and uri.endswith("/latest"):
            uuid = uri.replace("gpu://", "").replace("/latest", "")
            return self._handle_gpu_status(uuid)
        elif uri == "balance://overview":
            return self._handle_balance()
        else:
            return json.dumps({"error": f"Unknown resource: {uri}"})

    def list_prompts(self) -> list[dict]:
        """MCP: 返回所有 Prompt 模板。"""
        return self._prompts

    # ─── 内部处理器 ───

    def _handle_gpu_status(self, uuid: str) -> str:
        inst = self.registry.get(uuid)
        if not inst:
            return json.dumps({"error": f"Instance {uuid} not found"})

        from ..gpu_collector import GPUCollector
        collector = GPUCollector(
            ssh_key_path=inst.get("ssh_key_path", ""),
            ssh_user=inst.get("ssh_user", "root"),
            ssh_password=inst.get("ssh_password", ""),
        )
        result = collector.collect(inst["ssh_host"], inst.get("ssh_port", 22))
        if not result:
            return json.dumps({
                "uuid": uuid,
                "alias": inst.get("alias", ""),
                "status": inst.get("status", "unknown"),
                "error": "SSH unreachable",
            })

        return json.dumps({
            "uuid": uuid,
            "alias": inst.get("alias", ""),
            "gpu_utilization_percent": result["util_percent"],
            "memory_used_gb": result["mem_used_gb"],
            "memory_total_gb": result["mem_total_gb"],
            "temperature_c": result["temp_c"],
            "power_watts": result.get("power_w", 0),
            "processes": result.get("processes", []),
            "timestamp": result.get("timestamp", ""),
        }, ensure_ascii=False, indent=2)

    def _handle_gpu_history(self, uuid: str, hours: int = 24) -> str:
        from ..db import get_db
        db = get_db()
        snapshots = db.get_gpu_history(uuid, hours)
        return json.dumps({
            "uuid": uuid,
            "hours": hours,
            "snapshot_count": len(snapshots),
            "snapshots": [
                {
                    "timestamp": s["timestamp"],
                    "util_percent": s["util_percent"],
                    "mem_used_gb": s["mem_used_gb"],
                    "temp_c": s["temp_c"],
                }
                for s in snapshots[-50:]  # 最多返回50条
            ],
        }, ensure_ascii=False, indent=2)

    def _handle_list_instances(self) -> str:
        instances = self.registry.list_all()
        return json.dumps({
            "total": len(instances),
            "instances": [
                {
                    "uuid": i["uuid"][:12],
                    "alias": i.get("alias", ""),
                    "source": i.get("source", "unknown"),
                    "status": i.get("status", "unknown"),
                    "gpu_type": i.get("gpu_type", ""),
                    "price_per_hour": i.get("price_per_hour", 0),
                }
                for i in instances
            ],
        }, ensure_ascii=False, indent=2)

    def _handle_probe(self, uuid: str) -> str:
        result = self.registry.probe_ssh(uuid)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def _handle_balance(self) -> str:
        config = self._load_config()
        token = config.get("auto_dl", {}).get("token", "")
        if not token or token == "your-token-here":
            return json.dumps({"error": "AutoDL token not configured"})

        from ..autodl_api import AutoDLAPI
        api = AutoDLAPI(token)
        try:
            bal = api.get_balance()
            return json.dumps({
                "balance_yuan": round(bal["assets_yuan"], 2),
                "total_spent_yuan": round(bal["accumulate_yuan"], 2),
                "voucher_balance": bal.get("voucher_balance", 0),
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _load_config(self) -> dict:
        config_path = Path(__file__).parent.parent.parent / "config.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}


# ─── MCP Client 示例 ───

def demo_mcp_client():
    """演示 MCP Client 如何发现和调用 GPU Monitor Server。

    任何 MCP Client 的标准流程：
    1. list_tools() → 发现可用工具
    2. call_tool(name, args) → 调用工具
    3. list_resources() → 发现可读数据
    4. read_resource(uri) → 读取数据
    """
    server = MCPServer()

    print("=== MCP Server Demo ===")
    print(f"\nTools ({len(server.list_tools())}):")
    for t in server.list_tools():
        print(f"  - {t['name']}: {t['description'][:60]}")

    print(f"\nResources ({len(server.list_resources())}):")
    for r in server.list_resources():
        print(f"  - {r['uri']}: {r['description'][:60]}")

    print(f"\nPrompts ({len(server.list_prompts())}):")
    for p in server.list_prompts():
        print(f"  - {p['name']}: {p['description'][:60]}")

    print("\n=== Calling list_gpu_instances ===")
    result = server.call_tool("list_gpu_instances", {})
    print(result[:500])


if __name__ == "__main__":
    demo_mcp_client()
