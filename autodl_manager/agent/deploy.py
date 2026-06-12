"""一键部署 Claude Code 到 GPU 服务器。

☀️ SSH连接 → 检测环境 → 装Node → 装Claude Code → 配DeepSeek API → tmux启动

整个部署一次 SSH，之后 Claude Code 在服务器本地运行。
用 DeepSeek 的 Anthropic 兼容 API，不需要公网 IP。
"""

import json
from pathlib import Path

import paramiko
import yaml


class ClaudeCodeDeployer:
    """将 Claude Code 部署到远程 GPU 服务器。"""

    def __init__(self, host: str, port: int = 22, username: str = "root",
                 password: str = "", key_filename: str = ""):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.client: paramiko.SSHClient | None = None
        self.log: list[str] = []
        self._sftp = None

    def _connect(self):
        self._log(f"  SSH {self.username}@{self.host}:{self.port}")
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kwargs = {"hostname": self.host, "port": self.port, "username": self.username, "timeout": 15, "banner_timeout": 10}
        if self.key_filename:
            kwargs["key_filename"] = self.key_filename
        elif self.password:
            kwargs["password"] = self.password
        else:
            raise RuntimeError("需要 SSH 密码或密钥")
        self.client.connect(**kwargs)
        self._sftp = self.client.open_sftp()

    def _exec(self, cmd: str, timeout: int = 30) -> tuple[str, str, int]:
        """执行命令，返回 (stdout, stderr, exit_code)。"""
        if not self.client:
            raise RuntimeError("Not connected")
        stdin, stdout, stderr = self.client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode(errors="replace").strip()
        err = stderr.read().decode(errors="replace").strip()
        code = stdout.channel.recv_exit_status()
        return out, err, code

    def _exec_checked(self, cmd: str, desc: str = "", timeout: int = 60) -> str:
        """执行命令并检查结果。失败抛出异常。返回 stdout。"""
        out, err, code = self._exec(cmd, timeout=timeout)
        if code != 0 and "npm WARN" not in err and "deprecated" not in err.lower():
            # npm 的 warning 不算失败
            if "could not be installed" in (out + err).lower() or "error" in (out + err).lower():
                raise RuntimeError(f"{desc} 失败 (exit {code}): {err[:200]}")
        return out

    def _write_file(self, remote_path: str, content: str):
        """通过 SFTP 写文件到远程（避免 shell 转义问题）。"""
        if not self._sftp:
            raise RuntimeError("SFTP not connected")
        self._exec(f"mkdir -p {str(Path(remote_path).parent)}")
        with self._sftp.file(remote_path, 'w') as f:
            f.write(content)

    def _log(self, msg: str):
        self.log.append(msg)

    # ─── 主流程 ───

    def deploy(self, api_key: str, workspace: str = "/root/autodl-workspace") -> dict:
        """完成部署。

        Args:
            api_key: DeepSeek API Key（sk-xxx），用户设置里填的那个
            workspace: 工作目录

        Returns:
            {"success": bool, "steps": [...], ...}
        """
        try:
            # Step 1: SSH
            self._log("[1/5] SSH 连接")
            self._connect()

            # Step 2: 环境检测
            self._log("[2/5] 检测环境")
            env = self._check_environment()
            self._log(f"  OS: {env.get('os', '?')}")
            self._log(f"  GPU: {env.get('gpu', '?')}")
            self._log(f"  Node.js: {env.get('node_version') or '未安装'}")
            self._log(f"  npm: {env.get('npm_version') or '未安装'}")

            # Step 3: Node.js（按需安装）
            self._log("[3/5] Node.js")
            if env.get("node_version"):
                self._log(f"  已安装，跳过")
            else:
                self._log("  安装中...")
                self._install_nodejs()
                # 验证
                v, _, _ = self._exec("node --version 2>/dev/null")
                if not v:
                    raise RuntimeError("Node.js 安装后仍不可用")
                self._log(f"  安装完成: {v}")

            # Step 4: Claude Code
            self._log("[4/5] Claude Code")
            self._install_claude_code()

            # Step 5: 配置环境 + 部署 watchdog + 启动
            self._log("[5/5] 配置 + watchdog + 启动")
            self._configure_env(api_key)
            self._deploy_watchdog(workspace)
            self._start_tmux(workspace)

            if self.client:
                self.client.close()

            return {
                "success": True,
                "tmux_session": "claude-code",
                "workspace": workspace,
                "attach_cmd": "tmux attach -t claude-code",
                "log": self.log,
            }

        except Exception as e:
            self._log(f"!! 部署失败: {e}")
            if self.client:
                try:
                    self.client.close()
                except Exception:
                    pass
            return {"success": False, "error": str(e), "log": self.log}

    # ─── 环境检测 ───

    def _check_environment(self) -> dict:
        checks = {
            "node_version": "node --version 2>/dev/null || echo ''",
            "npm_version": "npm --version 2>/dev/null || echo ''",
            "python_version": "python3 --version 2>/dev/null || python --version 2>/dev/null || echo ''",
            "gpu": "nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo ''",
            "os": "cat /etc/os-release 2>/dev/null | head -1 || echo ''",
            "has_tmux": "which tmux 2>/dev/null && echo yes || echo ''",
            "disk_free": "df -h /root 2>/dev/null | tail -1 | awk '{print $4}' || echo ''",
        }
        env = {}
        for k, cmd in checks.items():
            out, _, _ = self._exec(cmd)
            env[k] = out.strip() if out and out.strip() else None
        # Fix booleans
        env["has_tmux"] = bool(env.get("has_tmux"))
        return env

    # ─── 安装 Node.js ───

    def _install_nodejs(self):
        """装 Node.js 20 LTS。"""
        # 先试 apt（Ubuntu/Debian）
        _, _, apt_ok = self._exec("which apt-get 2>/dev/null")
        if apt_ok == 0:
            cmds = [
                "curl -fsSL https://deb.nodesource.com/setup_20.x | bash - 2>&1",
                "apt-get install -y nodejs 2>&1",
            ]
            for c in cmds:
                out, err, code = self._exec(c, timeout=120)
                if code != 0 and "error" in (out + err).lower():
                    raise RuntimeError(f"Node.js 安装失败: {out} {err}")
            return

        # 再试 yum（CentOS/RHEL）
        _, _, yum_ok = self._exec("which yum 2>/dev/null")
        if yum_ok == 0:
            self._exec_checked("curl -fsSL https://rpm.nodesource.com/setup_20.x | bash -", timeout=120)
            self._exec_checked("yum install -y nodejs", timeout=120)
            return

        raise RuntimeError("无法安装 Node.js：未找到 apt-get 或 yum")

    # ─── 安装 Claude Code ───

    def _install_claude_code(self):
        """npm install -g @anthropic-ai/claude-code。"""
        # 检查是否已安装
        out, _, _ = self._exec("claude --version 2>/dev/null || echo ''")
        if out.strip():
            self._log(f"  已安装: {out.strip()}")
            return

        self._log("  npm install -g @anthropic-ai/claude-code ...")
        out, err, code = self._exec(
            "npm install -g @anthropic-ai/claude-code 2>&1",
            timeout=180,
        )
        if code != 0:
            # 有些 npm 版本 WARN 也算非0，检查是否真的装上了
            v, _, _ = self._exec("claude --version 2>/dev/null || echo ''")
            if not v.strip():
                raise RuntimeError(f"Claude Code 安装失败: {err[:300]}")
        self._log("  安装完成")

    # ─── 配置环境 ───

    def _configure_env(self, api_key: str):
        """把 DeepSeek API 配置写入远程服务器的 ~/.bashrc。

        用户在自己的 cc-autodl 设置里填的 DeepSeek API Key，
        通过这里注入到远程 Claude Code 的环境中。
        """
        exports = [
            'export ANTHROPIC_AUTH_TOKEN=' + api_key,
            'export ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic',
            'export ANTHROPIC_MODEL=deepseek-v4-pro[1m]',
            'export ANTHROPIC_DEFAULT_SONNET_MODEL=deepseek-v4-pro[1m]',
            'export ANTHROPIC_DEFAULT_HAIKU_MODEL=deepseek-v4-flash',
        ]

        # 构造一个 env.sh 脚本（SFTP 写入，避免 shell 转义）
        script = '\n'.join(exports) + '\n'
        self._write_file("/root/.claude/env.sh", script)

        # 在 .bashrc 中 source（如果还没加过）
        out, _, _ = self._exec("grep -q 'env.sh' ~/.bashrc 2>/dev/null && echo yes || echo ''")
        if not out.strip():
            self._exec("echo 'source ~/.claude/env.sh' >> ~/.bashrc")

        self._log(f"  API Key: sk-...{api_key[-4:]}")
        self._log(f"  API URL: https://api.deepseek.com/anthropic")
        self._log(f"  Model: deepseek-v4-pro")

    # ─── watchdog ───

    def _deploy_watchdog(self, workspace: str):
        """部署任务监听器的 Python 脚本到服务器。

        watchdog.py 每 10s 扫描 tasks/*.yaml，自动调 CC 执行，
        结果写入 results/*.json，上报面板 ChromaDB。
        """
        # 找 watchdog.py 的位置
        import autodl_manager.agent.watchdog as wd
        wd_path = Path(wd.__file__)

        # SFTP 上传
        remote_path = f"{workspace}/watchdog.py"
        self._log(f"  上传 watchdog.py ...")
        with open(wd_path, "r") as src:
            self._write_file(remote_path, src.read())

        # 装依赖
        self._exec("pip3 install pyyaml 2>/dev/null || pip install pyyaml 2>/dev/null || true", timeout=60)

        self._log(f"  watchdog 已部署到 {remote_path}")

    # ─── tmux ───

    def _start_tmux(self, workspace: str):
        """在 tmux 中分别启动 Claude Code 和 watchdog。"""
        # 装 tmux（如果没有）
        _, _, code = self._exec("which tmux 2>/dev/null")
        if code != 0:
            self._log("  安装 tmux...")
            self._exec("apt-get update -qq && apt-get install -y tmux 2>&1 || yum install -y tmux 2>&1", timeout=90)

        self._exec(f"mkdir -p {workspace}/tasks {workspace}/results")

        # 1. 启动 Claude Code
        self._exec("tmux kill-session -t claude-code 2>/dev/null; true")
        cc_cmd = f"cd {workspace} && source ~/.claude/env.sh && claude"
        self._exec(f"tmux new-session -d -s claude-code {repr(cc_cmd)}")

        # 2. 启动 watchdog
        self._exec("tmux kill-session -t watchdog 2>/dev/null; true")
        wd_cmd = f"cd {workspace} && python3 watchdog.py"
        self._exec(f"tmux new-session -d -s watchdog {repr(wd_cmd)}")

        self._log(f"  tmux: claude-code + watchdog")
        self._log(f"  CC:  tmux attach -t claude-code")
        self._log(f"  WD:  tmux attach -t watchdog")
