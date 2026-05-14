# Skills 模块小白版说明

## 读完这篇你能明白什么

- Skill 是什么，长什么样，怎么被系统识别和使用的
- "解析器"、"注册表"、"加载器"、"管理器"这几个组件各自干嘛、怎么配合的
- 内容缓存是什么、为什么需要它
- 条件激活和动态发现是怎么回事
- 系统启动时和对话过程中，Skill 分别经历了什么

***

## 一、Skill 是什么？——一张给 AI 看的"操作指南卡"

你可以把一个 Skill 想象成一张**操作指南卡**。就像餐厅后厨贴的菜谱卡片一样：上面写着菜名（Skill 名称）、什么时候用这道菜谱（触发条件）、以及具体的操作步骤（正文内容）。

项目中真实存在的 Skill 文件长这样：

**例子：`skills/test-execution.md`**

```markdown
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

## 功能说明
这里写的是详细的操作指南，告诉 AI 怎么执行自动化测试...
比如先启动浏览器、然后打开页面、点击按钮、检查结果等等。
```

**例子：`skills/kb-query/SKILL.md`**

```markdown
---
name: kb-query
description: 知识库渐进式检索 - 按步骤检索知识库文档...
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
---

这里写的是知识库检索的详细步骤和策略...
```

每个 Skill 文件都是 Markdown 格式，分为两部分：

1. **YAML 头**（`---` 之间的部分）：这就是 Skill 的"名片"，包含了名称、描述、触发词等信息
2. **正文**（`---` 之后的部分）：这就是"操作指南"本身，告诉 AI 具体该怎么做

> 💡 **什么叫 "YAML 头"？**
> 你就把它理解为一个用 YAML 格式写的"属性卡"。YAML 是一种配置文件格式，用缩进和冒号来组织数据。在 Skill 文件里，两个 `---` 之间夹着的那一段就是 YAML 头，里面放着这个 Skill 的各种元信息（名字、描述、触发词等）。这种写法在很多技术体系里都有用到，比如 GitHub Pages 的博客文章也用同样的方式在文章开头标注日期和分类。

***

## 二、四个核心组件：各司其职的小团队

Skills 模块有四个核心文件，可以理解为四个分工不同的小组成员：

| 文件 | 核心类 | 一句话职责 |
|------|--------|-----------|
| `parser.py` | `SkillMetadata`, `SkillParser` | "翻译官"——把 Skill 文件翻译成系统认识的格式 |
| `registry.py` | `SkillRegistry` | "档案管理员"——保管所有 Skill 的登记信息和内容缓存 |
| `loader.py` | `SkillLoader` | "采购员"——负责从磁盘上把 Skill 文件读进来 |
| `manager.py` | `ConditionalSkill`, `SkillManager` | "调度主管"——在采购员的基础上，增加条件激活和动态发现能力 |

下面逐个讲解。

***

## 三、SkillParser 和 SkillMetadata（parser.py）——"翻译官"

### SkillMetadata：Skill 的"身份证"

`SkillMetadata` 是一个 Pydantic 数据模型，你可以理解为一张"身份证"，上面记录了 Skill 的关键信息：

| 字段 | 类型 | 干嘛的 | 举例 |
|------|------|--------|------|
| `name` | str | Skill 的唯一名字 | `"test-execution"` |
| `description` | str | 一句话描述 | `"自动化测试执行能力"` |
| `version` | str | 版本号 | `"1.0"` |
| `author` | str | 作者 | `"rubato"` |
| `triggers` | List[str] | 触发词列表 | `["测试", "执行测试"]` |
| `tools` | List[str] | 需要哪些工具 | `["ShellTool"]` |
| `paths` | List[str] | 路径模式（条件激活用） | `["src/**/*.py"]` |
| `file_path` | str | 文件在磁盘上的位置 | `"skills/test-execution.md"` |

### SkillParser：把文件"翻译"成身份证

`SkillParser` 的工作流程非常直观，就是：

1. 读文件内容
2. 找到两个 `---`，把中间的 YAML 部分切出来
3. 把 YAML 解析成 `SkillMetadata` 身份证
4. 把 `---` 后面的正文也切出来
5. 返回身份证 + 正文

**举例**：当解析器读到 `test-execution.md` 时：
- 切出 YAML 头 → 解析成 `SkillMetadata(name="test-execution", triggers=["测试", "执行测试", "测试案例"], ...)`
- 切出正文 → `"## 功能说明\n这里写的是详细的操作指南..."`
- 返回这两个东西给调用方

如果文件没有 YAML 头（不符合格式），解析器不会报错，而是返回一个"空身份证"（name 为空字符串），后续流程会自然忽略它。

