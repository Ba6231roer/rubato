# Rubato

<p align="center">
  <strong>自然语言驱动的自动化测试执行框架</strong>
</p>

<p align="center">
  <a href="#核心特性">核心特性</a> •
  <a href="#环境要求">环境要求</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#架构设计">架构设计</a> •
  <a href="README_EN.md">English</a>
</p>

---

## 项目简介

Rubato 是一个自然语言驱动的自动化测试执行框架。用户只需用自然语言描述测试场景，Agent 即可自动解析意图、规划步骤，并通过浏览器自动化工具执行测试。支持 Playwright CLI 工具调用、Skill 动态加载、多 Agent 协作，以及上下文压缩。

## 核心特性

- **自然语言驱动** - 用自然语言描述测试场景，无需编写代码脚本
- **自主规划** - Agent 根据提示词自主推理、规划和执行
- **ReAct 模式** - 通用的推理(Reason) → 行动(Act) → 观察(Observe) 循环
- **双流程架构** - 支持 LangGraph ReAct Agent 和 Query Engine 两种执行模式
- **Query Engine** - 完整的对话生命周期管理，支持预算控制、中断恢复、使用量统计
- **多 Agent 协作** - 支持主 Agent 调用子 Agent，子 Agent 有独立的系统提示词和上下文
- **角色系统** - 支持多角色配置，不同角色可拥有独立的系统提示词、模型配置和工具集
- **多实例并行** - 支持多 Agent 实例并行执行任务，提高效率
- **Skill 动态加载** - 启动时加载元数据，对话中按需加载完整内容
- **Playwright CLI 集成** - 通过 ShellTool 执行 playwright-cli 命令进行浏览器自动化，Token 效率高
- **Playwright MCP（可选）** - 支持 Playwright MCP 作为替代方案，默认禁用
- **上下文压缩** - 自动管理对话历史，避免 token 溢出
- **浏览器持久化** - 浏览器作为独立进程运行，支持状态复用和跨会话持久化
- **双模式运行** - 支持 CLI 命令行和 Web UI 两种交互模式
- **HTTP 服务层** - 提供 RESTful API 和 WebSocket 接口，支持配置管理和实时通信
- **轻量前端** - 纯 HTML/CSS/JS 实现，零构建依赖，易于部署

## 环境要求

- **Python**: 3.12+
- **Node.js**: 18+ (用于运行 Playwright CLI)
- **操作系统**: Windows / macOS / Linux

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 安装 Playwright CLI

```bash
npm install -g @playwright/cli@latest
playwright-cli --help
```

> **提示**：Playwright CLI 是推荐的浏览器自动化方式。如需使用 Playwright MCP 替代方案，请在 `config/mcp_config.yaml` 中启用。

### 3. 配置 API 密钥

**方式一：环境变量（推荐）**

```bash
# Windows PowerShell
$env:OPENAI_API_KEY = "your-api-key-here"

# Linux/macOS
export OPENAI_API_KEY="your-api-key-here"
```

**方式二：配置文件**

编辑 `config/model_config.yaml`：

```yaml
model:
  provider: "openai"
  name: "gpt-4"
  api_key: "your-api-key-here"
```

### 4. 启动运行

**CLI 模式（默认）**

```bash
python -m src.main
```

**Web 模式**

```bash
# 默认端口 8000
python -m src.main --web

# 指定端口
python -m src.main --web --port 8080
```

启动后看到以下界面表示成功：

**CLI 模式**
```
╔══════════════════════════════════════════════════════════╗
║                       Rubato                             ║
╠══════════════════════════════════════════════════════════╣
║ 状态: 模型: gpt-4 | Skills: playwright-cli, test-execution
╚══════════════════════════════════════════════════════════╝
```

**Web 模式**
```
HTTP服务已启动: http://127.0.0.1:8000
按 Ctrl+C 停止服务
```

浏览器访问 `http://127.0.0.1:8000` 即可使用 Web 控制台。

### 5. 快速测试示例

```
> 打开百度搜索 Python
```

Agent 会自动：
1. 导航到百度首页
2. 获取页面快照并分析元素
3. 识别搜索框和搜索按钮
4. 输入 "Python" 并搜索
5. 截图并返回结果

### 6. 使用 Query Engine（高级）

