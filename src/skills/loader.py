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
    
    async def load_skill_metadata(self) -> List[SkillMetadata]:
        """启动时加载所有Skill的元数据
        
        如果 enabled_skills 非空，只加载列表中指定的 skill
        如果 enabled_skills 为空，加载目录下所有 skill
        """
        skills = []
        
        if not self.skills_dir.exists():
            return skills
        
        for skill_file in self.skills_dir.rglob("*.md"):
            try:
                metadata, content = self.parser.parse_file(skill_file)
                if metadata.name:
                    if self.enabled_skills and metadata.name not in self.enabled_skills:
                        continue
                    self.registry.register(metadata, content)
                    skills.append(metadata)
            except Exception as e:
                print(f"加载Skill失败 {skill_file}: {e}")
        
        return skills
    
    async def load_full_skill(self, skill_name: str) -> str:
        """对话中按需加载完整Skill内容"""
        content = self.registry.get_content(skill_name)
        if content:
            return content
        
        skill_file = self.registry.get_skill_file(skill_name)
        if skill_file:
            with open(skill_file, 'r', encoding='utf-8') as f:
                content = f.read()
            self.registry.store_content(skill_name, content)
            return content
        
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
        result = {}
        for metadata in self.registry.list_skills():
            result[metadata.name] = {
                "name": metadata.name,
                "description": metadata.description,
                "triggers": metadata.triggers,
                "required_tools": metadata.required_tools if hasattr(metadata, 'required_tools') else []
            }
        return result
    
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
