"""测试角色切换后 Skill 全文加载修复"""
import asyncio
import sys
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.agent import RubatoAgent
from src.config.models import (
    AppConfig, FullModelConfig, ModelConfig, MCPConfig,
    PromptConfig, SkillsConfig, AgentConfig, AgentExecutionConfig,
    ProjectConfig, FileToolsConfig, UnifiedToolsConfig, RoleConfig,
    WorkspaceConfig
)
from src.context.manager import ContextManager
from src.mcp.tools import ToolRegistry
from src.skills.loader import SkillLoader
from src.skills.parser import SkillParser


def create_test_config(tmp_dir: str) -> AppConfig:
    return AppConfig(
        model=FullModelConfig(
            model=ModelConfig(
                provider="openai",
                name="test-model",
                api_key="test-api-key",
                base_url="https://api.test.com/v1",
                temperature=0.7,
                max_tokens=80000
            )
        ),
        mcp=MCPConfig(servers={}),
        prompts=PromptConfig(
            system_prompt_file=str(Path(tmp_dir) / "system_prompt.txt")
        ),
        skills=SkillsConfig(
            directory=str(Path(tmp_dir) / "skills"),
            auto_load=False,
            enabled_skills=[]
        ),
        agent=AgentConfig(
            max_context_tokens=80000,
            execution=AgentExecutionConfig(
                recursion_limit=100,
                sub_agent_recursion_limit=50
            )
        ),
        project=ProjectConfig(
            name="test-project",
            root=Path(tmp_dir),
            workspace=WorkspaceConfig(main=Path(tmp_dir))
        ),
        file_tools=FileToolsConfig(),
        tools=UnifiedToolsConfig()
    )


def create_test_skill_file(skills_dir: Path, name: str, body: str, description: str = "Test skill") -> None:
    skills_dir.mkdir(parents=True, exist_ok=True)
    content = f"""---
name: {name}
description: {description}
triggers:
  - "{name}"
---

{body}
"""
    skill_file = skills_dir / f"{name}.md"
    skill_file.write_text(content, encoding='utf-8')


def create_test_system_prompt(tmp_dir: str, content: str = "You are a test assistant.") -> None:
    prompt_file = Path(tmp_dir) / "system_prompt.txt"
    prompt_file.write_text(content, encoding='utf-8')


def create_test_role_prompt(tmp_dir: str, role_name: str, content: str) -> str:
    prompts_dir = Path(tmp_dir) / "prompts" / "roles"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = prompts_dir / f"{role_name}.txt"
    prompt_file.write_text(content, encoding='utf-8')
    return str(prompt_file)


def test_load_full_skill_strips_yaml_header():
    """测试 load_full_skill() 返回不含 YAML 头的正文"""
    print("=" * 50)
    print("测试: load_full_skill() 返回不含 YAML 头的正文")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        create_test_skill_file(skills_dir, "test-skill", "This is the skill body content.", "A test skill")

        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        asyncio.run(loader.load_skill_metadata())

        content = asyncio.run(loader.load_full_skill("test-skill"))

        assert content is not None, "load_full_skill() 应返回非空内容"
        assert "---" not in content, f"返回内容不应包含 YAML 头分隔符 ---, 实际: {content[:100]}"
        assert "This is the skill body content." in content, f"返回内容应包含 skill 正文, 实际: {content[:100]}"
        assert "name: test-skill" not in content, f"返回内容不应包含 YAML 元数据, 实际: {content[:100]}"

    print("[PASS] load_full_skill() 正确剥离 YAML 头\n")


def test_get_skill_content_sync_strips_yaml_header():
    """测试 get_skill_content_sync() 返回不含 YAML 头的正文"""
    print("=" * 50)
    print("测试: get_skill_content_sync() 返回不含 YAML 头的正文")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        create_test_skill_file(skills_dir, "sync-skill", "Sync skill body content.", "A sync test skill")

        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        asyncio.run(loader.load_skill_metadata())

        content = loader.get_skill_content_sync("sync-skill")

        assert content is not None, "get_skill_content_sync() 应返回非空内容"
        assert "---" not in content, f"返回内容不应包含 YAML 头分隔符 ---, 实际: {content[:100]}"
        assert "Sync skill body content." in content, f"返回内容应包含 skill 正文, 实际: {content[:100]}"
        assert "name: sync-skill" not in content, f"返回内容不应包含 YAML 元数据, 实际: {content[:100]}"

    print("[PASS] get_skill_content_sync() 正确剥离 YAML 头\n")


