"""Python sidecar — 仅启动 FastAPI 服务器 (:8899)。

Tauri 负责窗口和托盘，Python 只做业务逻辑。
启动时自动杀掉占用端口的旧进程。
"""

import os
import sys
import socket
import uvicorn
from autodl_manager.api_server import create_app
from autodl_manager.db import get_db

PORT = 8899


def kill_existing():
    """杀掉占用 PORT 的旧进程，避免端口冲突。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex(('127.0.0.1', PORT))
        s.close()
        if result != 0:
            return  # 端口空闲，无需处理
    except Exception:
        return

    # 端口被占用，强杀旧进程
    import subprocess
    try:
        out = subprocess.check_output(
            f'netstat -ano | findstr :{PORT} | findstr LISTENING',
            shell=True, text=True, timeout=5,
        )
        for line in out.strip().split('\n'):
            parts = line.strip().split()
            if parts:
                pid = parts[-1]
                try:
                    subprocess.run(
                        ['taskkill', '/F', '/PID', pid],
                        capture_output=True, timeout=5,
                    )
                    print(f'[sidecar] killed old process PID {pid} on port {PORT}')
                except Exception:
                    pass
    except Exception:
        pass


if __name__ == "__main__":
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))

    kill_existing()
    get_db()

    app = create_app()
    print(f'[sidecar] AutoDL API starting on http://127.0.0.1:{PORT}')

    # 无终端环境下禁用彩色日志
    import logging
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["default"]["use_colors"] = False
    log_config["formatters"]["access"]["use_colors"] = False

    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning", log_config=log_config)
