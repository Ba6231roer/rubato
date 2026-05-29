---
name: webui-cache
description: WebUI 页面元素缓存系统，与 playwright-cli 配合使用。存储页面的稳定 locator，避免重复 snapshot 调用。在对已访问过的页面进行浏览器自动化时使用。
version: 1.0
triggers:
  - 缓存
  - cache
  - 页面缓存
  - 元素缓存
  - webui cache
tools:
  - ShellTool
  - FileTools
allowed-tools: Bash(playwright-cli:*)
---

# WebUI 页面元素缓存系统

## 缓存系统概述

webui-cache 通过缓存页面的稳定 Playwright locator 来减少 snapshot 调用，提升浏览器自动化效率。

**核心工作流程**：

```
snapshot → 找到 ref → generate-locator → 缓存 → 复用
```

1. 首次访问页面：执行 `snapshot` 获取页面元素 ref
2. 使用 `playwright-cli generate-locator <ref>` 将不稳定的 ref 转换为稳定的 locator
3. 将 locator 写入 YAML 缓存文件
4. 后续访问同一页面：直接读取缓存 locator，无需 snapshot
5. 若缓存 locator 失效：回退到 snapshot + generate-locator 流程，更新缓存

## 缓存目录结构

```
webui_cache/
├── INDEX.yaml              # 缓存目录索引
├── <system_name>/           # 按系统划分子目录
│   ├── <page_name>.yaml     # 单页缓存文件
│   └── ...
└── _templates/
    └── page_template.yaml   # 新建缓存文件参考模板
```

## INDEX.yaml 格式

索引文件记录所有已缓存的系统和页面，便于快速查找：

```yaml
systems:
  - name: example_system
    description: 示例系统
    pages:
      - name: login
        file: example_system/login.yaml
        url_patterns:
          - "https://example.com/login"
        description: 登录页面
        last_verified: "2026-05-22"
      - name: dashboard
        file: example_system/dashboard.yaml
        url_patterns:
          - "https://example.com/dashboard"
        description: 仪表盘页面
        last_verified: "2026-05-22"
```

## 页面缓存文件格式

每个页面的缓存文件包含以下部分：

```yaml
page:
  system: example_system        # 所属系统名称
  name: login                   # 页面名称
  url_patterns:                 # 页面 URL 匹配模式（支持多个）
    - "https://example.com/login"
  description: 登录页面          # 页面描述

elements:                       # 页面元素缓存列表
  - id: username_input          # 元素唯一标识
    description: 用户名输入框    # 元素描述
    locator: "getByRole('textbox', { name: '用户名' })"  # Playwright locator
    action_type: fill           # 操作类型: click / fill / eval / select / hover
    usage: 输入登录用户名         # 使用说明

  - id: password_input
    description: 密码输入框
    locator: "getByRole('textbox', { name: '密码' })"
    action_type: fill
    usage: 输入登录密码

  - id: login_button
    description: 登录按钮
    locator: "getByRole('button', { name: '登录' })"
    action_type: click
    usage: 点击提交登录表单

workflows:                      # 多步骤操作流程
  - name: 登录流程
    description: 标准登录操作流程
    steps:
      - action: fill
        element: username_input
        description: 输入用户名
      - action: fill
        element: password_input
        description: 输入密码
      - action: click
        element: login_button
        description: 点击登录按钮

last_verified: "2026-05-22"     # 最后验证时间
version: 1                      # 缓存版本号
```

**字段说明**：

| 字段 | 说明 |
|------|------|
| `page.system` | 所属系统名称，对应 `webui_cache/` 下的子目录名 |
| `page.url_patterns` | URL 匹配模式列表，支持包含 `*` 通配符的部分匹配 |
| `elements[].id` | 元素唯一标识，在页面内不可重复，供 `workflows` 引用 |
| `elements[].locator` | Playwright 稳定 locator 字符串，由 `generate-locator` 生成 |
| `elements[].action_type` | 该元素支持的交互类型 |
| `workflows` | 可选，预定义的多步骤操作流程，步骤中的 `element` 引用 `elements[].id` |

## 缓存使用流程（CRITICAL）

### 步骤 1：任务开始时读取索引

每个浏览器自动化任务开始时，**必须先读取** `webui_cache/INDEX.yaml` 了解可用的缓存：

```bash
read_file webui_cache/INDEX.yaml
```

### 步骤 2：导航到页面时检查缓存

当使用 `playwright-cli goto <url>` 导航到某个页面后，检查该页面 URL 是否匹配已有缓存：

- 匹配规则：URL 与缓存文件中 `url_patterns` 的任一模式匹配（支持 `*` 通配符）
- 若匹配成功，读取对应的 YAML 缓存文件

### 步骤 3：使用缓存 locator（优先）

**如果有缓存，直接使用缓存 locator，不要先执行 snapshot**：

```bash
playwright-cli goto https://example.com/login
# 有缓存：直接使用 locator
playwright-cli fill "getByRole('textbox', { name: '用户名' })" "admin"
playwright-cli fill "getByRole('textbox', { name: '密码' })" "password123"
playwright-cli click "getByRole('button', { name: '登录' })"
```

### 步骤 4：缓存 locator 失效时回退

如果缓存 locator 执行失败（元素未找到等错误），执行回退流程：