def test_get_skill_content_sync_after_lru_eviction():
    """测试 LRU 淘汰后 get_skill_content_sync() 仍返回不含 YAML 头的正文"""
    print("=" * 50)
    print("测试: LRU 淘汰后 get_skill_content_sync() 仍返回不含 YAML 头的正文")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        create_test_skill_file(skills_dir, "evict-skill", "Evicted skill body.", "Eviction test")

        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=1)
        asyncio.run(loader.load_skill_metadata())

        loader.registry.get_content("evict-skill")

        create_test_skill_file(skills_dir, "other-skill", "Other skill body.", "Other test")
        loader._load_skills_from_dir(skills_dir, skip_existing=True)

        loader.get_skill_content_sync("other-skill")

        content = loader.get_skill_content_sync("evict-skill")

        assert content is not None, "LRU 淘汰后重新加载应返回非空内容"
        assert "---" not in content, f"LRU 淘汰后重新加载的内容不应包含 YAML 头, 实际: {content[:100]}"
        assert "Evicted skill body." in content, f"LRU 淘汰后重新加载的内容应包含正文, 实际: {content[:100]}"

    print("[PASS] LRU 淘汰后重新加载仍正确剥离 YAML 头\n")


def test_build_system_prompt_with_skills():
    """测试 _build_system_prompt_with_skills() 正确拼接 skill 全文"""
    print("=" * 50)
    print("测试: _build_system_prompt_with_skills() 正确拼接 skill 全文")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        create_test_system_prompt(tmpdir, "Base prompt content.")

        skills_dir = Path(tmpdir) / "skills"
        create_test_skill_file(skills_dir, "my-skill", "My skill body with CLI commands.", "My test skill")

        config = create_test_config(tmpdir)
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        asyncio.run(loader.load_skill_metadata())
        context_manager = ContextManager()
        tool_registry = ToolRegistry()

        agent = RubatoAgent(
            config=config,
            skill_loader=loader,
            context_manager=context_manager,
            tool_registry=tool_registry
        )

        base_prompt = "Base prompt for testing."
        agent._role_skills = ["my-skill"]

        result = agent._build_system_prompt_with_skills(base_prompt)

        assert "Base prompt for testing." in result, "结果应包含基础提示词"
        assert "# 角色专用 Skills" in result, "结果应包含角色专用 Skills 标题"
        assert "## my-skill" in result, "结果应包含 skill 名称标题"
        assert "My skill body with CLI commands." in result, "结果应包含 skill 正文"
        assert "name: my-skill" not in result, "结果不应包含 YAML 元数据"
        assert "---" not in result, "结果不应包含 YAML 头分隔符"

    print("[PASS] _build_system_prompt_with_skills() 正确拼接 skill 全文\n")


def test_reload_system_prompt_includes_skills():
    """测试 reload_system_prompt() 包含 skill 全文"""
    print("=" * 50)
    print("测试: reload_system_prompt() 包含 skill 全文")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        create_test_system_prompt(tmpdir, "Base prompt for reload test.")

        skills_dir = Path(tmpdir) / "skills"
        create_test_skill_file(skills_dir, "reload-skill", "Reload skill body content.", "Reload test skill")

        config = create_test_config(tmpdir)
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        asyncio.run(loader.load_skill_metadata())
        context_manager = ContextManager()
        tool_registry = ToolRegistry()

        agent = RubatoAgent(
            config=config,
            skill_loader=loader,
            context_manager=context_manager,
            tool_registry=tool_registry
        )

        role_prompt_file = create_test_role_prompt(tmpdir, "test_role", "Role specific prompt.")
        role_config = RoleConfig(
            name='test-role',
            description='测试角色',
            system_prompt_file=role_prompt_file,
            tools={"skills": ["reload-skill"]}
        )

        agent.reload_system_prompt(role_config)

        prompt = agent.get_current_system_prompt()
        assert "Role specific prompt." in prompt, f"系统提示词应包含角色提示词, 实际: {prompt[:200]}"
        assert "# 角色专用 Skills" in prompt, f"系统提示词应包含角色专用 Skills 标题, 实际: {prompt[:200]}"
        assert "## reload-skill" in prompt, f"系统提示词应包含 skill 名称标题, 实际: {prompt[:200]}"
        assert "Reload skill body content." in prompt, f"系统提示词应包含 skill 正文, 实际: {prompt[:200]}"
        assert "name: reload-skill" not in prompt, "系统提示词不应包含 YAML 元数据"

    print("[PASS] reload_system_prompt() 正确包含 skill 全文\n")


