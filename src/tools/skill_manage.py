import json
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import yaml
from langchain_core.tools import tool

from src.skills.parser import SkillParser


_NAME_PATTERN = re.compile(r'^[a-z0-9][a-z0-9._-]*$')
_MAX_NAME_LENGTH = 64
_MAX_CONTENT_CHARS = 100000


def _validate_name(name: str) -> Optional[str]:
    if not name:
        return "Skill name cannot be empty"
    if len(name) > _MAX_NAME_LENGTH:
        return f"Skill name exceeds maximum length of {_MAX_NAME_LENGTH} characters"
    if not _NAME_PATTERN.match(name):
        return f"Skill name must match pattern ^[a-z0-9][a-z0-9._-]*$ (got: {name})"
    return None


def _validate_frontmatter(content: str) -> Optional[str]:
    if not content.startswith('---'):
        return "Content must start with YAML frontmatter (---)"
    parts = content.split('---', 2)
    if len(parts) < 3:
        return "Content must have closing YAML frontmatter (---)"
    yaml_content = parts[1].strip()
    if not yaml_content:
        return "YAML frontmatter is empty"
    try:
        parsed = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        return f"Invalid YAML in frontmatter: {e}"
    if not isinstance(parsed, dict):
        return "YAML frontmatter must be a key-value mapping"
    if 'name' not in parsed:
        return "YAML frontmatter must contain 'name' field"
    if 'description' not in parsed:
        return "YAML frontmatter must contain 'description' field"
    body = parts[2].strip()
    if not body:
        return "Skill content must have a non-empty body after frontmatter"
    return None


def _validate_content_size(content: str, max_chars: int = _MAX_CONTENT_CHARS) -> Optional[str]:
    if len(content) > max_chars:
        return f"Content exceeds maximum size of {max_chars} characters (got: {len(content)})"
    return None


def _atomic_write_text(file_path: Path, content: str):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=str(file_path.parent),
        prefix=".tmp_",
        suffix=".md"
    )
    try:
        with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
            f.write(content)
        os.replace(tmp_path, str(file_path))
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _backup_skill_file(file_path: Path, skills_dir: Path) -> str:
    backups_dir = skills_dir / ".backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    if file_path.name == "SKILL.md":
        stem = file_path.parent.name
    else:
        stem = file_path.stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{stem}_{timestamp}.md"
    backup_path = backups_dir / backup_name
    shutil.copy2(str(file_path), str(backup_path))
    return str(backup_path)


