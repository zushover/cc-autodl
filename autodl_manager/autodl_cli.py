import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import yaml

from .autodl_api import AutoDLAPI
from .db import get_db
from .instance_registry import InstanceRegistry
from .state_manager import StateManager
from .fleet_manager import FleetManager
from .session_manager import SessionManager
from .cost_tracker import CostTracker


STATUS_ICONS = {
    "running": "\033[32mRUNNING\033[0m",
    "stopped": "\033[90mSTOPPED\033[0m",
    "powering_on": "\033[33mBOOTING\033[0m",
    "powering_off": "\033[33mHALTING\033[0m",
    "released": "\033[31mRELEASED\033[0m",
    "creating": "\033[33mCREATING\033[0m",
}


def _load_config() -> dict:
    # 1. 开发模式：相对于源码目录
    config_path = Path(__file__).parent.parent / "config.yaml"
    # 2. PyInstaller frozen：exe 所在目录
    frozen_path = Path.cwd() / "config.yaml"
    for p in (config_path, frozen_path):
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
    raise FileNotFoundError(f"config.yaml 未找到 (查找: {config_path}, {frozen_path})")


def _icon(s: str) -> str:
    return STATUS_ICONS.get(s, s.upper())


def _get_ssh_cmd(key_path: str, user: str, host: str, port: int) -> list:
    return [
        "ssh", "-i", key_path,
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        f"{user}@{host}", "-p", str(port),
    ]


def _get_scp_cmd(key_path: str, port: int) -> list:
    return [
        "scp", "-i", key_path,
        "-o", "StrictHostKeyChecking=no",
        "-P", str(port),
    ]



def cmd_list(args, fleet: FleetManager):
    if args.sync or not args.local:
        fleet.sync_from_api()
    instances = fleet.list_instances()
    current_uuid = fleet.state.read().get("current_instance_uuid")

    if not instances:
        print("暂无实例")
        return

    for inst in instances:
        uuid = inst.get("instance_uuid", "")[:14]
        name = inst.get("instance_name", "-") or "-"
        gpu = inst.get("gpu_type", "?")
        region = inst.get("region_sign", "?")
        status = inst.get("status", "?")
        price = inst.get("payg_price", 0)
        marker = " *当前" if inst["instance_uuid"] == current_uuid else ""
        tags = ",".join(inst.get("tags", []))
        print(f"  {_icon(status):22s}  {uuid:16s}  {gpu:12s}  {region:8s}  ¥{price}/h  {name}{marker}")
        if tags:
            print(f"  {'':22s}  {'':16s}  标签: {tags}")

    running = sum(1 for i in instances if i.get("status") == "running")
    stopped = sum(1 for i in instances if i.get("status") == "stopped")
    print(f"\n{running} 运行中, {stopped} 已停止, {len(instances)} 总计")


def cmd_use(args, fleet: FleetManager):
    inst = fleet.switch_to(args.identifier)
    print(f"已切换到 {inst['instance_name'] or inst['instance_uuid'][:14]}")
    print(f"状态: {inst.get('status')}  GPU: {inst.get('gpu_type')}  区域: {inst.get('region_sign')}")
    if inst.get("ssh_command"):
        print(f"SSH: {inst['ssh_command']}")
    print("'ssh autodl' 已更新")