如果需要预算控制、中断恢复等高级功能，可以使用 Query Engine：

```python
from src.core.query_engine import QueryEngine, QueryEngineConfig

config = QueryEngineConfig(
    cwd="/workspace",
    llm=llm_instance,
    tools=tools,
    skills=skills,
    can_use_tool=lambda name, args: True,
    get_app_state=lambda: {},
    set_app_state=lambda state: None,
    max_budget_usd=1.0,
    max_turns=10
)

engine = QueryEngine(config)

async for message in engine.submit_message("执行测试任务"):
    if message.type == "assistant":
        print(message.content)
    elif message.type == "result":
        usage = engine.get_usage()
        print(f"完成，费用: ${usage.cost_usd:.4f}")
```

详细使用方法请参考 [Query Engine 使用指南](docs/query_engine_guide.md)。

## 架构设计

### 双流程架构

Rubato 实现了双流程架构，支持两种执行模式：

#### 流程一：LangGraph ReAct Agent（默认）

```
用户输入 → Console → RubatoAgent → LangGraph ReAct Agent → Tools/Skills
                         ↓
                  ContextManager
                         ↓
                   MessageCompression
```

**特点**：简洁高效，适合大多数场景

#### 流程二：Query Engine（高级）

```
用户输入 → Console → QueryEngine → LLMCaller → Tools/Skills
                         ↓
                  AbortController
                         ↓
                   Usage Tracking
                         ↓
                  Budget Control
```

**特点**：完整的生命周期管理，支持预算控制、中断恢复

### 架构层次

```
┌─────────────────────────────────────────────────────────┐
│                 Web交互层 (Web UI)                        │
│              浏览器 / WebSocket客户端                      │
├─────────────────────────────────────────────────────────┤
│                 HTTP服务层 (API)                          │
│         FastAPI / WebSocket / 配置管理API                 │
├─────────────────────────────────────────────────────────┤
│                    控制台交互层 (CLI)                      │
│              console.py / commands.py                    │
├─────────────────────────────────────────────────────────┤
│                     核心引擎层                            │
│    agent.py / query_engine.py / sub_agents.py           │
├─────────────────────────────────────────────────────────┤
│                      工具层                              │
│     ShellTool / 工具注册表 / Skill加载器                  │
├─────────────────────────────────────────────────────────┤
│                      支撑层                              │
│      上下文管理 / 配置加载 / 日志记录                      │
├─────────────────────────────────────────────────────────┤
│                    配置文件层                            │
│   model_config / prompt_config / skills                 │
└─────────────────────────────────────────────────────────┘
```

### 核心设计原则

1. **自然语言驱动**: 用自然语言描述测试场景，Agent 自动解析并执行
2. **自主规划**: Agent 根据提示词自主推理、规划和执行
3. **ReAct 模式**: 通用的推理-行动-观察循环
4. **双流程架构**: 支持 LangGraph ReAct Agent 和 Query Engine 两种执行模式
5. **Query Engine**: 完整的对话生命周期管理，支持预算控制、中断恢复
6. **多 Agent 协作**: 支持主 Agent 调用子 Agent
7. **配置驱动**: 所有配置以文件形式存在，便于管理
8. **Skill 动态加载**: 启动时加载元数据，对话中按需加载完整内容
9. **工具集成**: 支持 ShellTool 执行 CLI 命令、子 Agent 工具和 Skill 工具扩展
10. **上下文压缩**: 自动管理对话历史，避免 token 溢出
11. **浏览器持久化**: 浏览器作为独立进程运行，支持状态复用
12. **双模式运行**: 支持 CLI 命令行和 Web UI 两种交互模式
13. **HTTP 服务层**: 提供 RESTful API 和 WebSocket 接口
14. **轻量前端**: 纯 HTML/CSS/JS 实现，零构建依赖

## 项目结构

