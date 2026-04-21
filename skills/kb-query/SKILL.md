---
name: kb-query
description: 知识库渐进式检索 - 按步骤检索知识库文档，支持目录浏览、功能概述、关键流程、交互元素等多级检索，最小化上下文token消耗
version: 1.0
author: Rubato Team
triggers:
  - 知识检索
  - 查询知识库
  - 检索文档
  - 读取知识
  - 业务知识
tools:
  - ShellTool
allowed-tools: Bash(python:*)
---

# 知识库渐进式检索

## 知识库文档结构

知识库由 `bs-ui-kb-orchestrator` 编排、`bs-ui-kb-curator` 生成，标准目录结构：

```
{知识库目录}/
├── 目录.md                          # 全局目录，列出所有模块和页面
├── {页面A}_功能概述.md               # 页面核心功能简述
├── {页面A}_可交互元素清单.md         # 页面所有可交互元素
├── {页面A}_关键功能交互流程.md       # 页面关键操作流程（按二级标题分流程）
├── {页面B}_功能概述.md
├── {页面B}_可交互元素清单.md
└── {页面B}_关键功能交互流程.md
```

## 检索脚本

脚本路径：`skills/kb-query/kb_query.py`

## 命令参考

### 读取目录
```bash
python skills/kb-query/kb_query.py <知识库目录> toc
```

### 读取功能概述
```bash
python skills/kb-query/kb_query.py <知识库目录> overview <页面名称>
```

### 列出关键功能交互流程的所有流程标题
```bash
python skills/kb-query/kb_query.py <知识库目录> flows <页面名称>
```
输出格式：`L行号  流程标题`

### 读取某个具体流程的内容
```bash
python skills/kb-query/kb_query.py <知识库目录> flow <页面名称> <流程标题>
```
仅读取指定二级标题下的内容，最小化 token 消耗。

### 读取可交互元素清单
```bash
python skills/kb-query/kb_query.py <知识库目录> elements <页面名称>
```

### 列出任意文件的所有标题和行号
```bash
python skills/kb-query/kb_query.py <知识库目录> headings <文件路径>
```

### 读取任意文件中指定标题下的内容
```bash
python skills/kb-query/kb_query.py <知识库目录> section <文件路径> <标题>
```

## 渐进式检索策略

按以下优先级逐步检索，每步评估是否足够：

1. **目录** → 了解系统全局模块和页面
2. **功能概述** → 了解某页面的核心功能，判断是否为目标页面
3. **关键流程标题** → 列出某页面的所有流程名称
4. **具体流程内容** → 仅读取与需求相关的某个流程
5. **可交互元素** → 需要元素定位或交互细节时读取

每步检索后，由调用者（模型）决定：
- 信息已足够 → 结束检索
- 需要更多细节 → 继续下一步
- 当前页面不相关 → 返回目录重新选择

## 示例

```bash
# 步骤1：了解系统有哪些页面
python skills/kb-query/kb_query.py ./output/my-system toc

# 步骤2：了解"用户管理"页面的核心功能
python skills/kb-query/kb_query.py ./output/my-system overview 用户管理

# 步骤3：列出"用户管理"页面的所有流程
python skills/kb-query/kb_query.py ./output/my-system flows 用户管理

# 步骤4：仅读取"新增用户"流程的详细步骤
python skills/kb-query/kb_query.py ./output/my-system flow 用户管理 "流程1：新增用户"

# 步骤5：如需元素定位信息
python skills/kb-query/kb_query.py ./output/my-system elements 用户管理
```