def cmd_status(args, fleet: FleetManager):
    current = fleet.get_current()
    if not current:
        print("未设置当前实例，请先 autodl use <id>")
        return

    uuid = current["instance_uuid"][:14]
    try:
        detail = fleet.api.get_instance_detail(current["instance_uuid"])
        usage = detail.get("usage_info", {})
        status_val = detail.get("status", current.get("status", "?"))
        gpu_util = usage.get("gpu_util", "?")
        mem_used = usage.get("mem_used", "?")
        mem_total = usage.get("mem_total", "?")
    except Exception:
        status_val = current.get("status", "?")
        gpu_util = "?"
        mem_used = "?"
        mem_total = "?"

    print(f"  {current.get('instance_name') or uuid}  [{uuid}]")
    print(f"  状态: {_icon(status_val)}")
    print(f"  GPU:  {current.get('gpu_type')}  |  {gpu_util}%  |  {mem_used}/{mem_total}GB")
    print(f"  SSH:  {current.get('ssh_command')}")
    if current.get("jupyter_url"):
        print(f"  Jupyter: {current.get('jupyter_url')}  token={current.get('jupyter_token')}")
    print(f"  到期: {current.get('expired_at')}")
    print(f"  单价: ¥{current.get('payg_price', 0)}/h")

    session = fleet.state.read().get("session")
    if session and session.get("instance_uuid") == current["instance_uuid"]:
        print(f"  任务: {session.get('task', '-')}")
        print(f"  进度: {session.get('task_progress', '-')}")


def cmd_start(args, fleet: FleetManager):
    uuid = args.identifier
    if not uuid:
        current = fleet.get_current()
        if not current:
            print("请指定实例: autodl start <uuid/name/tag>")
            return
        uuid = current["instance_uuid"]
    fleet.start_instance(uuid)
    print(f"启动指令已发送: {uuid[:14]}")


def cmd_stop(args, fleet: FleetManager):
    uuid = args.identifier
    if not uuid:
        current = fleet.get_current()
        if not current:
            print("请指定实例: autodl stop <uuid/name/tag>")
            return
        uuid = current["instance_uuid"]
    fleet.stop_instance(uuid, force=args.force)
    print(f"关机指令已发送: {uuid[:14]}")


def cmd_release(args, fleet: FleetManager):
    if not args.yes:
        ans = input(f"确认释放 {args.identifier}？数据盘内容将丢失 [y/N]: ")
        if ans.lower() != "y":
            return
    fleet.release_instance(args.identifier)
    print(f"释放指令已发送: {args.identifier[:14]}")


def cmd_sync(args, fleet: FleetManager):
    instances = fleet.sync_from_api()
    print(f"已同步 {len(instances)} 个实例")



def cmd_balance(args, fleet: FleetManager):
    bal = fleet.api.get_balance()
    print(f"  余额:  ¥{bal['assets_yuan']:.2f}")
    if bal.get("voucher_balance"):
        print(f"  代金券: ¥{bal['voucher_balance']:.2f}")
    print(f"  累计消费: ¥{bal['accumulate_yuan']:.2f}")


def cmd_cost(args, fleet: FleetManager, cost: CostTracker):
    daily = cost.get_daily_total()
    weekly = cost.get_weekly_total()
    runway = cost.predict_runway()
    print(f"  今日消费: ¥{daily:.2f}")
    print(f"  本周消费: ¥{weekly:.2f}")
    print(f"  余额: ¥{runway['balance_yuan']:.2f}")
    print(f"  日均消费: ¥{runway['daily_rate_yuan']:.2f}")
    if runway.get("runway_days") is not None:
        print(f"  预估可跑: {runway['runway_days']} 天")



