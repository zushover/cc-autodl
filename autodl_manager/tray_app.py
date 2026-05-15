import os
import sys
import time
import threading
from pathlib import Path

import yaml
from PIL import Image, ImageDraw
import pystray

from .state_manager import StateManager


ICON_SIZE = 64


def _make_icon(color: str) -> Image.Image:
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r = ICON_SIZE // 2 - 4
    cx = ICON_SIZE // 2
    cy = ICON_SIZE // 2
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    return img


ICONS = {
    "gray": _make_icon("#484f58"),
    "green": _make_icon("#238636"),
    "yellow": _make_icon("#d29922"),
    "red": _make_icon("#da3633"),
}


def _load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _calc_status(state: StateManager) -> str:
    data = state.read()
    uuid = data.get("current_instance_uuid")
    if not uuid:
        return "gray"
    inst = (data.get("instances") or {}).get(uuid)
    if not inst or inst.get("status") != "running":
        return "gray"
    alerts = [a for a in data.get("alerts", []) if not a.get("dismissed")]
    if any(a.get("severity") == "critical" for a in alerts):
        return "red"
    gpu = data.get("gpu") or {}
    util = gpu.get("util_percent", 0)
    if util < 10:
        return "yellow"
    if any(a for a in alerts):
        return "yellow"
    return "green"


def _build_menu(icon: pystray.Icon, state: StateManager, web_port: int = 8899):
    def status_action():
        data = state.read()
        uuid = data.get("current_instance_uuid")
        if not uuid:
            icon.notify("未设置当前实例")
            return
        inst = (data.get("instances") or {}).get(uuid, {})
        gpu = data.get("gpu") or {}
        info = f"{inst.get('instance_name') or uuid[:14]}\nGPU: {gpu.get('util_percent','?')}% | {gpu.get('mem_used_gb','?')}/{gpu.get('mem_total_gb','?')}GB\n余额: ¥{data.get('balance',{}).get('assets_yuan','?')}"
        icon.notify(info, title="AutoDL Status")

    def open_panel_action():
        os.startfile(f"http://localhost:{web_port}")

    def exit_action():
        icon.stop()

    return pystray.Menu(
        pystray.MenuItem("状态摘要", lambda: status_action(), default=True),
        pystray.MenuItem("打开 Web 面板", lambda: open_panel_action()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("退出", lambda: exit_action()),
    )


def _run_web(port: int = 8899):
    from .api_server import create_app
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def main():
    config = _load_config()
    token = config.get("auto_dl", {}).get("token", "")
    if not token or token == "your-token-here":
        print("[WARN] config.yaml 未配置 Token，将使用本地缓存数据演示")

    state = StateManager()
    port = 8899

    web_thread = threading.Thread(target=_run_web, args=(port,), daemon=True)
    web_thread.start()
    time.sleep(1)

    icon = pystray.Icon("autodl", ICONS["gray"], "AutoDL Manager")

    def setup(icon_instance):
        icon_instance.visible = True
        while True:
            current = _calc_status(state)
            icon_instance.icon = ICONS.get(current, ICONS["gray"])
            icon_instance.update_menu()
            time.sleep(10)

    icon.run(setup)


if __name__ == "__main__":
    main()
