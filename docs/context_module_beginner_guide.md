# Context 模块小白版说明

## 读完这篇你能明白什么

- AI 聊着聊着"记性不够用了"是怎么回事，系统怎么解决这个问题的
- "四级压缩管线"每一级具体干了什么，为什么要分四级
- 各种术语到底什么意思：管线、boundary、LRU、断路器、PTL重试、Token预算……
- 工具结果太大了怎么办（存磁盘 + 替换为预览）
- 用户的"最初任务"怎么保证不被压缩丢掉
- 对话历史怎么保存到文件、怎么恢复

***

## 一、这个模块解决什么问题？

和 AI 聊天时，每一条消息（你说的、AI 回的、工具执行结果）都会被放进一个叫"上下文"的东西里。你可以把它想象成一个**固定大小的桶**——桶的容量就是 LLM 的"上下文窗口"，比如 80000 个 token。

问题是：聊得越多，桶里的东西越多，最终桶会装满。装满了怎么办？不能简单地把最旧的东西倒掉，因为那里面可能包含重要的信息（比如你最初说要做什么任务、之前遇到过什么 bug 怎么修的）。

Context 模块的核心工作就是：**在桶快满的时候，用一套聪明的方法把旧内容"压缩"，腾出空间，同时尽量保留重要信息。**

***

## 二、先搞懂几个关键术语

在讲具体实现之前，先把一些容易让人迷糊的术语讲清楚。

### "管线"（Pipeline）是什么？

> 想象一个工厂的**流水线**：原材料（一堆聊天消息）从一头进去，依次经过好几个加工站（压缩级别），每个加工站做自己的活儿，最终从另一头出来的是处理好的产品（压缩后的消息）。
>
> 所以"管线"就是"流水线"的意思，叫"管线"是因为英语是 pipeline（管道），像水管一样数据从一段流入、经过层层处理、从另一端流出。
>
> 在这里，消息会依次经过 4 个加工站：boundary截取 → tool\_result\_budget → snip\_compact → auto\_compact。每个站点干活的方式不同、力度不同，越往后的力度越重。

### "Boundary"（压缩边界）是什么？

> 想象你看一本很厚的小说，前面 50 页你已经看完并且写了摘要。你在第 50 页夹了一张书签，上面写着"前面的内容我已经总结到前言里了"。这个书签就是 boundary（边界）。
>
> 系统在每次压缩后都会插一个这样的"书签"到消息列表里。下次压缩时，看到这个书签就知道：书签之前的内容已经总结过了，不需要再处理。

### "断路器"（Circuit Breaker）是什么？

> 这个词来自电路系统。家里电闸有个保护装置：如果电流过大（比如短路了），它会自动"跳闸"断电，防止电器烧毁或起火。等故障排除了，再手动合闸恢复供电。
>
> 在这里也是同样的道理：如果 LLM 摘要连续失败了 3 次（比如网络问题、API 异常等），系统就"跳闸"——不再尝试自动压缩了，避免无限重试白白浪费时间和资源。这就是断路器保护。

### "PTL 重试"是什么？

> PTL = Prompt Too Long（提示词太长了）。调用 LLM 生成摘要时，如果塞进去的消息太多，超过 LLM 的输入限制，就会报这个错。
>
> 系统的处理方式很聪明：把消息按"API 轮次"分组（一轮 = 用户说一句话 + AI 回复 + 工具结果），然后**从最前面砍掉一整组**，缩短总长度，再重试。最多重试 3 次。

### "Token 预算"（Token Budget）是什么？

> 就像每个月有工资预算一样——吃饭花多少、房租花多少、娱乐花多少，加起来不能超。
>
> 在这里，"预算"指的是上下文桶里给"工具结果"分配的空间额度。比如总共 80000 token 的桶，给工具结果分配 200000 字符的预算。如果所有工具结果加起来超了这个预算，就把最大的那些"搬到磁盘上住"（持久化），消息里只留一个"预览 + 文件路径"的引用。

***

## 三、八个核心组件：各自的角色