def cmd_run(args, config: dict, fleet: FleetManager, session_mgr: SessionManager, cost_tracker: CostTracker):
    current = fleet.get_current()
    if not current or current.get("status") != "running":
        print("当前无可运行实例")
        return

    script = args.script
    script_path = Path(script)
    if not script_path.exists():
        print(f"文件不存在: {script}")
        return

    host = current.get("ssh_host", "")
    port = current.get("ssh_port", 22)
    key = config.get("ssh", {}).get("key_path", "")
    user = config.get("ssh", {}).get("user", "root")

    remote_dir = f"/root/autodl-tmp/{script_path.stem}"
    print(f"[1/4] 上传 {script_path.name} ...")
    scp_base = _get_scp_cmd(key, port)
    subprocess.run(scp_base + [str(script_path), f"{user}@{host}:{remote_dir}/"], check=False)

    print("[2/4] 安装依赖 ...")
    ssh_base = _get_ssh_cmd(key, user, host, port)
    subprocess.run(ssh_base + [
        f"cd {remote_dir} && pip install -r requirements.txt -q 2>/dev/null; "
        "export HF_ENDPOINT=https://hf-mirror.com; echo READY"
    ], check=False)

    print("[3/4] tmux 启动训练 ...")
    tmux_cmd = (
        f"tmux new-session -d -s autodl -c {remote_dir}; "
        f"tmux send-keys -t autodl 'export HF_ENDPOINT=https://hf-mirror.com && python {script_path.name} 2>&1 | tee run.log' Enter"
    )
    subprocess.run(ssh_base + [tmux_cmd], check=False)

    session_mgr.start_session(current["instance_uuid"], task=script)
    price = current.get("payg_price", 0) or 0
    cost_tracker.record_snapshot(current["instance_uuid"], current.get("instance_name", ""), price, event="session_start")

    print(f"[4/4] 训练已启动，监控: autodl progress")
    print(f"  tmux: ssh autodl → tmux attach -t autodl")


def cmd_prep(args, config: dict, fleet: FleetManager):
    current = fleet.get_current()
    if not current or current.get("status") != "running":
        print("当前无可运行实例")
        return

    host = current.get("ssh_host", "")
    port = current.get("ssh_port", 22)
    key = config.get("ssh", {}).get("key_path", "")
    user = config.get("ssh", {}).get("user", "root")
    ssh_base = _get_ssh_cmd(key, user, host, port)

    checks = [
        ("磁盘空间", "df -h /root/autodl-tmp | tail -1"),
        ("GPU 状态", "nvidia-smi --query-gpu=name,memory.free --format=csv,noheader"),
        ("Python 版本", "python --version 2>&1"),
        ("PyTorch", "python -c 'import torch; print(torch.__version__)' 2>&1"),
        ("CUDA 可用", "python -c 'import torch; print(torch.cuda.is_available())' 2>&1"),
    ]

    print(f"{'检查项':12s}  结果")
    print("-" * 50)
    for name, cmd in checks:
        result = subprocess.run(ssh_base + [cmd], capture_output=True, text=True, check=False)
        output = result.stdout.strip() or result.stderr.strip()
        print(f"  {name:10s}  {output}")
    print(f"  单价: ¥{current.get('payg_price', 0)}/h")


def cmd_progress(args, config: dict, fleet: FleetManager, session_mgr: SessionManager):
    current = fleet.get_current()
    if not current or current.get("status") != "running":
        print("当前无可运行实例")
        return

    host = current.get("ssh_host", "")
    port = current.get("ssh_port", 22)
    key = config.get("ssh", {}).get("key_path", "")
    user = config.get("ssh", {}).get("user", "root")
    ssh_base = _get_ssh_cmd(key, user, host, port)

    result = subprocess.run(
        ssh_base + ["cat /root/autodl-tmp/*/run.log 2>/dev/null | tail -20 || echo ''"],
        capture_output=True, text=True, check=False,
    )
    snippet = result.stdout
    if not snippet.strip():
        print("未找到训练日志")
        return

    progress = session_mgr.parse_training_log(snippet)
    if progress:
        for k, v in progress.items():
            print(f"  {k}: {v}")
    else:
        print("未检测到训练指标")

    anomalies = session_mgr.check_anomaly(snippet)
    if anomalies:
        print("\n异常检测:")
        for a in anomalies:
            print(f"  [{a['severity'].upper()}] {a['message']}")
    else:
        print("  无异常")


def cmd_snapshot(args, fleet: FleetManager):
    current = fleet.get_current()
    uuid = args.identifier or (current["instance_uuid"] if current else None)
    if not uuid:
        print("请指定实例")
        return
    image_uuid = fleet.api.save_image(uuid, args.name)
    print(f"镜像保存中: {args.name}")
    print(f"image_uuid: {image_uuid}")


