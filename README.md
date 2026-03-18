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

Rubato 是一个自然语言驱动的自动化测试执行框架。用户只需用自然语言描述测试场景，Agent 即可自动解析意图、规划步骤，并通过浏览器自动化工具执行测试。支持 Playwright MCP 工具调用、Skill 动态加载、多 Agent 协作，以及上下文压缩。

## 核心特性

- **自然语言驱动** - 用自然语言描述测试场景，无需编写代码脚本
- **自主规划** - Agent 根据提示词自主推理、规划和执行
- **ReAct 模式** - 通用的推理(Reason) → 行动(Act) → 观察(Observe) 循环
- **多 Agent 协作** - 支持主 Agent 调用子 Agent，子 Agent 有独立的系统提示词和上下文
- **Skill 动态加载** - 启动时加载元数据，对话中按需加载完整内容
- **MCP 工具集成** - 支持 Playwright MCP 进行浏览器自动化操作
- **上下文压缩** - 自动管理对话历史，避免 token 溢出
- **浏览器持久化** - 浏览器在任务间保持打开，支持状态复用和自动重连

## 环境要求

- **Python**: 3.12+
- **Node.js**: 18+ (用于运行 Playwright MCP)
- **操作系统**: Windows / macOS / Linux

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 安装 Playwright MCP

```bash
npm install -g @playwright/mcp
npx playwright install chromium
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

```bash
python -m src.main
```

启动后看到以下界面表示成功：

```
╔══════════════════════════════════════════════════════════╗
║                       Rubato                             ║
╠══════════════════════════════════════════════════════════╣
║ 状态: 模型: gpt-4 | MCP: 已连接
║ 已加载Skills: test-execution
╚══════════════════════════════════════════════════════════╝
```

### 5. 快速测试示例

```
> 打开百度搜索 Python
```

Agent 会自动：
1. 导航到百度首页
2. 调用子 Agent 分析页面快照
3. 识别搜索框和搜索按钮
4. 输入 "Python" 并搜索
5. 截图并返回结果

## 架构设计

### 架构层次

```
┌─────────────────────────────────────────────────────────┐
│                    控制台交互层 (CLI)                      │
│              console.py / commands.py                    │
├─────────────────────────────────────────────────────────┤
│                     核心引擎层                            │
│            agent.py / sub_agents.py                      │
├─────────────────────────────────────────────────────────┤
│                      工具层                              │
│     MCP客户端 / 工具注册表 / Skill加载器                   │
├─────────────────────────────────────────────────────────┤
│                      支撑层                              │
│      上下文管理 / 配置加载 / 日志记录                      │
├─────────────────────────────────────────────────────────┤
│                    配置文件层                            │
│   model_config / mcp_config / prompt_config / skills    │
└─────────────────────────────────────────────────────────┘
```

### 核心设计原则

1. **自然语言驱动**: 用自然语言描述测试场景，Agent 自动解析并执行
2. **自主规划**: Agent 根据提示词自主推理、规划和执行
3. **ReAct 模式**: 通用的推理-行动-观察循环
4. **多 Agent 协作**: 支持主 Agent 调用子 Agent
5. **配置驱动**: 所有配置以文件形式存在，便于管理
6. **Skill 动态加载**: 启动时加载元数据，对话中按需加载完整内容
7. **工具集成**: 支持 MCP 工具调用、子 Agent 工具和 Skill 工具扩展
8. **上下文压缩**: 自动管理对话历史，避免 token 溢出
9. **浏览器持久化**: 浏览器在任务间保持打开，支持状态复用

## 项目结构

```
rubato/
├── src/                    # 源代码
│   ├── main.py            # 程序入口
│   ├── core/              # 核心模块
│   │   ├── agent.py       # 主 Agent
│   │   └── sub_agents.py  # 子 Agent 机制
│   ├── mcp/               # MCP 集成
│   ├── skills/            # Skill 系统
│   ├── context/           # 上下文管理
│   ├── config/            # 配置管理
│   └── cli/               # 命令行界面
├── config/                # 配置文件
├── prompts/               # 提示词
├── skills/                # Skill 文件
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
| `/browser status` | 查看浏览器状态 |
| `/browser close` | 关闭浏览器 |
| `/browser reopen` | 重新打开浏览器 |

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
- langchain-mcp-adapters
- Playwright MCP
- Pydantic

## 常见问题

### MCP 连接失败

1. 确保已安装 Node.js 18+
2. 运行 `npx -y @playwright/mcp` 测试
3. 检查网络连接和防火墙设置

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

## License

MIT License
