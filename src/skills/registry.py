from typing import Dict, Optional, List
from collections import OrderedDict
from .parser import SkillMetadata


class SkillRegistry:
    """Skill注册表"""
    
    def __init__(self, max_loaded_skills: int = 3):
        self.skills: Dict[str, SkillMetadata] = {}
        self.skill_contents: OrderedDict[str, str] = OrderedDict()
        self.max_loaded_skills = max_loaded_skills
        self._content_access_order: List[str] = []
    
    def register(self, metadata: SkillMetadata, content: str = "") -> None:
        """注册Skill元数据"""
        self.skills[metadata.name] = metadata
        if content:
            self._store_content_with_limit(metadata.name, content)
    
    def unregister(self, name: str) -> None:
        """注销Skill"""
        if name in self.skills:
            del self.skills[name]
        if name in self.skill_contents:
            del self.skill_contents[name]
        if name in self._content_access_order:
            self._content_access_order.remove(name)
    
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
        """存储Skill内容（带LRU限制）"""
        self._store_content_with_limit(name, content)
    
    def _store_content_with_limit(self, name: str, content: str) -> None:
        """存储内容，如果超过限制则移除最久未使用的"""
        if name in self.skill_contents:
            del self.skill_contents[name]
            self._content_access_order.remove(name)
        
        while len(self.skill_contents) >= self.max_loaded_skills:
            if self._content_access_order:
                oldest_name = self._content_access_order.pop(0)
                if oldest_name in self.skill_contents:
                    del self.skill_contents[oldest_name]
            else:
                break
        
        self.skill_contents[name] = content
        self._content_access_order.append(name)
    
    def get_content(self, name: str) -> Optional[str]:
        """获取Skill内容（更新访问顺序）"""
        content = self.skill_contents.get(name)
        if content and name in self._content_access_order:
            self._content_access_order.remove(name)
            self._content_access_order.append(name)
        return content
    
    def get_loaded_count(self) -> int:
        """获取已加载内容的Skill数量"""
        return len(self.skill_contents)
    
    def get_max_loaded_limit(self) -> int:
        """获取最大加载限制"""
        return self.max_loaded_skills
    
    def set_max_loaded_skills(self, limit: int) -> None:
        """设置最大加载限制"""
        self.max_loaded_skills = limit
        while len(self.skill_contents) > self.max_loaded_skills:
            if self._content_access_order:
                oldest_name = self._content_access_order.pop(0)
                if oldest_name in self.skill_contents:
                    del self.skill_contents[oldest_name]