| 文件                          | 核心类                    | 一句话职责                 |
| --------------------------- | ---------------------- | --------------------- |
| `manager.py`                | `ContextManager`       | 简单记录员——记着哪些 Skill 加载过 |
| `system_prompt_registry.py` | `SystemPromptRegistry` | 系统提示词三层收纳柜            |
| `conversation_history.py`   | `ConversationHistory`  | 对话轮次整理员               |
| `compressor.py`             | `ContextCompressor`    | 压缩引擎——四级管线的核心         |
| `compact_prompt.py`         | 各种函数                   | 压缩用的提示词模板             |
| `tool_result_storage.py`    | `ToolResultStorage`    | 大工具结果搬运工（搬到磁盘）        |
| `task_intent_manager.py`    | `TaskIntentManager`    | 用户最初任务的"保险箱"          |
| `session_storage.py`        | `SessionStorage`       | 对话存档管理员（存 JSON 文件）    |

下面逐个讲解。

***

## 四、ContextManager（manager.py）——简单记录员

这是最简单的组件，就干两件事：

1. **记着哪些 Skill 已经加载过了**：通过 `_loaded_skills` 列表和 `mark_skill_loaded()` 方法
2. **存一些应用状态**：通过 `_app_state` 字典，可以存键值对

**举例**：AI 在对话中加载了 `test-execution` 和 `kb-query` 两个 Skill，ContextManager 就记着：`_loaded_skills = ["test-execution", "kb-query"]`。下次 AI 想知道"这个 Skill 我加载过没"，直接问它就行。

***

## 五、SystemPromptRegistry（system\_prompt\_registry.py）——三层收纳柜

系统提示词是告诉 AI "你是谁、该怎么做"的那些指令。这个组件把这些指令分成三层来管理：

| 层级  | 名字          | 特点      | 举例                 |
| --- | ----------- | ------- | ------------------ |
| 第一层 | static（静态）  | 基本不变    | "你是一个 AI 助手..."    |
| 第二层 | skill（技能）   | 可以随时加/删 | "关于自动化测试，你应该..."   |
| 第三层 | dynamic（动态） | 经常变     | "当前时间是 2025-04-23" |

每一层的内容用 `PromptSection` 表示，里面记录了内容、类别、添加时间和最后引用时间。

**过时自动清理**：如果一个 Skill 很久没被用到（超过 `max_age_seconds`），`remove_stale_skills()` 会自动把它移除。就像冰箱里放了太久没吃的东西，该扔就扔。当 Skill 被触发词再次匹配或用户通过 `/skill load` 重新加载时，`mark_skill_referenced()` 会刷新引用时间戳，重置过期倒计时，防止活跃 Skill 被误删。

**举例**：

- 系统启动时，添加 static 层："你是 Rubato 助手..."
- AI 加载了 test-execution Skill → 添加 skill 层
- 加载了 kb-query Skill → 添加 skill 层
- 对话继续，test-execution 长时间没被引用 → 自动清理掉
- 最终 `build()` 把所有层的内容拼在一起，组成完整的系统提示词

***

## 六、ConversationHistory（conversation\_history.py）——对话轮次整理员

对话不是一堆散乱的消息，而是有结构的。这个组件把对话组织成"轮次"（Turn）：

```
一轮对话 = 用户消息 + AI 的所有回复步骤
一个步骤 = AI 回复 + 对应的工具结果
```

**举例**：

```
轮次1:
  用户: "帮我看看 main.py 的内容"
  步骤1:
    AI: "我来看看..."
    工具结果: "file content of main.py: import os..."
  步骤2:
    AI: "这个文件主要做了以下几件事..."

轮次2:
  用户: "帮我加个函数"
  步骤1:
    AI: "好的，我来加..."
    工具结果: "文件已修改"
  步骤2:
    AI: "函数已添加完成。"
```

**压缩边界**：当旧轮次被压缩后，`_compact_boundary_turn_idx` 记录了"从这个索引开始的轮次是活的（未被压缩的）"。`flatten_to_messages()` 方法负责把轮次结构展平成消息列表，给 LLM 使用。