def cmd_snapshots(args, fleet: FleetManager):
    images = fleet.api.list_private_images()
    if not images:
        print("暂无私有镜像")
        return
    for img in images:
        print(f"  {img.get('image_uuid','?')[:20]}  {img.get('image_name','?')}  {img.get('created_at','?')}")


def cmd_exec(args, config: dict, fleet: FleetManager):
    current = fleet.get_current()
    if not current or current.get("status") != "running":
        print("当前无可运行实例")
        return

    host = current.get("ssh_host", "")
    port = current.get("ssh_port", 22)
    key = config.get("ssh", {}).get("key_path", "")
    user = config.get("ssh", {}).get("user", "root")
    ssh_base = _get_ssh_cmd(key, user, host, port)

    result = subprocess.run(ssh_base + [args.command], capture_output=True, text=True, check=False)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)

def cmd_register(args, config: dict):
    """注册新实例（Web 控制台 / 自定义 SSH / Pro API）"""
    reg = InstanceRegistry(get_db())

    if args.source == "pro":
        if not args.uuid:
            print("Pro 实例 UUID 必填")
            return
        inst = reg.register_pro(args.uuid)
        print(f"已注册 Pro 实例: {inst['uuid']}")
        return

    ssh_host = args.host or ""
    if not ssh_host:
        print("SSH 主机地址必填 (--host)")
        return

    ssh_key = args.ssh_key or config.get("ssh", {}).get("key_path", "")
    tags = [t.strip() for t in args.tags.split(",")] if args.tags else []

    if args.source == "web":
        inst = reg.register_web(
            ssh_host=ssh_host, ssh_port=args.port, ssh_user=args.user,
            ssh_key_path=ssh_key, alias=args.alias,
            gpu_type=args.gpu or "", region=args.region or "",
            price_per_hour=args.price or 0.0, tags=tags,
        )
    else:
        inst = reg.register_ssh(
            host=ssh_host, port=args.port, username=args.user,
            key_filename=ssh_key, alias=args.alias,
            gpu_type=args.gpu or "", tags=tags,
        )

    print(f"已注册 {args.source} 实例: {inst['uuid']}")
    print(f"  别名: {inst.get('alias', '')}  GPU: {inst.get('gpu_type', '?')}")
    print(f"  SSH: {inst.get('ssh_user','root')}@{inst.get('ssh_host','')}:{inst.get('ssh_port',22)}")

    if args.probe:
        print("正在探测...")
        result = reg.probe_ssh(inst["uuid"])
        if result.get("reachable"):
            gpu = result.get("gpu", {})
            print(f"  ✅ 可达 · GPU: {gpu.get('gpu_name','?')} · Python: {result.get('python','?')}")
        else:
            print(f"  ❌ 不可达: {result.get('error','?')}")


def cmd_probe(args, config: dict):
    """SSH 探测实例"""
    reg = InstanceRegistry(get_db())
    uuid = args.identifier
    if not uuid:
        current = reg.get_current()
        if not current:
            print("请指定实例: autodl probe <uuid>")
            return
        uuid = current["uuid"]

    print(f"正在探测 {uuid[:14]}...")
    result = reg.probe_ssh(uuid)
    if result.get("reachable"):
        gpu = result.get("gpu", {})
        print(f"✅ 可达")
        print(f"   GPU: {gpu.get('gpu_name', '?')} ({gpu.get('mem_total_mb',0)}MB)")
        print(f"   主机: {result.get('hostname', '?')}")
        print(f"   Python: {result.get('python', '?')}")
        print(f"   磁盘: {result.get('disk', '?')}")
    else:
        print(f"❌ 不可达: {result.get('error', '?')}")


