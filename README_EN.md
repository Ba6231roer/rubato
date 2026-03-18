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

Rubato is a natural language-driven automated test execution framework. Users simply describe test scenarios in natural language, and the agent automatically parses the intent, plans the steps, and executes tests through browser automation tools. It supports Playwright MCP tool calling, dynamic Skill loading, multi-agent collaboration, and context compression.

## Key Features

- **Natural Language-Driven** - Describe test scenarios in natural language, no coding required
- **Autonomous Planning** - Agent autonomously reasons, plans, and executes based on prompts
- **ReAct Pattern** - Universal Reason → Act → Observe loop
- **Multi-Agent Collaboration** - Supports main agent calling sub-agents with independent system prompts and contexts
- **Dynamic Skill Loading** - Loads metadata at startup, full content on-demand during conversations
- **MCP Tool Integration** - Supports Playwright MCP for browser automation
- **Context Compression** - Automatically manages conversation history to avoid token overflow
- **Browser Persistence** - Browser stays open between tasks, supporting state reuse and auto-reconnection

## Requirements

- **Python**: 3.12+
- **Node.js**: 18+ (for running Playwright MCP)
- **OS**: Windows / macOS / Linux

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright MCP

```bash
npm install -g @playwright/mcp
npx playwright install chromium
```

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

```bash
python -m src.main
```

You'll see the following interface when successfully started:

```
╔══════════════════════════════════════════════════════════╗
║                       Rubato                             ║
╠══════════════════════════════════════════════════════════╣
║ Status: Model: gpt-4 | MCP: Connected
║ Loaded Skills: test-execution
╚══════════════════════════════════════════════════════════╝
```

### 5. Quick Test Example

```
> Open Baidu and search for Python
```

The agent will automatically:
1. Navigate to Baidu homepage
2. Call sub-agent to analyze page snapshot
3. Identify search box and search button
4. Type "Python" and search
5. Take screenshot and return results

## Architecture

### Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│                 Console Interaction Layer                │
│              console.py / commands.py                    │
├─────────────────────────────────────────────────────────┤
│                    Core Engine Layer                     │
│            agent.py / sub_agents.py                      │
├─────────────────────────────────────────────────────────┤
│                       Tool Layer                         │
│     MCP Client / Tool Registry / Skill Loader            │
├─────────────────────────────────────────────────────────┤
│                     Support Layer                        │
│      Context Manager / Config Loader / Logger            │
├─────────────────────────────────────────────────────────┤
│                  Configuration Layer                     │
│   model_config / mcp_config / prompt_config / skills     │
└─────────────────────────────────────────────────────────┘
```

### Core Design Principles

1. **Natural Language-Driven**: Describe test scenarios in natural language, agent automatically parses and executes
2. **Autonomous Planning**: Agent autonomously reasons, plans, and executes based on prompts
3. **ReAct Pattern**: Universal Reason-Act-Observe loop
4. **Multi-Agent Collaboration**: Supports main agent calling sub-agents
5. **Configuration-Driven**: All configurations exist as files for easy management
6. **Dynamic Skill Loading**: Loads metadata at startup, full content on-demand
7. **Tool Integration**: Supports MCP tool calling, sub-agent tools, and Skill tool extensions
8. **Context Compression**: Automatically manages conversation history to avoid token overflow
9. **Browser Persistence**: Browser stays open between tasks, supporting state reuse

## Project Structure

```
rubato/
├── src/                    # Source code
│   ├── main.py            # Entry point
│   ├── core/              # Core modules
│   │   ├── agent.py       # Main agent
│   │   └── sub_agents.py  # Sub-agent mechanism
│   ├── mcp/               # MCP integration
│   ├── skills/            # Skill system
│   ├── context/           # Context management
│   ├── config/            # Configuration management
│   └── cli/               # Command-line interface
├── config/                # Configuration files
├── prompts/               # Prompts
├── skills/                # Skill files
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
| `/skill list` | List all available Skills |
| `/skill show <name>` | Show Skill details |
| `/tool list` | List all available tools |
| `/prompt show` | Display current system prompt |
| `/browser status` | Check browser status |
| `/browser close` | Close browser |
| `/browser reopen` | Reopen browser |

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
- langchain-mcp-adapters
- Playwright MCP
- Pydantic

## Troubleshooting

### MCP Connection Failed

1. Ensure Node.js 18+ is installed
2. Run `npx -y @playwright/mcp` to test
3. Check network connection and firewall settings

### Invalid API Key

1. Check if environment variable is set correctly
2. Or fill in the API key directly in `config/model_config.yaml`

### Browser Startup Failed

```bash
npx playwright install chromium
```

## Documentation

- [Quick Start Guide](QUICK_START.md) (Chinese)
- [Architecture Design Document](dev_docs/design.md) (Chinese)

## License

MIT License
