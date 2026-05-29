import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.skills import SkillLoader, SkillMetadata


def _make_skill_file(skills_dir: Path, name: str, description: str = "") -> Path:
    content = f"""---
name: {name}
description: {description}
---
# {name}

Body text.
"""
    skill_file = skills_dir / f"{name}.md"
    skill_file.write_text(content, encoding="utf-8")
    return skill_file


def test_empty_disabled_skills_loads_all():
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        skills_dir.mkdir()
        _make_skill_file(skills_dir, "alpha", "A")
        _make_skill_file(skills_dir, "beta", "B")
        _make_skill_file(skills_dir, "gamma", "C")

        loader = SkillLoader(skills_dir=str(skills_dir), disabled_skills=None)
        loaded = loader._load_skills_from_dir(skills_dir)

        names = [m.name for m in loaded]
        assert set(names) == {"alpha", "beta", "gamma"}


def test_empty_list_disabled_skills_loads_all():
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        skills_dir.mkdir()
        _make_skill_file(skills_dir, "alpha", "A")
        _make_skill_file(skills_dir, "beta", "B")

        loader = SkillLoader(skills_dir=str(skills_dir), disabled_skills=[])
        loaded = loader._load_skills_from_dir(skills_dir)

        names = [m.name for m in loaded]
        assert set(names) == {"alpha", "beta"}


def test_non_empty_disabled_skills_excludes_listed():
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        skills_dir.mkdir()
        _make_skill_file(skills_dir, "keep-this", "kept")
        _make_skill_file(skills_dir, "test-skill", "excluded")
        _make_skill_file(skills_dir, "another-ok", "ok")

        loader = SkillLoader(
            skills_dir=str(skills_dir), disabled_skills=["test-skill"]
        )
        loaded = loader._load_skills_from_dir(skills_dir)

        names = [m.name for m in loaded]
        assert "test-skill" not in names
        assert set(names) == {"keep-this", "another-ok"}


def test_disabled_skills_excludes_multiple():
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        skills_dir.mkdir()
        _make_skill_file(skills_dir, "a", "A")
        _make_skill_file(skills_dir, "b", "B")
        _make_skill_file(skills_dir, "c", "C")
        _make_skill_file(skills_dir, "d", "D")

        loader = SkillLoader(
            skills_dir=str(skills_dir), disabled_skills=["b", "d"]
        )
        loaded = loader._load_skills_from_dir(skills_dir)

        names = [m.name for m in loaded]
        assert set(names) == {"a", "c"}


def test_is_skill_enabled_empty_blacklist():
    loader = SkillLoader(skills_dir="/tmp/nonexistent", disabled_skills=None)
    assert loader.is_skill_enabled("anything") is True
    assert loader.is_skill_enabled("test-skill") is True


def test_is_skill_enabled_empty_list():
    loader = SkillLoader(skills_dir="/tmp/nonexistent", disabled_skills=[])
    assert loader.is_skill_enabled("anything") is True


def test_is_skill_enabled_non_empty_blacklist():
    loader = SkillLoader(
        skills_dir="/tmp/nonexistent", disabled_skills=["test-skill", "blocked"]
    )
    assert loader.is_skill_enabled("test-skill") is False
    assert loader.is_skill_enabled("blocked") is False
    assert loader.is_skill_enabled("allowed") is True


def test_register_skill_from_agent_bypasses_blacklist():
    loader = SkillLoader(
        skills_dir="/tmp/nonexistent", disabled_skills=["new-skill"]
    )
    assert loader.is_skill_enabled("new-skill") is False

    metadata = loader.register_skill_from_agent(
        name="new-skill",
        description="Agent-created skill",
        content="body",
        triggers=["trigger"],
        category="test",
    )

    assert metadata.name == "new-skill"
    assert loader.has_skill("new-skill") is True
    assert loader.registry.get_content("new-skill") == "body"
