import os
import pytest
from pathlib import Path

from src.skills.manager import SkillManager, ConditionalSkill
from src.skills.parser import SkillMetadata


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


class TestConditionalSkill:
    def test_matches_gitwildmatch_pattern(self):
        skill = SkillMetadata(
            name="req-skill",
            description="Requirements skill",
            paths=["requirements/**/*.md", "docs/**/*.md"]
        )
        cs = ConditionalSkill(skill=skill, path_patterns=skill.paths)
        cwd = os.getcwd()
        assert cs.matches("requirements/test.md", cwd) is True
        assert cs.matches("requirements/sub/deep.md", cwd) is True
        assert cs.matches("docs/guide.md", cwd) is True
        assert cs.matches("src/main.py", cwd) is False
        assert cs.matches("README.md", cwd) is False

    def test_matches_no_patterns_returns_false(self):
        skill = SkillMetadata(name="no-paths", description="No paths")
        cs = ConditionalSkill(skill=skill, path_patterns=[])
        assert cs.matches("any/file.md", os.getcwd()) is False

    def test_matches_star_pattern(self):
        skill = SkillMetadata(
            name="py-skill",
            description="Python skill",
            paths=["**/*.py"]
        )
        cs = ConditionalSkill(skill=skill, path_patterns=skill.paths)
        cwd = os.getcwd()
        assert cs.matches("src/main.py", cwd) is True
        assert cs.matches("deep/nested/module.py", cwd) is True
        assert cs.matches("src/main.js", cwd) is False


class TestSkillManagerLoadSkills:
    @pytest.mark.asyncio
    async def test_load_separates_conditional_and_unconditional(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "uncond.md", "uncond-skill", "Unconditional",
                     triggers=["test"], body="Unconditional body")
        _write_skill(skills_dir, "cond.md", "cond-skill", "Conditional",
                     triggers=["cond"], paths=["src/**/*.py"], body="Conditional body")
        manager = SkillManager(skills_dir=str(skills_dir), cwd=str(tmp_path))
        result = await manager.load_skills()
        names = {s.name for s in result}
        assert "uncond-skill" in names
        assert "cond-skill" not in names
        assert manager.get_conditional_skills_count() == 1

    @pytest.mark.asyncio
    async def test_load_from_additional_dirs(self, tmp_path):
        skills_dir = tmp_path / "skills"
        extra_dir = tmp_path / "extra"
        _write_skill(skills_dir, "main.md", "main-skill", "Main")
        _write_skill(extra_dir, "extra.md", "extra-skill", "Extra")
        manager = SkillManager(
            skills_dir=str(skills_dir),
            additional_dirs=[str(extra_dir)],
            cwd=str(tmp_path)
        )
        result = await manager.load_skills()
        names = {s.name for s in result}
        assert "main-skill" in names
        assert "extra-skill" in names

    @pytest.mark.asyncio
    async def test_deduplicate_skills(self, tmp_path):
        skills_dir = tmp_path / "skills"
        extra_dir = tmp_path / "extra"
        _write_skill(skills_dir, "dup.md", "dup-skill", "From main")
        _write_skill(extra_dir, "dup.md", "dup-skill", "From extra")
        manager = SkillManager(
            skills_dir=str(skills_dir),
            additional_dirs=[str(extra_dir)],
            cwd=str(tmp_path)
        )
        result = await manager.load_skills()
        dup_skills = [s for s in result if s.name == "dup-skill"]
        assert len(dup_skills) == 1

    @pytest.mark.asyncio
    async def test_load_with_managed_and_user_dirs(self, tmp_path):
        skills_dir = tmp_path / "skills"
        managed_dir = tmp_path / "managed"
        user_dir = tmp_path / "user"
        _write_skill(skills_dir, "base.md", "base-skill", "Base")
        _write_skill(managed_dir, "managed.md", "managed-skill", "Managed")
        _write_skill(user_dir, "user.md", "user-skill", "User")
        manager = SkillManager(skills_dir=str(skills_dir), cwd=str(tmp_path))
        manager.set_managed_skills_dir(str(managed_dir))
        manager.set_user_skills_dir(str(user_dir))
        result = await manager.load_skills()
        names = {s.name for s in result}
        assert "base-skill" in names
        assert "managed-skill" in names
        assert "user-skill" in names


class TestActivateForPaths:
    @pytest.mark.asyncio
    async def test_activate_matching_conditional_skill(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "cond.md", "cond-skill", "Conditional",
                     paths=["requirements/**/*.md"], body="Cond body")
        manager = SkillManager(skills_dir=str(skills_dir), cwd=str(tmp_path))
        await manager.load_skills()
        assert manager.get_conditional_skills_count() == 1
        req_dir = tmp_path / "requirements"
        req_dir.mkdir()
        test_file = req_dir / "test.md"
        test_file.write_text("# Test", encoding="utf-8")
        activated = manager.activate_for_paths([str(test_file)])
        assert activated == ["cond-skill"]
        assert manager.get_conditional_skills_count() == 0
        assert manager.get_dynamic_skills_count() == 1

    @pytest.mark.asyncio
    async def test_activate_no_match(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "cond.md", "cond-skill", "Conditional",
                     paths=["requirements/**/*.md"])
        manager = SkillManager(skills_dir=str(skills_dir), cwd=str(tmp_path))
        await manager.load_skills()
        activated = manager.activate_for_paths([str(tmp_path / "src" / "main.py")])
        assert activated == []
        assert manager.get_conditional_skills_count() == 1

    @pytest.mark.asyncio
    async def test_activate_stores_content(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "cond.md", "cond-skill", "Conditional",
                     paths=["src/**/*.py"], body="Skill body content")
        manager = SkillManager(skills_dir=str(skills_dir), cwd=str(tmp_path))
        await manager.load_skills()
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        py_file = src_dir / "main.py"
        py_file.write_text("pass", encoding="utf-8")
        manager.activate_for_paths([str(py_file)])
        content = manager.registry.get_content("cond-skill")
        assert content == "Skill body content"


