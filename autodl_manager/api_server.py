"""AutoDL Manager API Server — REST + SSE + Web 面板。

重构后支持三种实例来源（Pro API / Web 控制台 / 自定义 SSH），
SSE 实时推送 GPU 数据，Vue 3 现代化前端。
"""

import json
import time
import asyncio
import queue
from pathlib import Path
from typing import Optional

import paramiko
import yaml
from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .autodl_api import AutoDLAPI, AutoDLAPIError
from .db import get_db
from .instance_registry import InstanceRegistry
from .gpu_collector import GPUCollector
from .gpu_data import GPU_TYPES, PRO_GPU_TYPES, REGIONS, find_gpu
from .daemon import DaemonV2, set_broadcaster

# ─── SSE 订阅者管理 ───
_sse_subscribers: list[queue.Queue] = []


def _sse_broadcast(event: str, data: dict):
    """向所有 SSE 订阅者推送事件。"""
    dead = []
    for q in _sse_subscribers:
        try:
            q.put_nowait({"event": event, "data": data})
        except Exception:
            dead.append(q)
    for q in dead:
        _sse_subscribers.remove(q)


# ─── 配置 ───

def _load_config() -> dict:
    # 1. 开发模式：相对于源码目录
    config_path = Path(__file__).parent.parent / "config.yaml"
    # 2. PyInstaller frozen：exe 所在目录（sidecar.py 已 chdir 到那里）
    frozen_path = Path.cwd() / "config.yaml"
    for p in (config_path, frozen_path):
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
    return {}


def _has_token() -> bool:
    config = _load_config()
    t = config.get("auto_dl", {}).get("token", "")
    return bool(t and t != "your-token-here")


# ─── 全局服务 ───

_registry: Optional[InstanceRegistry] = None
_api: Optional[AutoDLAPI] = None
_collector: Optional[GPUCollector] = None


def _get_registry() -> InstanceRegistry:
    global _registry
    if _registry is None:
        _registry = InstanceRegistry(get_db())
    return _registry


def _get_api() -> AutoDLAPI:
    global _api
    if _api is None:
        config = _load_config()
        token = config.get("auto_dl", {}).get("token", "")
        _api = AutoDLAPI(token)
    return _api


def _get_collector() -> GPUCollector:
    global _collector
    if _collector is None:
        config = _load_config()
        _collector = GPUCollector(
            config.get("ssh", {}).get("key_path", ""),
            config.get("ssh", {}).get("user", "root"),
        )
    return _collector



# ─── FastAPI App ───

# 前端文件路径
def _frontend_dir() -> Path:
    """返回前端 dist 目录。支持多种部署模式。"""
    import sys
    candidates = []

    # 1. 相对于可执行文件（优先级最高，方便热更新 dist/）
    try:
        candidates.append(Path(sys.executable).parent / "dist")
    except Exception:
        pass

    # 2. 相对于 CWD（sidecar chdir 到 exe 所在目录后）
    candidates.append(Path.cwd() / "dist")

    # 3. 开发模式：相对于 api_server.py
    candidates.append(Path(__file__).parent.parent / "dist")

    # 4. PyInstaller: dist/ 作为 data 文件被打包到 sys._MEIPASS（最低优先级）
    if getattr(sys, 'frozen', False):
        candidates.append(Path(sys._MEIPASS) / "dist")

    for p in candidates:
        if (p / "index.html").exists():
            return p
    return candidates[0]  # 返回第一个作为默认值

FRONTEND_PATH = _frontend_dir() / "index.html"
STATIC_DIR = _frontend_dir() / "assets"


