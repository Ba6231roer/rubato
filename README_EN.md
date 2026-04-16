# Rubato

Natural Language-Driven Automated Test Execution Framework

## Core Features

- **ReAct + Skills Architecture** — LLM reasoning + tool-calling loop + natural language workflow snippets
- **Multi-Level Context Compression** — Four-stage progressive compression pipeline (boundary → budget → snip → auto) to prevent context overflow
- **Structured System Prompt Management** — Layered storage by change frequency, supporting independent Skill loading/unloading/stale removal
- **Session Persistence & Recovery** — Incremental conversation saving, historical session loading, SubAgent session association
- **Sub-Agent Mechanism** — Task decomposition and specialized processing with multi-level nesting support
- **Role System** — Multi-role configuration for customized agent behavior across different scenarios
- **Dual-Mode Interaction** — CLI console mode + Web HTTP mode
- **Tool System Integration** — Built-in tools, MCP tools, file tools, shell tools
- **Structured Streaming Output** — WebSocket structured messages with type differentiation (text/tool calls/errors)

## Tech Stack

| Technology | Purpose |
|------------|---------|
| Python >=3.12 | Primary language |
| LangChain | LLM invocation, tool integration, callback handling |
| FastAPI | HTTP service layer, REST API |
| Pydantic | Configuration models, API data models |
| tiktoken | Context token precise counting |
| pathspec | GitWildMatch pattern for conditional Skill activation |
| PyYAML | YAML configuration file loading |
| asyncio | Fully asynchronous architecture |

## Quick Start

### Prerequisites

- Python >=3.12

### Installation

```bash
# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate  # Linux/macOS

# Install project
pip install -e .
```

### Configuration

Edit YAML files in the `config/` directory. The `model_config.yaml` file requires API Key and model configuration.

### Running

```bash
# CLI mode
python -m src.main

# Web mode
python -m src.main --web --port 8000
```

## Project Structure

```
src/
├── api/            HTTP service layer (FastAPI, WebSocket, REST API)
├── cli/            Console interaction
├── commands/       Command system (parsing, registration, dispatch)
├── config/         Configuration infrastructure (Pydantic models, YAML loaders)
├── context/        Context management (compression engine, session storage)
├── core/           Core engine (Agent, QueryEngine, SubAgent, role management)
├── mcp/            MCP protocol bridging
├── skills/         Skill system (parsing, registration, loading, conditional activation)
├── tools/          Tool abstraction layer (built-in/Shell/MCP/file tools)
├── utils/          Utilities (logging, callbacks)
└── web/            Web frontend (pure HTML + CSS + JS)
```

## Commands

| Command | Description |
|---------|-------------|
| `/help` | Show help information |
| `/quit` | Exit the program |
| `/config` | View or modify configuration |
| `/role` | Switch or manage roles |
| `/skill` | View, load, or manage Skills |
| `/tool` | View available tools |
| `/browser` | Browser-related operations |
| `/history` | View conversation history |
| `/clear` | Clear current conversation |
| `/new` | Start a new conversation |
| `/reload` | Reload configuration |
| `/prompt` | View or edit system prompt |
| `/status` | View current status |
| `/session` | Manage sessions (save, load, list) |

## Configuration Files

| File | Description |
|------|-------------|
| `model_config.yaml` | LLM model configuration (API Key, model name, parameters) |
| `mcp_config.yaml` | MCP server connection configuration |
| `prompt_config.yaml` | System prompt configuration |
| `skills_config.yaml` | Skill system configuration |
| `agent_config.yaml` | Agent behavior configuration (context compression, execution parameters, logging) |
| `project_config.yaml` | Project-level configuration |
| `tools_config.yaml` | Tool system configuration |

## Architecture Documentation

For detailed architecture design, see the [dev_docs/](dev_docs/) directory. Start with the overall framework design at [framework_design.md](dev_docs/framework_design.md).

## License

MIT
