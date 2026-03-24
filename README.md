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
- **多 Agent 协作** - 支持主 Agent 调用子 Agent，子 Agent 有独立的系统提示词和上下文
- **Skill 动态加载** - 启动时加载元数据，对话中按需加载完整内容
- **Playwright CLI 集成** - 支持 Playwright CLI 进行浏览器自动化操作，Token 效率高
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

## 架构设计

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
│            agent.py / sub_agents.py                      │
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
4. **多 Agent 协作**: 支持主 Agent 调用子 Agent
5. **配置驱动**: 所有配置以文件形式存在，便于管理
6. **Skill 动态加载**: 启动时加载元数据，对话中按需加载完整内容
7. **工具集成**: 支持 ShellTool 执行 CLI 命令、子 Agent 工具和 Skill 工具扩展
8. **上下文压缩**: 自动管理对话历史，避免 token 溢出
9. **浏览器持久化**: 浏览器作为独立进程运行，支持状态复用
10. **双模式运行**: 支持 CLI 命令行和 Web UI 两种交互模式
11. **HTTP 服务层**: 提供 RESTful API 和 WebSocket 接口
12. **轻量前端**: 纯 HTML/CSS/JS 实现，零构建依赖

## 项目结构

```
rubato/
├── src/                    # 源代码
│   ├── main.py            # 程序入口（支持CLI/Web模式）
│   ├── core/              # 核心模块
│   │   ├── agent.py       # 主 Agent
│   │   └── sub_agents.py  # 子 Agent 机制
│   ├── api/               # HTTP服务层
│   │   ├── app.py         # FastAPI应用
│   │   ├── routes/        # API路由
│   │   └── websocket.py   # WebSocket处理
│   ├── web/               # Web UI
│   │   ├── templates/     # HTML模板
│   │   └── static/        # 静态资源
│   ├── skills/            # Skill 系统
│   ├── context/           # 上下文管理
│   ├── config/            # 配置管理
│   └── cli/               # 命令行界面
├── config/                # 配置文件
├── prompts/               # 提示词
├── skills/                # Skill 文件
│   └── playwright-cli/    # Playwright CLI Skill
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
| `/skill list` | 列出所有可用 Skills |
| `/skill show <name>` | 显示 Skill 详情 |
| `/tool list` | 列出所有可用工具 |
| `/prompt show` | 显示当前系统提示词 |

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
- Playwright CLI
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

## 详细文档

- [快速上手指南](QUICK_START.md)
- [架构设计文档](dev_docs/design.md)
- [Playwright CLI 迁移设计](dev_docs/playwright-cli-migration-design.md)
- [Playwright MCP 配置指南（可选）](dev_docs/playwright-mcp-setup.md)

## License

MIT License