class TestDiscoverForPaths:
    @pytest.mark.asyncio
    async def test_discover_nested_skills_dir(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        nested_dir = tmp_path / "project" / ".skills"
        _write_skill(nested_dir, "nested.md", "nested-skill", "Nested",
                     body="Nested body")
        project_file = tmp_path / "project" / "README.md"
        project_file.parent.mkdir(parents=True, exist_ok=True)
        project_file.write_text("# Project", encoding="utf-8")
        manager = SkillManager(skills_dir=str(skills_dir), cwd=str(tmp_path))
        discovered = manager.discover_for_paths([str(project_file)])
        assert "nested-skill" in discovered
        assert manager.get_dynamic_skills_count() == 1

    @pytest.mark.asyncio
    async def test_discover_no_nested_dir(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        manager = SkillManager(skills_dir=str(skills_dir), cwd=str(tmp_path))
        project_file = tmp_path / "project" / "README.md"
        project_file.parent.mkdir(parents=True, exist_ok=True)
        project_file.write_text("# No skills dir", encoding="utf-8")
        discovered = manager.discover_for_paths([str(project_file)])
        assert discovered == []

    @pytest.mark.asyncio
    async def test_discover_skips_already_discovered(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        nested_dir = tmp_path / "project" / ".skills"
        _write_skill(nested_dir, "nested.md", "nested-skill", "Nested")
        project_file = tmp_path / "project" / "README.md"
        project_file.parent.mkdir(parents=True, exist_ok=True)
        project_file.write_text("# Project", encoding="utf-8")
        manager = SkillManager(skills_dir=str(skills_dir), cwd=str(tmp_path))
        first = manager.discover_for_paths([str(project_file)])
        second = manager.discover_for_paths([str(project_file)])
        assert len(first) == 1
        assert second == []

    @pytest.mark.asyncio
    async def test_discover_respects_max_depth(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        deep_dir = tmp_path / "a" / ".skills"
        _write_skill(deep_dir, "deep.md", "deep-skill", "Deep")
        deep_file = tmp_path / "a" / "b" / "c" / "file.txt"
        deep_file.parent.mkdir(parents=True, exist_ok=True)
        deep_file.write_text("deep", encoding="utf-8")
        manager = SkillManager(skills_dir=str(skills_dir), cwd=str(tmp_path))
        discovered = manager.discover_for_paths([str(deep_file)], max_depth=1)
        assert "deep-skill" not in discovered


class TestTriggerMatching:
    @pytest.mark.asyncio
    async def test_trigger_match_via_registry(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "deploy.md", "deploy-skill", "Deploy",
                     triggers=["deploy", "发布"])
        manager = SkillManager(skills_dir=str(skills_dir), cwd=str(tmp_path))
        await manager.load_skills()
        assert manager.find_matching_skill("please deploy the app") == "deploy-skill"
        assert manager.find_matching_skill("请发布应用") == "deploy-skill"
        assert manager.find_matching_skill("nothing here") is None


class TestGetAllActiveSkills:
    @pytest.mark.asyncio
    async def test_includes_dynamic_skills(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "base.md", "base-skill", "Base")
        _write_skill(skills_dir, "cond.md", "cond-skill", "Conditional",
                     paths=["src/**/*.py"])
        manager = SkillManager(skills_dir=str(skills_dir), cwd=str(tmp_path))
        await manager.load_skills()
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        py_file = src_dir / "main.py"
        py_file.write_text("pass", encoding="utf-8")
        manager.activate_for_paths([str(py_file)])
        active = manager.get_all_active_skills()
        names = {s.name for s in active}
        assert "base-skill" in names
        assert "cond-skill" in names

    @pytest.mark.asyncio
    async def test_no_duplicates(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "base.md", "base-skill", "Base")
        manager = SkillManager(skills_dir=str(skills_dir), cwd=str(tmp_path))
        await manager.load_skills()
        active = manager.get_all_active_skills()
        names = [s.name for s in active]
        assert names.count("base-skill") == 1


class TestClearAndReset:
    @pytest.mark.asyncio
    async def test_clear_dynamic_skills(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        manager = SkillManager(skills_dir=str(skills_dir), cwd=str(tmp_path))
        manager.dynamic_skills.append(SkillMetadata(name="dyn", description="Dynamic"))
        assert manager.get_dynamic_skills_count() == 1
        manager.clear_dynamic_skills()
        assert manager.get_dynamic_skills_count() == 0

    @pytest.mark.asyncio
    async def test_reset_conditional_skills(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "cond.md", "cond-skill", "Conditional",
                     paths=["src/**/*.py"])
        manager = SkillManager(skills_dir=str(skills_dir), cwd=str(tmp_path))
        await manager.load_skills()
        assert manager.get_conditional_skills_count() == 1
        manager.reset_conditional_skills()
        assert manager.get_conditional_skills_count() == 0
