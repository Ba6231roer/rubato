from pathlib import Path
from typing import List, Optional

from .parser import SkillParser, SkillMetadata
from .registry import SkillRegistry


class SkillLoader:
    """Skill加载器"""
    
    def __init__(self, skills_dir: str):
        self.skills_dir = Path(skills_dir)
        self.registry = SkillRegistry()
        self.parser = SkillParser()
    
    async def load_skill_metadata(self) -> List[SkillMetadata]:
        """启动时加载所有Skill的元数据"""
        skills = []
        
        if not self.skills_dir.exists():
            return skills
        
        for skill_file in self.skills_dir.rglob("*.md"):
            try:
                metadata, content = self.parser.parse_file(skill_file)
                if metadata.name:
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
