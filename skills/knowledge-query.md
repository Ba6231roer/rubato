---
name: knowledge-query
description: 知识查询 - 查询相关业务知识和历史功能设计
version: 1.0
author: Rubato Team
triggers:
  - 知识查询
  - 查询知识
  - 业务知识
  - 历史功能
tools:
  - file_search
  - file_read
---

# 知识查询Skill

## 功能
查询相关业务知识和历史功能设计，辅助测试案例生成。

## 使用方法
通过 `spawn_agent` 工具调用：
```
spawn_agent(agent_name="knowledge-query", task="查询[关键词]相关业务知识")
```

## 当前状态
**占位实现**：暂时返回"未找到相关知识"，后续可扩展实现真实的知识查询功能。

## 返回格式
```
查询结果：
- 相关业务知识：[知识内容或"未找到相关知识"]
- 历史功能设计：[设计文档或"未找到相关设计"]
```

## 后续扩展方向
1. 集成知识库系统
2. 支持语义搜索
3. 支持历史项目文档查询