***

## 七、ContextCompressor（compressor.py）——压缩引擎

这是整个 Context 模块最核心、最复杂的组件。它实现了**四级渐进压缩管线**。

### 为什么分四级？不是一次搞定？

> 因为每一级的"代价"不同：
>
> - 前两级几乎零成本（不调 LLM，纯本地操作）
> - 第三级也是零成本但"破坏性"更大（把旧工具结果清掉）
> - 第四级最重（要调一次 LLM 来生成摘要，花时间、花钱）
>
> 所以策略是：先试轻量操作，够用就行；不够用再升级到更重的操作。

### Level 1：Boundary 截取

**做什么**：找最后一个"书签"（`[compact_boundary]`），只保留书签之后的消息。

**举例**：

- 前一次压缩插了书签在消息 #50 的位置
- 当前有 100 条消息
- Level 1 直接把 #1\~#50 扔掉，只处理 #51\~#100

**如果没有书签**：说明从未压缩过，跳过这级。

### Level 2：tool\_result\_budget（工具结果预算控制）

**做什么**：统计所有工具结果的字符总数，如果超过预算（默认 200000 字符），就把最大的那些搬到磁盘上。

**举例**：

- 消息里有 5 个工具结果，分别 80000、60000、50000、30000、10000 字符
- 总共 230000 字符，超了 200000 的预算
- 超了 30000，所以把最大的那个（80000 字符）搬到磁盘
- 消息里 80000 字符的内容被替换成：

```
<persisted-output>
Tool result persisted to: /session/tool-results/abc123.txt
Original size: 80000 characters (truncated)
Preview:
这里是前 2000 字节的预览内容...
</persisted-output>
```

### Level 3：snip\_compact（旧工具结果清理）

**做什么**：找到所有旧的工具结果（不是最近 N 个的），直接把内容替换成 `[Old tool result content cleared]`。

**举例**：

- 消息里有 10 个工具结果
- 最近 6 个保留不动（`snip_keep_recent = 6`）
- 旧的 4 个内容被替换成 `"[Old tool result content cleared]"`
- 这几个工具结果可能有几千 token，替换后只有几个 token，省出很多空间

### Level 3.5：preprocess\_large\_messages（大消息预处理）

**做什么**：对超过 50000 字符的用户消息（HumanMessage），截断到只保留前 10000 字符。

**举例**：用户粘贴了一大段日志，200000 字符。截断后变成：

```
[日志的前 10000 字符]

...[内容已截断，原始大小: 200000 字符]
```

**有两个例外**：

- 压缩摘要消息（以 "This session is being continued" 开头）——不截断
- 任务意图消息（以 "\[Task Intent - PRESERVED]" 开头）——不截断

### Level 4：auto\_compact（LLM 摘要压缩）

**做什么**：最重的操作——调用 LLM，让它阅读整段对话，生成一个结构化的 10 段摘要。

**10 段摘要结构**（模板在 `compact_prompt.py` 里）：

| 段落                         | 内容            |
| -------------------------- | ------------- |
| 1. Primary Request         | 用户最初想干什么      |
| 2. Task Specification      | 具体的任务规格       |
| 3. Key Technical Concepts  | 涉及哪些技术        |
| 4. Files and Code Sections | 动过哪些文件        |
| 5. Errors and Fixes        | 遇到什么 bug，怎么修的 |
| 6. Problem Solving         | 解决问题的思路       |
| 7. All User Messages       | 用户说过的所有话      |
| 8. Pending Tasks           | 还没做完的事        |
| 9. Current Work            | 当前正在干什么       |
| 10. Optional Next Step     | 下一步建议做什么      |

**压缩后的消息结构**：

```
[系统消息] ← 保留
[compact_boundary 书签] ← 新插入
[摘要消息] ← LLM 生成的 10 段摘要
[任务意图恢复消息] ← 如果有的话
[最近 6 条消息] ← 原样保留
```

**PTL 重试机制**：如果调用 LLM 时报 "prompt too long" 错误：