```
rubato/
├── src/                    # 源代码
│   ├── main.py            # 程序入口（支持CLI/Web模式）
│   ├── core/              # 核心模块
│   │   ├── agent.py       # 主 Agent
│   │   ├── agent_pool.py  # Agent 实例池
│   │   ├── role_manager.py # 角色管理器
│   │   └── sub_agents.py  # 子 Agent 机制
│   ├── api/               # HTTP服务层
│   │   ├── app.py         # FastAPI应用
│   │   ├── routes/        # API路由
│   │   └── websocket.py   # WebSocket处理
│   ├── web/               # Web UI
│   │   ├── templates/     # HTML模板
│   │   └── static/        # 静态资源
│   ├── commands/          # 命令系统
│   ├── skills/            # Skill 系统
│   ├── context/           # 上下文管理
│   ├── config/            # 配置管理
│   └── cli/               # 命令行界面
├── config/                # 配置文件
│   ├── model_config.yaml  # 模型配置
│   ├── agent_config.yaml  # Agent配置
│   ├── mcp_config.yaml    # MCP配置
│   └── roles/             # 角色配置
├── prompts/               # 提示词
│   └── roles/             # 角色提示词
├── skills/                # Skill 文件
│   ├── playwright-cli/    # Playwright CLI Skill（推荐）
│   │   ├── SKILL.md       # 主 Skill 文件
│   │   └── references/    # 参考文档
│   └── test-execution.md  # 测试执行 Skill
├── sub_agents/            # 子 Agent 配置
├── logs/                  # 日志目录
└── tests/                 # 测试文件
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助信息 |
| `/quit` 或 `/exit` | 退出程序 |
| `/config` | 显示当前配置 |
| `/history` | 显示对话历史 |
| `/clear` | 清空对话历史 |
| `/new` | 开始新对话（保留角色和系统提示词） |
| `/reload` | 重新加载所有配置（模型、角色、Skill） |
| `/status` | 显示当前状态概览（角色、工具数量、提示词长度） |
| `/status full` | 显示完整状态信息（包含完整系统提示词和工具列表） |
| `/status tools` | 显示当前可用工具 |
| `/status prompt` | 显示完整系统提示词（包含工具说明） |
| `/skill list` | 列出所有可用 Skills |
| `/skill show <name>` | 显示 Skill 详情 |
| `/tool list` | 列出所有可用工具 |
| `/prompt show` | 显示当前系统提示词 |
| `/role <name>` | 切换到指定角色 |
| `/role list` | 列出所有可用角色 |
| `/role show <name>` | 显示角色详细信息 |
| `/browser status` | 查看浏览器状态（需启用MCP） |
| `/browser close` | 关闭浏览器（需启用MCP） |
| `/browser reopen` | 重新打开浏览器（需启用MCP） |

## 扩展性

### 自定义 Skill

在 `skills/` 目录下创建新的 Markdown 文件：

```markdown
---
name: my-skill
description: 自定义 Skill 描述
version: 1.0
triggers:
  - 触发词1
  - 触发词2
tools:
  - ShellTool
---

# My Skill

## 功能说明
...
```

### 自定义子 Agent

在 `sub_agents/` 目录下创建新的 YAML 文件：

```yaml
name: my-custom-agent
description: 自定义子 Agent 描述
version: 1.0

system_prompt: |
  你是 XXX 专家...
  
  任务：...

execution:
  timeout: 60
  max_retries: 1
```

## 技术栈

- Python 3.12
- LangChain 0.3.25
- LangGraph 0.4.5
- FastAPI 0.109+
- Uvicorn 0.27+
- Playwright CLI（推荐）
- Playwright MCP（可选）
- Pydantic

## 常见问题

### Playwright CLI 未安装

```bash
npm install -g @playwright/cli@latest
playwright-cli --help
```

### API 密钥无效

1. 检查环境变量是否正确设置
2. 或在 `config/model_config.yaml` 中直接填写 API 密钥

### 浏览器启动失败

```bash
npx playwright install chromium
```

### Playwright MCP 连接失败（如使用 MCP 替代方案）

1. 检查 `config/mcp_config.yaml` 中 `enabled: true`
2. 确认 Playwright MCP 已正确安装
3. 检查网络连接

## 详细文档

- [快速上手指南](QUICK_START.md)
- [架构设计文档](dev_docs/design.md)
- [Query Engine API 文档](docs/query_engine_api.md)
- [Query Engine 使用指南](docs/query_engine_guide.md)
- [Playwright CLI 迁移设计](dev_docs/playwright-cli-migration-design.md)
- [Playwright MCP 配置指南（可选）](dev_docs/playwright-mcp-setup.md)

## License

MIT License