```bash
# 缓存 locator 失败
playwright-cli click "getByRole('button', { name: '登录' })"
# → Error: element not found

# 回退：执行 snapshot 获取当前页面结构
playwright-cli snapshot

# 从 snapshot 中找到目标元素的 ref（如 e15）
playwright-cli generate-locator e15
# → 输出新的 locator 字符串

# 用新 locator 执行操作
playwright-cli click "getByRole('button', { name: 'Sign in' })"

# 更新缓存文件中的 locator
```

### 步骤 5：无缓存时创建缓存

如果页面无缓存，执行正常的 snapshot 流程，操作成功后创建缓存文件：

1. 执行 `playwright-cli snapshot`
2. 对需要交互的元素使用 `generate-locator` 生成稳定 locator
3. 操作成功后，创建/更新缓存文件
4. 更新 `webui_cache/INDEX.yaml`

## 多环境 URL 匹配

同一业务系统可能有多个测试环境（如 `www.test1.baidu.com` 和 `www.test2.baidu.com`），URL 不同但页面结构几乎一致。缓存支持跨环境复用：

### URL 通配符模式
`url_patterns` 支持使用 `*` 通配符匹配多变部分：
- `https://www.test*.baidu.com/login` — 匹配所有测试环境的登录页
- `https://*.example.com/dashboard` — 匹配任意子域名的仪表盘
- `https://example.com/user/*/profile` — 匹配路径中的动态段

### 缓存匹配判断
判断页面是否有缓存时，按以下优先级：
1. **精确 URL 匹配**：当前 URL 与缓存文件中的 url_patterns 某一项完全一致
2. **通配符 URL 模式匹配**：当前 URL 与通配符模式匹配（`*` 匹配任意字符）
3. **页面结构相似性判断**：同路径不同域名，页面标题和结构相似时可共用缓存

### 示例
假设缓存文件的 url_patterns 为 `https://www.test*.baidu.com/login`：
- `https://www.test1.baidu.com/login` → 命中（通配符匹配）
- `https://www.test2.baidu.com/login` → 命中（通配符匹配）
- `https://www.prod.baidu.com/login` → 未命中（但可按相似性判断是否复用）

## generate-locator 命令

将 snapshot 中不稳定的 ref 引用转换为稳定的 Playwright locator：

```bash
# 基本用法
playwright-cli generate-locator <ref>

# 示例
playwright-cli snapshot
# snapshot 输出中包含 ref: e15 → 用户名输入框

playwright-cli generate-locator e15
# 输出: getByRole('textbox', { name: '用户名' })
```

转换后的 locator 可以直接用于 click / fill / hover 等命令：
```bash
playwright-cli fill "getByRole('textbox', { name: '用户名' })" "admin"
```

## Locator 策略优先级

生成 locator 时，按以下优先级从最稳定到最不稳定选择：

| 优先级 | 策略 | 示例 |
|--------|------|------|
| 1 | `getByTestId` | `getByTestId('submit-btn')` |
| 2 | `getByRole` | `getByRole('button', { name: '登录' })` |
| 3 | `getByText` | `getByText('提交订单')` |
| 4 | `getByLabel` | `getByLabel('用户名')` |
| 5 | CSS Selector | `page.locator('.login-form .submit')` |
| 6 | XPath（最后手段） | `page.locator('//button[@type="submit"]')` |

**原则**：优先使用语义化 locator（testId > role > text > label），避免使用结构相关的 CSS/XPath。当页面 DOM 结构变化时，语义化 locator 更不容易失效。

## 缓存创建/更新规范

### 创建新缓存文件

1. 参考模板：`webui_cache/_templates/page_template.yaml`
2. 在 `webui_cache/<system_name>/` 下创建 `<page_name>.yaml`
3. 填写 `page` 信息（system、name、url_patterns、description）
4. 对每个需要缓存的元素：
   - 执行 `playwright-cli snapshot` 获取 ref
   - 执行 `playwright-cli generate-locator <ref>` 获取稳定 locator
   - **操作验证成功后再写入缓存**（先执行操作，确认无误）
5. 根据需要编写 `workflows` 预定义流程

### 更新索引文件

每次新增、删除页面缓存时，必须同步更新 `webui_cache/INDEX.yaml`。

### 更新已有缓存

当 locator 失效时：
1. 回退到 snapshot + generate-locator（参见步骤 4）
2. 更新对应元素的 `locator` 字段
3. 更新 `last_verified` 时间戳

## 重要注意事项

1. **locator 必须用双引号包裹** - 传入 shell 命令时：
   ```bash
   # 正确
   playwright-cli click "getByRole('button', { name: '登录' })"
   # 错误：shell 会错误解析单引号
   playwright-cli click getByRole('button', { name: '登录' })
   ```

2. **连续 3 个以上缓存 locator 失效** - 表明页面结构可能发生重大变化，应当**重建整个页面缓存**：
   - 重新执行 snapshot
   - 对所有元素重新 generate-locator
   - 完全重写缓存文件

3. **SPA 页面处理** - 对于 URL 不变化的单页应用，不同的页面状态应通过以下方式区分：
   - 在 `page.name` 中使用描述性名称（如 `dashboard_default`、`dashboard_settings`）
   - 在 `page.description` 中明确当前状态
   - 在 `url_patterns` 中尽可能使用带 hash 或 query 的 URL 模式

4. **先验证再缓存** - 生成 locator 后，必须先执行对应操作确认成功，再将 locator 写入缓存。不要缓存未经验证的 locator。

5. **缓存粒度** - 只需缓存当前任务可能交互的元素，不必缓存页面上所有元素。按需缓存，保持文件精简。