1. 把消息按 API 轮次分组
2. 砍掉最前面的一组
3. 用缩短后的消息重试
4. 最多重试 3 次

**断路器保护**：如果连续失败 3 次，停止尝试自动压缩。

### Token 警告三级制

系统会实时监控 token 使用量，有三个级别：

| 级别          | 触发条件          | 系统行为         |
| ----------- | ------------- | ------------ |
| 正常          | < max - 20000 | 正常运行         |
| warning     | ≥ max - 20000 | 开始提醒         |
| autocompact | ≥ max - 13000 | 触发自动压缩       |
| blocking    | ≥ max - 3000  | 上下文已满，必须强制压缩 |

**举例**（`max_context_tokens = 80000`）：

- token 用量 55000 → 正常
- token 用量 61000 → warning（≥ 80000 - 20000 = 60000）
- token 用量 68000 → autocompact（≥ 80000 - 13000 = 67000）
- token 用量 78000 → blocking（≥ 80000 - 3000 = 77000），触发强制压缩

### Token 估算的"双轨制"

系统用两种方式估算 token 数量：

1. **API 精确用量**：每次调 LLM API 后，从响应里拿到实际消耗的 token 数（最准确）
2. **tiktoken 估算**：用 tiktoken 库（cl100k\_base 编码器）本地计算（降级方案）

优先用 API 精确值，没有时才用 tiktoken 估算。

***

## 八、compact\_prompt.py——压缩用的提示词模板

这个文件定义了给 LLM 看的"压缩指令"，告诉它应该怎么写摘要。有三种模板：

| 模板                             | 适用场景             | 聚焦范围          |
| ------------------------------ | ---------------- | ------------- |
| `BASE_COMPACT_PROMPT` (full)   | 第一次压缩            | 完整对话          |
| `PARTIAL_COMPACT_PROMPT_FROM`  | 有 boundary 之后的压缩 | boundary 后的消息 |
| `PARTIAL_COMPACT_PROMPT_UP_TO` | 保留最近消息的压缩        | 最近消息之前的早期消息   |

所有模板都有一个重要的前缀和后缀：**禁止 LLM 调用任何工具**。因为压缩是一次性的文本任务，不需要读文件、执行命令。

> 💡 **为什么要禁止工具调用？** 因为 LLM 在生成摘要时，如果"顺手"调了个读文件的工具，会打乱压缩流程，浪费一个 API 调用。所以模板里明确写了："不要调用任何工具，只输出纯文本。"

***

## 九、ToolResultStorage（tool\_result\_storage.py）——大工具结果搬运工

工具执行后的结果可能非常巨大。比如 `cat` 了一个大文件，返回了几万行内容。这些内容不能一直占着上下文桶。

### 持久化到磁盘

当工具结果超过 `persist_threshold`（默认 50000 字符）时：

1. 把完整内容写入磁盘文件（`{session_dir}/tool-results/{tool_use_id}.txt`）
2. 生成一个预览（前 2000 字节，按行边界截断）
3. 消息里的内容替换成：文件路径 + 预览

**举例**：AI 用工具读了一个 100000 字符的文件。完整内容保存到磁盘，消息里变成：

```
<persisted-output>
Tool result persisted to: /session/tool-results/call_abc123.txt
Original size: 100000 characters (truncated)
Preview:
import os
import sys
from pathlib import Path
...（前 2000 字节的内容）
</persisted-output>
```

### ContentReplacementState——替换状态追踪

这个组件确保一件事：**同一个工具结果不会被重复处理**。

- `seen_ids`：记录已经处理过的工具结果 ID
- `replacements`：记录已经被替换的工具结果 ID 和替换后的文本

**为什么需要？** 因为压缩管线每轮对话都会执行，如果上一轮已经把某个工具结果搬到磁盘了，这一轮不能再搬一次，直接用上次的替换文本就行。

### 预览生成的细节

`generate_preview()` 生成预览时的截断策略很细致：

1. 按字节截断（不是字符），因为要处理多字节字符
2. 在最后一个换行符处截断，保证预览内容不会在行中间断开
3. 用 `errors="ignore"` 处理可能被截断的多字节字符

