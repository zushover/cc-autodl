# cc-autodl

AutoDL GPU 云管理工具 —— CLI + Web 面板 + 桌面托盘，一站管理你的 GPU 实例。

## 功能

- **实例管理**：列出、切换、开机、关机、释放
- **GPU 监控**：SSH 直连采集 GPU 利用率/显存/温度/进程
- **费用追踪**：实时余额、今日/本周消费、预估剩余天数
- **Web 面板**：`localhost:8899`，侧边栏导航，纯 HTML 无外部依赖
- **桌面托盘**：4 色状态图标，右键快捷操作
- **CLI 工具**：15 个子命令，支持脚本化和 Claude Code Skills 调用

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置 Token
cp config.example.yaml config.yaml
# 编辑 config.yaml，填入 AutoDL Token（控制台 → 设置 → 开发者 Token）

# 启动
python launcher.py
```

启动后自动打开浏览器进入管理面板，系统托盘出现状态图标。

## CLI

```
autodl list          # 实例列表
autodl use <id>      # 切换当前实例
autodl status        # 当前实例详情
autodl start [id]    # 开机
autodl stop [id]     # 关机
autodl release <id>  # 释放
autodl sync          # 从 API 同步
autodl balance       # 查询余额
autodl cost          # 费用汇总
autodl run <script>  # 上传并启动训练
autodl prep          # 环境检查
autodl progress      # 训练进度
autodl snapshot <name>  # 保存镜像
autodl snapshots     # 镜像列表
autodl exec <cmd>    # 执行远程命令
```

## 打包

```bash
pip install pyinstaller
pyinstaller autodl_manager.spec
# 输出: dist/autodl-manager.exe (~28MB)
```

双击 exe 即可启动托盘 + Web 面板，无需安装 Python。

## 技术栈

Python 3.8+ · requests · paramiko · FastAPI · pystray · PyInstaller

零外部服务依赖，JSON + CSV 本地存储，Windows 优先。

## 架构

```
CLI / 托盘 / Web 面板  →  state.json + config.yaml
    →  fleet / session / gpu / cost  →  autodl_api.py  →  AutoDL API + SSH
```