def create_skill_manage_tool(skill_manager, on_skill_changed: Optional[Callable[[str, str], None]] = None):
    @tool
    async def skill_manage(
        action: str,
        name: str = "",
        description: str = "",
        content: str = "",
        triggers: str = "",
        category: str = "",
        old_string: str = "",
        new_string: str = "",
    ) -> str:
        """管理 Skills（创建、修改、查看）。Skills 是你的程序性记忆——针对特定类型任务的可复用方法。

操作：
- create: 创建新 Skill（需提供 name, description, content，content 为完整的 SKILL.md 内容含 YAML 头）
- patch: 局部修改（需提供 name, old_string, new_string）——推荐用于小修小补
- edit: 全量替换（需提供 name, content）——仅用于大幅改写
- list: 列出所有可用 Skills
- view: 查看指定 Skill 的完整内容

何时创建：完成复杂任务（5+工具调用）、克服了错误、发现了非平凡工作流。
何时修改：使用 Skill 时发现指令过时/错误、缺少步骤或陷阱。
修改已有 Skill 时系统会自动备份原文件（加时间戳），你可以用文件工具查看差异确认变更。
创建 Skill 后，如果当前在执行测试案例，建议将 Skill 名称添加到案例文档的[参考skill]章节中，这样下次执行该案例时会自动加载此 Skill。"""
        if skill_manager is None:
            return json.dumps({"success": False, "error": "skill_manage 工具未正确初始化：skill_manager 不可用"}, ensure_ascii=False)
        if action == "create":
            err = _validate_name(name)
            if err:
                return json.dumps({"success": False, "error": err}, ensure_ascii=False)

            if skill_manager.has_skill(name):
                return json.dumps({"success": False, "error": f"Skill '{name}' already exists"}, ensure_ascii=False)

            err = _validate_frontmatter(content)
            if err:
                return json.dumps({"success": False, "error": err}, ensure_ascii=False)

            err = _validate_content_size(content)
            if err:
                return json.dumps({"success": False, "error": err}, ensure_ascii=False)

            skill_dir = Path(skill_manager.skills_dir) / ".self-improved" / name
            file_path = skill_dir / "SKILL.md"

            try:
                _atomic_write_text(file_path, content)
            except Exception as e:
                return json.dumps({"success": False, "error": f"Failed to write skill file: {e}"}, ensure_ascii=False)

            metadata, body = SkillParser.parse_content(content)
            triggers_list = [t.strip() for t in triggers.split(",") if t.strip()] if triggers else []
            desc = description or metadata.description or ""
            cat = category or metadata.category or ""

            skill_manager.register_skill_from_agent(name, desc, body, triggers_list, cat)
            skill_manager.registry.skills[name].file_path = str(file_path)

            if on_skill_changed:
                on_skill_changed("create", name)

            return json.dumps({
                "success": True,
                "message": f"Skill '{name}' created.",
                "path": str(file_path)
            }, ensure_ascii=False)

        elif action == "patch":
            if not name:
                return json.dumps({"success": False, "error": "Skill name is required"}, ensure_ascii=False)

            if not skill_manager.has_skill(name):
                return json.dumps({"success": False, "error": f"Skill '{name}' not found"}, ensure_ascii=False)

            if not old_string:
                return json.dumps({"success": False, "error": "old_string is required for patch action"}, ensure_ascii=False)

            file_path_str = skill_manager.registry.get_skill_file(name)
            if not file_path_str:
                return json.dumps({"success": False, "error": f"Skill file path not found for '{name}'"}, ensure_ascii=False)

            file_path = Path(file_path_str)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    current_content = f.read()
            except Exception as e:
                return json.dumps({"success": False, "error": f"Failed to read skill file: {e}"}, ensure_ascii=False)

            if old_string not in current_content:
                preview = current_content[:500]
                return json.dumps({
                    "success": False,
                    "error": "old_string not found in skill content",
                    "preview": preview
                }, ensure_ascii=False)

            patched_content = current_content.replace(old_string, new_string, 1)

            err = _validate_frontmatter(patched_content)
            if err:
                return json.dumps({"success": False, "error": f"Patched content has invalid frontmatter: {err}"}, ensure_ascii=False)

            backup_path = _backup_skill_file(file_path, Path(skill_manager.skills_dir))

            try:
                _atomic_write_text(file_path, patched_content)
            except Exception as e:
                shutil.copy2(backup_path, file_path)
                return json.dumps({"success": False, "error": f"Failed to write patched skill file: {e}. Restored from backup."}, ensure_ascii=False)

            _, new_body = SkillParser._split_yaml_header(patched_content)
            skill_manager.update_skill_from_agent(name, new_body)

            if on_skill_changed:
                on_skill_changed("patch", name)

            return json.dumps({
                "success": True,
                "message": f"Skill '{name}' patched.",
                "backup": backup_path
            }, ensure_ascii=False)

        elif action == "edit":
            if not name:
                return json.dumps({"success": False, "error": "Skill name is required"}, ensure_ascii=False)

            if not skill_manager.has_skill(name):
                return json.dumps({"success": False, "error": f"Skill '{name}' not found"}, ensure_ascii=False)

            err = _validate_frontmatter(content)
            if err:
                return json.dumps({"success": False, "error": err}, ensure_ascii=False)

            file_path_str = skill_manager.registry.get_skill_file(name)
            if not file_path_str:
                return json.dumps({"success": False, "error": f"Skill file path not found for '{name}'"}, ensure_ascii=False)

            file_path = Path(file_path_str)
            backup_path = _backup_skill_file(file_path, Path(skill_manager.skills_dir))

            try:
                _atomic_write_text(file_path, content)
            except Exception as e:
                shutil.copy2(backup_path, file_path)
                return json.dumps({"success": False, "error": f"Failed to write skill file: {e}. Restored from backup."}, ensure_ascii=False)

            _, new_body = SkillParser._split_yaml_header(content)
            skill_manager.update_skill_from_agent(name, new_body)

            if on_skill_changed:
                on_skill_changed("edit", name)

            return json.dumps({
                "success": True,
                "message": f"Skill '{name}' updated.",
                "backup": backup_path
            }, ensure_ascii=False)

        elif action == "list":
            all_metadata = skill_manager.get_all_skill_metadata()
            if not all_metadata:
                return "No skills available."

            lines = []
            for skill_name, meta in all_metadata.items():
                created_by = meta.get("created_by", "")
                desc = meta.get("description", "")
                lines.append(f"- {skill_name}: {desc} (created_by: {created_by})")

            return "\n".join(lines)

        elif action == "view":
            if not name:
                return json.dumps({"success": False, "error": "Skill name is required"}, ensure_ascii=False)

            file_path_str = skill_manager.registry.get_skill_file(name)
            if not file_path_str:
                return json.dumps({"success": False, "error": f"Skill '{name}' not found"}, ensure_ascii=False)

            try:
                with open(file_path_str, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                return json.dumps({"success": False, "error": f"Failed to read skill file: {e}"}, ensure_ascii=False)

        else:
            return json.dumps({"success": False, "error": f"Unknown action: {action}. Valid actions: create, patch, edit, list, view"}, ensure_ascii=False)

    return skill_manage