***

## 十、TaskIntentManager（task\_intent\_manager.py）——用户任务的"保险箱"

### 为什么需要它？

压缩的时候，旧消息会被摘要替代。但如果用户的**最初那条消息**也被压缩掉了，AI 可能就忘了用户到底想干什么。这个组件就是用来保护用户的"任务意图"不被丢失的。

### 两种存储模式

根据用户第一条消息的长短，有两种存储方式：

| 模式               | 条件                           | 做法                        |
| ---------------- | ---------------------------- | ------------------------- |
| full（完整存储）       | 消息 ≤ 2000 字符 且 token ≤ 10000 | 完整存在内存里                   |
| persisted（持久化存储） | 消息 > 2000 字符 或 token > 10000 | 完整内容存磁盘，内存只保留前 2000 字符的预览 |

**举例**：

- 用户说"帮我写个冒泡排序" → 短消息，full 模式，完整保存
- 用户贴了 50000 字的需求文档 → 长消息，persisted 模式，磁盘保存 + 2000 字符预览

### 压缩后恢复

每次 `auto_compact` 执行后，系统会调用 `build_recovery_message()` 把任务意图重新插入到上下文里：

```
[Task Intent - PRESERVED]
帮我实现用户注册功能，需要包含邮箱验证和密码加密...
[Full task specification persisted to: /session/task-intent.txt]
```

> 💡 **大输入快速路径**：如果任务意图超过 10000 token，恢复时跳过复杂的二分查找截断逻辑，直接返回预览 + 文件路径。因为对超大内容做精确截断既慢又没必要。

### 二分查找截断

当任务意图超过 token 预算（默认 10000）时，需要截断。但截断不能随便切——要切在刚好不超过预算的位置。这里用了**二分查找**：在文本长度范围内，不断尝试中间位置，计算 token 数，直到找到刚好不超过预算的最大长度。

***

## 十一、SessionStorage（session\_storage.py）——对话存档管理员

### 做什么的？

把整个对话保存到 JSON 文件，下次可以恢复继续聊。

### 消息的序列化和反序列化

`MessageSerializer` 负责把内存中的消息对象（HumanMessage、AIMessage、ToolMessage 等）转成 JSON 字典，以及从 JSON 字典恢复回消息对象。

**每种消息类型的特殊字段**：

- AIMessage：额外保存 `tool_calls`（工具调用记录）、`response_metadata`（API 响应元数据）、`id`
- ToolMessage：额外保存 `tool_call_id`（对应哪个工具调用）、`name`（工具名）

### 线程安全

用 `threading.Lock` 保证多线程同时访问不会出问题。

### 元数据合并

保存会话时，如果已有旧数据：

- `created_at`（创建时间）保持不变
- `updated_at`（更新时间）更新为当前时间
- `sub_sessions`（子会话）合并旧的和新的
- 其他字段用新数据覆盖旧数据

**举例**：

```
sessions/
├── abc123.json    ← 主会话
└── def456.json    ← 子会话
```

`abc123.json` 的内容结构：

```json
{
  "metadata": {
    "session_id": "abc123",
    "created_at": "2025-04-23T10:00:00",
    "updated_at": "2025-04-23T11:30:00",
    "message_count": 42,
    "role": "developer",
    "model": "claude-3.5-sonnet",
    "skills": ["test-execution", "kb-query"],
    "sub_sessions": [
      {"session_id": "def456", "agent_name": "test-agent", "relation": "spawn"}
    ]
  },
  "messages": [
    {"type": "human", "content": "帮我跑测试", ...},
    {"type": "ai", "content": "好的...", "tool_calls": [...], ...},
    {"type": "tool", "content": "测试结果...", "tool_call_id": "call_xxx", ...},
    ...
  ]
}
```

***

## 十二、完整场景走读：一个 40 轮对话的压缩过程

假设你正在和 AI 讨论一个 Python 项目，已经聊了 40 轮：

### 初始状态

