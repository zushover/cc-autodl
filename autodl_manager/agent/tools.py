"""Agent Tools — 把 cc-autodl 的现有能力包装为 LLM 可调用的 LangChain Tool。

每个 Tool 是一个有明确输入输出的函数，LLM 根据用户自然语言请求
自主决定调用哪个 Tool、传什么参数。
"""

import json
from pathlib import Path

import paramiko
import yaml
from langchain_core.tools import tool

from ..db import get_db
from ..instance_registry import InstanceRegistry
from ..gpu_collector import GPUCollector


# ─── 配置加载（复用 api_server 的逻辑）───

def _load_config() -> dict:
    config_path = Path(__file__).parent.parent.parent / "config.yaml"
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


def _get_registry() -> InstanceRegistry:
    return InstanceRegistry(get_db())


# ─── Tool 定义 ───

@tool
def list_gpu_instances() -> str:
    """列出所有 GPU 实例及其状态、GPU 型号。

    不需要参数。返回所有已注册实例的简要信息（uuid, alias, status, gpu_type, price_per_hour）。
    适合用户询问"有哪些实例"、"GPU 状态怎么样"时首先调用。
    """
    reg = _get_registry()
    instances = reg.list_all()
    if not instances:
        return "当前没有注册任何实例。请先通过面板或 API 注册 GPU 实例。"

    return json.dumps([
        {
            "uuid": i["uuid"][:12],
            "alias": i.get("alias", ""),
            "source": i.get("source", "unknown"),
            "status": i.get("status", "unknown"),
            "gpu_type": i.get("gpu_type", ""),
            "ssh_host": i.get("ssh_host", ""),
            "price_per_hour": i.get("price_per_hour", 0),
        }
        for i in instances
    ], ensure_ascii=False, indent=2)


@tool
def check_gpu_utilization(uuid: str) -> str:
    """检查指定实例的实时 GPU 利用率和显存占用。

    Args:
        uuid: 实例 UUID，可以只提供前 12 位。从 list_gpu_instances 的返回结果中获取。

    Returns:
        GPU 利用率百分比、显存占用/总量(GB)、温度、功耗、运行的进程列表。
    """
    reg = _get_registry()
    inst = reg.get(uuid)
    if not inst:
        # 尝试前缀匹配
        all_inst = reg.list_all()
        matches = [i for i in all_inst if i["uuid"].startswith(uuid)]
        if len(matches) == 1:
            inst = matches[0]
        elif len(matches) > 1:
            return f"前缀 {uuid} 匹配到多个实例，请提供更完整的 UUID：{[m['uuid'][:12] for m in matches]}"
        else:
            return f"实例 {uuid} 不存在。请用 list_gpu_instances 查看所有实例。"

    host = inst.get("ssh_host", "")
    if not host:
        return f"实例 {inst.get('alias', uuid[:12])} 未配置 SSH 连接信息，无法采集 GPU 数据。"

    collector = GPUCollector(
        ssh_key_path=inst.get("ssh_key_path", ""),
        ssh_user=inst.get("ssh_user", "root"),
        ssh_password=inst.get("ssh_password", ""),
    )
    result = collector.collect(host, inst.get("ssh_port", 22))
    if not result:
        return (f"无法连接到实例 {inst.get('alias', uuid[:12])} ({host})。"
                f"可能原因：实例已关机、SSH 凭据错误、网络不可达。"
                f"建议用 probe 功能先检测实例状态。")

    return json.dumps({
        "instance_alias": inst.get("alias", ""),
        "gpu_utilization_percent": result["util_percent"],
        "memory_used_gb": result["mem_used_gb"],
        "memory_total_gb": result["mem_total_gb"],
        "memory_utilization_percent": result["mem_util_percent"],
        "temperature_c": result["temp_c"],
        "power_watts": result.get("power_w", 0),
        "running_processes": result.get("processes", []),
    }, ensure_ascii=False, indent=2)


