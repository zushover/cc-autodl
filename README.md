# Triple A

> **AutodlAgents** — AI-powered GPU cloud management desktop app.  
> Natural language control of GPU instances, multi-agent orchestration, shared memory, one-click Claude Code deployment.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![Vue](https://img.shields.io/badge/Vue-3.5-green)
![Tauri](https://img.shields.io/badge/Tauri-2.0-orange)

---

## What is Triple A?

Triple A (AutodlAgents) is a desktop application that turns GPU cloud management into a conversation. Instead of SSH-ing into servers and running commands manually, you talk to an AI agent that manages everything for you.

**Core idea:** Panel is the brain. Servers are the limbs. Claude Code on both sides communicates through a shared memory layer.

```
You → "Check GPU utilization on all instances, shutdown idle ones"
  → Triple A Agent autonomously:
    1. Lists all GPU instances
    2. Checks each one's utilization via SSH
    3. Identifies idle instances (<10% GPU util)
    4. Asks for confirmation before shutdown
    5. Reports results
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Triple A Desktop (Tauri + Vue 3)          │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              Master Agent (LangGraph ReAct)             │  │
│  │  8 Tools: list/check/execute/delegate/shutdown/...      │  │
│  │  Model: DeepSeek V4 Flash (Anthropic-compatible API)    │  │
│  └────────────────────┬───────────────────────────────────┘  │
│                       │                                      │
│  ┌────────────────────┴───────────────────────────────────┐  │
│  │            Memory Hub (ChromaDB)                        │  │
│  │  conversations · experiments · documents · decisions    │  │
│  └────────────────────┬───────────────────────────────────┘  │
│                       │                                      │
│  ┌────────────────────┴───────────────────────────────────┐  │
│  │            MCP Server (GPU Monitor)                     │  │
│  │  5 Tools + 3 Resources + 2 Prompts                      │  │
│  └────────────────────┬───────────────────────────────────┘  │
│                       │                                      │
│  ┌────────────────────┴───────────────────────────────────┐  │
│  │            Vue 3 Panel (5 pages)                        │  │
│  │  Servers · Triple A · Knowledge Base · Cost · Settings   │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  Python Sidecar: FastAPI + SQLite + Paramiko + LangChain     │
│  Desktop Shell:   Tauri 2 (Rust) + System Tray              │
└──────────────────────┬───────────────────────────────────────┘
                       │ SSH + REST API
┌──────────────────────┴───────────────────────────────────────┐
│                    GPU Servers (AutoDL)                      │
│                                                              │
│  ┌─────────────────────────┐  ┌─────────────────────────┐   │
│  │  Server A · 3080Ti      │  │  Server B · 4090D       │   │
│  │                         │  │                         │   │
│  │  Claude Code (tmux)     │  │  Claude Code (tmux)     │   │
│  │  Watchdog (task poller) │  │  Watchdog (task poller) │   │
│  │                         │  │                         │   │
│  │  Deployed by ☀️ button  │  │  Deployed by ☀️ button  │   │
│  └─────────────────────────┘  └─────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### Communication Flow

```
User → Master Agent → Tool Selection → SSH to Server → nvidia-smi/log → Agent Analysis → Response

For delegated tasks:
Master Agent → delegate_to_server(uuid, task)
  → SSH → claude -p "task" on remote server
  → Server Claude Code executes locally → returns result
  → Master summarizes and presents to user
```

---

## Features

### 🖥 Server Management
- **Three-source instance registry:** Pro API / Web Console / Custom SSH
- **Smart probe:** SSH connection → GPU detection → system info collection → auto-status update
- **GPU monitoring:** Real-time utilization, memory, temperature, process list via `nvidia-smi`
- **SSH command parsing:** Paste connection string → auto-extract host/port/user
- **Idle detection:** GPU <5% → alert → auto-shutdown option

### 🤖 Triple A (Master Agent)
- **Natural language GPU management:** "Find idle GPUs and shut them down"
- **LangGraph ReAct loop:** Observe → Think → Act → Observe
- **8 Tools:** list_gpu_instances, check_gpu_utilization, probe_instance_health, execute_on_server, delegate_to_server, get_balance_and_cost, shutdown_idle_instance, save_to_knowledge_base
- **Streaming SSE responses:** Real-time token-by-token rendering
- **Sub-agent delegation:** `delegate_to_server()` calls remote Claude Code

### ☀️ One-Click Claude Code Deployment
- SSH → detect environment → install Node.js → `npm install -g @anthropic-ai/claude-code`
- Configure DeepSeek API via SFTP (`~/.claude/env.sh`)
- Start in tmux session (`claude-code` + `watchdog`)
- Server CC automatically connects back via MCP

### 🧠 Shared Memory (ChromaDB)
- **3 collections:** conversations / experiments / agent_decisions
- **REST API:** Read/write/search from any agent
- **Auto-save:** Every agent conversation persisted
- **Loop detection:** Semantic similarity check on decisions

### 📡 MCP Server
- **5 Tools:** gpu_status, gpu_history, list_gpu_instances, probe_instance, get_balance
- **3 Resources:** instances://list, gpu://{uuid}/latest, balance://overview
- **Standard MCP protocol:** Any MCP Client can discover and call

### 📚 Knowledge Base
- Full-text search across conversations, experiments, documents
- Category filters: All / Conversations / Experiments / Decisions / Documents
- Per-agent memory (reserved)

### 💰 Cost Tracking
- AutoDL: real-time balance + cumulative spending
- DeepSeek: API balance query (granted + topped up)
- Combined total balance display

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Desktop Shell | Tauri 2 (Rust) |
| Frontend | Vue 3 + TypeScript + Vite |
| Backend | Python 3.12 + FastAPI |
| Database | SQLite (WAL mode) |
| Agent Framework | LangChain + LangGraph |
| Memory | ChromaDB (vector database) |
| SSH | Paramiko |
| LLM | DeepSeek V4 Flash (Anthropic-compatible) |
| MCP | Model Context Protocol (custom server) |
| Packaging | PyInstaller (sidecar) + Tauri bundler (NSIS) |

---

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 20+
- Rust (for Tauri builds)
- AutoDL account (or any SSH-accessible GPU server)

### Development

```bash
# 1. Clone
git clone https://github.com/zushover/cc-autodl.git
cd cc-autodl

# 2. Install dependencies
pip install -r requirements.txt
npm install

# 3. Configure
cp config.example.yaml config.yaml
# Edit config.yaml:
#   - auto_dl.token: your AutoDL developer token
#   - llm.api_key: your DeepSeek API key (sk-xxx)
#   - llm.api_base: https://api.deepseek.com/v1
#   - llm.model: deepseek-v4-flash

# 4. Start backend
python sidecar.py

# 5. Start frontend (another terminal)
npm run dev

# 6. Open browser
# http://127.0.0.1:8899
```

### Production Build

```bash
# Build frontend
npm run build

# Build Python sidecar
pyinstaller sidecar.spec --distpath src-tauri/target/debug
cp -r dist src-tauri/target/debug/
cp src-tauri/target/debug/python-sidecar.exe src-tauri/binaries/

# Build Tauri desktop app
cd src-tauri && cargo build --release
```

> **Note:** Browser-based testing uses the exact same code as the packaged Tauri app. The Tauri WebView loads the same Vue frontend, and the Python sidecar runs as a child process.

---

## Project Structure

```
cc-autodl/
├── autodl_manager/          # Python backend
│   ├── api_server.py        # FastAPI (44 routes)
│   ├── autodl_api.py        # AutoDL Pro API client
│   ├── instance_registry.py # Three-source instance management
│   ├── gpu_collector.py     # nvidia-smi SSH collector
│   ├── daemon.py            # Background monitor daemon
│   ├── db.py                # SQLite database layer
│   ├── log_parser.py        # Training log anomaly detection
│   └── agent/               # Agent module (core)
│       ├── tools.py         # 8 LangChain Tools
│       ├── agent_loop.py    # LangGraph ReAct loop
│       ├── memory.py        # ChromaDB 3-collection memory
│       ├── prompts.py       # System prompt templates
│       ├── executor.py      # Server-side task executor
│       ├── multi_agent.py   # Multi-agent orchestrator
│       ├── mcp_server.py    # MCP GPU Monitor server
│       ├── deploy.py        # One-click CC deployment
│       ├── watchdog.py      # Server task listener
│       └── observability.py # LangFuse tracing
├── src/                     # Vue 3 frontend
│   ├── App.vue              # Root component (state hub)
│   ├── api.ts               # REST + SSE client
│   ├── types.ts             # TypeScript definitions
│   ├── style.css            # Design system (CSS variables)
│   └── components/
│       ├── Dashboard.vue    # Server management page
│       ├── AgentLog.vue     # Triple A chat interface
│       ├── KnowledgeBase.vue# Knowledge base browser
│       ├── CostAnalysis.vue # Dual cost tracking
│       ├── SettingsPanel.vue# Token & API config
│       ├── RegisterDialog.vue# Instance registration
│       ├── TopBar.vue       # Server selector bar
│       ├── Sidebar.vue      # Navigation sidebar
│       └── ...              # More components
├── src-tauri/               # Tauri Rust shell
│   ├── src/lib.rs           # Tray icon + sidecar manager
│   └── tauri.conf.json      # Tauri configuration
├── sidecar.py               # PyInstaller entry point
├── config.example.yaml      # Configuration template
└── requirements.txt         # Python dependencies
```

---

## Agent Tool Set

| Tool | Description | Requires |
|------|-------------|----------|
| `list_gpu_instances` | List all registered GPU instances | — |
| `check_gpu_utilization(uuid)` | Real-time GPU util/mem/temp | SSH |
| `probe_instance_health(uuid)` | SSH probe + system info + auto-detect | SSH |
| `execute_on_server(uuid, cmd)` | Remote command execution | SSH |
| `delegate_to_server(uuid, task)` | Delegate AI task to server CC | SSH + CC deployed |
| `get_balance_and_cost` | AutoDL balance + spending | API token |
| `shutdown_idle_instance(uuid)` | Shutdown idle instance | SSH |
| `save_to_knowledge_base(cat, title, content)` | Write to ChromaDB memory | — |

---

## API Endpoints (44 total)

### Agent
- `POST /api/agent/query` — Single-agent ReAct query
- `POST /api/agent/stream` — Streaming SSE agent
- `POST /api/agent/orchestrate` — Multi-agent orchestration
- `GET /api/agent/status` — Agent system status
- `POST /api/agent/tasks` — Create task
- `POST /api/agent/report` — Server agent status report

### MCP
- `GET /mcp/tools` — List MCP tools
- `POST /mcp/call` — Call MCP tool
- `GET /mcp/resources` — List MCP resources
- `POST /mcp/read` — Read MCP resource
- `GET /mcp/prompts` — List MCP prompts

### Memory
- `GET /api/memory/conversations` — Recent conversations
- `POST /api/memory/conversations` — Add conversation
- `GET /api/memory/experiments` — Search experiments
- `POST /api/memory/experiments` — Add experiment
- `GET /api/memory/decisions/check` — Loop risk check
- `GET /api/knowledge/all` — All knowledge base entries

### Instance Management
- `GET /api/instances` — List all instances
- `POST /api/instances/register` — Register new instance
- `POST /api/instances/{uuid}/probe` — Probe instance health
- `POST /api/instances/{uuid}/deploy` — ☀️ One-click CC deploy
- ... and more

---

## Testing

All agent features tested with real hardware:
- Instance listing + GPU probing → Real-time 3080Ti data ✅
- Agent query → LangGraph ReAct with actual tool calls ✅
- One-click CC deployment → Successful deploy to GPU server ✅
- Knowledge base → ChromaDB conversation/experiment storage ✅
- MCP Server → Standard protocol tools/resources ✅
- Cost tracking → AutoDL + DeepSeek dual balance ✅

---

## License

MIT
