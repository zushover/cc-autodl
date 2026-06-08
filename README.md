# cc-autodl

AutoDL GPU 云管理桌面应用 —— 系统托盘常驻，一站管理你的 GPU 实例。

## 功能

- **实例管理**: 列出、注册、探测、关机（支持 Pro API / Web 控制台 / 自定义 SSH）
- **GPU 监控**: SSH 直连采集 GPU 利用率 / 显存 / 温度 / 运行进程
- **费用追踪**: 实时余额、累计消费、今日/本周消费、预估可用天数
- **智能探测**: 一键检测实例状态（运行中 / 无卡模式 / 已关机），自动更新
- **桌面托盘**: 窗口关闭即缩到托盘，右键快捷操作
- **SSH 解析**: 粘贴 SSH 连接命令自动拆主机/端口/用户

## 架构

```
cc-autodl.exe (Tauri/Rust 桌面壳)
  ├─ 启动时 spawn python-sidecar.exe (FastAPI :8899)
  ├─ WebView 加载 Vue 3 前端
  └─ 系统托盘 (Rust native)
```

## 技术栈

| 层 | 技术 |
|------|------|
| 桌面壳 | Tauri 2 (Rust) |
| 前端 | Vue 3 + TypeScript + Vite |
| 后端 | Python FastAPI + SQLite |
| SSH | Paramiko |
| 打包 | PyInstaller (sidecar) + Tauri bundler (NSIS) |

## 快速开始

### 开发模式

```bash
# 1. 安装依赖
pip install -r requirements.txt
npm install

# 2. 配置
cp config.example.yaml config.yaml
# 编辑 config.yaml，填入 AutoDL Token

# 3. 启动后端
python sidecar.py

# 4. 启动前端（另一个终端）
npm run dev

# 5. 启动 Tauri
cd src-tauri && cargo run
```

### 构建发布版

```bash
# 1. 构建前端
npm run build

# 2. 打包 sidecar
pyinstaller sidecar.spec --distpath src-tauri/target/debug
cp -r dist src-tauri/target/debug/
cp src-tauri/target/debug/python-sidecar.exe src-tauri/binaries/

# 3. 构建 Tauri
cd src-tauri && cargo build --release
```

## 项目结构

```
cc-autodl/
├── autodl_manager/      # Python 后端
│   ├── api_server.py    # FastAPI REST + SSE
│   ├── autodl_api.py    # AutoDL Pro API 封装
│   ├── instance_registry.py  # 三源实例注册表
│   ├── gpu_collector.py # GPU 数据采集
│   ├── db.py            # SQLite 数据库
│   └── gpu_data.py      # GPU 型号/区域/价格数据
├── src/                 # Vue 3 前端
│   ├── App.vue          # 主组件（仪表盘/实例/费用/设置）
│   └── style.css        # 全局样式
├── src-tauri/           # Tauri Rust 桌面壳
│   ├── src/lib.rs       # 托盘 + sidecar 管理
│   └── tauri.conf.json  # Tauri 配置
├── sidecar.py           # PyInstaller 入口
├── sidecar.spec         # PyInstaller 打包配置
└── config.example.yaml  # 配置模板
```

## License

MIT