@tool
def shutdown_idle_instance(uuid: str, confirm: bool = False) -> str:
    """关闭指定 GPU 实例（危险操作，需确认）。

    适合用户说"关掉那个空闲的 GPU"时调用。
    会先检查实例当前状态再执行关机。

    Args:
        uuid: 实例 UUID
        confirm: 必须显式设为 True 才会真正执行关机。默认为 False 时仅预览。

    Returns:
        操作结果说明。
    """
    reg = _get_registry()
    inst = reg.get(uuid)
    if not inst:
        # 尝试前缀匹配
        all_inst = reg.list_all()
        matches = [i for i in all_inst if i["uuid"].startswith(uuid)]
        if len(matches) == 1:
            inst = matches[0]
        else:
            return f"实例 {uuid} 不存在。"

    alias = inst.get("alias", uuid[:12])
    status = inst.get("status", "unknown")

    if status not in ("running", "reachable", "no_gpu"):
        return f"实例 {alias} 当前状态为 {status}，无需关机。"

    if not confirm:
        return (f"⚠️ 预览模式：将关闭实例 {alias}（{inst.get('gpu_type', '未知GPU')}，"
                f"IP: {inst.get('ssh_host', '未知')}）。如需执行，请设置 confirm=True。")

    host = inst.get("ssh_host", "")
    port = inst.get("ssh_port", 22)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        kwargs = {
            "hostname": host,
            "port": port,
            "username": inst.get("ssh_user", "root"),
            "timeout": 10,
        }
        if inst.get("ssh_key_path"):
            kwargs["key_filename"] = inst["ssh_key_path"]
        elif inst.get("ssh_password"):
            kwargs["password"] = inst["ssh_password"]
        else:
            return f"❌ 实例 {alias} 没有配置 SSH 凭据，无法远程关机。"

        client.connect(**kwargs)
        client.exec_command("shutdown -h now", timeout=5)
        client.close()
        reg.update_status(uuid, "stopped")
        return f"✅ 实例 {alias} 关机指令已成功发送。GPU: {inst.get('gpu_type', '未知')}，费用: ¥{inst.get('price_per_hour', 0)}/小时。"
    except Exception as e:
        return f"❌ 关机失败: {e}"
    finally:
        try:
            client.close()
        except Exception:
            pass


@tool
def get_balance_and_cost() -> str:
    """查询 AutoDL 账户余额和费用概览。

    不需要参数。返回账户余额、累计消费、今日/本周费用、预估剩余可用天数。
    适合用户询问"还有多少钱"、"余额够不够"时调用。
    """
    if not _has_token():
        return "AutoDL Token 未配置，无法查询余额。请在 config.yaml 中设置 auto_dl.token。"

    from ..autodl_api import AutoDLAPI
    config = _load_config()
    api = AutoDLAPI(config["auto_dl"]["token"])

    try:
        bal = api.get_balance()
    except Exception as e:
        return f"查询余额失败: {e}"

    db = get_db()
    runway = db.predict_runway(bal["assets_yuan"])

    return json.dumps({
        "balance_yuan": round(runway["balance_yuan"], 2),
        "total_spent_yuan": round(bal["accumulate_yuan"], 2),
        "voucher_balance_yuan": bal.get("voucher_balance", 0),
        "daily_avg_cost_yuan": runway["daily_rate_yuan"],
        "today_cost_yuan": runway["today_cost"],
        "week_cost_yuan": runway["week_cost"],
        "estimated_days_remaining": runway["runway_days"],
        "status": (
            "⚠️ 余额不足" if runway["balance_yuan"] < 50
            else "⚠️ 余额偏低" if runway["balance_yuan"] < 100
            else "✅ 余额充足"
        ),
    }, ensure_ascii=False, indent=2)