***

## 四、SkillRegistry（registry.py）——"档案管理员"

`SkillRegistry` 就像一个**档案管理员**，它管理着两个柜子：

### 柜子一：元数据字典 `skills: Dict[str, SkillMetadata]`

这个字典存储了所有已注册 Skill 的"身份证"（元数据）。键是 Skill 名称，值是 SkillMetadata 对象。

**举例**：
```python
registry.skills = {
    "test-execution": SkillMetadata(name="test-execution", ...),
    "kb-query": SkillMetadata(name="kb-query", ...),
}
```

### 柜子二：内容缓存 `skill_contents: Dict[str, str]`

这个字典缓存了 Skill 的完整正文内容。

> 💡 **什么叫 "内容缓存"？**
> 内容缓存就是把之前读过的 Skill 正文存在内存里，下次再需要时直接从内存读取，不用再去磁盘读文件。
>
> **为什么需要这个？** 因为 Skill 的正文可能很长（有些几百行甚至更多），每次从磁盘读取都需要 I/O 操作。把已加载的内容缓存起来，后续访问时直接从缓存获取即可。

### 触发词匹配

档案管理员还有一个重要工作：`find_matching_skill(user_input)`。

**举例**：用户说"帮我执行测试"，系统就把这句话传给档案管理员。管理员遍历所有 Skill 的触发词列表：
- `test-execution` 的触发词有 `["测试", "执行测试", "测试案例"]`
- "帮我**执行测试**" 里面包含了 "执行测试" 这个触发词（不区分大小写）
- 匹配成功！返回 `"test-execution"`

***

## 五、SkillLoader（loader.py）——"采购员"

`SkillLoader` 的工作是**从磁盘读取 Skill 文件**，但它有一个非常聪明的策略：**分两步走**。

### 第一步：启动时——只读"名片"（元数据）

应用启动时，`load_skill_metadata()` 被调用。它会：
1. 扫描 Skill 目录下所有 `.md` 文件
2. 对每个文件，只解析 YAML 头部分，提取出 SkillMetadata
3. 把元数据注册到 Registry 的元数据字典里
4. **不读正文！**

**为什么？** 假设项目里有 20 个 Skill，每个正文 200 行。如果启动时全读进来，就要在内存里放 4000 行内容，但当前对话可能只需要用到其中 2 个。所以启动时只读"名片"，用到哪个再读哪个。

> 💡 **黑名单机制**：`disabled_skills` 是一个可选的"黑名单"。如果设置了黑名单（比如 `{"test-execution"}`），那么名字在这个黑名单里的 Skill 会被跳过，其他的一律正常加载。如果黑名单为空（默认），则加载全部 Skill。

### 第二步：对话中——按需加载正文

当对话中需要某个 Skill 的完整内容时，`load_full_skill(skill_name)` 被调用：

1. 先查 Registry 的内容缓存——如果已经有了，直接返回
2. 如果没有，从 Registry 的元数据里找到文件路径
3. 从磁盘读取文件，用解析器剥离 YAML 头，只保留正文
4. 把正文存入缓存，然后返回

**举例**：AI 在对话中决定需要使用 `kb-query` 这个 Skill。
1. 查缓存 → 没找到
2. 查元数据 → `file_path = "skills/kb-query/SKILL.md"`
3. 读文件，剥离 YAML 头，拿到正文
4. 存入缓存
5. 返回正文给 AI

***

## 六、ConditionalSkill 和 SkillManager（manager.py）——"调度主管"

### ConditionalSkill：只在特定条件下"醒来"的 Skill

有些 Skill 不应该总是激活，而是只有当你操作特定类型的文件时才激活。

**举例**：假设你有一个"Python 测试"Skill，它的 YAML 头里有 `paths: ["**/*.py"]`。这意味着只有当你操作 `.py` 文件时，这个 Skill 才会被激活。

> 💡 **路径匹配用的是 GitWildMatchPattern**，就是 `.gitignore` 文件里用的那种语法。比如 `**/*.py` 匹配所有 Python 文件，`src/**/*.ts` 匹配 src 目录下所有 TypeScript 文件。底层用 `pathspec` 库实现，匹配时会把绝对路径转成相对路径，统一用 `/` 分隔。

### SkillManager：加载 + 条件激活 + 动态发现

`SkillManager` 继承了 `SkillLoader`，在"采购员"的基础上增加了三个高级能力：

#### 能力一：多来源并行加载

启动时，`load_skills()` 可以同时从**多个目录**加载 Skill：
- 项目自己的 `skills/` 目录
- 额外配置的目录（`additional_dirs`）
- 托管目录（`_managed_skills_dir`）
- 用户目录（`_user_skills_dir`）

