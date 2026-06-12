"""AutoDL CLI — 统一实例管理命令行工具。

v2.1: 统一使用 InstanceRegistry (SQLite) 作为唯一数据源。
       Pro API 实例通过 AutoDLAPI 管理生命周期，
       Web/SSH 实例通过 SSH 管理。
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

from .autodl_api import AutoDLAPI, AutoDLAPIError
from .db import get_db
from .instance_registry import InstanceRegistry
from .log_parser import parse_training_log, check_anomaly

STATUS_ICONS = {
    "running": "\033[32mRUNNING\033[0m",
    "stopped": "\033[90mSTOPPED\033[0m",
    "powering_on": "\033[33mBOOTING\033[0m",
    "powering_off": "\033[33mHALTING\033[0m",
    "released": "\033[31mRELEASED\033[0m",
    "creating": "\033[33mCREATING\033[0m",
    "no_gpu": "\033[33mNO_GPU\033[0m",
    "reachable": "\033[32mREACHABLE\033[0m",
}


def _load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.yaml"
    frozen_path = Path.cwd() / "config.yaml"
    for p in (config_path, frozen_path):
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
    raise FileNotFoundError(f"config.yaml 未找到 (查找: {config_path}, {frozen_path})")


def _icon(s: str) -> str:
    return STATUS_ICONS.get(s, s.upper())


def _get_ssh_cmd(key_path: str, user: str, host: str, port: int, password: str = "") -> list:
    """构建 SSH 命令。优先密钥，其次密码。"""
    cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10"]
    if key_path:
        cmd += ["-i", key_path]
    if password:
        # sshpass 方式（如果可用），否则提示用户手动输入
        cmd += ["-o", "PreferredAuthentications=password"]
    cmd += [f"{user}@{host}", "-p", str(port)]
    return cmd


def _get_scp_cmd(key_path: str, port: int) -> list:
    return [
        "scp", "-i", key_path,
        "-o", "StrictHostKeyChecking=no",
        "-P", str(port),
    ]


def _find_instance(reg: InstanceRegistry, identifier: str) -> dict | None:
    """通过 uuid / alias / tag 查找实例。"""
    # 精确 uuid 匹配
    inst = reg.get(identifier)
    if inst:
        return inst
    # 模糊搜索
    results = reg.search(identifier)
    return results[0] if results else None


def _ssh_exec(inst: dict, command: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """通过 SSH 在实例上执行命令。"""
    host = inst.get("ssh_host", "")
    port = inst.get("ssh_port", 22)
    user = inst.get("ssh_user", "root")
    key = inst.get("ssh_key_path", "") or ""
    password = inst.get("ssh_password", "") or ""

    ssh_base = _get_ssh_cmd(key, user, host, port, password)
    return subprocess.run(ssh_base + [command], capture_output=True, text=True, timeout=timeout)


# ─── 命令实现 ───

def cmd_list(args, reg: InstanceRegistry):
    """列出所有已注册实例。"""
    if args.sync:
        _do_sync(reg)
    instances = reg.list_all()
    current = reg.get_current()
    current_uuid = current["uuid"] if current else None

    if not instances:
        print("暂无实例。使用 autodl register --source web --host <host> 注册")
        return

    status_icon_map = {
        "running": "\033[32m●\033[0m", "stopped": "\033[90m○\033[0m",
        "reachable": "\033[32m●\033[0m", "no_gpu": "\033[33m◐\033[0m",
    }

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

        icon = status_icon_map.get(status, "\033[90m○\033[0m")
        print(f"  {icon} {source:5s}  {uuid:16s}  {gpu:12s}  {region:8s}  ¥{price}/h  {name}{marker}")
        if tags_str and tags_str != "[]":
            try:
                tags = json.loads(tags_str)
                print(f"  {'':7s}  {'':16s}  标签: {','.join(tags)}")
            except Exception:
                pass

    s = reg.stats()
    print(f"\n{s['running']} 运行中, {s['stopped']} 已停止, {s['total']} 总计")
    print(f"来源: Web={s['by_source']['web']}  Pro={s['by_source']['pro']}  SSH={s['by_source']['ssh']}")


def cmd_use(args, reg: InstanceRegistry):
    """切换当前实例。"""
    inst = _find_instance(reg, args.identifier)
    if not inst:
        print(f"未找到实例: {args.identifier}")
        return
    reg.set_current(inst["uuid"])
    uuid = inst["uuid"][:14]
    print(f"已切换到 {inst.get('alias') or uuid}")
    print(f"状态: {inst.get('status')}  GPU: {inst.get('gpu_type', '?')}  区域: {inst.get('region', '?')}")
    ssh = inst.get("ssh_host", "")
    if ssh:
        print(f"SSH: {inst.get('ssh_user','root')}@{ssh}:{inst.get('ssh_port',22)}")


def cmd_status(args, reg: InstanceRegistry):
    """显示当前实例状态。"""
    current = reg.get_current()
    if not current:
        print("未设置当前实例，请先 autodl use <id>")
        return

    uuid = current["uuid"][:14]
    print(f"  {current.get('alias') or uuid}  [{uuid}]")
    print(f"  来源: {current.get('source')}  状态: {_icon(current.get('status', '?'))}")
    print(f"  GPU:  {current.get('gpu_type', '?')}  区域: {current.get('region', '?')}")
    print(f"  SSH:  {current.get('ssh_user','root')}@{current.get('ssh_host','')}:{current.get('ssh_port',22)}")
    print(f"  单价: ¥{current.get('price_per_hour', 0)}/h")

    # 尝试获取最新 GPU 快照
    db = get_db()
    latest = db.get_latest_gpu(current["uuid"])
    if latest:
        print(f"  GPU: {latest.get('util_percent','?')}%  |  显存: {latest.get('mem_used_gb','?')}/{latest.get('mem_total_gb','?')}GB  |  温度: {latest.get('temp_c','?')}°C")


def cmd_start(args, reg: InstanceRegistry, api: AutoDLAPI):
    """启动实例。"""
    uuid = args.identifier
    if not uuid:
        current = reg.get_current()
        if not current:
            print("请指定实例: autodl start <uuid/name/tag>")
            return
        uuid = current["uuid"]

    inst = _find_instance(reg, uuid) if uuid else None
    if not inst:
        print(f"未找到实例: {uuid}")
        return

    if inst.get("source") == "pro":
        try:
            api.power_on(inst["uuid"])
            reg.update_status(inst["uuid"], "powering_on")
            print(f"启动指令已发送 (Pro API): {inst['uuid'][:14]}")
        except AutoDLAPIError as e:
            print(f"启动失败: {e}")
    else:
        print(f"Web/SSH 实例请通过 AutoDL 控制台开机。")
        print(f"SSH: {inst.get('ssh_user','root')}@{inst.get('ssh_host','')}:{inst.get('ssh_port',22)}")


def cmd_stop(args, reg: InstanceRegistry, api: AutoDLAPI):
    """停止实例。"""
    uuid = args.identifier
    if not uuid:
        current = reg.get_current()
        if not current:
            print("请指定实例: autodl stop <uuid/name/tag>")
            return
        uuid = current["uuid"]

    inst = _find_instance(reg, uuid) if uuid else None
    if not inst:
        print(f"未找到实例: {uuid}")
        return

    if inst.get("source") == "pro":
        try:
            api.power_off(inst["uuid"])
            reg.update_status(inst["uuid"], "powering_off")
            print(f"关机指令已发送 (Pro API): {inst['uuid'][:14]}")
        except AutoDLAPIError as e:
            print(f"关机失败: {e}")
    else:
        # Web/SSH 实例通过 SSH 关机
        host = inst.get("ssh_host", "")
        if not host:
            print("SSH host 未配置，无法关机")
            return
        try:
            print(f"正在通过 SSH 发送关机指令...")
            _ssh_exec(inst, "shutdown -h now", timeout=10)
            reg.update_status(inst["uuid"], "stopped")
            print(f"关机指令已发送 (SSH): {inst['uuid'][:14]}")
        except Exception as e:
            print(f"SSH 关机失败: {e}")


def cmd_release(args, reg: InstanceRegistry, api: AutoDLAPI):
    """释放实例。"""
    inst = _find_instance(reg, args.identifier)
    if not inst:
        print(f"未找到实例: {args.identifier}")
        return

    if not args.yes:
        ans = input(f"确认释放 {inst.get('alias') or inst['uuid'][:14]}？数据盘内容将丢失 [y/N]: ")
        if ans.lower() != "y":
            return

    if inst.get("source") == "pro":
        try:
            api.release_instance(inst["uuid"])
            reg.unregister(inst["uuid"])
            print(f"释放指令已发送 (Pro API): {inst['uuid'][:14]}")
        except AutoDLAPIError as e:
            print(f"释放失败: {e}")
    else:
        reg.unregister(inst["uuid"])
        print(f"已注销本地注册 (实例需在控制台手动释放): {inst['uuid'][:14]}")


def _do_sync(reg: InstanceRegistry):
    """从 Pro API 同步实例列表。"""
    config = _load_config()
    token = config.get("auto_dl", {}).get("token", "")
    if not token or token == "your-token-here":
        print("请在 config.yaml 中填入 AutoDL Token")
        return 0

    api = AutoDLAPI(token)
    try:
        raw = api.list_instances()
        count = 0
        for inst in raw:
            uid = inst.get("uuid") or inst.get("instance_uuid", "")
            if not uid:
                continue
            try:
                detail = api.get_instance_detail(uid)
            except Exception:
                detail = {}
            price = detail.get("payg_price", 0)
            if price > 100:
                price = round(price / 100.0, 2)
            reg.register_pro(uid, {
                "status": inst.get("status", "unknown"),
                "gpu_type": inst.get("gpu_type", inst.get("gpu_spec_uuid", "")),
                "region_sign": inst.get("region_sign", ""),
                "payg_price": price,
                "proxy_host": detail.get("proxy_host", ""),
                "ssh_port": detail.get("ssh_port", 22),
                "instance_name": inst.get("instance_name", inst.get("name", "")),
            })
            count += 1
        return count
    except AutoDLAPIError as e:
        print(f"同步失败: {e}")
        return -1


def cmd_sync(args, reg: InstanceRegistry):
    """从 Pro API 同步实例。"""
    count = _do_sync(reg)
    if count >= 0:
        print(f"已同步 {count} 个 Pro API 实例")


def cmd_balance(args, config: dict):
    """查询余额。"""
    token = config.get("auto_dl", {}).get("token", "")
    if not token or token == "your-token-here":
        print("请在 config.yaml 中填入 AutoDL Token")
        return
    api = AutoDLAPI(token)
    try:
        bal = api.get_balance()
        print(f"  余额:  ¥{bal['assets_yuan']:.2f}")
        if bal.get("voucher_balance"):
            print(f"  代金券: ¥{bal['voucher_balance']:.2f}")
        print(f"  累计消费: ¥{bal['accumulate_yuan']:.2f}")
    except AutoDLAPIError as e:
        print(f"查询失败: {e}")


def cmd_cost(args, config: dict, reg: InstanceRegistry):
    """费用汇总。"""
    db = get_db()
    # 尝试获取最新余额
    balance_yuan = 0.0
    token = config.get("auto_dl", {}).get("token", "")
    if token and token != "your-token-here":
        try:
            api = AutoDLAPI(token)
            bal = api.get_balance()
            balance_yuan = bal.get("assets_yuan", 0)
        except Exception:
            pass

    runway = db.predict_runway(balance_yuan)
    print(f"  今日消费: ¥{runway.get('today_cost', 0):.2f}")
    print(f"  本周消费: ¥{runway.get('week_cost', 0):.2f}")
    print(f"  余额: ¥{runway['balance_yuan']:.2f}")
    print(f"  日均消费: ¥{runway.get('daily_rate_yuan', 0):.2f}")
    if runway.get("runway_days") is not None:
        print(f"  预估可跑: {runway['runway_days']} 天")


def cmd_register(args, config: dict):
    """注册新实例。"""
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
            ssh_key_path=ssh_key, ssh_password=args.password or "",
            alias=args.alias, gpu_type=args.gpu or "", region=args.region or "",
            price_per_hour=args.price or 0.0, tags=tags,
        )
    else:
        inst = reg.register_ssh(
            host=ssh_host, port=args.port, username=args.user,
            key_filename=ssh_key, password=args.password or "",
            alias=args.alias, gpu_type=args.gpu or "", tags=tags,
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


def cmd_probe(args, reg: InstanceRegistry):
    """SSH 探测实例。"""
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
        print(f"   GPU: {gpu.get('gpu_name', '?')}")
        print(f"   利用率: {gpu.get('util_percent','?')}%  显存: {gpu.get('mem_used_gb','?')}/{gpu.get('mem_total_gb','?')}GB  温度: {gpu.get('temp_c','?')}°C")
        print(f"   主机: {result.get('hostname', '?')}")
        print(f"   Python: {result.get('python', '?')}")
        print(f"   磁盘: {result.get('disk', '?')}")
        print(f"   内存: {result.get('ram', '?')}")
        processes = result.get("processes", [])
        if processes:
            print(f"   GPU 进程:")
            for p in processes:
                print(f"     PID {p.get('pid')}  {p.get('name','?')}  {p.get('gpu_mem_mb','?')}MB")
    else:
        print(f"❌ 不可达: {result.get('error', '?')}")


def cmd_stats(args, reg: InstanceRegistry):
    """显示统计信息。"""
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


def cmd_run(args, config: dict, reg: InstanceRegistry):
    """上传脚本并在实例上启动训练。"""
    current = reg.get_current()
    if not current or current.get("status") not in ("running", "reachable", "no_gpu"):
        print("当前无可运行实例，请先 autodl use <id> 或确认实例状态")
        return

    script = args.script
    script_path = Path(script)
    if not script_path.exists():
        print(f"文件不存在: {script}")
        return

    host = current.get("ssh_host", "")
    port = current.get("ssh_port", 22)
    key = current.get("ssh_key_path", "") or config.get("ssh", {}).get("key_path", "")
    user = current.get("ssh_user", "root")

    remote_dir = f"/root/autodl-tmp/{script_path.stem}"
    print(f"[1/4] 上传 {script_path.name} ...")
    scp_base = _get_scp_cmd(key, port)
    subprocess.run(scp_base + [str(script_path), f"{user}@{host}:{remote_dir}/"], check=False)

    print("[2/4] 安装依赖 ...")
    ssh_base = _get_ssh_cmd(key, user, host, port)
    subprocess.run(ssh_base + [
        f"cd {remote_dir} && pip install -r requirements.txt -q 2>/dev/null; "
        "export HF_ENDPOINT=https://hf-mirror.com; echo READ¥"
    ], check=False)

    print("[3/4] tmux 启动训练 ...")
    tmux_cmd = (
        f"tmux new-session -d -s autodl -c {remote_dir}; "
        f"tmux send-keys -t autodl 'export HF_ENDPOINT=https://hf-mirror.com && python {script_path.name} 2>&1 | tee run.log' Enter"
    )
    subprocess.run(ssh_base + [tmux_cmd], check=False)

    print(f"[4/4] 训练已启动")
    print(f"  tmux: ssh → tmux attach -t autodl")
    print(f"  监控: autodl progress")


def cmd_prep(args, config: dict, reg: InstanceRegistry):
    """环境检查。"""
    current = reg.get_current()
    if not current or current.get("status") not in ("running", "reachable", "no_gpu"):
        print("当前无可运行实例")
        return

    host = current.get("ssh_host", "")
    port = current.get("ssh_port", 22)
    key = current.get("ssh_key_path", "") or config.get("ssh", {}).get("key_path", "")
    user = current.get("ssh_user", "root")
    ssh_base = _get_ssh_cmd(key, user, host, port)

    checks = [
        ("磁盘空间", "df -h /root/autodl-tmp | tail -1"),
        ("GPU 状态", "nvidia-smi --query-gpu=name,memory.free --format=csv,noheader 2>/dev/null || echo '无GPU'"),
        ("Python 版本", "python --version 2>&1 || python3 --version 2>&1"),
        ("PyTorch", "python -c 'import torch; print(torch.__version__)' 2>&1"),
        ("CUDA 可用", "python -c 'import torch; print(torch.cuda.is_available())' 2>&1"),
    ]

    print(f"{'检查项':12s}  结果")
    print("-" * 50)
    for name, cmd in checks:
        result = subprocess.run(ssh_base + [cmd], capture_output=True, text=True, timeout=15)
        output = result.stdout.strip() or result.stderr.strip() or "N/A"
        print(f"  {name:10s}  {output}")
    print(f"  单价: ¥{current.get('price_per_hour', 0)}/h")


def cmd_progress(args, config: dict, reg: InstanceRegistry):
    """查看训练进度。"""
    current = reg.get_current()
    if not current or current.get("status") not in ("running", "reachable", "no_gpu"):
        print("当前无可运行实例")
        return

    host = current.get("ssh_host", "")
    port = current.get("ssh_port", 22)
    key = current.get("ssh_key_path", "") or config.get("ssh", {}).get("key_path", "")
    user = current.get("ssh_user", "root")
    ssh_base = _get_ssh_cmd(key, user, host, port)

    result = subprocess.run(
        ssh_base + ["cat /root/autodl-tmp/*/run.log 2>/dev/null | tail -20 || echo ''"],
        capture_output=True, text=True, timeout=15,
    )
    snippet = result.stdout
    if not snippet.strip():
        print("未找到训练日志")
        return

    progress = parse_training_log(snippet)
    if progress:
        for k, v in progress.items():
            print(f"  {k}: {v}")
    else:
        print("未检测到训练指标")

    anomalies = check_anomaly(snippet)
    if anomalies:
        print("\n异常检测:")
        for a in anomalies:
            print(f"  [{a['severity'].upper()}] {a['message']}")
    else:
        print("  无异常")


def cmd_snapshot(args, config: dict, reg: InstanceRegistry):
    """保存实例为镜像（仅 Pro API）。"""
    token = config.get("auto_dl", {}).get("token", "")
    if not token or token == "your-token-here":
        print("Pro API 需要配置 Token")
        return
    api = AutoDLAPI(token)

    current = reg.get_current()
    uuid = args.identifier or (current["uuid"] if current else None)
    if not uuid:
        print("请指定实例")
        return

    inst = reg.get(uuid) if uuid else None
    if inst and inst.get("source") != "pro":
        print("仅 Pro API 实例支持保存镜像。Web/SSH 实例请在控制台操作。")
        return

    try:
        image_uuid = api.save_image(uuid, args.name)
        print(f"镜像保存中: {args.name}")
        print(f"image_uuid: {image_uuid}")
    except AutoDLAPIError as e:
        print(f"保存镜像失败: {e}")


def cmd_snapshots(args, config: dict):
    """列出私有镜像。"""
    token = config.get("auto_dl", {}).get("token", "")
    if not token or token == "your-token-here":
        print("Pro API 需要配置 Token")
        return
    api = AutoDLAPI(token)
    try:
        images = api.list_private_images()
        if not images:
            print("暂无私有镜像")
            return
        for img in images:
            print(f"  {img.get('image_uuid','?')[:20]}  {img.get('image_name','?')}  {img.get('created_at','?')}")
    except AutoDLAPIError as e:
        print(f"查询失败: {e}")


def cmd_exec(args, config: dict, reg: InstanceRegistry):
    """在实例上执行命令。"""
    current = reg.get_current()
    if not current or current.get("status") not in ("running", "reachable", "no_gpu"):
        print("当前无可运行实例")
        return

    try:
        result = _ssh_exec(current, args.command)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
    except Exception as e:
        print(f"执行失败: {e}")


# ─── 主入口 ───

def main():
    # 修复 Windows GBK 终端无法输出 ¥ 等 Unicode 字符的问题
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    parser = argparse.ArgumentParser(prog="autodl", description="AutoDL GPU 云管理工具")
    sub = parser.add_subparsers(dest="command")

    # list
    p_list = sub.add_parser("list", help="列出所有实例")
    p_list.add_argument("--sync", action="store_true", help="强制从 Pro API 同步")

    # use
    p_use = sub.add_parser("use", help="切换当前实例")
    p_use.add_argument("identifier", help="实例 uuid / alias / tag")

    # status
    sub.add_parser("status", help="当前实例状态")

    # start / stop
    p_start = sub.add_parser("start", help="启动实例")
    p_start.add_argument("identifier", nargs="?", help="实例 uuid / alias / tag")
    p_stop = sub.add_parser("stop", help="停止实例")
    p_stop.add_argument("identifier", nargs="?", help="实例 uuid / alias / tag")
    p_stop.add_argument("--force", action="store_true", help="强制关机")

    # release
    p_release = sub.add_parser("release", help="释放实例")
    p_release.add_argument("identifier", help="实例 uuid / alias")
    p_release.add_argument("--yes", action="store_true", help="跳过确认")

    # sync / balance / cost
    sub.add_parser("sync", help="从 Pro API 同步实例列表")
    sub.add_parser("balance", help="查询余额")
    sub.add_parser("cost", help="费用汇总")

    # run / prep / progress
    p_run = sub.add_parser("run", help="上传并启动训练脚本")
    p_run.add_argument("script", help="本地 Python 脚本路径")
    sub.add_parser("prep", help="Pre-flight 环境检查")
    sub.add_parser("progress", help="查看训练进度")

    # snapshot / snapshots
    p_snapshot = sub.add_parser("snapshot", help="保存实例为镜像 (Pro API)")
    p_snapshot.add_argument("name", help="镜像名称")
    p_snapshot.add_argument("--identifier", help="实例 uuid")
    sub.add_parser("snapshots", help="列出私有镜像")

    # exec
    p_exec = sub.add_parser("exec", help="在实例上执行命令")
    p_exec.add_argument("command", help="Shell 命令")

    # register
    p_register = sub.add_parser("register", help="注册实例（Web/SSH/Pro）")
    p_register.add_argument("--source", default="web", choices=["web", "ssh", "pro"], help="来源类型")
    p_register.add_argument("--host", help="SSH 主机地址")
    p_register.add_argument("--port", type=int, default=22, help="SSH 端口")
    p_register.add_argument("--user", default="root", help="SSH 用户名")
    p_register.add_argument("--password", default="", help="SSH 密码")
    p_register.add_argument("--ssh-key", help="SSH 私钥路径")
    p_register.add_argument("--alias", default="", help="别名")
    p_register.add_argument("--gpu", help="GPU 型号")
    p_register.add_argument("--region", default="", help="区域")
    p_register.add_argument("--price", type=float, help="单价")
    p_register.add_argument("--tags", default="", help="标签（逗号分隔）")
    p_register.add_argument("--uuid", help="Pro 实例 UUID (source=pro)")
    p_register.add_argument("--probe", action="store_true", help="注册后立即探测")

    # probe
    p_probe = sub.add_parser("probe", help="SSH 探测实例")
    p_probe.add_argument("identifier", nargs="?", help="实例 uuid / alias")

    # stats
    sub.add_parser("stats", help="显示统计信息")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    config = _load_config()
    reg = InstanceRegistry(get_db())

    # 需要 Pro API Token 的命令
    needs_token = args.command in ("sync", "balance", "snapshot", "snapshots")

    if needs_token:
        token = config.get("auto_dl", {}).get("token", "")
        if not token or token == "your-token-here":
            print("请在 config.yaml 中填入 AutoDL Token")
            sys.exit(1)

    # 按需创建 API 客户端
    def _get_api():
        token = config.get("auto_dl", {}).get("token", "")
        return AutoDLAPI(token)

    # 路由到处理函数
    if args.command == "list":
        cmd_list(args, reg)
    elif args.command == "use":
        cmd_use(args, reg)
    elif args.command == "status":
        cmd_status(args, reg)
    elif args.command == "start":
        cmd_start(args, reg, _get_api())
    elif args.command == "stop":
        cmd_stop(args, reg, _get_api())
    elif args.command == "release":
        cmd_release(args, reg, _get_api())
    elif args.command == "sync":
        cmd_sync(args, reg)
    elif args.command == "balance":
        cmd_balance(args, config)
    elif args.command == "cost":
        cmd_cost(args, config, reg)
    elif args.command == "register":
        cmd_register(args, config)
    elif args.command == "probe":
        cmd_probe(args, reg)
    elif args.command == "stats":
        cmd_stats(args, reg)
    elif args.command == "run":
        cmd_run(args, config, reg)
    elif args.command == "prep":
        cmd_prep(args, config, reg)
    elif args.command == "progress":
        cmd_progress(args, config, reg)
    elif args.command == "snapshot":
        cmd_snapshot(args, config, reg)
    elif args.command == "snapshots":
        cmd_snapshots(args, config)
    elif args.command == "exec":
        cmd_exec(args, config, reg)


if __name__ == "__main__":
    main()
