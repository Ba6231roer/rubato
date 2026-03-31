# Rubato

<p align="center">
  <strong>Natural Language-Driven Automated Test Execution Framework</strong>
</p>

<p align="center">
  <a href="#key-features">Key Features</a> •
  <a href="#requirements">Requirements</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#architecture">Architecture</a> •
  <a href="README.md">中文</a>
</p>

---

## Introduction

Rubato is a natural language-driven automated test execution framework. Users simply describe test scenarios in natural language, and the agent automatically parses the intent, plans the steps, and executes tests through browser automation tools. It supports Playwright CLI tool calling, dynamic Skill loading, multi-agent collaboration, and context compression.

## Key Features

- **Natural Language-Driven** - Describe test scenarios in natural language, no coding required
- **Autonomous Planning** - Agent autonomously reasons, plans, and executes based on prompts
- **ReAct Pattern** - Universal Reason → Act → Observe loop
- **Multi-Agent Collaboration** - Supports main agent calling sub-agents with independent system prompts and contexts
- **Role System** - Supports multi-role configuration, each role can have independent system prompts, model configs, and tool sets
- **Multi-Instance Parallel** - Supports multiple agent instances running in parallel for improved efficiency
- **Dynamic Skill Loading** - Loads metadata at startup, full content on-demand during conversations
- **Playwright CLI Integration** - Browser automation via ShellTool executing playwright-cli commands, high token efficiency
- **Playwright MCP (Optional)** - Supports Playwright MCP as an alternative solution, disabled by default
- **Context Compression** - Automatically manages conversation history to avoid token overflow
- **Browser Persistence** - Browser runs as independent process, supporting state reuse and cross-session persistence
- **Dual Mode Operation** - Supports both CLI command-line and Web UI interaction modes
- **HTTP Service Layer** - Provides RESTful API and WebSocket interfaces for configuration management and real-time communication
- **Lightweight Frontend** - Pure HTML/CSS/JS implementation, zero build dependencies, easy deployment

## Requirements

- **Python**: 3.12+
- **Node.js**: 18+ (for running Playwright CLI)
- **OS**: Windows / macOS / Linux

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright CLI

```bash
npm install -g @playwright/cli@latest
playwright-cli --help
```

> **Tip**: Playwright CLI is the recommended approach for browser automation. If you prefer to use Playwright MCP as an alternative, enable it in `config/mcp_config.yaml`.

### 3. Configure API Key

**Option 1: Environment Variable (Recommended)**

```bash
# Windows PowerShell
$env:OPENAI_API_KEY = "your-api-key-here"

# Linux/macOS
export OPENAI_API_KEY="your-api-key-here"
```

**Option 2: Configuration File**

Edit `config/model_config.yaml`:

```yaml
model:
  provider: "openai"
  name: "gpt-4"
  api_key: "your-api-key-here"
```

### 4. Run

**CLI Mode (Default)**

```bash
python -m src.main
```

**Web Mode**

```bash
# Default port 8000
python -m src.main --web

# Custom port
python -m src.main --web --port 8080
```

You'll see the following interface when successfully started:

**CLI Mode**
```
╔══════════════════════════════════════════════════════════╗
║                       Rubato                             ║
╠══════════════════════════════════════════════════════════╣
║ Status: Model: gpt-4 | Skills: playwright-cli, test-execution
╚══════════════════════════════════════════════════════════╝
```

**Web Mode**
```
HTTP Server started: http://127.0.0.1:8000
Press Ctrl+C to stop
```

Visit `http://127.0.0.1:8000` in your browser to use the Web Console.

### 5. Quick Test Example

```
> Open Baidu and search for Python
```

The agent will automatically:
1. Navigate to Baidu homepage
2. Get page snapshot and analyze elements
3. Identify search box and search button
4. Type "Python" and search
5. Take screenshot and return results

## Architecture

### Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│                 Web Interaction Layer                    │
│              Browser / WebSocket Client                  │
├─────────────────────────────────────────────────────────┤
│                 HTTP Service Layer                       │
│         FastAPI / WebSocket / Config Management API      │
├─────────────────────────────────────────────────────────┤
│                 Console Interaction Layer                │
│              console.py / commands.py                    │
├─────────────────────────────────────────────────────────┤
│                     Core Engine Layer                    │
│            agent.py / sub_agents.py                      │
├─────────────────────────────────────────────────────────┤
│                       Tool Layer                         │
│     ShellTool / Tool Registry / Skill Loader             │
├─────────────────────────────────────────────────────────┤
│                     Support Layer                        │
│      Context Manager / Config Loader / Logger            │
├─────────────────────────────────────────────────────────┤
│                  Configuration Layer                     │
│   model_config / prompt_config / skills                  │
└─────────────────────────────────────────────────────────┘
```

### Core Design Principles

1. **Natural Language-Driven**: Describe test scenarios in natural language, agent automatically parses and executes
2. **Autonomous Planning**: Agent autonomously reasons, plans, and executes based on prompts
3. **ReAct Pattern**: Universal Reason-Act-Observe loop
4. **Multi-Agent Collaboration**: Supports main agent calling sub-agents
5. **Configuration-Driven**: All configurations exist as files for easy management
6. **Dynamic Skill Loading**: Loads metadata at startup, full content on-demand
7. **Tool Integration**: Supports ShellTool for CLI commands, sub-agent tools, and Skill tool extensions
8. **Context Compression**: Automatically manages conversation history to avoid token overflow
9. **Browser Persistence**: Browser runs as independent process, supporting state reuse
10. **Dual Mode Operation**: Supports both CLI command-line and Web UI interaction modes
11. **HTTP Service Layer**: Provides RESTful API and WebSocket interfaces
12. **Lightweight Frontend**: Pure HTML/CSS/JS implementation, zero build dependencies

## Project Structure

```
rubato/
├── src/                    # Source code
│   ├── main.py            # Entry point (supports CLI/Web modes)
│   ├── core/              # Core modules
│   │   ├── agent.py       # Main agent
│   │   ├── agent_pool.py  # Agent instance pool
│   │   ├── role_manager.py # Role manager
│   │   └── sub_agents.py  # Sub-agent mechanism
│   ├── api/               # HTTP service layer
│   │   ├── app.py         # FastAPI application
│   │   ├── routes/        # API routes
│   │   └── websocket.py   # WebSocket handler
│   ├── web/               # Web UI
│   │   ├── templates/     # HTML templates
│   │   └── static/        # Static assets
│   ├── commands/          # Command system
│   ├── skills/            # Skill system
│   ├── context/           # Context management
│   ├── config/            # Configuration management
│   └── cli/               # Command-line interface
├── config/                # Configuration files
│   ├── model_config.yaml  # Model configuration
│   ├── agent_config.yaml  # Agent configuration
│   ├── mcp_config.yaml    # MCP configuration
│   └── roles/             # Role configurations
├── prompts/               # Prompts
│   └── roles/             # Role prompts
├── skills/                # Skill files
│   ├── playwright-cli/    # Playwright CLI Skill (recommended)
│   │   ├── SKILL.md       # Main skill file
│   │   └── references/    # Reference docs
│   └── test-execution.md  # Test execution skill
├── sub_agents/            # Sub-agent configurations
├── logs/                  # Log directory
└── tests/                 # Test files
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `/help` | Display help information |
| `/quit` or `/exit` | Exit the program |
| `/config` | Display current configuration |
| `/history` | Display conversation history |
| `/clear` | Clear conversation history |
| `/new` | Start new conversation (keeps role and system prompt) |
| `/reload` | Reload all configurations (model, role, Skill) |
| `/skill list` | List all available Skills |
| `/skill show <name>` | Show Skill details |
| `/tool list` | List all available tools |
| `/prompt show` | Display current system prompt |
| `/role <name>` | Switch to specified role |
| `/role list` | List all available roles |
| `/role show <name>` | Show role details |
| `/browser status` | View browser status (requires MCP) |
| `/browser close` | Close browser (requires MCP) |
| `/browser reopen` | Reopen browser (requires MCP) |

## Extensibility

### Custom Skill

Create a new Markdown file in the `skills/` directory:

```markdown
---
name: my-skill
description: Custom Skill description
version: 1.0
triggers:
  - trigger-word-1
  - trigger-word-2
tools:
  - ShellTool
---

# My Skill

## Description
...
```

### Custom Sub-Agent

Create a new YAML file in the `sub_agents/` directory:

```yaml
name: my-custom-agent
description: Custom sub-agent description
version: 1.0

system_prompt: |
  You are an XXX expert...
  
  Task: ...

execution:
  timeout: 60
  max_retries: 1
```

## Tech Stack

- Python 3.12
- LangChain 0.3.25
- LangGraph 0.4.5
- FastAPI 0.109+
- Uvicorn 0.27+
- Playwright CLI (Recommended)
- Playwright MCP (Optional)
- Pydantic

## Troubleshooting

### Playwright CLI Not Installed

```bash
npm install -g @playwright/cli@latest
playwright-cli --help
```

### Invalid API Key

1. Check if environment variable is set correctly
2. Or fill in the API key directly in `config/model_config.yaml`

### Browser Startup Failed

```bash
npx playwright install chromium
```

### Playwright MCP Connection Failed (if using MCP alternative)

1. Check `enabled: true` in `config/mcp_config.yaml`
2. Confirm Playwright MCP is correctly installed
3. Check network connection

## Documentation

- [Quick Start Guide](QUICK_START.md) (Chinese)
- [Architecture Design Document](dev_docs/design.md) (Chinese)
- [Playwright CLI Migration Design](dev_docs/playwright-cli-migration-design.md) (Chinese)
- [Playwright MCP Setup Guide (Optional)](dev_docs/playwright-mcp-setup.md) (Chinese)

## License

MIT License
