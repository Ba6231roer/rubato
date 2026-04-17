import pytest
from pathlib import Path

from src.skills.loader import SkillLoader


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


class TestLoadSkillMetadata:
    @pytest.mark.asyncio
    async def test_load_metadata_from_directory(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "skill-a.md", "skill-a", "Skill A",
                     triggers=["deploy"], body="Body A")
        _write_skill(skills_dir, "skill-b.md", "skill-b", "Skill B",
                     triggers=["test"], body="Body B")
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        result = await loader.load_skill_metadata()
        names = {m.name for m in result}
        assert names == {"skill-a", "skill-b"}

    @pytest.mark.asyncio
    async def test_load_metadata_skips_no_name(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        no_name_file = skills_dir / "no-name.md"
        no_name_file.write_text("# No YAML header\n\nJust text.", encoding="utf-8")
        loader = SkillLoader(skills_dir=str(skills_dir))
        result = await loader.load_skill_metadata()
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_load_metadata_recursive(self, tmp_path):
        skills_dir = tmp_path / "skills"
        sub_dir = skills_dir / "sub"
        _write_skill(sub_dir, "nested.md", "nested-skill", "Nested")
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        result = await loader.load_skill_metadata()
        assert len(result) == 1
        assert result[0].name == "nested-skill"

    @pytest.mark.asyncio
    async def test_load_metadata_nonexistent_dir(self, tmp_path):
        loader = SkillLoader(skills_dir=str(tmp_path / "nonexistent"))
        result = await loader.load_skill_metadata()
        assert result == []


class TestEnabledSkillsFilter:
    @pytest.mark.asyncio
    async def test_enabled_skills_whitelist(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "skill-a.md", "skill-a", "A")
        _write_skill(skills_dir, "skill-b.md", "skill-b", "B")
        _write_skill(skills_dir, "skill-c.md", "skill-c", "C")
        loader = SkillLoader(
            skills_dir=str(skills_dir),
            enabled_skills=["skill-a", "skill-c"],
            max_loaded_skills=10
        )
        result = await loader.load_skill_metadata()
        names = {m.name for m in result}
        assert names == {"skill-a", "skill-c"}

    @pytest.mark.asyncio
    async def test_enabled_skills_empty_loads_all(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "skill-a.md", "skill-a", "A")
        _write_skill(skills_dir, "skill-b.md", "skill-b", "B")
        loader = SkillLoader(
            skills_dir=str(skills_dir),
            enabled_skills=[],
            max_loaded_skills=10
        )
        result = await loader.load_skill_metadata()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_enabled_skills_none_loads_all(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "skill-a.md", "skill-a", "A")
        loader = SkillLoader(
            skills_dir=str(skills_dir),
            enabled_skills=None,
            max_loaded_skills=10
        )
        result = await loader.load_skill_metadata()
        assert len(result) == 1


class TestGetSkillContent:
    @pytest.mark.asyncio
    async def test_load_full_skill_returns_body(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "my-skill.md", "my-skill", "My Skill",
                     body="# My Skill Body\n\nDetailed content.")
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        await loader.load_skill_metadata()
        content = await loader.load_full_skill("my-skill")
        assert "# My Skill Body" in content
        assert "Detailed content." in content
        assert "---" not in content
        assert "name: my-skill" not in content

    @pytest.mark.asyncio
    async def test_load_full_skill_nonexistent(self, tmp_path):
        loader = SkillLoader(skills_dir=str(tmp_path / "skills"))
        content = await loader.load_full_skill("ghost")
        assert content == ""

    @pytest.mark.asyncio
    async def test_load_full_skill_uses_cache(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "cached.md", "cached", "Cached", body="Cached body")
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        await loader.load_skill_metadata()
        content1 = await loader.load_full_skill("cached")
        content2 = await loader.load_full_skill("cached")
        assert content1 == content2 == "Cached body"

    def test_get_skill_content_sync(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "sync.md", "sync-skill", "Sync", body="Sync body")
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        import asyncio
        asyncio.run(loader.load_skill_metadata())
        content = loader.get_skill_content_sync("sync-skill")
        assert "Sync body" in content
        assert "---" not in content


class TestHelperMethods:
    @pytest.mark.asyncio
    async def test_list_skills(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "a.md", "skill-a", "A")
        _write_skill(skills_dir, "b.md", "skill-b", "B")
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        await loader.load_skill_metadata()
        names = {s.name for s in loader.list_skills()}
        assert names == {"skill-a", "skill-b"}

    @pytest.mark.asyncio
    async def test_find_matching_skill(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "deploy.md", "deploy", "Deploy",
                     triggers=["deploy", "发布"])
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        await loader.load_skill_metadata()
        assert loader.find_matching_skill("please deploy") == "deploy"
        assert loader.find_matching_skill("请发布") == "deploy"
        assert loader.find_matching_skill("nothing") is None

    @pytest.mark.asyncio
    async def test_get_all_skill_metadata(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "a.md", "skill-a", "Desc A",
                     triggers=["trigger-a"], tools=["tool-a"])
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        await loader.load_skill_metadata()
        meta = loader.get_all_skill_metadata()
        assert "skill-a" in meta
        assert meta["skill-a"]["name"] == "skill-a"
        assert meta["skill-a"]["description"] == "Desc A"
        assert meta["skill-a"]["triggers"] == ["trigger-a"]
        assert meta["skill-a"]["required_tools"] == ["tool-a"]

    @pytest.mark.asyncio
    async def test_is_skill_enabled(self, tmp_path):
        loader = SkillLoader(
            skills_dir=str(tmp_path / "skills"),
            enabled_skills=["a", "b"]
        )
        assert loader.is_skill_enabled("a") is True
        assert loader.is_skill_enabled("c") is False

    @pytest.mark.asyncio
    async def test_is_skill_enabled_no_filter(self, tmp_path):
        loader = SkillLoader(skills_dir=str(tmp_path / "skills"))
        assert loader.is_skill_enabled("anything") is True

    @pytest.mark.asyncio
    async def test_has_skill(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "exists.md", "exists", "Exists")
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        await loader.load_skill_metadata()
        assert loader.has_skill("exists") is True
        assert loader.has_skill("ghost") is False

    @pytest.mark.asyncio
    async def test_get_registry(self, tmp_path):
        loader = SkillLoader(skills_dir=str(tmp_path / "skills"))
        from src.skills.registry import SkillRegistry
        assert isinstance(loader.get_registry(), SkillRegistry)
