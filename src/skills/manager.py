import asyncio
import os
from pathlib import Path
from typing import List, Optional, Set, Dict
from dataclasses import dataclass, field
import pathspec

from .parser import SkillParser, SkillMetadata
from .registry import SkillRegistry
from .loader import SkillLoader


@dataclass
class ConditionalSkill:
    """条件激活的 Skill"""
    skill: SkillMetadata
    path_patterns: List[str]
    content: str = ""
    _spec: Optional[pathspec.PathSpec] = field(default=None, repr=False)
    
    def __post_init__(self):
        if self.path_patterns:
            self._spec = pathspec.PathSpec.from_lines(
                pathspec.patterns.GitWildMatchPattern,
                self.path_patterns
            )
    
    def matches(self, file_path: str, cwd: str = ".") -> bool:
        """检查文件路径是否匹配"""
        if not self._spec:
            return False
        
        abs_file_path = os.path.abspath(file_path)
        abs_cwd = os.path.abspath(cwd)
        
        try:
            relative_path = os.path.relpath(abs_file_path, abs_cwd)
            relative_path = relative_path.replace(os.sep, '/')
            return self._spec.match_file(relative_path)
        except ValueError:
            return False


class SkillManager(SkillLoader):
    """Skill 管理器，扩展 SkillLoader 支持条件激活和动态发现"""
    
    def __init__(
        self,
        skills_dir: str,
        enabled_skills: Optional[List[str]] = None,
        max_loaded_skills: int = 3,
        additional_dirs: Optional[List[str]] = None,
        cwd: str = "."
    ):
        super().__init__(
            skills_dir=skills_dir,
            enabled_skills=enabled_skills,
            max_loaded_skills=max_loaded_skills
        )
        self.additional_dirs = additional_dirs or []
        self.cwd = cwd
        self.conditional_skills: List[ConditionalSkill] = []
        self.dynamic_skills: List[SkillMetadata] = []
        self.discovered_dirs: Set[str] = set()
        self._managed_skills_dir: Optional[str] = None
        self._user_skills_dir: Optional[str] = None
    
    async def load_skills(self) -> List[SkillMetadata]:
        """加载所有 Skills（并行加载多个来源）"""
        tasks = []
        
        tasks.append(self._load_from_dir(self.skills_dir, "project"))
        
        for extra_dir in self.additional_dirs:
            tasks.append(self._load_from_dir(Path(extra_dir), "additional"))
        
        if self._managed_skills_dir:
            tasks.append(self._load_from_dir(Path(self._managed_skills_dir), "managed"))
        
        if self._user_skills_dir:
            tasks.append(self._load_from_dir(Path(self._user_skills_dir), "user"))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_skills = []
        for result in results:
            if isinstance(result, list):
                all_skills.extend(result)
            elif isinstance(result, Exception):
                print(f"加载 Skills 失败: {result}")
        
        unique_skills = self._deduplicate_skills(all_skills)
        
        unconditional, conditional = self._separate_conditional_skills(unique_skills)
        
        self.conditional_skills = conditional
        
        return unconditional
    
    async def _load_from_dir(
        self, 
        dir_path: Path, 
        source: str
    ) -> List[SkillMetadata]:
        """从指定目录加载 Skills"""
        skills = []
        
        if not dir_path.exists():
            return skills
        
        for skill_file in dir_path.rglob("*.md"):
            try:
                metadata, content = self.parser.parse_file(skill_file)
                if metadata.name:
                    if self.enabled_skills and metadata.name not in self.enabled_skills:
                        continue
                    
                    if not self.registry.has_skill(metadata.name):
                        self.registry.register(metadata, content)
                        skills.append(metadata)
            except Exception as e:
                print(f"加载 Skill 失败 {skill_file}: {e}")
        
        return skills
    
    def _deduplicate_skills(
        self, 
        skills: List[SkillMetadata]
    ) -> List[SkillMetadata]:
        """去重 Skills"""
        seen: Dict[str, SkillMetadata] = {}
        for skill in skills:
            if skill.name not in seen:
                seen[skill.name] = skill
        return list(seen.values())
    
    def _separate_conditional_skills(
        self, 
        skills: List[SkillMetadata]
    ) -> tuple[List[SkillMetadata], List[ConditionalSkill]]:
        """分离条件 Skills"""
        unconditional = []
        conditional = []
        
        for skill in skills:
            if skill.paths:
                content = self.registry.get_content(skill.name) or ""
                conditional_skill = ConditionalSkill(
                    skill=skill,
                    path_patterns=skill.paths,
                    content=content
                )
                conditional.append(conditional_skill)
            else:
                unconditional.append(skill)
        
        return unconditional, conditional
    
    def activate_for_paths(self, file_paths: List[str]) -> List[str]:
        """激活匹配路径的条件 Skills"""
        activated = []
        
        for conditional_skill in self.conditional_skills[:]:
            for file_path in file_paths:
                if conditional_skill.matches(file_path, self.cwd):
                    self.dynamic_skills.append(conditional_skill.skill)
                    self.conditional_skills.remove(conditional_skill)
                    activated.append(conditional_skill.skill.name)
                    
                    if conditional_skill.content:
                        self.registry.store_content(
                            conditional_skill.skill.name,
                            conditional_skill.content
                        )
                    break
        
        return activated
    
    def discover_for_paths(
        self, 
        file_paths: List[str], 
        max_depth: int = 5
    ) -> List[str]:
        """发现嵌套的 Skills 目录"""
        discovered_skills = []
        
        for file_path in file_paths:
            abs_path = os.path.abspath(file_path)
            current_dir = os.path.dirname(abs_path) if os.path.isfile(abs_path) else abs_path
            
            depth = 0
            while current_dir and current_dir != os.path.dirname(self.cwd) and depth < max_depth:
                skills_dir = os.path.join(current_dir, ".skills")
                
                if skills_dir not in self.discovered_dirs and os.path.isdir(skills_dir):
                    self.discovered_dirs.add(skills_dir)
                    
                    skills = self._discover_skills_in_dir(skills_dir)
                    discovered_skills.extend(skills)
                
                parent = os.path.dirname(current_dir)
                if parent == current_dir:
                    break
                current_dir = parent
                depth += 1
        
        return discovered_skills
    
    def _discover_skills_in_dir(self, dir_path: str) -> List[str]:
        """在目录中发现 Skills"""
        discovered = []
        skills_dir = Path(dir_path)
        
        if not skills_dir.exists():
            return discovered
        
        for skill_file in skills_dir.rglob("*.md"):
            try:
                metadata, content = self.parser.parse_file(skill_file)
                if metadata.name:
                    if not self.registry.has_skill(metadata.name):
                        self.registry.register(metadata, content)
                        self.dynamic_skills.append(metadata)
                        discovered.append(metadata.name)
            except Exception as e:
                print(f"发现 Skill 失败 {skill_file}: {e}")
        
        return discovered
    
    def set_managed_skills_dir(self, dir_path: str) -> None:
        """设置托管 Skills 目录"""
        self._managed_skills_dir = dir_path
    
    def set_user_skills_dir(self, dir_path: str) -> None:
        """设置用户 Skills 目录"""
        self._user_skills_dir = dir_path
    
    def get_all_active_skills(self) -> List[SkillMetadata]:
        """获取所有激活的 Skills（包括动态激活的）"""
        base_skills = self.list_skills()
        dynamic_names = {s.name for s in self.dynamic_skills}
        
        all_skills = list(base_skills)
        for skill in self.dynamic_skills:
            if skill.name not in {s.name for s in base_skills}:
                all_skills.append(skill)
        
        return all_skills
    
    def get_conditional_skills_count(self) -> int:
        """获取条件 Skills 数量"""
        return len(self.conditional_skills)
    
    def get_dynamic_skills_count(self) -> int:
        """获取动态 Skills 数量"""
        return len(self.dynamic_skills)
    
    def get_discovered_dirs_count(self) -> int:
        """获取已发现目录数量"""
        return len(self.discovered_dirs)
    
    def clear_dynamic_skills(self) -> None:
        """清空动态 Skills"""
        self.dynamic_skills.clear()
    
    def reset_conditional_skills(self) -> None:
        """重置条件 Skills（重新加载）"""
        self.conditional_skills.clear()
