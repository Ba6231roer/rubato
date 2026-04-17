"""测试 /skill load 命令"""
import asyncio
import tempfile
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.commands.impl.skill import SkillCommand
from src.commands.models import CommandResult, ResultType
from src.skills.loader import SkillLoader
from src.skills.parser import SkillMetadata
from src.context.system_prompt_registry import SystemPromptRegistry
from src.context.manager import ContextManager


def _create_test_skill_file(skills_dir, name, description, triggers=None, content_body="Test content"):
    skill_content = f"""---
name: {name}
description: {description}
version: "1.0"
triggers:
  - "{triggers[0] if triggers else name}"
---

# {name}

{content_body}
"""
    skill_file = skills_dir / f"{name}.md"
    skill_file.write_text(skill_content, encoding='utf-8')


def _create_mock_context(skill_loader, agent=None):
    context = MagicMock()
    context.skill_loader = skill_loader
    context.agent = agent or _create_mock_agent()
    return context


def _create_mock_agent():
    agent = MagicMock()
    agent._system_prompt_registry = SystemPromptRegistry()
    agent._current_system_prompt = ""
    agent.context_manager = ContextManager(system_prompt_registry=agent._system_prompt_registry)
    agent._rebuild_query_engine = MagicMock()
    return agent


async def test_load_single_skill():
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        skills_dir.mkdir()
        _create_test_skill_file(skills_dir, "test-skill", "A test skill", ["测试"])

        loader = SkillLoader(str(skills_dir))
        await loader.load_skill_metadata()

        agent = _create_mock_agent()
        context = _create_mock_context(loader, agent)
        cmd = SkillCommand()

        result = await cmd.execute("load test-skill", context)

        assert result.type == ResultType.INFO
        assert "test-skill" in result.data["loaded"]
        assert len(result.data["loaded"]) == 1
        assert agent._system_prompt_registry.has_skill("test-skill")
        assert agent.context_manager.is_skill_loaded("test-skill")
        agent._rebuild_query_engine.assert_called()

    print("[PASS] 加载单个 Skill 测试通过")


async def test_load_multiple_skills():
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        skills_dir.mkdir()
        _create_test_skill_file(skills_dir, "skill-a", "Skill A", ["a"])
        _create_test_skill_file(skills_dir, "skill-b", "Skill B", ["b"])

        loader = SkillLoader(str(skills_dir))
        await loader.load_skill_metadata()

        agent = _create_mock_agent()
        context = _create_mock_context(loader, agent)
        cmd = SkillCommand()

        result = await cmd.execute("load skill-a skill-b", context)

        assert result.type == ResultType.INFO
        assert "skill-a" in result.data["loaded"]
        assert "skill-b" in result.data["loaded"]
        assert len(result.data["loaded"]) == 2
        assert agent._system_prompt_registry.has_skill("skill-a")
        assert agent._system_prompt_registry.has_skill("skill-b")

    print("[PASS] 加载多个 Skill 测试通过")


async def test_load_already_loaded_skill():
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        skills_dir.mkdir()
        _create_test_skill_file(skills_dir, "test-skill", "A test skill", ["测试"])

        loader = SkillLoader(str(skills_dir))
        await loader.load_skill_metadata()

        agent = _create_mock_agent()
        context = _create_mock_context(loader, agent)
        cmd = SkillCommand()

        await cmd.execute("load test-skill", context)
        result = await cmd.execute("load test-skill", context)

        assert result.type == ResultType.INFO
        assert "test-skill" in result.data["already_loaded"]
        assert len(result.data["loaded"]) == 0

    print("[PASS] 加载已加载 Skill 测试通过")


async def test_load_not_found_skill():
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        skills_dir.mkdir()

        loader = SkillLoader(str(skills_dir))
        await loader.load_skill_metadata()

        agent = _create_mock_agent()
        context = _create_mock_context(loader, agent)
        cmd = SkillCommand()

        result = await cmd.execute("load nonexistent", context)

        assert result.type == ResultType.INFO
        assert "nonexistent" in result.data["not_found"]
        assert len(result.data["not_found"]) == 1

    print("[PASS] 加载不存在的 Skill 测试通过")


async def test_load_no_name():
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        skills_dir.mkdir()

        loader = SkillLoader(str(skills_dir))
        await loader.load_skill_metadata()

        agent = _create_mock_agent()
        context = _create_mock_context(loader, agent)
        cmd = SkillCommand()

        result = await cmd.execute("load", context)

        assert result.type == ResultType.ERROR
        assert "请指定" in result.message

    print("[PASS] 未指定 Skill 名称测试通过")


async def test_load_mixed_results():
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        skills_dir.mkdir()
        _create_test_skill_file(skills_dir, "skill-a", "Skill A", ["a"])
        _create_test_skill_file(skills_dir, "skill-b", "Skill B", ["b"])

        loader = SkillLoader(str(skills_dir))
        await loader.load_skill_metadata()

        agent = _create_mock_agent()
        context = _create_mock_context(loader, agent)
        cmd = SkillCommand()

        await cmd.execute("load skill-a", context)
        result = await cmd.execute("load skill-a skill-b nonexistent", context)

        assert result.type == ResultType.INFO
        assert "skill-b" in result.data["loaded"]
        assert "skill-a" in result.data["already_loaded"]
        assert "nonexistent" in result.data["not_found"]

    print("[PASS] 混合结果测试通过")


async def test_usage_string():
    cmd = SkillCommand()
    assert "load" in cmd.usage

    print("[PASS] usage 字符串测试通过")


async def main():
    print("=" * 50)
    print("开始测试 /skill load 命令")
    print("=" * 50)

    await test_load_single_skill()
    await test_load_multiple_skills()
    await test_load_already_loaded_skill()
    await test_load_not_found_skill()
    await test_load_no_name()
    await test_load_mixed_results()
    await test_usage_string()

    print("=" * 50)
    print("所有测试通过！")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
