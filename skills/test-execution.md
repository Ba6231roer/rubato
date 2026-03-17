---
name: test-execution
description: 自动化测试执行能力
version: 1.0
author: rubato
triggers:
  - 测试
  - 执行测试
  - 测试案例
---

# Test Execution Skill

## 功能说明
提供自动化测试执行能力，支持自然语言描述测试案例。

## 使用场景
- 用户需要执行浏览器自动化测试
- 用户描述测试步骤
- 用户验证测试结果

## 工作方法
1. 理解用户的测试需求
2. 分析测试步骤
3. 调用Playwright工具执行
4. 验证结果并报告

## 示例对话
用户: 打开百度搜索Python
助手: 我将执行以下步骤：
1. 导航到百度首页
2. 在搜索框输入"Python"
3. 点击搜索按钮

[调用工具: browser_navigate]
[调用工具: browser_type]
[调用工具: browser_click]

测试执行完成！