def test_load_role_skills_includes_full_content():
    """测试 load_role_skills() 包含 skill 全文"""
    print("=" * 50)
    print("测试: load_role_skills() 包含 skill 全文")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        create_test_system_prompt(tmpdir, "Base prompt for load_role_skills test.")

        skills_dir = Path(tmpdir) / "skills"
        create_test_skill_file(skills_dir, "load-skill", "Load skill body with CLI: test-cmd --flag", "Load test skill")

        config = create_test_config(tmpdir)
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        asyncio.run(loader.load_skill_metadata())
        context_manager = ContextManager()
        tool_registry = ToolRegistry()

        agent = RubatoAgent(
            config=config,
            skill_loader=loader,
            context_manager=context_manager,
            tool_registry=tool_registry
        )

        asyncio.run(agent.load_role_skills(["load-skill"]))

        prompt = agent.get_current_system_prompt()
        assert "# 角色专用 Skills" in prompt, "系统提示词应包含角色专用 Skills 标题"
        assert "## load-skill" in prompt, "系统提示词应包含 skill 名称标题"
        assert "Load skill body with CLI: test-cmd --flag" in prompt, "系统提示词应包含 skill 正文（含 CLI 命令）"
        assert "name: load-skill" not in prompt, "系统提示词不应包含 YAML 元数据"

    print("[PASS] load_role_skills() 正确包含 skill 全文\n")


def test_agent_init_with_role_skills():
    """测试 Agent 初始化时加载 skill 全文"""
    print("=" * 50)
    print("测试: Agent 初始化时加载 skill 全文")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        create_test_system_prompt(tmpdir, "Init test base prompt.")

        skills_dir = Path(tmpdir) / "skills"
        create_test_skill_file(skills_dir, "init-skill", "Init skill body: run-test --verbose", "Init test skill")

        config = create_test_config(tmpdir)
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        asyncio.run(loader.load_skill_metadata())
        context_manager = ContextManager()
        tool_registry = ToolRegistry()

        role_prompt_file = create_test_role_prompt(tmpdir, "init_role", "Init role prompt.")
        role_config = RoleConfig(
            name='init-role',
            description='初始化测试角色',
            system_prompt_file=role_prompt_file,
            tools={"skills": ["init-skill"]}
        )

        agent = RubatoAgent(
            config=config,
            skill_loader=loader,
            context_manager=context_manager,
            tool_registry=tool_registry,
            role_config=role_config
        )

        prompt = agent.get_current_system_prompt()
        assert "Init role prompt." in prompt, f"初始系统提示词应包含角色提示词, 实际: {prompt[:200]}"
        assert "# 角色专用 Skills" in prompt, f"初始系统提示词应包含角色专用 Skills 标题, 实际: {prompt[:200]}"
        assert "## init-skill" in prompt, f"初始系统提示词应包含 skill 名称标题, 实际: {prompt[:200]}"
        assert "Init skill body: run-test --verbose" in prompt, f"初始系统提示词应包含 skill 正文, 实际: {prompt[:200]}"

    print("[PASS] Agent 初始化时正确加载 skill 全文\n")