- token 用量：75000 / 80000
- 消息列表里有很多工具结果（读文件、执行命令的输出等）

### 每轮对话开始时，压缩管线自动运行

**Level 1 — Boundary 截取**：

- 找到上一次压缩插的书签（在第 60 条消息的位置）
- 只保留 #61 之后的消息
- 消息从 120 条减少到 60 条

**Level 2 — tool\_result\_budget**：

- 统计这 60 条消息里的工具结果总字符数：250000
- 超过预算 200000，需要砍掉 50000 字符
- 最大的工具结果是 80000 字符 → 搬到磁盘，替换为预览
- 现在总字符数降到了 170000，在预算内

**Level 3 — snip\_compact**：

- 这 60 条消息里有 15 个工具结果
- 最近 6 个保留，旧的 9 个内容替换为 `[Old tool result content cleared]`
- 释放了不少 token

**Level 3.5 — preprocess\_large\_messages**：

- 发现一条用户消息有 80000 字符（之前粘贴的大段日志）
- 截断到 10000 字符 + 截断提示
- 又释放了一些 token

**Level 4 — auto\_compact\_if\_needed**：

- 检查当前 token 是否还超过 autocompact 阈值（67000）
- 如果是：调用 LLM 生成 10 段摘要，只保留摘要 + 最近 6 条消息
- 插入新的 boundary 书签
- 恢复任务意图消息
- 如果否（前几级已经释放了足够空间）：跳过

### 压缩后的消息结构

```
[SystemMessage] "你是 Rubato 助手..."          ← 系统提示词
[SystemMessage] "[compact_boundary] ..."       ← 新书签
[HumanMessage] "Summary:                       ← LLM 生成的摘要
  1. 用户想给项目添加自动化测试
  2. 涉及 Python, Playwright, pytest
  3. 已修改 main.py, test_login.py
  4. 遇到了元素定位超时的错误，已通过增加等待时间修复
  ..."
[HumanMessage] "[Task Intent - PRESERVED]      ← 任务意图恢复
  帮我给登录功能写自动化测试..."
[HumanMessage] "帮我看看最后这个测试..."         ← 最近 6 条消息
[AIMessage] "好的，我来看看..."                 ← 保留
[ToolMessage] "test result..."                 ← 保留
...
```

这样，桶里的内容从 75000 token 可能降到了 30000 token，同时又保留了所有关键信息，AI 可以无缝继续工作。

***

## 十三、消息链验证——防止"断链"

压缩过程中有一个容易被忽略但很重要的问题：**消息链完整性**。

LLM API 要求消息列表符合一定的格式规则。比如 `ToolMessage`（工具结果）前面必须有一个对应的 `AIMessage`（AI 的工具调用请求）。如果中间的 AI 消息被压缩掉了，ToolMessage 就变成了"孤儿"。

`_ensure_message_chain_valid()` 负责修复这个问题：

**举例**：

- 原来有：`AIMessage(tool_calls=[...]) → ToolMessage(result)`
- 压缩后 AIMessage 被移除了，只剩 `ToolMessage`
- 系统把孤立的 ToolMessage 转换为 `HumanMessage(content="[工具结果摘要]: ...")`
- 这样消息链就不会断裂，LLM 不会报错

***

## 十四、组件协作关系

```
                    QueryEngine（核心引擎）
                         │
           ┌─────────────┼─────────────┐
           │             │             │
           ▼             ▼             ▼
    ContextCompressor  ToolResultStorage  ConversationHistory
    （压缩引擎）        （大结果搬运）      （轮次管理）
           │             │
           ▼             ▼
    compact_prompt    ContentReplacementState
    （提示词模板）      （替换状态追踪）
           │
           ▼
    TaskIntentManager
    （任务意图保护）

    SystemPromptRegistry ←── ContextManager
    （系统提示词管理）      （Skill状态追踪）

    SessionStorage
    （会话存档）
```

每轮 ReAct 循环开始时，QueryEngine 驱动压缩管线（通过 ContextCompressor）。对话结束后，QueryEngine 把消息增量保存到 SessionStorage。
