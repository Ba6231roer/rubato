import pytest
from pathlib import Path

from src.skills.manager import SkillManager


def _write_skill(directory: Path, filename: str, name: str, description: str = "",
                 triggers: list = None, tools: list = None, paths: list = None,
                 body: str = "") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    yaml_parts = [f"name: {name}"]
    if description:
        yaml_parts.append(f"description: {description}")
    if triggers:
        yaml_parts.append("triggers:")
        for t in triggers:
            yaml_parts.append(f'  - "{t}"')
    if tools:
        yaml_parts.append("tools:")
        for t in tools:
            yaml_parts.append(f"  - {t}")
    if paths:
        yaml_parts.append("paths:")
        for p in paths:
            yaml_parts.append(f'  - "{p}"')
    yaml_header = "\n".join(yaml_parts)
    content = f"---\n{yaml_header}\n---\n\n{body}"
    skill_file = directory / filename
    skill_file.write_text(content, encoding="utf-8")
    return skill_file


class TestRegisterSkillFromAgent:
    def test_creates_metadata_with_created_by_agent(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        manager = SkillManager(skills_dir=str(skills_dir), cwd=str(tmp_path))
        metadata = manager.register_skill_from_agent(
            name="agent-skill",
            description="Created by agent",
            content="Agent skill body",
        )
        assert metadata.name == "agent-skill"
        assert metadata.description == "Created by agent"
        assert metadata.created_by == "agent"
        assert metadata.updated_at != ""

    def test_registers_to_registry(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        manager = SkillManager(skills_dir=str(skills_dir), cwd=str(tmp_path))
        manager.register_skill_from_agent(
            name="reg-skill",
            description="Registered skill",
            content="Registered body",
        )
        assert manager.registry.has_skill("reg-skill")
        assert manager.registry.get_content("reg-skill") == "Registered body"

    def test_with_triggers(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        manager = SkillManager(skills_dir=str(skills_dir), cwd=str(tmp_path))
        metadata = manager.register_skill_from_agent(
            name="trigger-skill",
            description="With triggers",
            content="Body",
            triggers=["deploy", "发布"],
        )
        assert metadata.triggers == ["deploy", "发布"]

    def test_with_category(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        manager = SkillManager(skills_dir=str(skills_dir), cwd=str(tmp_path))
        metadata = manager.register_skill_from_agent(
            name="cat-skill",
            description="With category",
            content="Body",
            category="coding",
        )
        assert metadata.category == "coding"

    def test_with_paths_creates_conditional_skill(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        manager = SkillManager(skills_dir=str(skills_dir), cwd=str(tmp_path))
        metadata = manager.register_skill_from_agent(
            name="path-skill",
            description="With paths",
            content="Path body",
            triggers=["path"],
        )
        metadata.paths = ["src/**/*.py"]
        from src.skills.manager import ConditionalSkill
        cs = ConditionalSkill(
            skill=metadata,
            path_patterns=metadata.paths,
            content="Path body",
        )
        manager.conditional_skills.append(cs)
        assert manager.get_conditional_skills_count() == 1


class TestUpdateSkillFromAgent:
    @pytest.mark.asyncio
    async def test_updates_content(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "existing.md", "existing-skill", "Existing",
                     body="Old body")
        manager = SkillManager(skills_dir=str(skills_dir), cwd=str(tmp_path))
        await manager.load_skills()
        result = manager.update_skill_from_agent("existing-skill", "New body")
        assert result is True
        assert manager.registry.get_content("existing-skill") == "New body"

    @pytest.mark.asyncio
    async def test_returns_false_for_nonexistent_skill(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        manager = SkillManager(skills_dir=str(skills_dir), cwd=str(tmp_path))
        result = manager.update_skill_from_agent("ghost-skill", "Some content")
        assert result is False

    def test_returns_true_for_agent_registered_skill(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        manager = SkillManager(skills_dir=str(skills_dir), cwd=str(tmp_path))
        manager.register_skill_from_agent(
            name="agent-skill",
            description="Agent created",
            content="Original body",
        )
        result = manager.update_skill_from_agent("agent-skill", "Updated body")
        assert result is True
        assert manager.registry.get_content("agent-skill") == "Updated body"

    @pytest.mark.asyncio
    async def test_updates_timestamp(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "ts-skill.md", "ts-skill", "Timestamp",
                     body="Old body")
        manager = SkillManager(skills_dir=str(skills_dir), cwd=str(tmp_path))
        await manager.load_skills()
        old_updated_at = manager.registry.get_skill("ts-skill").updated_at
        manager.update_skill_from_agent("ts-skill", "New body")
        new_updated_at = manager.registry.get_skill("ts-skill").updated_at
        assert new_updated_at != ""