def test_new_command_preserves_skills():
    """测试 /new 命令后 skill 全文保留"""
    print("=" * 50)
    print("测试: /new 命令后 skill 全文保留")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        create_test_system_prompt(tmpdir, "New command test base prompt.")

        skills_dir = Path(tmpdir) / "skills"
        create_test_skill_file(skills_dir, "new-skill", "New skill body: execute-test --mode=ci", "New test skill")

        config = create_test_config(tmpdir)
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        asyncio.run(loader.load_skill_metadata())
        context_manager = ContextManager()
        tool_registry = ToolRegistry()

        role_prompt_file = create_test_role_prompt(tmpdir, "new_role", "New role prompt.")
        role_config = RoleConfig(
            name='new-role',
            description='New命令测试角色',
            system_prompt_file=role_prompt_file,
            tools={"skills": ["new-skill"]}
        )

        agent = RubatoAgent(
            config=config,
            skill_loader=loader,
            context_manager=context_manager,
            tool_registry=tool_registry,
            role_config=role_config
        )

        prompt_before = agent.get_current_system_prompt()
        assert "New skill body: execute-test --mode=ci" in prompt_before, "初始提示词应包含 skill 正文"

        agent.clear_context()
        agent.reload_system_prompt(role_config)

        prompt_after = agent.get_current_system_prompt()
        assert "New role prompt." in prompt_after, f"/new 后系统提示词应包含角色提示词, 实际: {prompt_after[:200]}"
        assert "# 角色专用 Skills" in prompt_after, f"/new 后系统提示词应包含角色专用 Skills 标题, 实际: {prompt_after[:200]}"
        assert "## new-skill" in prompt_after, f"/new 后系统提示词应包含 skill 名称标题, 实际: {prompt_after[:200]}"
        assert "New skill body: execute-test --mode=ci" in prompt_after, f"/new 后系统提示词应包含 skill 正文, 实际: {prompt_after[:200]}"

    print("[PASS] /new 命令后 skill 全文正确保留\n")


def test_multiple_role_switches():
    """测试多次角色切换后 skill 全文正确更新"""
    print("=" * 50)
    print("测试: 多次角色切换后 skill 全文正确更新")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        create_test_system_prompt(tmpdir, "Multi switch base prompt.")

        skills_dir = Path(tmpdir) / "skills"
        create_test_skill_file(skills_dir, "role-a-skill", "Role A skill: cmd-a --opt", "Role A skill")
        create_test_skill_file(skills_dir, "role-b-skill", "Role B skill: cmd-b --flag", "Role B skill")

        config = create_test_config(tmpdir)
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        asyncio.run(loader.load_skill_metadata())
        context_manager = ContextManager()
        tool_registry = ToolRegistry()

        agent = RubatoAgent(
            config=config,
            skill_loader=loader,
            context_manager=context_manager,
            tool_registry=tool_registry
        )

        role_a_prompt = create_test_role_prompt(tmpdir, "role_a", "Role A prompt.")
        role_a_config = RoleConfig(
            name='role-a',
            description='角色A',
            system_prompt_file=role_a_prompt,
            tools={"skills": ["role-a-skill"]}
        )

        role_b_prompt = create_test_role_prompt(tmpdir, "role_b", "Role B prompt.")
        role_b_config = RoleConfig(
            name='role-b',
            description='角色B',
            system_prompt_file=role_b_prompt,
            tools={"skills": ["role-b-skill"]}
        )

        asyncio.run(agent.load_role_skills(["role-a-skill"]))
        agent.role_config = role_a_config
        agent._current_system_prompt = agent._build_system_prompt_with_skills(agent._load_system_prompt())

        prompt_a = agent.get_current_system_prompt()
        assert "## role-a-skill" in prompt_a, "切换到角色A后应包含 role-a-skill"
        assert "Role A skill: cmd-a --opt" in prompt_a, "切换到角色A后应包含 role-a-skill 正文"
        assert "role-b-skill" not in prompt_a, "切换到角色A后不应包含 role-b-skill"

        asyncio.run(agent.load_role_skills(["role-b-skill"]))
        agent.role_config = role_b_config
        agent._current_system_prompt = agent._build_system_prompt_with_skills(agent._load_system_prompt())

        prompt_b = agent.get_current_system_prompt()
        assert "## role-b-skill" in prompt_b, "切换到角色B后应包含 role-b-skill"
        assert "Role B skill: cmd-b --flag" in prompt_b, "切换到角色B后应包含 role-b-skill 正文"
        assert "role-a-skill" not in prompt_b, "切换到角色B后不应包含 role-a-skill"

        asyncio.run(agent.load_role_skills(["role-a-skill"]))
        agent.role_config = role_a_config
        agent._current_system_prompt = agent._build_system_prompt_with_skills(agent._load_system_prompt())

        prompt_a2 = agent.get_current_system_prompt()
        assert "## role-a-skill" in prompt_a2, "再次切换到角色A后应包含 role-a-skill"
        assert "Role A skill: cmd-a --opt" in prompt_a2, "再次切换到角色A后应包含 role-a-skill 正文"
        assert "role-b-skill" not in prompt_a2, "再次切换到角色A后不应包含 role-b-skill"

    print("[PASS] 多次角色切换后 skill 全文正确更新\n")


