# Rubato Quick Start Guide

快速上手指南 - 让你5分钟内开始使用 Rubato 执行自然语言测试案例

---

## 1. 环境要求

- **Python**: 3.12+
- **Node.js**: 18+ (用于运行 Playwright MCP)
- **操作系统**: Windows / macOS / Linux

---

## 2. 安装步骤

### 2.1 安装 Python 依赖

```bash
cd rubato
pip install -r requirements.txt
```

### 2.2 安装 Playwright MCP

```bash
# 全局安装 Playwright MCP 服务器
npm install -g @playwright/mcp

# 或者使用 npx 直接运行（推荐，无需全局安装）
npx -y @playwright/mcp
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

### 3.2 配置 MCP 服务器

编辑 `config/mcp_config.yaml`：

```yaml
mcp:
  playwright:
    enabled: true
    command: "npx"
    args: ["-y", "@playwright/mcp"]
    
    connection:
      retry_times: 3      # 连接重试次数
      retry_delay: 5      # 重试间隔（秒）
      timeout: 30         # 连接超时（秒）
    
    browser:
      type: "chromium"    # chromium / firefox / webkit
      headless: false     # true=无头模式，false=显示浏览器
      viewport:
        width: 1280
        height: 720
```

### 3.3 配置 Skills（可选）

编辑 `config/skills_config.yaml` 启用/禁用特定 Skill：

```yaml
skills:
  directory: "skills"
  auto_load: true
  enabled_skills:
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
║ 状态: 模型: gpt-4 | MCP: 已连接
║ 已加载Skills: test-execution
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
2. 调用子Agent分析页面快照
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

## 6. 子Agent自动调用机制

Rubato 会在需要时**自动调用子Agent**进行页面快照分析：

### 触发条件

当主Agent执行以下操作时，会自动调用 `snapshot-analyzer` 子Agent：

1. **导航到新页面后** - 分析页面结构
2. **需要定位元素时** - 识别可交互元素
3. **操作失败后** - 重新分析页面状态

### 子Agent返回内容

`snapshot-analyzer` 子Agent会返回：

```json
{
  "page_layout": {
    "title": "百度一下，你就知道",
    "main_sections": ["搜索区域", "导航链接"],
    "page_type": "搜索页"
  },
  "interactive_elements": [
    {
      "id": "s1",
      "type": "input",
      "description": "搜索输入框",
      "selector": "#kw",
      "visible_text": ""
    },
    {
      "id": "s2", 
      "type": "button",
      "description": "百度一下搜索按钮",
      "selector": "#su",
      "visible_text": "百度一下"
    }
  ],
  "next_action_recommendation": {
    "element_id": "s1",
    "action_type": "type",
    "action_value": "Python",
    "reason": "根据任务需要在搜索框输入搜索内容"
  }
}
```

### 工作流程图

```
用户输入自然语言测试案例
        ↓
    主Agent分析任务
        ↓
  browser_navigate 导航到目标页面
        ↓
  browser_snapshot 获取页面快照
        ↓
┌─────────────────────────────────────┐
│   spawn_agent("snapshot-analyzer")  │
│   ┌─────────────────────────────┐   │
│   │ 子Agent独立分析快照：        │   │
│   │ 1. 页面布局概况              │   │
│   │ 2. 可交互元素清单            │   │
│   │ 3. 下一步操作推荐            │   │
│   └─────────────────────────────┘   │
└─────────────────────────────────────┘
        ↓
    返回分析结果给主Agent
        ↓
    主Agent执行推荐操作
        ↓
    继续下一步或完成
```

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

### Q1: MCP 连接失败

```
错误：无法连接MCP服务器
```

**解决方案**：
1. 确保已安装 Node.js 18+
2. 运行 `npx -y @playwright/mcp` 测试
3. 检查网络连接和防火墙设置

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
- Agent 会自动尝试多种选择器
- 可以在对话中提供更精确的元素描述
- 子Agent会分析页面快照并推荐最佳选择器

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
│   ├── mcp/               # MCP集成
│   ├── skills/            # Skill系统
│   ├── context/           # 上下文管理
│   ├── config/            # 配置管理
│   └── cli/               # 命令行界面
├── config/                # 配置文件
├── prompts/               # 提示词
├── skills/                # Skill文件
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
