# Rubato

自然语言驱动的自动化测试执行框架

## 核心特性

- **ReAct + Skills 架构** — LLM 推理 + 工具调用循环 + 自然语言工作流片段
- **多级上下文压缩** — 四级渐进压缩管线（boundary → budget → snip → auto），防止上下文溢出
- **系统提示词分段管理** — 按变化频率分层存储，支持 Skill 独立加载/卸载/过期移除
- **会话持久化与恢复** — 对话增量保存、历史会话加载、SubAgent 会话关联
- **子智能体机制** — 任务分解与专业化处理，支持多层嵌套
- **角色系统** — 多角色配置，实现不同场景下的智能体行为定制
- **双模式交互** — CLI 控制台模式 + Web HTTP 模式
- **工具系统集成** — 内置工具、MCP 工具、文件工具、Shell 工具
- **结构化流式输出** — WebSocket 结构化消息，支持文本/工具调用/错误等类型区分

## 技术栈

| 技术 | 用途 |
|------|------|
| Python >=3.12 | 项目主体语言 |
| LangChain | LLM 调用、工具集成、回调处理 |
| FastAPI | HTTP 服务层、REST API |
| Pydantic | 配置模型、API 数据模型 |
| tiktoken | 上下文 token 精确计数 |
| pathspec | Skill 条件激活的 GitWildMatch 模式 |
| PyYAML | YAML 配置文件加载 |
| asyncio | 全异步架构 |

## 快速开始

### 环境要求

- Python >=3.12

### 安装

```bash
# 创建虚拟环境（推荐）
python -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate  # Linux/macOS

# 安装项目
pip install -e .
```

### 配置

编辑 `config/` 目录下的 YAML 文件。其中 `model_config.yaml` 需配置 API Key 和模型信息。

### 运行

```bash
# CLI 模式
python -m src.main

# Web 模式
python -m src.main --web --port 8000
```

## 项目结构

```
src/
├── api/            HTTP 服务层（FastAPI、WebSocket、REST API）
├── cli/            控制台交互
├── commands/       命令系统（解析、注册、分发）
├── config/         配置基础设施（Pydantic 模型、YAML 加载器）
├── context/        上下文管理（压缩引擎、会话存储）
├── core/           核心引擎（Agent、QueryEngine、SubAgent、角色管理）
├── mcp/            MCP 协议桥接
├── skills/         Skill 系统（解析、注册、加载、条件激活）
├── tools/          工具抽象层（内置/Shell/MCP/文件工具）
├── utils/          通用工具（日志、回调）
└── web/            Web 前端（纯 HTML + CSS + JS）
```

## 命令列表

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助信息 |
| `/quit` | 退出程序 |
| `/config` | 查看或修改配置 |
| `/role` | 切换或管理角色 |
| `/skill` | 查看、加载或管理 Skill |
| `/tool` | 查看可用工具 |
| `/browser` | 浏览器相关操作 |
| `/history` | 查看对话历史 |
| `/clear` | 清除当前对话 |
| `/new` | 新建对话 |
| `/reload` | 重新加载配置 |
| `/prompt` | 查看或编辑系统提示词 |
| `/status` | 查看当前状态 |
| `/session` | 管理会话（保存、加载、列表） |

## 配置文件

| 文件 | 说明 |
|------|------|
| `model_config.yaml` | LLM 模型配置（API Key、模型名称、参数） |
| `mcp_config.yaml` | MCP 服务器连接配置 |
| `prompt_config.yaml` | 系统提示词配置 |
| `skills_config.yaml` | Skill 系统配置 |
| `agent_config.yaml` | Agent 行为配置（上下文压缩、执行参数、日志） |
| `project_config.yaml` | 项目级配置 |
| `tools_config.yaml` | 工具系统配置 |

## 架构文档

详细架构设计见 [dev_docs/](dev_docs/) 目录，整体框架设计参考 [framework_design.md](dev_docs/framework_design.md)。

## License

MIT