@tool
def probe_instance_health(uuid: str) -> str:
    """对指定实例执行健康检测：SSH 连接测试 + GPU 状态采集 + 系统信息收集。

    自动判断实例状态（运行中 / 无卡模式 / 已关机），并更新数据库。
    适合用户询问"这个实例能不能用"、"检测一下服务器状态"时调用。

    Args:
        uuid: 实例 UUID

    Returns:
        可达性、GPU 信息、系统信息、Python 版本等。
    """
    reg = _get_registry()
    inst = reg.get(uuid)
    if not inst:
        all_inst = reg.list_all()
        matches = [i for i in all_inst if i["uuid"].startswith(uuid)]
        if len(matches) == 1:
            inst = matches[0]
        else:
            return f"实例 {uuid} 不存在。"

    result = reg.probe_ssh(uuid)

    if result.get("reachable"):
        return json.dumps({
            "reachable": True,
            "status": result.get("status", "reachable"),
            "gpu": result.get("gpu"),
            "processes": result.get("processes", []),
            "hostname": result.get("hostname", ""),
            "python_version": result.get("python", ""),
            "disk": result.get("disk", ""),
            "ram": result.get("ram", ""),
            "os": result.get("os", ""),
        }, ensure_ascii=False, indent=2)
    else:
        return json.dumps({
            "reachable": False,
            "status": result.get("status", "stopped"),
            "error": result.get("error", "SSH 连接失败"),
        }, ensure_ascii=False, indent=2)


@tool
def execute_on_server(uuid: str, command: str) -> str:
    """在指定实例上通过 SSH 远程执行命令，返回 stdout。

    适合用户说"在服务器上运行某个命令"时调用。
    例如：跑 Python 脚本、查看文件、安装包、git clone 等。

    Args:
        uuid: 实例 UUID
        command: 要执行的 bash 命令。多命令用 && 连接。

    Returns:
        命令的 stdout 输出（截取前 3000 字符）。
    """
    reg = _get_registry()
    inst = reg.get(uuid)
    if not inst:
        all_inst = reg.list_all()
        matches = [i for i in all_inst if i["uuid"].startswith(uuid)]
        if len(matches) == 1:
            inst = matches[0]
        else:
            return f"实例 {uuid} 不存在"

    host = inst.get("ssh_host", "")
    if not host:
        return f"实例 {inst.get('alias', uuid[:12])} 未配置 SSH"

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        kwargs = {"hostname": host, "port": inst.get("ssh_port", 22),
                  "username": inst.get("ssh_user", "root"), "timeout": 15}
        if inst.get("ssh_key_path"):
            kwargs["key_filename"] = inst["ssh_key_path"]
        elif inst.get("ssh_password"):
            kwargs["password"] = inst["ssh_password"]
        else:
            return "未配置 SSH 凭据"

        client.connect(**kwargs)
        stdin, stdout, stderr = client.exec_command(command, timeout=30)
        out = stdout.read().decode(errors="replace").strip()
        err = stderr.read().decode(errors="replace").strip()
        code = stdout.channel.recv_exit_status()
        client.close()

        result = out or "(no output)"
        if err and code != 0:
            result += f"\n[stderr]: {err[:500]}"
        return result[:3000]
    except Exception as e:
        return f"执行失败: {e}"
    finally:
        try:
            client.close()
        except Exception:
            pass


@tool
def delegate_to_server(uuid: str, task: str) -> str:
    """把自然语言任务委派给服务器上的 Claude Code 执行。

    前提：服务器已通过 ☀️ 部署了 Claude Code。
    此 Tool 会 SSH 到服务器，调 claude -p 执行任务并返回结果。

    适合用户说"帮我在服务器上写一个训练脚本"、"分析服务器上的日志"等
    需要 AI 推理的任务（不是简单命令）。

    Args:
        uuid: 实例 UUID
        task: 自然语言任务描述，会传给服务器的 Claude Code

    Returns:
        服务器 CC 返回的结果（截取前 3000 字符）。
    """
    return execute_on_server(uuid, f"source ~/.claude/env.sh 2>/dev/null; claude -p {repr(task)}")


# ─── 工具注册表 ───

ALL_TOOLS = [
    list_gpu_instances,
    check_gpu_utilization,
    shutdown_idle_instance,
    get_balance_and_cost,
    probe_instance_health,
    execute_on_server,
    delegate_to_server,
]
