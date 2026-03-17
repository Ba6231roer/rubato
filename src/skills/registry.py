from typing import Dict, Optional, List
from .parser import SkillMetadata


class SkillRegistry:
    """Skill注册表"""
    
    def __init__(self):
        self.skills: Dict[str, SkillMetadata] = {}
        self.skill_contents: Dict[str, str] = {}
    
    def register(self, metadata: SkillMetadata, content: str = "") -> None:
        """注册Skill元数据"""
        self.skills[metadata.name] = metadata
        if content:
            self.skill_contents[metadata.name] = content
    
    def unregister(self, name: str) -> None:
        """注销Skill"""
        if name in self.skills:
            del self.skills[name]
        if name in self.skill_contents:
            del self.skill_contents[name]
    
    def get_skill(self, name: str) -> Optional[SkillMetadata]:
        """获取Skill元数据"""
        return self.skills.get(name)
    
    def get_skill_file(self, skill_name: str) -> str:
        """获取Skill文件路径"""
        if skill_name in self.skills:
            return self.skills[skill_name].file_path
        return ""
    
    def find_matching_skill(self, user_input: str) -> Optional[str]:
        """根据用户输入匹配Skill"""
        user_input_lower = user_input.lower()
        for name, metadata in self.skills.items():
            for trigger in metadata.triggers:
                if trigger.lower() in user_input_lower:
                    return name
        return None
    
    def list_skills(self) -> List[SkillMetadata]:
        """列出所有Skill"""
        return list(self.skills.values())
    
    def has_skill(self, name: str) -> bool:
        """检查Skill是否存在"""
        return name in self.skills
    
    def store_content(self, name: str, content: str) -> None:
        """存储Skill内容"""
        self.skill_contents[name] = content
    
    def get_content(self, name: str) -> Optional[str]:
        """获取Skill内容"""
        return self.skill_contents.get(name)
