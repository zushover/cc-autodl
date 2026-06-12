"""一键部署 Claude Code 到 GPU 服务器。

☀️ 流程：SSH连接 → 检测环境 → 装Node.js → 装Claude Code → 配MCP → tmux启动

整个部署只需一次 SSH，之后 Claude Code 通过 MCP 和面板通信。
"""

import json
import re
import time
from pathlib import Path

import paramiko
import yaml


class ClaudeCodeDeployer:
    """将 Claude Code 部署到远程 GPU 服务器的部署器。"""

    def __init__(self, host: str, port: int = 22, username: str = "root",
                 password: str = "", key_filename: str = ""):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.client: paramiko.SSHClient | None = None
        self.log: list[str] = []

    def _connect(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kwargs = {"hostname": self.host, "port": self.port, "username": self.username, "timeout": 15}
        if self.key_filename:
            kwargs["key_filename"] = self.key_filename
        elif self.password:
            kwargs["password"] = self.password
        self.client.connect(**kwargs)

    def _exec(self, cmd: str, timeout: int = 30) -> tuple[str, str, int]:
        """执行命令，返回 (stdout, stderr, exit_code)。"""
        if not self.client:
            raise RuntimeError("Not connected")
        stdin, stdout, stderr = self.client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode(errors="replace").strip()
        err = stderr.read().decode(errors="replace").strip()
        code = stdout.channel.recv_exit_status()
        return out, err, code

    def _log(self, msg: str):
        self.log.append(msg)

    def deploy(self, panel_host: str, api_key: str, workspace: str = "/root/autodl-workspace") -> dict:
        """执行完整部署流程。

        Args:
            panel_host: 面板地址（服务器能访问到的 IP:8899）。AutoDL 实例通常用 connect.xxx.seetacloud.com
            api_key: DeepSeek/Anthropic API Key
            workspace: 工作目录

        Returns:
            {"success": bool, "steps": [...], "tmux_session": str}
        """
        steps = []

        try:
            # Step 1: SSH 连接
            self._log("[1/6] SSH 连接...")
            self._connect()
            steps.append({"step": "ssh_connect", "ok": True})

            # Step 2: 检测环境
            self._log("[2/6] 检测环境...")
            env = self._check_environment()
            steps.append({"step": "check_env", "ok": True, "env": env})

            # Step 3: 装 Node.js（如果没有）
            if env.get("node_version"):
                self._log(f"  Node.js {env['node_version']} ✓ (已安装)")
                steps.append({"step": "install_node", "ok": True, "skipped": True})
            else:
                self._log("  安装 Node.js...")
                self._install_nodejs()
                steps.append({"step": "install_node", "ok": True})

            # Step 4: 装 Claude Code
            self._log("[3/6] 安装 Claude Code...")
            cc_ver = self._install_claude_code()
            steps.append({"step": "install_cc", "ok": True, "version": cc_ver})

            # Step 5: 配 MCP + API Key
            self._log("[4/6] 配置 MCP + API Key...")
            self._configure_mcp(panel_host, api_key)
            steps.append({"step": "configure", "ok": True})

            # Step 6: 创建工作目录 + tmux 启动
            self._log("[5/6] 创建工作目录...")
            self._exec(f"mkdir -p {workspace}")

            self._log("[6/6] tmux 启动 Claude Code...")
            self._start_tmux(workspace)
            steps.append({"step": "tmux_start", "ok": True, "session": "claude-code"})

            self.client.close()
            return {
                "success": True,
                "steps": steps,
                "tmux_session": "claude-code",
                "workspace": workspace,
                "attach_cmd": "tmux attach -t claude-code",
                "log": self.log,
            }

        except Exception as e:
            steps.append({"step": "error", "ok": False, "error": str(e)})
            if self.client:
                try:
                    self.client.close()
                except Exception:
                    pass
            return {"success": False, "steps": steps, "error": str(e), "log": self.log}

    # ─── 环境检测 ───

    def _check_environment(self) -> dict:
        env = {}
        # Node
        out, _, _ = self._exec("node --version 2>/dev/null || echo ''")
        env["node_version"] = out.strip() if out else None

        # Python
        out, _, _ = self._exec("python3 --version 2>/dev/null || python --version 2>/dev/null || echo ''")
        env["python_version"] = out.strip() if out else None

        # CUDA
        out, _, _ = self._exec("nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo ''")
        env["gpu"] = out.strip() if out else None

        # OS
        out, _, _ = self._exec("cat /etc/os-release 2>/dev/null | head -1 || echo ''")
        env["os"] = out.strip() if out else None

        # tmux
        out, _, _ = self._exec("which tmux 2>/dev/null || echo ''")
        env["has_tmux"] = bool(out.strip())

        # npm
        out, _, _ = self._exec("npm --version 2>/dev/null || echo ''")
        env["npm_version"] = out.strip() if out else None

        # 磁盘空间
        out, _, _ = self._exec("df -h /root | tail -1 | awk '{print $4}'")
        env["disk_free"] = out.strip() if out else None

        return env

    # ─── 安装 Node.js ───

    def _install_nodejs(self):
        """通过 nvm 或 apt 装 Node.js 20 LTS。"""
        # 尝试 nvm（推荐，版本可控）
        _, _, code = self._exec("which nvm 2>/dev/null || echo ''")
        if code == 0:
            self._exec("nvm install 20 && nvm use 20", timeout=120)
            self._exec('echo "source ~/.nvm/nvm.sh" >> ~/.bashrc')
            return

        # 尝试 apt
        out, _, code = self._exec("which apt-get 2>/dev/null || echo ''")
        if code == 0:
            cmds = [
                "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -",
                "apt-get install -y nodejs",
            ]
            for cmd in cmds:
                self._exec(cmd, timeout=120)
            return

        # 最后尝试 yum
        self._exec("curl -fsSL https://rpm.nodesource.com/setup_20.x | bash -", timeout=120)
        self._exec("yum install -y nodejs", timeout=120)

    # ─── 安装 Claude Code ───

    def _install_claude_code(self) -> str:
        """npm install -g @anthropic-ai/claude-code。"""
        self._exec("npm install -g @anthropic-ai/claude-code 2>&1 || "
                   "npm install -g claude-code 2>&1 || "
                   "echo 'FAIL'", timeout=120)
        out, _, _ = self._exec("claude --version 2>/dev/null || echo 'unknown'")
        return out.strip() or "installed"

    # ─── 配置 MCP ───

    def _configure_mcp(self, panel_host: str, api_key: str):
        """配置 Claude Code 的 MCP Server + API Key。

        panel_host 格式: 服务器能访问到的 IP:8899
        例如 AutoDL 实例可以用 connect.bjb2.seetacloud.com 作为 MCP host。
        """
        mcp_config = {
            "mcpServers": {
                "autodlagents": {
                    "url": f"http://{panel_host}/mcp",
                    "description": "GPU监控 + 知识库 + 任务管理",
                }
            }
        }

        # 写 MCP 配置
        self._exec("mkdir -p ~/.claude")
        mcp_json = json.dumps(mcp_config, indent=2)
        # 用 heredoc 避免转义问题
        escaped = mcp_json.replace("'", "'\\''")
        self._exec(f"cat > ~/.claude/mcp_servers.json << 'MCPEOF'\n{mcp_json}\nMCPEOF")

        # 写 API Key 到环境变量（~/.bashrc）
        self._exec(f"grep -q ANTHROPIC_AUTH_TOKEN ~/.bashrc 2>/dev/null || "
                   f"echo 'export ANTHROPIC_AUTH_TOKEN={api_key}' >> ~/.bashrc")
        # 也写个 .env 备用
        self._exec(f"echo 'ANTHROPIC_AUTH_TOKEN={api_key}' > ~/.claude/.env")

        self._log(f"  MCP Server: http://{panel_host}/mcp")
        self._log(f"  API Key: ...{api_key[-4:]}")

    # ─── tmux 启动 ───

    def _start_tmux(self, workspace: str):
        """在 tmux 中启动 Claude Code。"""
        # 确保 tmux 已安装
        _, _, code = self._exec("which tmux 2>/dev/null")
        if code != 0:
            self._exec("apt-get install -y tmux 2>/dev/null || yum install -y tmux", timeout=60)

        # 杀掉旧 session（如果存在）
        self._exec("tmux kill-session -t claude-code 2>/dev/null || true")

        # 启动新 session
        start_cmd = (
            f"cd {workspace} && "
            "source ~/.bashrc && "
            "claude"
        )
        self._exec(f"tmux new-session -d -s claude-code '{start_cmd}'")
        self._log(f"  tmux session: claude-code")
        self._log(f"  重新连接: tmux attach -t claude-code")
