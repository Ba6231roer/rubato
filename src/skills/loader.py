from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set

from .parser import SkillParser, SkillMetadata
from .registry import SkillRegistry


class SkillLoader:
    """Skill加载器"""

    def __init__(
        self,
        skills_dir: str,
        disabled_skills: Optional[List[str]] = None,
    ):
        self.skills_dir = Path(skills_dir)
        self.disabled_skills: Set[str] = set(disabled_skills) if disabled_skills else set()
        self.registry = SkillRegistry()
        self.parser = SkillParser()

    def _load_skills_from_dir(
        self,
        dir_path: Path,
        skip_existing: bool = False
    ) -> List[SkillMetadata]:
        skills = []

        if not dir_path.exists():
            return skills

        processed_dirs = set()

        for skill_file in dir_path.rglob("SKILL.md"):
            try:
                metadata, content = self.parser.parse_file(skill_file)
                if metadata.name:
                    if self.disabled_skills and metadata.name in self.disabled_skills:
                        continue
                    if skip_existing and self.registry.has_skill(metadata.name):
                        continue
                    self.registry.register(metadata, content)
                    skills.append(metadata)
                    processed_dirs.add(skill_file.parent)
            except Exception as e:
                print(f"加载Skill失败 {skill_file}: {e}")

        for skill_file in dir_path.rglob("*.md"):
            if skill_file.name == "SKILL.md":
                continue
            if skill_file.parent in processed_dirs:
                continue
            try:
                metadata, content = self.parser.parse_file(skill_file)
                if metadata.name:
                    if self.disabled_skills and metadata.name in self.disabled_skills:
                        continue
                    if skip_existing and self.registry.has_skill(metadata.name):
                        continue
                    self.registry.register(metadata, content)
                    skills.append(metadata)
            except Exception as e:
                print(f"加载Skill失败 {skill_file}: {e}")

        return skills

    async def load_skill_metadata(self) -> List[SkillMetadata]:
        """启动时加载所有Skill的元数据

        如果 disabled_skills 非空，排除列表中指定的 skill
        如果 disabled_skills 为空，加载目录下所有 skill
        """
        return self._load_skills_from_dir(self.skills_dir)

    async def load_full_skill(self, skill_name: str) -> str:
        """对话中按需加载完整Skill内容（仅正文，不含YAML头）"""
        content = self.registry.get_content(skill_name)
        if content:
            return content

        skill_file = self.registry.get_skill_file(skill_name)
        if skill_file:
            try:
                with open(skill_file, 'r', encoding='utf-8') as f:
                    raw_content = f.read()
                _, body = SkillParser._split_yaml_header(raw_content)
                content = body if body else raw_content
                self.registry.store_content(skill_name, content)
                return content
            except Exception:
                pass

        return ""

    def get_skill_content_sync(self, skill_name: str) -> str:
        """同步获取Skill正文内容（不含YAML头），供非async上下文使用"""
        content = self.registry.get_content(skill_name)
        if content:
            return content

        skill_file = self.registry.get_skill_file(skill_name)
        if skill_file:
            try:
                with open(skill_file, 'r', encoding='utf-8') as f:
                    raw_content = f.read()
                _, body = SkillParser._split_yaml_header(raw_content)
                content = body if body else raw_content
                self.registry.store_content(skill_name, content)
                return content
            except Exception:
                pass

        return ""

    def get_registry(self) -> SkillRegistry:
        """获取Skill注册表"""
        return self.registry

    def find_matching_skill(self, user_input: str) -> Optional[str]:
        """根据用户输入匹配Skill"""
        return self.registry.find_matching_skill(user_input)

    def list_skills(self) -> List[SkillMetadata]:
        """列出所有Skill"""
        return self.registry.list_skills()

    def get_all_skill_metadata(self) -> dict:
        return {
            metadata.name: {
                "name": metadata.name,
                "description": metadata.description,
                "triggers": metadata.triggers,
                "required_tools": metadata.tools,
                "category": metadata.category,
                "created_by": metadata.created_by,
            }
            for metadata in self.registry.list_skills()
        }

    def get_loaded_skills_count(self) -> int:
        """获取已加载内容的Skill数量"""
        return self.registry.get_loaded_count()

    def is_skill_enabled(self, skill_name: str) -> bool:
        """检查Skill是否在禁用列表中"""
        if not self.disabled_skills:
            return True
        return skill_name not in self.disabled_skills

    def has_skill(self, skill_name: str) -> bool:
        """检查Skill是否存在"""
        return self.registry.has_skill(skill_name)

    def register_skill_from_agent(
        self,
        name: str,
        description: str,
        content: str,
        triggers: Optional[List[str]] = None,
        category: str = ""
    ) -> SkillMetadata:
        metadata = SkillMetadata(
            name=name,
            description=description,
            triggers=triggers or [],
            category=category,
            created_by="agent",
            updated_at=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        )
        self.registry.register_new_skill(metadata, content)
        return metadata

    def update_skill_from_agent(self, name: str, content: str) -> bool:
        if not self.registry.has_skill(name):
            return False
        self.registry.update_skill_content(name, content)
        return True
