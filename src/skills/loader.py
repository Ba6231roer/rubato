from pathlib import Path
from typing import List, Optional, Set

from .parser import SkillParser, SkillMetadata
from .registry import SkillRegistry


class SkillLoader:
    """Skill加载器"""

    def __init__(
        self,
        skills_dir: str,
        enabled_skills: Optional[List[str]] = None,
        max_loaded_skills: int = 3
    ):
        self.skills_dir = Path(skills_dir)
        self.enabled_skills: Set[str] = set(enabled_skills) if enabled_skills else set()
        self.max_loaded_skills = max_loaded_skills
        self.registry = SkillRegistry(max_loaded_skills=max_loaded_skills)
        self.parser = SkillParser()

    def _load_skills_from_dir(
        self,
        dir_path: Path,
        skip_existing: bool = False
    ) -> List[SkillMetadata]:
        """从指定目录加载Skill元数据

        Args:
            dir_path: Skill目录路径
            skip_existing: 是否跳过已注册的同名Skill
        """
        skills = []

        if not dir_path.exists():
            return skills

        for skill_file in dir_path.rglob("*.md"):
            try:
                metadata, content = self.parser.parse_file(skill_file)
                if metadata.name:
                    if self.enabled_skills and metadata.name not in self.enabled_skills:
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

        如果 enabled_skills 非空，只加载列表中指定的 skill
        如果 enabled_skills 为空，加载目录下所有 skill
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
        """获取所有Skill的元数据字典"""
        return {
            metadata.name: {
                "name": metadata.name,
                "description": metadata.description,
                "triggers": metadata.triggers,
                "required_tools": metadata.tools,
            }
            for metadata in self.registry.list_skills()
        }

    def get_loaded_skills_count(self) -> int:
        """获取已加载内容的Skill数量"""
        return self.registry.get_loaded_count()

    def is_skill_enabled(self, skill_name: str) -> bool:
        """检查Skill是否在启用列表中"""
        if not self.enabled_skills:
            return True
        return skill_name in self.enabled_skills

    def has_skill(self, skill_name: str) -> bool:
        """检查Skill是否存在"""
        return self.registry.has_skill(skill_name)