这些目录的加载是**并行**的（用 `asyncio.gather`），加载完后做两件事：
1. **去重**：如果多个目录有同名的 Skill，只保留第一个加载到的
2. **分离条件 Skill**：把 `paths` 非空的 Skill 包装成 `ConditionalSkill`，单独放到 `conditional_skills` 列表里等待条件激活

#### 能力二：条件激活（`activate_for_paths`）

当你开始操作某些文件时，系统调用 `activate_for_paths(file_paths)`：

**举例**：
- 你打开了 `src/main.py` 和 `src/utils.py` 两个文件
- 系统把这些路径传给 `activate_for_paths`
- 它遍历所有条件 Skill，检查路径是否匹配
- 如果有个 "Python 测试" Skill 的 paths 是 `["**/*.py"]`，那它就匹配了
- 这个条件 Skill 被移到 `dynamic_skills`（动态技能列表）里，正式激活
- 返回 `["python-testing"]` 表示这个 Skill 被激活了

#### 能力三：动态发现（`discover_for_paths`）

这是一种更灵活的机制：从你正在操作的文件位置开始，**向上遍历目录树**，寻找名为 `.skills` 的隐藏目录。

**举例**：假设目录结构如下：

```
/home/user/project/
├── .skills/              ← 根目录的 Skills
│   └── general.md
├── src/
│   ├── backend/
│   │   ├── .skills/      ← 后端专属 Skills
│   │   │   └── api-test.md
│   │   └── api.py
│   └── frontend/
│       └── ui.tsx
```

当你打开 `api.py` 文件时，`discover_for_paths` 会：
1. 从 `src/backend/` 开始，发现 `.skills` 目录 → 扫描并注册里面的 `api-test.md`
2. 向上一层到 `src/` → 没有 `.skills` 目录
3. 再向上一层到 `/home/user/project/` → 发现 `.skills` 目录 → 扫描并注册 `general.md`
4. 继续向上 → 超过了项目根目录 → 停止

这样，AI 就能自动获取跟你当前工作区域最相关的 Skill。

***

## 七、全流程串讲：一个 Skill 从"躺硬盘"到"上场干活"

把上面的内容串起来，一个典型的完整流程是这样的：

### 启动阶段

1. 应用启动，`SkillManager.load_skills()` 被调用
2. 并行扫描项目 `skills/` 目录和其他配置目录下的 `.md` 文件
3. 解析器读每个文件的 YAML 头，生成 SkillMetadata
4. 黑名单过滤（如果有的话）
5. 去重（同名 Skill 只留第一个）
6. 把元数据注册到 Registry 的元数据字典
7. 把有 `paths` 字段的 Skill 包装成 ConditionalSkill，放入等待区
8. **此时没有任何 Skill 的正文被加载到内存**

### 对话阶段——触发匹配

1. 用户说"帮我跑一下测试"
2. 系统调用 `find_matching_skill("帮我跑一下测试")`
3. 匹配到 `test-execution`（因为触发词"测试"被命中）
4. AI 决定需要加载这个 Skill 的全文
5. `load_full_skill("test-execution")` 被调用
6. 从磁盘读取文件 → 剥离 YAML 头 → 存入缓存 → 返回正文
7. 正文被插入到系统提示词中，AI 就能按照指南操作了

### 对话阶段——条件激活

1. 你打开了一个 Python 文件
2. 系统调用 `activate_for_paths(["/path/to/file.py"])`
3. 遍历条件 Skill 列表，用 GitWildMatch 模式匹配路径
4. 匹配到的 Skill 被移到动态 Skill 列表，正式激活

### 对话阶段——动态发现

1. 你打开了一个嵌套很深的文件
2. 系统从文件所在目录向上搜索 `.skills` 目录
3. 找到的 `.skills` 目录里的 `.md` 文件被解析并注册
4. 这些 Skill 也被加入动态 Skill 列表

***

## 八、组件关系速览

```
SkillParser  ──解析文件──→  SkillMetadata
                                │
                                ▼
SkillRegistry  ←──注册元数据──  │
     │                          │
     ▼                          ▼
SkillLoader  ──从磁盘读取──→  Registry（存元数据 + 缓存内容）
     │
     ▼
SkillManager  ──扩展──→  多目录并行加载 + 条件激活 + 动态发现
     │
     ├── ConditionalSkill  ──路径匹配──→  GitWildMatchPattern
     ├── dynamic_skills    ──动态发现的 Skill
     └── conditional_skills ──等待激活的条件 Skill
```