def test_no_skills_role():
    """测试切换到无 skills 配置的角色时不包含 skill 全文"""
    print("=" * 50)
    print("测试: 切换到无 skills 配置的角色时不包含 skill 全文")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        create_test_system_prompt(tmpdir, "No skills base prompt.")

        skills_dir = Path(tmpdir) / "skills"
        create_test_skill_file(skills_dir, "some-skill", "Some skill body.", "Some skill")

        config = create_test_config(tmpdir)
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        asyncio.run(loader.load_skill_metadata())
        context_manager = ContextManager()
        tool_registry = ToolRegistry()

        role_prompt = create_test_role_prompt(tmpdir, "no_skill_role", "No skill role prompt.")
        role_config = RoleConfig(
            name='no-skill-role',
            description='无Skill角色',
            system_prompt_file=role_prompt
        )

        agent = RubatoAgent(
            config=config,
            skill_loader=loader,
            context_manager=context_manager,
            tool_registry=tool_registry,
            role_config=role_config
        )

        prompt = agent.get_current_system_prompt()
        assert "# 角色专用 Skills" not in prompt, "无 skills 配置的角色不应包含角色专用 Skills 标题"
        assert "Some skill body." not in prompt, "无 skills 配置的角色不应包含 skill 正文内容"

    print("[PASS] 无 skills 配置的角色不包含 skill 全文\n")


def test_update_role_skills_includes_content():
    """测试 update_role_skills() 包含 skill 全文"""
    print("=" * 50)
    print("测试: update_role_skills() 包含 skill 全文")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        create_test_system_prompt(tmpdir, "Update skills base prompt.")

        skills_dir = Path(tmpdir) / "skills"
        create_test_skill_file(skills_dir, "update-skill", "Update skill body: update-cmd --force", "Update test skill")

        config = create_test_config(tmpdir)
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        asyncio.run(loader.load_skill_metadata())
        context_manager = ContextManager()
        tool_registry = ToolRegistry()

        agent = RubatoAgent(
            config=config,
            skill_loader=loader,
            context_manager=context_manager,
            tool_registry=tool_registry
        )

        agent.update_role_skills(["update-skill"])

        prompt = agent.get_current_system_prompt()
        assert "# 角色专用 Skills" in prompt, "update_role_skills 后应包含角色专用 Skills 标题"
        assert "## update-skill" in prompt, "update_role_skills 后应包含 skill 名称标题"
        assert "Update skill body: update-cmd --force" in prompt, "update_role_skills 后应包含 skill 正文"

    print("[PASS] update_role_skills() 正确包含 skill 全文\n")


def test_build_system_prompt_marks_skills_loaded():
    """测试 _build_system_prompt_with_skills() 标记 skill 为已加载"""
    print("=" * 50)
    print("测试: _build_system_prompt_with_skills() 标记 skill 为已加载")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        create_test_system_prompt(tmpdir, "Mark loaded test prompt.")

        skills_dir = Path(tmpdir) / "skills"
        create_test_skill_file(skills_dir, "mark-skill", "Mark skill body.", "Mark test skill")

        config = create_test_config(tmpdir)
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        asyncio.run(loader.load_skill_metadata())
        context_manager = ContextManager()
        tool_registry = ToolRegistry()

        agent = RubatoAgent(
            config=config,
            skill_loader=loader,
            context_manager=context_manager,
            tool_registry=tool_registry
        )

        assert not context_manager.is_skill_loaded("mark-skill"), "调用前 skill 不应被标记为已加载"

        agent._role_skills = ["mark-skill"]
        agent._build_system_prompt_with_skills("Base prompt.")

        assert context_manager.is_skill_loaded("mark-skill"), "调用后 skill 应被标记为已加载"

    print("[PASS] _build_system_prompt_with_skills() 正确标记 skill 为已加载\n")


