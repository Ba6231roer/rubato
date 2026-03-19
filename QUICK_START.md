# Rubato Quick Start Guide

快速上手指南 - 让你5分钟内开始使用 Rubato 执行自然语言测试案例

---

## 1. 环境要求

- **Python**: 3.12+
- **Node.js**: 18+ (用于运行 Playwright CLI)
- **操作系统**: Windows / macOS / Linux

---

## 2. 安装步骤

### 2.1 安装 Python 依赖

```bash
cd rubato
pip install -r requirements.txt
```

### 2.2 安装 Playwright CLI

```bash
# 全局安装 Playwright CLI
npm install -g @playwright/cli@latest

# 验证安装
playwright-cli --help
```

### 2.3 安装 Playwright 浏览器（首次使用）

```bash
npx playwright install chromium
```

---

## 3. 配置项

### 3.1 配置 API 密钥

**方式一：环境变量（推荐）**

```bash
# Windows PowerShell
$env:OPENAI_API_KEY = "your-api-key-here"

# Windows CMD
set OPENAI_API_KEY=your-api-key-here

# Linux/macOS
export OPENAI_API_KEY="your-api-key-here"
```

**方式二：配置文件**

编辑 `config/model_config.yaml`：

```yaml
model:
  provider: "openai"
  name: "gpt-4"              # 或 "gpt-4o", "gpt-3.5-turbo"
  api_key: "your-api-key-here"  # 直接填写或使用 ${OPENAI_API_KEY}
  base_url: null              # 如使用代理，填写代理地址
  temperature: 0.7
  max_tokens: 2000
```

### 3.2 配置 Skills（可选）

编辑 `config/skills_config.yaml` 启用/禁用特定 Skill：

```yaml
skills:
  directory: "skills"
  auto_load: true
  enabled_skills:
    - playwright-cli
    - test-execution
  skill_loading:
    trigger_matching: true
    max_loaded_skills: 3
```

---

## 4. 启动运行

```bash
# 方式一：直接运行
python -m src.main

# 方式二：设置 PYTHONPATH 后运行
set PYTHONPATH=.
python src/main.py
```

启动后看到以下界面表示成功：

```
╔══════════════════════════════════════════════════════════╗
║                       Rubato                             ║
╠══════════════════════════════════════════════════════════╣
║ 状态: 模型: gpt-4 | Skills: playwright-cli, test-execution
╚══════════════════════════════════════════════════════════╝

输入 '/help' 查看帮助，'/quit' 退出

> 
```

---

## 5. 快速测试示例

### 示例 1：简单的搜索测试

```
> 打开百度搜索 Python
```

Agent 会自动：
1. 导航到百度首页
2. 获取页面快照并分析元素
3. 识别搜索框和搜索按钮
4. 输入 "Python" 并搜索
5. 截图并返回结果

### 示例 2：登录流程测试

```
> 打开 https://example.com/login，用户名输入 admin，密码输入 123456，点击登录
```

### 示例 3：表单填写测试

```
> 打开注册页面，填写姓名张三，邮箱 test@example.com，手机 13800138000，提交表单
```

---

## 6. Playwright CLI 工作流程

Rubato 使用 Playwright CLI 进行浏览器自动化，具有以下优势：

### Token 效率高

| 操作 | MCP 方式 | CLI 方式 |
|------|---------|---------|
| 工具定义加载 | ~10000 tokens | ~2500 tokens |
| Snapshot 输出 | ~3000 tokens | ~300 tokens |
| 单次交互总消耗 | ~15000 tokens | ~3000 tokens |

### 工作流程

```
用户输入自然语言测试案例
        ↓
    主Agent分析任务
        ↓
  playwright-cli open 打开浏览器
        ↓
  playwright-cli snapshot 获取页面快照
        ↓
    主Agent直接分析快照（无需调用子Agent）
        ↓
    playwright-cli type/click 执行操作
        ↓
    playwright-cli screenshot 截图
        ↓
    返回结果
```

### 常用命令

| 命令 | 说明 |
|------|------|
| `playwright-cli open <url> --headed` | 打开浏览器并导航 |
| `playwright-cli snapshot` | 获取页面快照 |
| `playwright-cli click <ref>` | 点击元素 |
| `playwright-cli type "<text>"` | 输入文本 |
| `playwright-cli press <key>` | 按键 |
| `playwright-cli screenshot` | 截图 |
| `playwright-cli list` | 列出所有 session |
| `playwright-cli close-all` | 关闭所有浏览器 |

---

## 7. CLI 命令参考

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

---

## 8. 常见问题

### Q1: Playwright CLI 未安装

```
错误：'playwright-cli' 不是内部或外部命令
```

**解决方案**：
```bash
npm install -g @playwright/cli@latest
playwright-cli --help
```

### Q2: API 密钥无效

```
错误：配置加载失败: 未设置API密钥
```

**解决方案**：
1. 检查环境变量是否正确设置
2. 或在 `config/model_config.yaml` 中直接填写 API 密钥

### Q3: 浏览器启动失败

```
错误：浏览器未安装
```

**解决方案**：
```bash
npx playwright install chromium
```

### Q4: 元素定位失败

**解决方案**：
- Agent 会自动获取 snapshot 分析页面
- 可以在对话中提供更精确的元素描述
- Playwright CLI 的 snapshot 输出简洁，Agent 可直接分析

---

## 9. 进阶配置

### 自定义子Agent

在 `sub_agents/` 目录下创建新的 YAML 文件：

```yaml
# sub_agents/my-custom-agent.yaml
name: my-custom-agent
description: 自定义子Agent描述
version: 1.0

system_prompt: |
  你是XXX专家...
  
  任务：...
  
  输出格式：...

execution:
  timeout: 60
  max_retries: 1

tool_permissions:
  inherit_from_parent: true
```

### 自定义 Skill

在 `skills/` 目录下创建新的 Markdown 文件：

```markdown
---
name: my-skill
description: 自定义Skill描述
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

## 使用方法
...
```

---

## 10. 项目结构

```
rubato/
├── src/                    # 源代码
│   ├── main.py            # 程序入口
│   ├── core/              # 核心模块
│   │   ├── agent.py       # 主Agent
│   │   └── sub_agents.py  # 子Agent机制
│   ├── skills/            # Skill系统
│   ├── context/           # 上下文管理
│   ├── config/            # 配置管理
│   └── cli/               # 命令行界面
├── config/                # 配置文件
├── prompts/               # 提示词
├── skills/                # Skill文件
│   └── playwright-cli/    # Playwright CLI Skill
├── sub_agents/            # 子Agent配置
├── logs/                  # 日志目录
└── tests/                 # 测试文件
```

---

## 11. 下一步

1. 尝试运行示例测试案例
2. 根据需要修改配置文件
3. 创建自定义 Skill 扩展功能
4. 创建自定义子Agent处理特定场景

**祝你使用愉快！** 🚀

---

## 附录：使用 Playwright MCP（可选）

如果你需要使用 Playwright MCP 作为替代方案，请参考 [Playwright MCP 配置指南](dev_docs/playwright-mcp-setup.md)。

**注意**: Playwright MCP 的 token 消耗较高，推荐使用默认的 Playwright CLI 方案。
