import asyncio
import json
from pathlib import Path

import pytest

from src.skills.manager import SkillManager
from src.tools.skill_manage import create_skill_manage_tool


VALID_CONTENT = "---\nname: test-skill\ndescription: A test skill\n---\n\n# Test Skill\n\nThis is a test."


@pytest.fixture
def skill_manager(tmp_path):
    return SkillManager(skills_dir=str(tmp_path))


@pytest.fixture
def tool(skill_manager):
    return create_skill_manage_tool(skill_manager)


def run_tool(tool, **kwargs):
    return asyncio.run(tool.ainvoke(kwargs))


class TestSkillManageCreate:
    def test_create_success(self, tool, skill_manager, tmp_path):
        result = run_tool(tool, action="create", name="test-skill", description="A test skill", content=VALID_CONTENT)
        result_data = json.loads(result)
        assert result_data["success"] is True
        assert (tmp_path / ".self-improved" / "test-skill" / "SKILL.md").exists()
        assert skill_manager.has_skill("test-skill")

    def test_create_registers_in_registry(self, tool, skill_manager):
        run_tool(tool, action="create", name="test-skill", description="A test skill", content=VALID_CONTENT)
        meta = skill_manager.registry.get_skill("test-skill")
        assert meta is not None
        assert meta.name == "test-skill"
        assert meta.created_by == "agent"

    def test_create_result_contains_path(self, tool, tmp_path):
        result = run_tool(tool, action="create", name="test-skill", description="A test skill", content=VALID_CONTENT)
        result_data = json.loads(result)
        expected_path = str(tmp_path / ".self-improved" / "test-skill" / "SKILL.md")
        assert result_data["path"] == expected_path

    def test_create_name_collision(self, tool):
        run_tool(tool, action="create", name="test-skill", description="A test skill", content=VALID_CONTENT)
        result = run_tool(tool, action="create", name="test-skill", description="Another", content=VALID_CONTENT)
        result_data = json.loads(result)
        assert result_data["success"] is False
        assert "already exists" in result_data["error"]


class TestSkillManagePatch:
    def test_patch_success(self, tool, skill_manager, tmp_path):
        run_tool(tool, action="create", name="test-skill", description="A test skill", content=VALID_CONTENT)
        result = run_tool(
            tool,
            action="patch",
            name="test-skill",
            old_string="This is a test.",
            new_string="This is patched.",
        )
        result_data = json.loads(result)
        assert result_data["success"] is True
        file_path = tmp_path / ".self-improved" / "test-skill" / "SKILL.md"
        patched_content = file_path.read_text(encoding="utf-8")
        assert "This is patched." in patched_content
        assert "This is a test." not in patched_content

    def test_patch_creates_backup(self, tool, tmp_path):
        run_tool(tool, action="create", name="test-skill", description="A test skill", content=VALID_CONTENT)
        result = run_tool(
            tool,
            action="patch",
            name="test-skill",
            old_string="This is a test.",
            new_string="This is patched.",
        )
        result_data = json.loads(result)
        assert "backup" in result_data
        backups_dir = tmp_path / ".backups"
        assert backups_dir.exists()
        backup_files = list(backups_dir.glob("*.md"))
        assert len(backup_files) == 1

    def test_patch_updates_registry(self, tool, skill_manager):
        run_tool(tool, action="create", name="test-skill", description="A test skill", content=VALID_CONTENT)
        run_tool(
            tool,
            action="patch",
            name="test-skill",
            old_string="This is a test.",
            new_string="This is patched.",
        )
        meta = skill_manager.registry.get_skill("test-skill")
        assert meta is not None
        assert meta.updated_at != ""

    def test_patch_old_string_not_found(self, tool):
        run_tool(tool, action="create", name="test-skill", description="A test skill", content=VALID_CONTENT)
        result = run_tool(
            tool,
            action="patch",
            name="test-skill",
            old_string="nonexistent text",
            new_string="replacement",
        )
        result_data = json.loads(result)
        assert result_data["success"] is False
        assert "not found" in result_data["error"]

    def test_patch_skill_not_found(self, tool):
        result = run_tool(
            tool,
            action="patch",
            name="no-such-skill",
            old_string="old",
            new_string="new",
        )
        result_data = json.loads(result)
        assert result_data["success"] is False
        assert "not found" in result_data["error"]