def test_skill_referenced_not_removed_as_stale():
    """测试：已加载的 Skill 被刷新引用时间后，不会被 remove_stale_skills 误删"""
    print("=" * 50)
    print("测试: 已加载 Skill 刷新引用后不被 remove_stale_skills 误删")
    print("=" * 50)

    from src.context.system_prompt_registry import SystemPromptRegistry
    import time

    registry = SystemPromptRegistry()
    registry.add_skill("active-skill", "Active skill content.")

    section = registry._sections["skill_active-skill"]
    section.last_referenced = time.time() - 290

    registry.mark_skill_referenced("active-skill")

    removed = registry.remove_stale_skills(300)
    assert "active-skill" not in removed, f"刷新引用后不应被清理, 实际被清理: {removed}"
    assert registry.has_skill("active-skill"), "刷新引用后 Skill 应仍在注册表中"

    print("[PASS] 刷新引用后的 Skill 不会被 remove_stale_skills 误删\n")


def test_skill_not_referenced_removed_as_stale():
    """测试：未刷新引用时间的 Skill 超时后会被正确清理"""
    print("=" * 50)
    print("测试: 未刷新引用时间的 Skill 超时后被正确清理")
    print("=" * 50)

    from src.context.system_prompt_registry import SystemPromptRegistry
    import time

    registry = SystemPromptRegistry()
    registry.add_skill("stale-skill", "Stale skill content.")

    section = registry._sections["skill_stale-skill"]
    section.last_referenced = time.time() - 301

    removed = registry.remove_stale_skills(300)
    assert "stale-skill" in removed, f"超时未引用的 Skill 应被清理, 实际: {removed}"
    assert not registry.has_skill("stale-skill"), "超时 Skill 应已从注册表中移除"

    print("[PASS] 超时未引用的 Skill 被正确清理\n")


def test_skill_reference_refresh_resets_timer():
    """测试：mark_skill_referenced 正确重置 last_referenced 时间戳"""
    print("=" * 50)
    print("测试: mark_skill_referenced 正确重置引用时间戳")
    print("=" * 50)

    from src.context.system_prompt_registry import SystemPromptRegistry
    import time

    registry = SystemPromptRegistry()
    registry.add_skill("timer-skill", "Timer skill content.")

    section = registry._sections["skill_timer-skill"]
    old_ref = section.last_referenced

    time.sleep(0.05)
    registry.mark_skill_referenced("timer-skill")

    new_ref = section.last_referenced
    assert new_ref > old_ref, f"mark_skill_referenced 后 last_referenced 应更新, 旧值={old_ref}, 新值={new_ref}"

    removed = registry.remove_stale_skills(300)
    assert "timer-skill" not in removed, "刚刷新引用的 Skill 不应被清理"

    print("[PASS] mark_skill_referenced 正确重置引用时间戳\n")


if __name__ == "__main__":
    test_load_full_skill_strips_yaml_header()
    test_get_skill_content_sync_strips_yaml_header()
    test_get_skill_content_sync_after_lru_eviction()
    test_build_system_prompt_with_skills()
    test_reload_system_prompt_includes_skills()
    test_load_role_skills_includes_full_content()
    test_agent_init_with_role_skills()
    test_new_command_preserves_skills()
    test_multiple_role_switches()
    test_no_skills_role()
    test_update_role_skills_includes_content()
    test_build_system_prompt_marks_skills_loaded()
    test_skill_referenced_not_removed_as_stale()
    test_skill_not_referenced_removed_as_stale()
    test_skill_reference_refresh_resets_timer()
    print("\n" + "=" * 50)
    print("所有测试通过!")
    print("=" * 50)
