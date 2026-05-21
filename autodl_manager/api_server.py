from pathlib import Path

import yaml
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .autodl_api import AutoDLAPI
from .state_manager import StateManager
from .fleet_manager import FleetManager
from .session_manager import SessionManager
from .cost_tracker import CostTracker


STYLE = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,'Microsoft YaHei',sans-serif;background:#0d1117;color:#c9d1d9;display:flex;min-height:100vh}
.sidebar{width:220px;background:#161b22;border-right:1px solid #30363d;padding:20px 0;flex-shrink:0;display:flex;flex-direction:column}
.sidebar .logo{font-size:1.1em;font-weight:bold;color:#f0f6fc;padding:0 20px 20px;border-bottom:1px solid #30363d;margin-bottom:12px}
.sidebar a{display:block;padding:8px 20px;color:#8b949e;font-size:0.9em;text-decoration:none;border:none;background:none;width:100%;text-align:left;cursor:pointer}
.sidebar a:hover,.sidebar a.active{color:#f0f6fc;background:#1c2129}
.sidebar .nav-section{font-size:0.75em;color:#484f58;padding:16px 20px 6px;text-transform:uppercase;letter-spacing:0.5px}
.sidebar .token-warn{margin:auto 20px 20px;padding:10px;border-radius:6px;background:#3d1f1f;border:1px solid #f8514933;font-size:0.8em;color:#f85149}
.main{flex:1;padding:24px;overflow-y:auto}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;margin-bottom:16px}
.card-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
.card-header h2{font-size:1.05em;color:#f0f6fc}
.metrics{display:flex;gap:12px;flex-wrap:wrap}
.metric{flex:1;min-width:120px;text-align:center;padding:14px 10px;background:#0d1117;border-radius:6px}
.metric .value{font-size:1.8em;font-weight:bold;color:#58a6ff}
.metric .label{font-size:0.8em;color:#8b949e;margin-top:4px}
.badge{display:inline-block;padding:2px 10px;border-radius:12px;font-size:0.75em;font-weight:bold}
.badge-running{background:#238636;color:#fff}
.badge-stopped{background:#484f58;color:#8b949e}
.badge-warning{background:#9e6a03;color:#fff}
.badge-critical{background:#da3633;color:#fff}
.btn{display:inline-block;padding:6px 14px;border-radius:6px;font-size:0.85em;font-weight:500;cursor:pointer;border:1px solid #30363d;background:#21262d;color:#c9d1d9;text-decoration:none;font-family:inherit}
.btn:hover{background:#30363d}
.btn-primary{background:#238636;border-color:#238636;color:#fff}
.btn-primary:hover{background:#2ea043}
.btn-danger{background:#da3633;border-color:#da3633;color:#fff}
.btn-danger:hover{background:#f85149}
.btn-sm{padding:3px 10px;font-size:0.75em}
.btn-group{display:flex;gap:8px;flex-wrap:wrap}
table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #21262d;font-size:0.85em}
th{color:#8b949e;font-weight:500}
.alert{padding:8px 12px;border-radius:4px;margin-bottom:4px;font-size:0.85em}
.alert-warning{background:#3d2e00;border-left:3px solid #d29922}
.alert-critical{background:#3d1f1f;border-left:3px solid #f85149}
.alert-info{background:#1c2a3a;border-left:3px solid #58a6ff}
.info-row{display:flex;gap:24px;margin-top:10px;font-size:0.85em;color:#8b949e;flex-wrap:wrap}
.info-row span{white-space:nowrap}
.page{display:none}
.page.active{display:block}
.empty{color:#8b949e;padding:20px;text-align:center}
.toast{padding:10px 18px;border-radius:8px;font-size:0.9em;margin-bottom:12px}
.toast-ok{background:#238636;color:#fff}
.toast-err{background:#da3633;color:#fff}
"""


def _load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


_MANAGERS = None


def _get_managers():
    global _MANAGERS
    if _MANAGERS is None:
        config = _load_config()
        token = config.get("auto_dl", {}).get("token", "")
        api = AutoDLAPI(token)
        state = StateManager()
        ssh_key = config.get("ssh", {}).get("key_path", "")
        ssh_user = config.get("ssh", {}).get("user", "root")
        fleet = FleetManager(api, state, ssh_key, ssh_user)
        session_mgr = SessionManager(state)
        cost = CostTracker(state)
        _MANAGERS = (api, state, fleet, session_mgr, cost)
    return _MANAGERS


def _has_token() -> bool:
    config = _load_config()
    t = config.get("auto_dl", {}).get("token", "")
    return bool(t and t != "your-token-here")


def _badge(status):
    m = {"running": "running", "stopped": "stopped", "powering_on": "warning", "powering_off": "warning", "released": "critical"}
    cls = m.get(status, "stopped")
    return f'<span class="badge badge-{cls}">{status.upper()}</span>'


def render_page(active_tab: str, msg: str = "", msg_ok: bool = True) -> str:
    api, state, fleet, session_mgr, cost = _get_managers()
    has_token = _has_token()
    token_warn = "" if has_token else '<div class="token-warn">Token 未配置<br>当前为演示模式</div>'

    tabs = [
        ("dashboard", "仪表盘"),
        ("instances", "实例管理"),
        ("cost", "费用"),
    ]
    nav = ""
    for tab_id, tab_name in tabs:
        cls = "active" if tab_id == active_tab else ""
        nav += f'<a href="?page={tab_id}" class="{cls}">{tab_name}</a>'

    toast = ""
    if msg:
        cls = "toast-ok" if msg_ok else "toast-err"
        toast = f'<div class="toast {cls}">{msg}</div>'

    if active_tab == "dashboard":
        body = render_dashboard(state) + render_alerts(state)
    elif active_tab == "instances":
        body = render_instances(state, fleet)
    elif active_tab == "cost":
        body = render_cost(state, cost)
    else:
        body = ""

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AutoDL Manager</title>
<style>{STYLE}</style>
</head>
<body>
<div class="sidebar">
  <div class="logo">AutoDL Manager</div>
  {nav}
  <div class="nav-section">操作</div>
  <form method="post" action="/action/sync?page=instances" style="padding:0 20px;margin-bottom:6px">
    <button class="btn btn-primary btn-sm" style="width:100%">同步 API</button>
  </form>
  {token_warn}
</div>
<div class="main">
  {toast}
  {body}
</div>
</body>
</html>"""


def _live_balance() -> dict:
    if not _has_token():
        return {}
    try:
        api, _, _, _, _ = _get_managers()
        bal = api.get_balance()
        api, state, _, _, _ = _get_managers()
        state.write({"balance": {"assets_yuan": bal["assets_yuan"], "updated_at": bal.get("updated_at", "")}})
        return bal
    except Exception:
        return {}


def render_dashboard(state: StateManager) -> str:
    data = state.read()
    uuid = data.get("current_instance_uuid")
    inst = (data.get("instances") or {}).get(uuid) if uuid else None
    gpu = data.get("gpu") or {}
    session = data.get("session") or {}

    live_bal = _live_balance()
    cached_bal = data.get("balance") or {}
    bal = live_bal if live_bal else cached_bal

    if not inst:
        html = '<div class="card"><div class="empty">未设置当前实例<br><small>请到「实例管理」中选择实例</small></div></div>'
        if bal:
            html += f'<div class="card"><div class="metrics"><div class="metric"><div class="value">¥{bal.get("assets_yuan","?.??")}</div><div class="label">当前余额</div></div></div></div>'
        return html

    html = f"""
    <div class="card">
      <div class="card-header">
        <h2>{inst.get('instance_name') or uuid[:14]} {_badge(inst.get('status','?'))}</h2>
        <form method="post" action="/action/refresh-gpu?page=dashboard">
          <button class="btn btn-sm">刷新 GPU</button>
        </form>
      </div>
      <div class="metrics">
        <div class="metric"><div class="value">{gpu.get('util_percent','?')}%</div><div class="label">GPU 利用率</div></div>
        <div class="metric"><div class="value">{gpu.get('mem_used_gb','?')}/{gpu.get('mem_total_gb','?')}G</div><div class="label">显存</div></div>
        <div class="metric"><div class="value">{gpu.get('temp_c','?')}°C</div><div class="label">温度</div></div>
        <div class="metric"><div class="value">¥{bal.get('assets_yuan','?.??')}</div><div class="label">余额</div></div>
      </div>
      <div class="info-row">
        <span>GPU: {inst.get('gpu_type','?')}</span><span>区域: {inst.get('region_sign','?')}</span><span>单价: ¥{inst.get('payg_price','?')}/h</span>
      </div>
      <div class="info-row">
        <span>SSH: {inst.get('ssh_command','?')}</span>
      </div>
    """
    if session.get("task"):
        html += f'<div class="info-row"><span style="color:#58a6ff;">任务: {session["task"]} | 进度: {session.get("task_progress","-")}</span></div>'
    html += "</div>"
    return html


def render_instances(state: StateManager, fleet) -> str:
    data = state.read()
    instances = list((data.get("instances") or {}).values())
    current_uuid = data.get("current_instance_uuid")

    html = f"""
    <div class="card">
      <div class="card-header">
        <h2>实例列表 ({len(instances)})</h2>
      </div>
    """

    if not instances:
        html += '<div class="empty">暂无实例<br><small>点击左侧「同步 API」从 AutoDL 拉取</small></div></div>'
        return html

    rows = []
    for i in instances:
        i_uuid = i.get("instance_uuid", "")
        short_uuid = i_uuid[:14]
        name = i.get("instance_name") or "-"
        gpu = i.get("gpu_type", "?")
        region = i.get("region_sign", "?")
        status = i.get("status", "?")
        price = i.get("payg_price", 0) or 0
        is_current = i_uuid and i_uuid == current_uuid
        marker = " ★" if is_current else ""

        actions = ""
        if not is_current and i_uuid:
            actions += f'<form method="post" action="/action/use?page=instances" style="display:inline"><input type="hidden" name="id" value="{i_uuid}"><button class="btn btn-sm">切换</button></form> '
        if status == "stopped" and i_uuid:
            actions += f'<form method="post" action="/action/start?page=instances" style="display:inline"><input type="hidden" name="id" value="{i_uuid}"><button class="btn btn-primary btn-sm">开机</button></form> '
        if status == "running" and i_uuid:
            actions += f'<form method="post" action="/action/stop?page=instances" style="display:inline"><input type="hidden" name="id" value="{i_uuid}"><button class="btn btn-danger btn-sm">关机</button></form> '

        rows.append(f"<tr><td>{_badge(status)}</td><td>{short_uuid}</td><td>{name}{marker}</td><td>{gpu}</td><td>{region}</td><td>¥{price}/h</td><td>{actions}</td></tr>")

    html += f"""<table><thead><tr><th>状态</th><th>UUID</th><th>名称</th><th>GPU</th><th>区域</th><th>单价</th><th>操作</th></tr></thead>
    <tbody>{''.join(rows)}</tbody></table></div>"""
    return html


def render_alerts(state: StateManager) -> str:
    alerts = state.read().get("alerts", [])
    active = [a for a in alerts if not a.get("dismissed")]
    html = '<div class="card"><div class="card-header"><h2>告警</h2></div>'
    if not active:
        html += '<div class="empty">无活跃告警</div>'
    else:
        for a in active[-5:]:
            sev = a.get("severity", "info")
            html += f'<div class="alert alert-{sev}">{a.get("message","")}</div>'
    html += "</div>"
    return html


def render_cost(state: StateManager, cost_tracker) -> str:
    daily = cost_tracker.get_daily_total()
    weekly = cost_tracker.get_weekly_total()
    runway = cost_tracker.predict_runway()

    live_bal = _live_balance()
    cached_bal = state.read().get("balance") or {}
    bal = live_bal if live_bal else cached_bal

    return f"""
    <div class="card">
      <div class="card-header"><h2>费用概览</h2></div>
      <div class="metrics">
        <div class="metric"><div class="value">¥{daily:.2f}</div><div class="label">今日消费</div></div>
        <div class="metric"><div class="value">¥{weekly:.2f}</div><div class="label">本周消费</div></div>
        <div class="metric"><div class="value">¥{bal.get('assets_yuan','?.??')}</div><div class="label">余额</div></div>
        <div class="metric"><div class="value">{runway.get('runway_days','?')}</div><div class="label">预估剩余 天</div></div>
      </div>
      <div class="info-row">
        <span>日均消费: ¥{runway.get('daily_rate_yuan',0):.2f}</span>
      </div>
    </div>
    """


def create_app() -> FastAPI:
    app = FastAPI(title="AutoDL Manager")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        page = request.query_params.get("page", "dashboard")
        return render_page(page)


    @app.post("/action/sync", response_class=HTMLResponse)
    async def action_sync(request: Request):
        page = request.query_params.get("page", "instances")
        if not _has_token():
            return render_page(page, "未配置 Token，无法同步 API", False)
        api, state, fleet, _, _ = _get_managers()
        try:
            fleet.sync_from_api()
            bal = api.get_balance()
            state.write({"balance": {"assets_yuan": bal["assets_yuan"], "accumulate_yuan": bal["accumulate_yuan"], "updated_at": ""}})
            instances = list(state.read().get("instances", {}).values())
            return render_page(page, f"同步成功，共 {len(instances)} 个实例，余额 ¥{bal['assets_yuan']:.2f}")
        except Exception as e:
            return render_page(page, f"同步失败: {e}", False)

    @app.post("/action/use", response_class=HTMLResponse)
    async def action_use(request: Request, id: str = Form(...)):
        page = request.query_params.get("page", "instances")
        api, state, fleet, _, _ = _get_managers()
        try:
            fleet.switch_to(id)
            return render_page(page, f"已切换实例 {id[:14]}")
        except Exception as e:
            return render_page(page, str(e), False)

    @app.post("/action/start", response_class=HTMLResponse)
    async def action_start(request: Request, id: str = Form(...)):
        page = request.query_params.get("page", "instances")
        if not _has_token():
            return render_page(page, "未配置 Token", False)
        api, state, fleet, _, _ = _get_managers()
        try:
            fleet.start_instance(id)
            return render_page(page, f"开机指令已发送 {id[:14]}")
        except Exception as e:
            return render_page(page, str(e), False)

    @app.post("/action/stop", response_class=HTMLResponse)
    async def action_stop(request: Request, id: str = Form(...)):
        page = request.query_params.get("page", "instances")
        if not _has_token():
            return render_page(page, "未配置 Token", False)
        api, state, fleet, _, _ = _get_managers()
        try:
            fleet.stop_instance(id)
            return render_page(page, f"关机指令已发送 {id[:14]}")
        except Exception as e:
            return render_page(page, str(e), False)

    @app.post("/action/refresh-gpu", response_class=HTMLResponse)
    async def action_refresh_gpu(request: Request):
        page = request.query_params.get("page", "dashboard")
        if not _has_token():
            return render_page(page, "未配置 Token，无法获取实时数据", False)
        api, state, fleet, _, _ = _get_managers()
        current = fleet.get_current()
        if current and current.get("status") == "running":
            from .gpu_collector import GPUCollector
            config = _load_config()
            g = GPUCollector(config.get("ssh", {}).get("key_path", ""), config.get("ssh", {}).get("user", "root"))
            result = g.collect(current.get("ssh_host", ""), current.get("ssh_port", 22))
            if result:
                state.update_gpu_snapshot(current["instance_uuid"], result)
                return render_page(page, "GPU 数据已刷新")
            return render_page(page, "SSH 连接失败", False)
        return render_page(page, "当前无运行中的实例", False)

    @app.get("/api/full")
    async def api_full():
        _, state, _, _, _ = _get_managers()
        return JSONResponse(state.read())

    return app


def main():
    import uvicorn
    if not _has_token():
        print("[WARN] config.yaml 未配置 Token")
    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=8899, log_level="warning")


if __name__ == "__main__":
    main()