def create_app() -> FastAPI:
    app = FastAPI(title="AutoDL Manager")

    # 静态文件（Vue 打包后的 JS/CSS）
    if STATIC_DIR.exists():
        app.mount("/assets", StaticFiles(directory=str(STATIC_DIR)), name="assets")

    # ─── 页面 ───

    @app.get("/", response_class=HTMLResponse)
    async def index():
        if FRONTEND_PATH.exists():
            return HTMLResponse(FRONTEND_PATH.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>Frontend not found</h1>")

    # ─── REST API: 实例 ───

    @app.get("/api/instances")
    async def list_instances(source: Optional[str] = Query(None)):
        reg = _get_registry()
        instances = reg.list_all(source)
        return {"instances": instances, "stats": reg.stats()}

    @app.post("/api/instances/register")
    async def register_instance(request: Request):
        # WebView2 在 Windows 中文环境下可能发送 GBK 编码的 JSON，
        # 需要手动解码而不是依赖 Starlette 的 UTF-8 默认解码
        body_bytes = await request.body()
        try:
            body = json.loads(body_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            body = json.loads(body_bytes.decode("gbk", errors="replace"))

        reg = _get_registry()
        source = body.get("source", "web")

        if source == "pro":
            uuid = body.get("uuid", "")
            if not uuid:
                return JSONResponse({"error": "uuid 必填"}, 400)
            inst = reg.register_pro(uuid, body.get("detail"))
            _sse_broadcast("instance_registered", inst)
            return {"instance": inst}

        elif source == "web":
            ssh_host = body.get("ssh_host", "")
            if not ssh_host:
                return JSONResponse({"error": "ssh_host 必填"}, 400)
            inst = reg.register_web(
                ssh_host=ssh_host,
                ssh_port=body.get("ssh_port", 22),
                ssh_user=body.get("ssh_user", "root"),
                ssh_key_path=body.get("ssh_key_path", ""),
                ssh_password=body.get("ssh_password", ""),
                alias=body.get("alias", ""),
                gpu_type=body.get("gpu_type", ""),
                region=body.get("region", ""),
                price_per_hour=body.get("price_per_hour", 0.0),
                tags=body.get("tags"),
                status=body.get("status", "stopped"),
            )
            _sse_broadcast("instance_registered", inst)
            return {"instance": inst}

        elif source == "ssh":
            host = body.get("host", "")
            if not host:
                return JSONResponse({"error": "host 必填"}, 400)
            inst = reg.register_ssh(
                host=host,
                port=body.get("port", 22),
                username=body.get("username", "root"),
                key_filename=body.get("key_filename", ""),
                password=body.get("password", ""),
                alias=body.get("alias", ""),
                gpu_type=body.get("gpu_type", ""),
                tags=body.get("tags"),
            )
            _sse_broadcast("instance_registered", inst)
            return {"instance": inst}

        return JSONResponse({"error": f"不支持的 source: {source}"}, 400)

    @app.delete("/api/instances/{uuid}")
    async def delete_instance(uuid: str):
        reg = _get_registry()
        ok = reg.unregister(uuid)
        if not ok:
            return JSONResponse({"error": "实例不存在"}, 404)
        _sse_broadcast("instance_removed", {"uuid": uuid})
        return {"ok": True}

    @app.put("/api/instances/{uuid}")
    async def update_instance(uuid: str, request: Request):
        body = await request.json()
        reg = _get_registry()
        inst = reg.get(uuid)
        if not inst:
            return JSONResponse({"error": "实例不存在"}, 404)
        alias = body.get("alias")
        tags = body.get("tags")
        if alias is not None or tags is not None:
            reg.update_alias(uuid, alias or inst.get("alias", ""), tags)
        return {"instance": reg.get(uuid)}

    @app.post("/api/instances/{uuid}/set-current")
    async def set_current(uuid: str):
        reg = _get_registry()
        try:
            reg.set_current(uuid)
            _sse_broadcast("current_changed", {"uuid": uuid})
            return {"ok": True}
        except ValueError as e:
            return JSONResponse({"error": str(e)}, 404)

    @app.post("/api/instances/{uuid}/probe")
    async def probe_instance(uuid: str):
        reg = _get_registry()
        result = reg.probe_ssh(uuid)
        if result.get("reachable"):
            _sse_broadcast("instance_probed", {"uuid": uuid, **result})
        _sse_broadcast("instance_status", {"uuid": uuid, "status": result.get("status", "unknown")})
        return result

    # ─── SSH 实例电源管理 ───

    @app.post("/api/instances/{uuid}/shutdown")
    def shutdown_instance(uuid: str):
        """通过 SSH 关机。"""
        reg = _get_registry()
        inst = reg.get(uuid)
        if not inst:
            return JSONResponse({"error": "实例不存在"}, 404)
        host = inst.get("ssh_host", "")
        if not host:
            return JSONResponse({"error": "SSH host 未配置"}, 400)

        password = inst.get("ssh_password", "") or ""
        key = inst.get("ssh_key_path", "") or ""
        if not password and not key:
            return JSONResponse({"error": "需要 SSH 密码或密钥"}, 400)

        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            kwargs = {"hostname": host, "port": inst.get("ssh_port", 22),
                      "username": inst.get("ssh_user", "root"), "timeout": 10}
            if key: kwargs["key_filename"] = key
            else: kwargs["password"] = password
            client.connect(**kwargs)
            client.exec_command("shutdown -h now", timeout=5)
            client.close()
            reg.update_status(uuid, "stopped")
            _sse_broadcast("instance_status", {"uuid": uuid, "status": "stopped"})
            return {"ok": True, "message": "关机指令已发送"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.post("/api/instances/{uuid}/reboot")
    def reboot_instance(uuid: str):
        """通过 SSH 重启。"""
        reg = _get_registry()
        inst = reg.get(uuid)
        if not inst:
            return JSONResponse({"error": "实例不存在"}, 404)
        host = inst.get("ssh_host", "")
        if not host:
            return JSONResponse({"error": "SSH host 未配置"}, 400)

        password = inst.get("ssh_password", "") or ""
        key = inst.get("ssh_key_path", "") or ""
        if not password and not key:
            return JSONResponse({"error": "需要 SSH 密码或密钥"}, 400)

        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            kwargs = {"hostname": host, "port": inst.get("ssh_port", 22),
                      "username": inst.get("ssh_user", "root"), "timeout": 10}
            if key: kwargs["key_filename"] = key
            else: kwargs["password"] = password
            client.connect(**kwargs)
            client.exec_command("reboot", timeout=5)
            client.close()
            _sse_broadcast("instance_status", {"uuid": uuid, "status": "powering_off"})
            return {"ok": True, "message": "重启指令已发送"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.get("/api/instances/{uuid}/gpu")
    async def get_instance_gpu(uuid: str):
        """主动采集一次 GPU 数据。使用实例级别的 SSH 凭据。"""
        reg = _get_registry()
        inst = reg.get(uuid)
        if not inst:
            return JSONResponse({"error": "实例不存在"}, 404)
        host = inst.get("ssh_host", "")
        port = inst.get("ssh_port", 22)
        if not host:
            return JSONResponse({"error": "SSH host 未配置"}, 400)

        # 使用实例级别的 SSH 凭据（密钥或密码）
        collector = GPUCollector(
            ssh_key_path=inst.get("ssh_key_path", ""),
            ssh_user=inst.get("ssh_user", "root"),
            ssh_password=inst.get("ssh_password", ""),
        )
        result = collector.collect(host, port)
        if result:
            reg.db.insert_gpu_snapshot(uuid, result)
            _sse_broadcast("gpu", {"uuid": uuid, **result})
            return result
        return JSONResponse({"error": "GPU 采集失败，SSH 不可达"}, 503)

    # ─── REST API: Pro API 同步 ───

    @app.post("/api/pro/sync")
    def sync_pro_instances():
        if not _has_token():
            return JSONResponse({"error": "Token 未配置"}, 400)
        try:
            api = _get_api()
            raw = api.list_instances()
            reg = _get_registry()
            count = 0
            for inst in raw:
                uid = inst.get("uuid") or inst.get("instance_uuid", "")
                if not uid:
                    continue
                try:
                    detail = api.get_instance_detail(uid)
                except Exception:
                    detail = {}
                inst["proxy_host"] = detail.get("proxy_host", "")
                inst["ssh_port"] = detail.get("ssh_port", 22)
                inst["payg_price"] = detail.get("payg_price", 0)
                price = inst.get("payg_price", 0)
                if price > 100:
                    price = round(price / 100.0, 2)
                reg.register_pro(uid, {
                    "status": inst.get("status", "unknown"),
                    "gpu_type": inst.get("gpu_type", inst.get("gpu_spec_uuid", "")),
                    "region_sign": inst.get("region_sign", ""),
                    "payg_price": price,
                    "proxy_host": inst.get("proxy_host", ""),
                    "ssh_port": inst.get("ssh_port", 22),
                    "instance_name": inst.get("instance_name", inst.get("name", "")),
                })
                count += 1

            _sse_broadcast("pro_synced", {"count": count})
            return {"ok": True, "synced": count}
        except AutoDLAPIError as e:
            return JSONResponse({"error": str(e), "request_id": e.request_id}, 500)

    @app.post("/api/pro/instances/{uuid}/power_on")
    def pro_power_on(uuid: str):
        if not _has_token():
            return JSONResponse({"error": "Token 未配置"}, 400)
        try:
            _get_api().power_on(uuid)
            reg = _get_registry()
            reg.update_status(uuid, "powering_on")
            _sse_broadcast("instance_status", {"uuid": uuid, "status": "powering_on"})
            return {"ok": True}
        except AutoDLAPIError as e:
            return JSONResponse({"error": str(e)}, 500)

    @app.post("/api/pro/instances/{uuid}/power_off")
    async def pro_power_off(uuid: str):
        if not _has_token():
            return JSONResponse({"error": "Token 未配置"}, 400)
        try:
            _get_api().power_off(uuid)
            reg = _get_registry()
            reg.update_status(uuid, "powering_off")
            _sse_broadcast("instance_status", {"uuid": uuid, "status": "powering_off"})
            return {"ok": True}
        except AutoDLAPIError as e:
            return JSONResponse({"error": str(e)}, 500)

    @app.post("/api/pro/instances/{uuid}/release")
    def pro_release(uuid: str):
        if not _has_token():
            return JSONResponse({"error": "Token 未配置"}, 400)
        try:
            _get_api().release_instance(uuid)
            reg = _get_registry()
            reg.unregister(uuid)
            _sse_broadcast("instance_removed", {"uuid": uuid})
            return {"ok": True}
        except AutoDLAPIError as e:
            return JSONResponse({"error": str(e)}, 500)

    @app.get("/api/balance")
    def get_balance():
        if not _has_token():
            return JSONResponse({"error": "Token 未配置"}, 400)
        try:
            bal = _get_api().get_balance()
            return bal
        except AutoDLAPIError as e:
            return JSONResponse({"error": str(e)}, 500)

    # ─── REST API: 费用 ───

    _ai_calls: int = 0

    def _track_ai_call():
        nonlocal _ai_calls
        _ai_calls += 1

    def _query_deepseek_balance() -> dict:
        """查询 DeepSeek API 余额。"""
        import requests as req
        config = _load_config()
        api_key = config.get("llm", {}).get("api_key", "")
        if not api_key:
            return {"balance": None, "error": "API Key 未配置"}
        try:
            r = req.get(
                "https://api.deepseek.com/user/balance",
                headers={"Accept": "application/json", "Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            data = r.json()
            infos = data.get("balance_infos", [])
            if infos:
                info = infos[0]
                return {
                    "balance": float(info.get("total_balance", 0)),
                    "granted": float(info.get("granted_balance", 0)),
                    "topped_up": float(info.get("topped_up_balance", 0)),
                    "currency": info.get("currency", "CNY"),
                }
            return {"balance": 0, "error": "无余额数据"}
        except Exception as e:
            return {"balance": None, "error": str(e)}

    @app.get("/api/cost")
    def cost_summary(refresh: str = "0"):
        # AutoDL
        server_balance = 0.0
        server_spent = 0.0
        if _has_token():
            try:
                bal = _get_api().get_balance()
                server_balance = bal.get("assets_yuan", 0)
                server_spent = bal.get("accumulate_yuan", 0)
            except Exception:
                pass

        # DeepSeek
        ai = _query_deepseek_balance() if refresh == "1" else {"balance": None}
        ai_balance = ai.get("balance")

        # Total
        total = server_balance + (ai_balance or 0)

        return {
            "server_balance": server_balance,
            "server_spent": server_spent,
            "ai_balance": ai_balance,
            "ai_granted": ai.get("granted", 0) if ai_balance is not None else None,
            "ai_topped_up": ai.get("topped_up", 0) if ai_balance is not None else None,
            "ai_calls": _ai_calls,
            "total_balance": round(total, 2),
        }

    # ─── REST API: 告警 ───

    @app.get("/api/alerts")
    async def get_alerts(instance_uuid: Optional[str] = Query(None)):
        db = get_db()
        return {"alerts": db.get_active_alerts(instance_uuid)}

    @app.post("/api/alerts/{alert_id}/dismiss")
    async def dismiss_alert(alert_id: str):
        db = get_db()
        db.dismiss_alert(alert_id)
        return {"ok": True}

    # ─── REST API: 统计 ───

    @app.get("/api/stats")
    async def get_stats():
        reg = _get_registry()
        return reg.stats()

    # ─── REST API: GPU 数据 ───

    @app.get("/api/gpu-types")
    def get_gpu_types(source: str = "web"):
        """返回 GPU 型号列表及参考价格。web=Web控制台, pro=Pro API"""
        types = GPU_TYPES if source != "pro" else PRO_GPU_TYPES
        return {"gpu_types": types}

    @app.get("/api/regions")
    def get_regions():
        return {"regions": REGIONS}

    # ─── SSH 连接字符串解析 ───

    @app.post("/api/parse-ssh")
    async def parse_ssh_string(request: Request):
        """解析 AutoDL SSH 连接字符串。输入: 'ssh -p 50479 root@connect.bjb2.seetacloud.com'"""
        import re
        raw = ""
        try:
            body_bytes = await request.body()
            # 尝试 UTF-8，失败则尝试 GBK
            try:
                body_str = body_bytes.decode("utf-8")
            except UnicodeDecodeError:
                body_str = body_bytes.decode("gbk", errors="replace")
            import json as _json
            body = _json.loads(body_str)
            raw = body.get("ssh_string", "").strip()
        except Exception:
            pass

        if not raw:
            return JSONResponse({"error": "请提供 SSH 连接字符串"}, 400)

        host = ""
        port = 22
        user = "root"

        # 匹配 -p PORT
        port_match = re.search(r"-p\s+(\d+)", raw)
        if port_match:
            port = int(port_match.group(1))

        # 找 user@host 部分（通常在最后）
        # 提取最后一个包含 @ 的token，或者最后一段
        tokens = raw.split()
        user_host_token = ""
        for t in reversed(tokens):
            if "@" in t:
                user_host_token = t
                break
        if not user_host_token and tokens:
            # 尝试最后一段作为 host
            user_host_token = tokens[-1]

        if "@" in user_host_token:
            u, h = user_host_token.rsplit("@", 1)
            user = u or "root"
            host = h.rstrip(".")
        else:
            host = user_host_token.rstrip(".")

        return {"host": host, "port": port, "user": user, "original": raw}

    # ─── REST API: 设置 ───

    @app.get("/api/settings")
    async def get_settings():
        config = _load_config()
        return {
            "token": config.get("auto_dl", {}).get("token", ""),
            "ssh_key": config.get("ssh", {}).get("key_path", ""),
            "ssh_user": config.get("ssh", {}).get("user", "root"),
            "llm_api_key": config.get("llm", {}).get("api_key", ""),
            "llm_api_base": config.get("llm", {}).get("api_base", "https://api.deepseek.com/v1"),
            "llm_model": config.get("llm", {}).get("model", "deepseek-v4-pro"),
        }

    @app.post("/api/settings")
    async def save_settings(request: Request):
        body = await request.json()
        config_path = Path(__file__).parent.parent / "config.yaml"

        current = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                current = yaml.safe_load(f) or {}

        if "token" in body:
            current.setdefault("auto_dl", {})["token"] = body["token"]
        if "ssh_key" in body:
            current.setdefault("ssh", {})["key_path"] = body["ssh_key"]
        if "ssh_user" in body:
            current.setdefault("ssh", {})["user"] = body["ssh_user"]
        if "llm_api_key" in body:
            current.setdefault("llm", {})["api_key"] = body["llm_api_key"]
        if "llm_api_base" in body:
            current.setdefault("llm", {})["api_base"] = body["llm_api_base"]
        if "llm_model" in body:
            current.setdefault("llm", {})["model"] = body["llm_model"]

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(current, f, allow_unicode=True, default_flow_style=False)

        # 清除缓存
        global _api
        _api = None

        _sse_broadcast("settings_updated", {"ok": True})
        return {"ok": True}

    # ─── Agent API：自然语言 GPU 管理 ───

    @app.post("/api/agent/query")
    async def agent_query(request: Request):
        """自然语言 Agent 查询。

        POST body: {"query": "检查所有GPU实例，哪些利用率低于10%？"}

        LLM 自主决定调用哪些工具来回答用户问题。
        配置从 config.yaml 的 llm 节读取。
        """
        body = await request.json()
        query = body.get("query", "").strip()
        if not query:
            return JSONResponse({"error": "query 必填"}, 400)

        config = _load_config()
        llm_config = config.get("llm", {})
        api_key = llm_config.get("api_key", "")
        api_base = llm_config.get("api_base", "https://api.deepseek.com/v1")
        model = llm_config.get("model", "deepseek-chat")

        if not api_key:
            return JSONResponse(
                {"error": "LLM API Key 未配置，请在 config.yaml 的 llm.api_key 填入密钥"},
                400,
            )

        try:
            from .agent.agent_loop import run_agent_query
            result = await run_agent_query(
                query, api_key=api_key, api_base=api_base, model=model,
                return_steps=True,
            )
            _track_ai_call()
            _sse_broadcast("agent_response", {"query": query, "answer": result["answer"]})
            return {"query": query, "answer": result["answer"], "steps": result["steps"]}
        except Exception as e:
            return JSONResponse({"error": f"Agent 执行失败: {e}"}, 500)

    @app.post("/api/agent/orchestrate")
    async def agent_orchestrate(request: Request):
        """多 Agent 编排：任务规划 → 分发 → 执行 → 汇总。

        POST body: {"query": "检查所有GPU实例，空闲的关机"}
        """
        body = await request.json()
        query = body.get("query", "").strip()
        if not query:
            return JSONResponse({"error": "query 必填"}, 400)

        config = _load_config()
        llm_config = config.get("llm", {})
        api_key = llm_config.get("api_key", "")
        api_base = llm_config.get("api_base", "https://api.deepseek.com/v1")
        model = llm_config.get("model", "deepseek-v4-pro")

        if not api_key:
            return JSONResponse(
                {"error": "LLM API Key 未配置"},
                400,
            )

        try:
            from .agent.multi_agent import MultiAgentOrchestrator
            from .agent.memory import AgentMemory

            orchestrator = MultiAgentOrchestrator(memory=AgentMemory())
            result = orchestrator.execute(
                query,
                llm_api_key=api_key,
                llm_api_base=api_base,
                llm_model=model,
            )
            _sse_broadcast("orchestrate_result", {
                "query": query,
                "summary": result["summary"],
                "task_count": result["tasks_planned"],
            })
            return result
        except Exception as e:
            return JSONResponse({"error": f"编排执行失败: {e}"}, 500)

    @app.get("/api/agent/status")
    async def agent_status():
        """获取 Agent 系统整体状态。"""
        try:
            from .agent.memory import AgentMemory
            mem = AgentMemory()
            return {
                "memory": {
                    "conversations": mem.conversations.count(),
                    "experiments": mem.experiments.count(),
                    "decisions": mem.decisions.count(),
                },
                "tools": len(["list_gpu_instances", "check_gpu_utilization",
                              "shutdown_idle_instance", "get_balance_and_cost",
                              "probe_instance_health"]),
            }
        except Exception as e:
            return JSONResponse({"error": str(e)}, 500)

    # ─── MCP 协议端点：GPU Monitor Server ───

    @app.get("/mcp/tools")
    async def mcp_list_tools():
        """MCP: 列出所有可用 Tool。"""
        from .agent.mcp_server import MCPServer
        return {"tools": MCPServer().list_tools()}

    @app.post("/mcp/call")
    async def mcp_call_tool(request: Request):
        """MCP: 调用指定 Tool。POST body: {"name": "gpu_status", "arguments": {"uuid": "..."}}"""
        body = await request.json()
        from .agent.mcp_server import MCPServer
        result = MCPServer().call_tool(body.get("name", ""), body.get("arguments", {}))
        return {"result": result}

    @app.get("/mcp/resources")
    async def mcp_list_resources():
        """MCP: 列出所有可用 Resource。"""
        from .agent.mcp_server import MCPServer
        return {"resources": MCPServer().list_resources()}

    @app.post("/mcp/read")
    async def mcp_read_resource(request: Request):
        """MCP: 读取指定 Resource。POST body: {"uri": "instances://list"}"""
        body = await request.json()
        from .agent.mcp_server import MCPServer
        result = MCPServer().read_resource(body.get("uri", ""))
        return {"result": result}

    @app.get("/mcp/prompts")
    async def mcp_list_prompts():
        """MCP: 列出所有 Prompt 模板。"""
        from .agent.mcp_server import MCPServer
        return {"prompts": MCPServer().list_prompts()}

    # ─── Agent Memory API：共享记忆层 ───

    @app.get("/api/memory/conversations")
    async def memory_conversations(n: int = Query(10, ge=1, le=100)):
        """获取最近的 N 轮 Agent 对话记忆。"""
        from .agent.memory import AgentMemory
        mem = AgentMemory()
        conversations = mem.get_recent_conversations(n)
        return {"count": len(conversations), "conversations": conversations}

    @app.post("/api/memory/conversations")
    async def memory_add_conversation(request: Request):
        """新增一轮对话记忆。POST body: {"user_msg": "...", "agent_response": "..."}"""
        body = await request.json()
        from .agent.memory import AgentMemory
        mem = AgentMemory()
        mem.add_conversation(
            user_msg=body.get("user_msg", ""),
            agent_response=body.get("agent_response", ""),
            metadata=body.get("metadata"),
        )
        return {"ok": True}

    @app.get("/api/memory/experiments")
    async def memory_search_experiments(q: str = Query(""), n: int = Query(5, ge=1, le=50)):
        """搜索相似实验记录。q: 查询文本, n: 返回数量。"""
        from .agent.memory import AgentMemory
        mem = AgentMemory()
        if q:
            results = mem.find_similar_experiments(q, n)
        else:
            results = []
        return {"query": q, "count": len(results), "results": results}

    @app.post("/api/memory/experiments")
    async def memory_add_experiment(request: Request):
        """新增实验记录。POST body: {"exp_id": "...", "config": {...}, "results": {...}, "notes": "..."}"""
        body = await request.json()
        from .agent.memory import AgentMemory
        mem = AgentMemory()
        mem.add_experiment(
            exp_id=body.get("exp_id", ""),
            config=body.get("config", {}),
            results=body.get("results", {}),
            notes=body.get("notes", ""),
        )
        _sse_broadcast("experiment_added", {"exp_id": body.get("exp_id", "")})
        return {"ok": True, "total_experiments": mem.get_experiment_count()}

    @app.get("/api/memory/decisions/check")
    async def memory_check_loop(action: str = Query("")):
        """检查拟执行的动作是否有循环风险。"""
        from .agent.memory import AgentMemory
        mem = AgentMemory()
        risk = mem.check_loop_risk(action)
        return {"action": action, "loop_risk": risk}

    # ─── SSE 实时流 ───

    @app.get("/api/stream")
    async def sse_stream():
        q: queue.Queue = queue.Queue()
        _sse_subscribers.append(q)

        async def generate():
            try:
                yield f"event: connected\ndata: {json.dumps({'ok': True})}\n\n"
                while True:
                    try:
                        msg = q.get(timeout=30)
                        yield f"event: {msg['event']}\ndata: {json.dumps(msg['data'], ensure_ascii=False)}\n\n"
                    except queue.Empty:
                        yield f"event: ping\ndata: {json.dumps({'ts': time.time()})}\n\n"
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                pass
            finally:
                if q in _sse_subscribers:
                    _sse_subscribers.remove(q)

        return StreamingResponse(generate(), media_type="text/event-stream")

    # ─── 一键关机 ───

    @app.post("/api/shutdown-all")
    def shutdown_all():
        reg = _get_registry()
        running = reg.get_running()
        results = []
        for inst in running:
            uuid = inst["uuid"]
            try:
                if inst.get("source") == "pro" and _has_token():
                    _get_api().power_off(uuid)
                reg.update_status(uuid, "powering_off")
                results.append({"uuid": uuid, "ok": True})
            except Exception as e:
                results.append({"uuid": uuid, "ok": False, "error": str(e)})
        _sse_broadcast("shutdown_all", {"results": results})
        return {"results": results}

    # ─── 后台守护进程 ───

    _daemon: DaemonV2 | None = None

    @app.on_event("startup")
    async def start_daemon():
        nonlocal _daemon
        # 注入 SSE 广播
        set_broadcaster(_sse_broadcast)
        # 创建并启动守护进程
        api = _get_api() if _has_token() else None
        _daemon = DaemonV2(registry=_get_registry(), db=get_db(), api=api)
        asyncio.create_task(_daemon.run())

    @app.on_event("shutdown")
    async def stop_daemon():
        if _daemon:
            _daemon.stop()

    return app