def cmd_stats(args):
    """显示统计信息"""
    reg = InstanceRegistry(get_db())
    s = reg.stats()
    print(f"总实例: {s['total']}  |  运行中: {s['running']}  |  已停止: {s['stopped']}")
    print(f"来源: Web={s['by_source']['web']}  Pro={s['by_source']['pro']}  SSH={s['by_source']['ssh']}")

    db = get_db()
    current = reg.get_current()
    if current:
        latest = db.get_latest_gpu(current["uuid"])
        print(f"\n当前实例: {current.get('alias') or current['uuid'][:14]}")
        if latest:
            print(f"  GPU: {latest.get('util_percent','?')}%  |  显存: {latest.get('mem_used_gb','?')}/{latest.get('mem_total_gb','?')}GB  |  温度: {latest.get('temp_c','?')}°C")


def cmd_list_all(args, fleet: FleetManager):
    """列出所有实例（Pro API + 本地注册）"""
    if args.sync:
        fleet.sync_from_api()
    reg = InstanceRegistry(get_db())
    instances = reg.list_all()
    current = reg.get_current()
    current_uuid = current["uuid"] if current else None

    if not instances:
        print("暂无实例。使用 autodl register --source web --host <host> 注册")
        return

    for inst in instances:
        uuid = inst.get("uuid", "")[:14]
        name = inst.get("alias", "-") or "-"
        gpu = inst.get("gpu_type", "?")
        region = inst.get("region", "?")
        status = inst.get("status", "?")
        source = inst.get("source", "?")
        price = inst.get("price_per_hour", 0) or 0
        marker = " ★" if inst["uuid"] == current_uuid else ""
        tags_str = inst.get("tags", "[]")

        status_icon = {"running": "\033[32m●\033[0m", "stopped": "\033[90m○\033[0m", "reachable": "\033[32m●\033[0m"}
        icon = status_icon.get(status, "\033[90m○\033[0m") if status else "\033[90m○\033[0m"

        print(f"  {icon} {source:5s}  {uuid:16s}  {gpu:12s}  {region:8s}  ¥{price}/h  {name}{marker}")
        if tags_str and tags_str != "[]":
            try:
                tags = json.loads(tags_str)
                print(f"  {'':7s}  {'':16s}  标签: {','.join(tags)}")
            except Exception:
                pass

    s = reg.stats()
    print(f"\n{s['running']} 运行中, {s['stopped']} 已停止, {s['total']} 总计")



