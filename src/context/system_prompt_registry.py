import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import List

import tiktoken

from ..utils.logger import get_llm_logger


@dataclass
class PromptSection:
    content: str
    category: str
    added_at: float = 0.0
    last_referenced: float = 0.0


class SystemPromptRegistry:
    def __init__(self, logger=None, log_skill_lifecycle: bool = True):
        self._sections: OrderedDict[str, PromptSection] = OrderedDict()
        self._logger = logger
        self._log_skill_lifecycle = log_skill_lifecycle

    def add_static(self, key: str, content: str) -> None:
        self._sections[key] = PromptSection(content=content, category="static")

    def add_skill(self, name: str, content: str) -> None:
        now = time.time()
        key = f"skill_{name}"
        self._sections[key] = PromptSection(
            content=content,
            category="skill",
            added_at=now,
            last_referenced=now,
        )
        if self._log_skill_lifecycle and self._logger is not None and hasattr(self._logger, "log_skill_lifecycle"):
            self._logger.log_skill_lifecycle("add", name)

    def add_dynamic(self, key: str, content: str) -> None:
        self._sections[key] = PromptSection(content=content, category="dynamic")

    def remove_skill(self, name: str) -> bool:
        key = f"skill_{name}"
        if key in self._sections:
            del self._sections[key]
            if self._log_skill_lifecycle and self._logger is not None and hasattr(self._logger, "log_skill_lifecycle"):
                self._logger.log_skill_lifecycle("remove", name)
            return True
        return False

    def mark_skill_referenced(self, name: str) -> None:
        key = f"skill_{name}"
        if key in self._sections:
            self._sections[key].last_referenced = time.time()

    def remove_stale_skills(self, max_age_seconds: int) -> List[str]:
        now = time.time()
        removed = []
        keys_to_remove = []
        for key, section in self._sections.items():
            if section.category == "skill" and (now - section.last_referenced) > max_age_seconds:
                keys_to_remove.append(key)
                skill_name = key[len("skill_"):]
                removed.append(skill_name)
        for key in keys_to_remove:
            del self._sections[key]
        if removed and self._log_skill_lifecycle and self._logger is not None and hasattr(self._logger, "log_skill_lifecycle"):
            for name in removed:
                self._logger.log_skill_lifecycle("remove_stale", name)
        return removed

    def build(self) -> str:
        return "\n\n".join(section.content for section in self._sections.values())

    def get_skill_names(self) -> List[str]:
        return [key[len("skill_"):] for key, section in self._sections.items() if section.category == "skill"]

    def get_skill_tokens(self) -> int:
        encoding = tiktoken.get_encoding("cl100k_base")
        total = 0
        for section in self._sections.values():
            if section.category == "skill":
                total += len(encoding.encode(section.content))
        return total

    def get_total_tokens(self) -> int:
        encoding = tiktoken.get_encoding("cl100k_base")
        total = 0
        for section in self._sections.values():
            total += len(encoding.encode(section.content))
        return total

    def has_skill(self, name: str) -> bool:
        return f"skill_{name}" in self._sections

    def get_section_keys(self) -> List[str]:
        return list(self._sections.keys())
