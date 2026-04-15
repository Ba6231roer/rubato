import time
import unittest
from unittest.mock import MagicMock

import tiktoken

from src.context.system_prompt_registry import PromptSection, SystemPromptRegistry


class TestPromptSection(unittest.TestCase):
    def test_default_values(self):
        section = PromptSection(content="hello", category="static")
        self.assertEqual(section.content, "hello")
        self.assertEqual(section.category, "static")
        self.assertEqual(section.added_at, 0.0)
        self.assertEqual(section.last_referenced, 0.0)

    def test_custom_values(self):
        now = time.time()
        section = PromptSection(content="world", category="skill", added_at=now, last_referenced=now)
        self.assertEqual(section.content, "world")
        self.assertEqual(section.category, "skill")
        self.assertEqual(section.added_at, now)
        self.assertEqual(section.last_referenced, now)


class TestSystemPromptRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = SystemPromptRegistry()

    def test_add_static(self):
        self.registry.add_static("base", "You are a helpful assistant.")
        self.assertIn("base", self.registry._sections)
        self.assertEqual(self.registry._sections["base"].content, "You are a helpful assistant.")
        self.assertEqual(self.registry._sections["base"].category, "static")

    def test_add_skill(self):
        self.registry.add_skill("search", "Search skill content here.")
        key = "skill_search"
        self.assertIn(key, self.registry._sections)
        self.assertEqual(self.registry._sections[key].content, "Search skill content here.")
        self.assertEqual(self.registry._sections[key].category, "skill")
        self.assertGreater(self.registry._sections[key].added_at, 0)
        self.assertGreater(self.registry._sections[key].last_referenced, 0)

    def test_add_skill_logs_when_logger_has_method(self):
        logger = MagicMock()
        logger.log_skill_lifecycle = MagicMock()
        registry = SystemPromptRegistry(logger=logger)
        registry.add_skill("search", "content")
        logger.log_skill_lifecycle.assert_called_once_with("add", "search")

    def test_add_skill_no_log_when_logger_none(self):
        registry = SystemPromptRegistry(logger=None)
        registry.add_skill("search", "content")

    def test_add_skill_no_log_when_logger_missing_method(self):
        logger = MagicMock(spec=[])
        registry = SystemPromptRegistry(logger=logger)
        registry.add_skill("search", "content")

    def test_add_dynamic(self):
        self.registry.add_dynamic("env", "Current time: 12:00")
        self.assertIn("env", self.registry._sections)
        self.assertEqual(self.registry._sections["env"].content, "Current time: 12:00")
        self.assertEqual(self.registry._sections["env"].category, "dynamic")

    def test_build_order(self):
        self.registry.add_static("base", "Base instruction")
        self.registry.add_skill("search", "Search skill")
        self.registry.add_dynamic("env", "Env info")
        result = self.registry.build()
        self.assertEqual(result, "Base instruction\n\nSearch skill\n\nEnv info")

    def test_build_empty(self):
        self.assertEqual(self.registry.build(), "")

    def test_build_single_section(self):
        self.registry.add_static("base", "Only one")
        self.assertEqual(self.registry.build(), "Only one")

    def test_remove_skill_success(self):
        self.registry.add_skill("search", "content")
        result = self.registry.remove_skill("search")
        self.assertTrue(result)
        self.assertNotIn("skill_search", self.registry._sections)

    def test_remove_skill_not_found(self):
        result = self.registry.remove_skill("nonexistent")
        self.assertFalse(result)

    def test_remove_skill_logs_when_logger_has_method(self):
        logger = MagicMock()
        logger.log_skill_lifecycle = MagicMock()
        registry = SystemPromptRegistry(logger=logger)
        registry.add_skill("search", "content")
        registry.remove_skill("search")
        logger.log_skill_lifecycle.assert_any_call("add", "search")
        logger.log_skill_lifecycle.assert_any_call("remove", "search")

    def test_remove_skill_no_log_when_not_found(self):
        logger = MagicMock()
        logger.log_skill_lifecycle = MagicMock()
        registry = SystemPromptRegistry(logger=logger)
        registry.remove_skill("nonexistent")
        logger.log_skill_lifecycle.assert_not_called()

    def test_mark_skill_referenced(self):
        self.registry.add_skill("search", "content")
        old_ref = self.registry._sections["skill_search"].last_referenced
        time.sleep(0.01)
        self.registry.mark_skill_referenced("search")
        new_ref = self.registry._sections["skill_search"].last_referenced
        self.assertGreater(new_ref, old_ref)

    def test_mark_skill_referenced_nonexistent(self):
        self.registry.mark_skill_referenced("nonexistent")

    def test_remove_stale_skills_removes_old(self):
        self.registry.add_skill("old_skill", "old content")
        self.registry._sections["skill_old_skill"].last_referenced = time.time() - 100
        removed = self.registry.remove_stale_skills(60)
        self.assertIn("old_skill", removed)
        self.assertNotIn("skill_old_skill", self.registry._sections)

    def test_remove_stale_skills_keeps_recent(self):
        self.registry.add_skill("new_skill", "new content")
        removed = self.registry.remove_stale_skills(60)
        self.assertNotIn("new_skill", removed)
        self.assertIn("skill_new_skill", self.registry._sections)

    def test_remove_stale_skills_does_not_affect_static(self):
        self.registry.add_static("base", "static content")
        removed = self.registry.remove_stale_skills(0)
        self.assertEqual(removed, [])
        self.assertIn("base", self.registry._sections)

    def test_remove_stale_skills_does_not_affect_dynamic(self):
        self.registry.add_dynamic("env", "dynamic content")
        removed = self.registry.remove_stale_skills(0)
        self.assertEqual(removed, [])
        self.assertIn("env", self.registry._sections)

    def test_remove_stale_skills_logs(self):
        logger = MagicMock()
        logger.log_skill_lifecycle = MagicMock()
        registry = SystemPromptRegistry(logger=logger)
        registry.add_skill("old_skill", "old content")
        registry._sections["skill_old_skill"].last_referenced = time.time() - 100
        registry.remove_stale_skills(60)
        logger.log_skill_lifecycle.assert_any_call("remove_stale", "old_skill")

    def test_remove_stale_skills_no_log_when_none_removed(self):
        logger = MagicMock()
        logger.log_skill_lifecycle = MagicMock()
        registry = SystemPromptRegistry(logger=logger)
        registry.add_skill("new_skill", "new content")
        registry.remove_stale_skills(3600)
        logger.log_skill_lifecycle.assert_called_once_with("add", "new_skill")

    def test_get_skill_names(self):
        self.registry.add_static("base", "base")
        self.registry.add_skill("search", "search content")
        self.registry.add_skill("code", "code content")
        self.registry.add_dynamic("env", "env")
        names = self.registry.get_skill_names()
        self.assertEqual(names, ["search", "code"])

    def test_get_skill_names_empty(self):
        self.assertEqual(self.registry.get_skill_names(), [])

    def test_get_skill_tokens(self):
        self.registry.add_static("base", "base content")
        self.registry.add_skill("search", "search content here")
        encoding = tiktoken.get_encoding("cl100k_base")
        expected = len(encoding.encode("search content here"))
        self.assertEqual(self.registry.get_skill_tokens(), expected)

    def test_get_skill_tokens_empty(self):
        self.assertEqual(self.registry.get_skill_tokens(), 0)

    def test_get_total_tokens(self):
        self.registry.add_static("base", "base content")
        self.registry.add_skill("search", "search content")
        self.registry.add_dynamic("env", "env content")
        encoding = tiktoken.get_encoding("cl100k_base")
        expected = (
            len(encoding.encode("base content"))
            + len(encoding.encode("search content"))
            + len(encoding.encode("env content"))
        )
        self.assertEqual(self.registry.get_total_tokens(), expected)

    def test_get_total_tokens_empty(self):
        self.assertEqual(self.registry.get_total_tokens(), 0)

    def test_has_skill_true(self):
        self.registry.add_skill("search", "content")
        self.assertTrue(self.registry.has_skill("search"))

    def test_has_skill_false(self):
        self.assertFalse(self.registry.has_skill("search"))

    def test_has_skill_after_removal(self):
        self.registry.add_skill("search", "content")
        self.registry.remove_skill("search")
        self.assertFalse(self.registry.has_skill("search"))

    def test_get_section_keys(self):
        self.registry.add_static("base", "base")
        self.registry.add_skill("search", "search")
        self.registry.add_dynamic("env", "env")
        keys = self.registry.get_section_keys()
        self.assertEqual(keys, ["base", "skill_search", "env"])

    def test_get_section_keys_empty(self):
        self.assertEqual(self.registry.get_section_keys(), [])

    def test_overwrite_static(self):
        self.registry.add_static("base", "v1")
        self.registry.add_static("base", "v2")
        self.assertEqual(self.registry._sections["base"].content, "v2")

    def test_overwrite_skill(self):
        self.registry.add_skill("search", "v1")
        self.registry.add_skill("search", "v2")
        self.assertEqual(self.registry._sections["skill_search"].content, "v2")


if __name__ == "__main__":
    unittest.main()