def main():
    parser = argparse.ArgumentParser(prog="autodl", description="AutoDL GPU 云管理工具")
    sub = parser.add_subparsers(dest="command")

    p_list = sub.add_parser("list", help="列出所有实例")
    p_list.add_argument("--sync", action="store_true", help="强制从 API 同步")
    p_list.add_argument("--local", action="store_true", help="仅本地缓存")

    p_use = sub.add_parser("use", help="切换当前实例")
    p_use.add_argument("identifier", help="实例 uuid / name / tag")

    sub.add_parser("status", help="当前实例状态")

    p_start = sub.add_parser("start", help="启动实例")
    p_start.add_argument("identifier", nargs="?", help="实例 uuid / name / tag")

    p_stop = sub.add_parser("stop", help="停止实例")
    p_stop.add_argument("identifier", nargs="?", help="实例 uuid / name / tag")
    p_stop.add_argument("--force", action="store_true", help="强制关机")

    p_release = sub.add_parser("release", help="释放实例")
    p_release.add_argument("identifier", help="实例 uuid")
    p_release.add_argument("--yes", action="store_true", help="跳过确认")

    sub.add_parser("sync", help="同步实例列表")

    sub.add_parser("balance", help="查询余额")
    sub.add_parser("cost", help="费用汇总")

    p_run = sub.add_parser("run", help="上传并启动训练脚本")
    p_run.add_argument("script", help="本地 Python 脚本路径")

    sub.add_parser("prep", help="Pre-flight 环境检查")

    sub.add_parser("progress", help="查看训练进度")

    p_snapshot = sub.add_parser("snapshot", help="保存实例为镜像")
    p_snapshot.add_argument("name", help="镜像名称")
    p_snapshot.add_argument("--identifier", help="实例 uuid")

    sub.add_parser("snapshots", help="列出私有镜像")

    p_exec = sub.add_parser("exec", help="在实例上执行命令")
    p_exec.add_argument("command", help="Shell 命令")

    # --- 新命令：三种来源注册 + 探测 ---
    p_register = sub.add_parser("register", help="注册实例（Web/SSH/Pro）")
    p_register.add_argument("--source", default="web", choices=["web", "ssh", "pro"], help="来源类型")
    p_register.add_argument("--host", help="SSH 主机地址")
    p_register.add_argument("--port", type=int, default=22, help="SSH 端口")
    p_register.add_argument("--user", default="root", help="SSH 用户名")
    p_register.add_argument("--ssh-key", help="SSH 私钥路径")
    p_register.add_argument("--alias", default="", help="别名")
    p_register.add_argument("--gpu", help="GPU 型号")
    p_register.add_argument("--region", default="", help="区域")
    p_register.add_argument("--price", type=float, help="单价")
    p_register.add_argument("--tags", default="", help="标签（逗号分隔）")
    p_register.add_argument("--uuid", help="Pro 实例 UUID (source=pro 时使用)")
    p_register.add_argument("--probe", action="store_true", help="注册后立即探测")

    p_probe = sub.add_parser("probe", help="SSH 探测实例")
    p_probe.add_argument("identifier", nargs="?", help="实例 uuid")

    sub.add_parser("stats", help="显示统计信息")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    config = _load_config()
    token = config.get("auto_dl", {}).get("token", "")

    # Token 仅在 Pro API 操作时必须。Web/SSH 注册和基础操作不需要。
    needs_token = args.command in ("sync", "balance", "run", "snapshot", "snapshots")

    if needs_token and (not token or token == "your-token-here"):
        print("请在 config.yaml 中填入 AutoDL Token")
        sys.exit(1)

    api = AutoDLAPI(token)
    state = StateManager()
    ssh_key = config.get("ssh", {}).get("key_path", "")
    ssh_user = config.get("ssh", {}).get("user", "root")
    fleet = FleetManager(api, state, ssh_key, ssh_user)
    session_mgr = SessionManager(state)
    cost_tracker = CostTracker(state)

    fleet_handlers = {
        "list": lambda a: cmd_list_all(a, fleet),
        "use": lambda a: cmd_use(a, fleet),
        "status": lambda a: cmd_status(a, fleet),
        "start": lambda a: cmd_start(a, fleet),
        "stop": lambda a: cmd_stop(a, fleet),
        "release": lambda a: cmd_release(a, fleet),
        "sync": lambda a: cmd_sync(a, fleet),
        "balance": lambda a: cmd_balance(a, fleet),
        "cost": lambda a: cmd_cost(a, fleet, cost_tracker),
        "register": lambda a: cmd_register(a, config),
        "probe": lambda a: cmd_probe(a, config),
        "stats": lambda a: cmd_stats(a),
    }

    pipeline_handlers = {
        "run": lambda a: cmd_run(a, config, fleet, session_mgr, cost_tracker),
        "prep": lambda a: cmd_prep(a, config, fleet),
        "progress": lambda a: cmd_progress(a, config, fleet, session_mgr),
        "snapshot": lambda a: cmd_snapshot(a, fleet),
        "snapshots": lambda a: cmd_snapshots(a, fleet),
        "exec": lambda a: cmd_exec(a, config, fleet),
    }

    handler = fleet_handlers.get(args.command) or pipeline_handlers.get(args.command)
    if handler:
        handler(args)


if __name__ == "__main__":
    main()
