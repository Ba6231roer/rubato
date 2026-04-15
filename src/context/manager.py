from typing import List, Optional


class ContextManager:
    """上下文管理器 - 管理技能状态和应用状态"""

    def __init__(self):
        self._loaded_skills: List[str] = []
        self._app_state: dict = {}

    def clear(self) -> None:
        """清空技能加载状态"""
        self._loaded_skills = []

    def mark_skill_loaded(self, skill_name: str) -> None:
        """标记Skill已加载"""
        if skill_name not in self._loaded_skills:
            self._loaded_skills.append(skill_name)

    def get_loaded_skills(self) -> List[str]:
        """获取已加载的Skills"""
        return self._loaded_skills.copy()

    def is_skill_loaded(self, skill_name: str) -> bool:
        """检查Skill是否已加载"""
        return skill_name in self._loaded_skills

    def get_context(self) -> dict:
        """获取应用状态字典"""
        return self._app_state.copy()

    def add_context(self, key: str, value) -> None:
        """添加应用状态"""
        self._app_state[key] = value

    def update_context(self, data: dict) -> None:
        """更新应用状态"""
        self._app_state.update(data)
