import pytest
from pathlib import Path

from src.skills.loader import SkillLoader


def _write_skill(directory: Path, filename: str, name: str, description: str = "",
                 triggers: list = None, tools: list = None, paths: list = None,
                 category: str = "", created_by: str = "",
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
    if category:
        yaml_parts.append(f"category: {category}")
    if created_by:
        yaml_parts.append(f"created_by: {created_by}")
    yaml_header = "\n".join(yaml_parts)
    content = f"---\n{yaml_header}\n---\n\n{body}"
    skill_file = directory / filename
    skill_file.write_text(content, encoding="utf-8")
    return skill_file


class TestDirectoryStyleSkillLoading:
    @pytest.mark.asyncio
    async def test_loads_skill_md_file(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skill_subdir = skills_dir / "my-skill"
        _write_skill(skill_subdir, "SKILL.md", "my-skill", "Directory style",
                     body="Directory body")
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        result = await loader.load_skill_metadata()
        assert len(result) == 1
        assert result[0].name == "my-skill"
        assert "SKILL.md" in result[0].file_path

    @pytest.mark.asyncio
    async def test_loads_nested_directory_style_skill(self, tmp_path):
        skills_dir = tmp_path / "skills"
        deep_dir = skills_dir / "category" / "deep-skill"
        _write_skill(deep_dir, "SKILL.md", "deep-skill", "Deep nested",
                     body="Deep body")
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        result = await loader.load_skill_metadata()
        assert len(result) == 1
        assert result[0].name == "deep-skill"


class TestFlatStyleSkillLoading:
    @pytest.mark.asyncio
    async def test_loads_flat_md_file(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "flat-skill.md", "flat-skill", "Flat style",
                     body="Flat body")
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        result = await loader.load_skill_metadata()
        assert len(result) == 1
        assert result[0].name == "flat-skill"

    @pytest.mark.asyncio
    async def test_loads_nested_flat_md_file(self, tmp_path):
        skills_dir = tmp_path / "skills"
        sub_dir = skills_dir / "sub"
        _write_skill(sub_dir, "nested-flat.md", "nested-flat", "Nested flat",
                     body="Nested flat body")
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        result = await loader.load_skill_metadata()
        assert len(result) == 1
        assert result[0].name == "nested-flat"


class TestDirectoryStylePriorityOverFlat:
    @pytest.mark.asyncio
    async def test_skill_md_takes_priority_over_other_md_in_same_dir(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skill_subdir = skills_dir / "my-skill"
        _write_skill(skill_subdir, "SKILL.md", "dir-skill", "From SKILL.md",
                     body="Directory body")
        _write_skill(skill_subdir, "other.md", "other-skill", "From other.md",
                     body="Other body")
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        result = await loader.load_skill_metadata()
        names = {m.name for m in result}
        assert "dir-skill" in names
        assert "other-skill" not in names

    @pytest.mark.asyncio
    async def test_flat_md_in_different_dir_still_loaded(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skill_subdir = skills_dir / "dir-skill"
        _write_skill(skill_subdir, "SKILL.md", "dir-skill", "From SKILL.md",
                     body="Directory body")
        _write_skill(skills_dir, "flat-skill.md", "flat-skill", "Flat skill",
                     body="Flat body")
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        result = await loader.load_skill_metadata()
        names = {m.name for m in result}
        assert "dir-skill" in names
        assert "flat-skill" in names

    @pytest.mark.asyncio
    async def test_mixed_styles_in_different_directories(self, tmp_path):
        skills_dir = tmp_path / "skills"
        dir_skill = skills_dir / "dir-style"
        _write_skill(dir_skill, "SKILL.md", "dir-style-skill", "Directory style")
        _write_skill(skills_dir, "flat-style.md", "flat-style-skill", "Flat style")
        another_dir = skills_dir / "another"
        _write_skill(another_dir, "SKILL.md", "another-dir-skill", "Another dir style")
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        result = await loader.load_skill_metadata()
        names = {m.name for m in result}
        assert names == {"dir-style-skill", "flat-style-skill", "another-dir-skill"}


class TestGetAllSkillMetadataNewFields:
    @pytest.mark.asyncio
    async def test_includes_category_field(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "cat.md", "cat-skill", "Categorized",
                     category="coding")
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        await loader.load_skill_metadata()
        meta = loader.get_all_skill_metadata()
        assert "cat-skill" in meta
        assert meta["cat-skill"]["category"] == "coding"

    @pytest.mark.asyncio
    async def test_includes_created_by_field(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "agent.md", "agent-skill", "Agent created",
                     created_by="agent")
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        await loader.load_skill_metadata()
        meta = loader.get_all_skill_metadata()
        assert "agent-skill" in meta
        assert meta["agent-skill"]["created_by"] == "agent"

    @pytest.mark.asyncio
    async def test_default_created_by_is_human(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "human.md", "human-skill", "Human created")
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        await loader.load_skill_metadata()
        meta = loader.get_all_skill_metadata()
        assert meta["human-skill"]["created_by"] == "human"

    @pytest.mark.asyncio
    async def test_default_category_is_empty(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(skills_dir, "nocat.md", "nocat-skill", "No category")
        loader = SkillLoader(skills_dir=str(skills_dir), max_loaded_skills=10)
        await loader.load_skill_metadata()
        meta = loader.get_all_skill_metadata()
        assert meta["nocat-skill"]["category"] == ""
