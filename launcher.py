"""AutoDL Manager — 桌面启动入口"""
import os
import sys
import time
import threading
import webbrowser

from autodl_manager.state_manager import StateManager
from autodl_manager.api_server import create_app

PORT = 8899


def run_web():
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


def run_tray():
    from PIL import Image, ImageDraw
    import pystray

    SIZE = 64

    def make_icon(color):
        img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        r = SIZE // 2 - 4
        cx = SIZE // 2
        cy = SIZE // 2
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
        return img

    icons = {
        "gray": make_icon("#484f58"),
        "green": make_icon("#238636"),
        "yellow": make_icon("#d29922"),
        "red": make_icon("#da3633"),
    }

    state = StateManager()

    def calc_status():
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
        if gpu.get("util_percent", 0) < 10:
            return "yellow"
        if any(alerts):
            return "yellow"
        return "green"

    def on_status(icon):
        data = state.read()
        uuid = data.get("current_instance_uuid")
        if not uuid:
            icon.notify("未设置当前实例")
            return
        inst = (data.get("instances") or {}).get(uuid, {})
        gpu = data.get("gpu") or {}
        info = f"{inst.get('instance_name') or uuid[:14]}\nGPU: {gpu.get('util_percent','?')}% | Mem: {gpu.get('mem_used_gb','?')}/{gpu.get('mem_total_gb','?')}GB\nBalance: {data.get('balance',{}).get('assets_yuan','?')}"
        icon.notify(info, title="AutoDL Manager")

    def on_open():
        webbrowser.open(f"http://localhost:{PORT}")

    def on_exit(icon):
        icon.stop()
        os._exit(0)

    menu = pystray.Menu(
        pystray.MenuItem("状态摘要", on_status, default=True),
        pystray.MenuItem("打开面板", on_open),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("退出", on_exit),
    )

    icon = pystray.Icon("autodl", icons["gray"], "AutoDL Manager", menu)

    def setup(icon_instance):
        icon_instance.visible = True
        while True:
            icon_instance.icon = icons.get(calc_status(), icons["gray"])
            time.sleep(10)

    icon.run(setup)


def main():
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))

    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    time.sleep(1.5)
    webbrowser.open(f"http://localhost:{PORT}")
    run_tray()


if __name__ == "__main__":
    main()