class TestSkillManageEdit:
    def test_edit_success(self, tool, tmp_path):
        run_tool(tool, action="create", name="test-skill", description="A test skill", content=VALID_CONTENT)
        new_content = "---\nname: test-skill\ndescription: Updated skill\n---\n\n# Updated\n\nCompletely new content."
        result = run_tool(tool, action="edit", name="test-skill", content=new_content)
        result_data = json.loads(result)
        assert result_data["success"] is True
        file_path = tmp_path / ".self-improved" / "test-skill" / "SKILL.md"
        file_content = file_path.read_text(encoding="utf-8")
        assert "Completely new content." in file_content
        assert "This is a test." not in file_content

    def test_edit_creates_backup(self, tool, tmp_path):
        run_tool(tool, action="create", name="test-skill", description="A test skill", content=VALID_CONTENT)
        new_content = "---\nname: test-skill\ndescription: Updated skill\n---\n\n# Updated\n\nCompletely new content."
        result = run_tool(tool, action="edit", name="test-skill", content=new_content)
        result_data = json.loads(result)
        assert "backup" in result_data
        backups_dir = tmp_path / ".backups"
        assert backups_dir.exists()
        backup_files = list(backups_dir.glob("*.md"))
        assert len(backup_files) == 1

    def test_edit_skill_not_found(self, tool):
        new_content = "---\nname: no-skill\ndescription: No\n---\n\n# No\n\nContent."
        result = run_tool(tool, action="edit", name="no-such-skill", content=new_content)
        result_data = json.loads(result)
        assert result_data["success"] is False
        assert "not found" in result_data["error"]


class TestSkillManageList:
    def test_list_returns_skill(self, tool):
        run_tool(tool, action="create", name="test-skill", description="A test skill", content=VALID_CONTENT)
        result = run_tool(tool, action="list")
        assert "test-skill" in result
        assert "A test skill" in result

    def test_list_empty(self, tool):
        result = run_tool(tool, action="list")
        assert result == "No skills available."

    def test_list_shows_created_by(self, tool):
        run_tool(tool, action="create", name="test-skill", description="A test skill", content=VALID_CONTENT)
        result = run_tool(tool, action="list")
        assert "created_by: agent" in result


class TestSkillManageView:
    def test_view_returns_full_content(self, tool):
        run_tool(tool, action="create", name="test-skill", description="A test skill", content=VALID_CONTENT)
        result = run_tool(tool, action="view", name="test-skill")
        assert "---" in result
        assert "name: test-skill" in result
        assert "description: A test skill" in result
        assert "# Test Skill" in result

    def test_view_nonexistent_skill(self, tool):
        result = run_tool(tool, action="view", name="no-such-skill")
        result_data = json.loads(result)
        assert result_data["success"] is False
        assert "not found" in result_data["error"]


class TestSkillManageNameValidation:
    def test_invalid_name_uppercase(self, tool):
        content = "---\nname: TestSkill\ndescription: Bad\n---\n\n# Bad\n\nContent."
        result = run_tool(tool, action="create", name="TestSkill", description="Bad", content=content)
        result_data = json.loads(result)
        assert result_data["success"] is False
        assert "must match pattern" in result_data["error"]

    def test_invalid_name_spaces(self, tool):
        content = "---\nname: test skill\ndescription: Bad\n---\n\n# Bad\n\nContent."
        result = run_tool(tool, action="create", name="test skill", description="Bad", content=content)
        result_data = json.loads(result)
        assert result_data["success"] is False

    def test_invalid_name_empty(self, tool):
        result = run_tool(tool, action="create", name="", description="Bad", content="content")
        result_data = json.loads(result)
        assert result_data["success"] is False
        assert "cannot be empty" in result_data["error"]

    def test_valid_name_with_dots_and_hyphens(self, tool, skill_manager):
        content = "---\nname: my.skill-v2\ndescription: Valid\n---\n\n# Valid\n\nContent."
        result = run_tool(tool, action="create", name="my.skill-v2", description="Valid", content=content)
        result_data = json.loads(result)
        assert result_data["success"] is True
        assert skill_manager.has_skill("my.skill-v2")


class TestSkillManageFrontmatterValidation:
    def test_create_missing_frontmatter(self, tool):
        result = run_tool(tool, action="create", name="bad-skill", description="Bad", content="No frontmatter here")
        result_data = json.loads(result)
        assert result_data["success"] is False
        assert "frontmatter" in result_data["error"]

    def test_create_empty_frontmatter(self, tool):
        content = "---\n---\n\nSome body"
        result = run_tool(tool, action="create", name="bad-skill", description="Bad", content=content)
        result_data = json.loads(result)
        assert result_data["success"] is False

    def test_create_missing_name_in_frontmatter(self, tool):
        content = "---\ndescription: No name\n---\n\n# No name\n\nContent."
        result = run_tool(tool, action="create", name="bad-skill", description="Bad", content=content)
        result_data = json.loads(result)
        assert result_data["success"] is False
        assert "name" in result_data["error"]

    def test_create_missing_description_in_frontmatter(self, tool):
        content = "---\nname: no-desc\n---\n\n# No desc\n\nContent."
        result = run_tool(tool, action="create", name="no-desc", description="Desc", content=content)
        result_data = json.loads(result)
        assert result_data["success"] is False
        assert "description" in result_data["error"]

    def test_create_empty_body(self, tool):
        content = "---\nname: empty-body\ndescription: Empty body\n---\n"
        result = run_tool(tool, action="create", name="empty-body", description="Empty body", content=content)
        result_data = json.loads(result)
        assert result_data["success"] is False
        assert "non-empty body" in result_data["error"]


class TestSkillManageInvalidAction:
    def test_unknown_action(self, tool):
        result = run_tool(tool, action="delete", name="test-skill")
        result_data = json.loads(result)
        assert result_data["success"] is False
        assert "Unknown action" in result_data["error"]
