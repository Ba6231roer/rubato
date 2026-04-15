import time
import unittest

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

from src.context.system_prompt_registry import SystemPromptRegistry
from src.context.conversation_history import ConversationHistory
from src.context.manager import ContextManager
from src.core.llm_wrapper import LLMCaller


class TestRegistryWithLLMCaller(unittest.TestCase):

    def test_prepare_messages_uses_registry_build(self):
        registry = SystemPromptRegistry()
        registry.add_static("base", "You are a helpful assistant.")
        registry.add_skill("search", "Search skill content.")

        caller = LLMCaller(
            api_key="test-key",
            model="test-model",
            base_url="https://api.test.com/v1",
            system_prompt_registry=registry,
        )

        messages = [HumanMessage(content="Hello")]
        prepared = caller._prepare_messages(messages)

        self.assertEqual(len(prepared), 2)
        self.assertIsInstance(prepared[0], SystemMessage)
        expected_content = "You are a helpful assistant.\n\nSearch skill content."
        self.assertEqual(prepared[0].content, expected_content)
        self.assertIsInstance(prepared[1], HumanMessage)
        self.assertEqual(prepared[1].content, "Hello")

    def test_prepare_messages_prefers_registry_over_static_prompt(self):
        registry = SystemPromptRegistry()
        registry.add_static("base", "Registry prompt")

        caller = LLMCaller(
            api_key="test-key",
            model="test-model",
            base_url="https://api.test.com/v1",
            system_prompt="Static prompt",
            system_prompt_registry=registry,
        )

        messages = [HumanMessage(content="Hi")]
        prepared = caller._prepare_messages(messages)

        self.assertEqual(prepared[0].content, "Registry prompt")

    def test_prepare_messages_without_registry_uses_static(self):
        caller = LLMCaller(
            api_key="test-key",
            model="test-model",
            base_url="https://api.test.com/v1",
            system_prompt="Static prompt",
        )

        messages = [HumanMessage(content="Hi")]
        prepared = caller._prepare_messages(messages)

        self.assertEqual(prepared[0].content, "Static prompt")

    def test_registry_build_changes_reflect_in_prepare_messages(self):
        registry = SystemPromptRegistry()
        registry.add_static("base", "Base prompt")

        caller = LLMCaller(
            api_key="test-key",
            model="test-model",
            base_url="https://api.test.com/v1",
            system_prompt_registry=registry,
        )

        messages = [HumanMessage(content="Hi")]
        prepared1 = caller._prepare_messages(messages)
        self.assertEqual(prepared1[0].content, "Base prompt")

        registry.add_skill("code", "Code skill content")
        prepared2 = caller._prepare_messages(messages)
        self.assertEqual(prepared2[0].content, "Base prompt\n\nCode skill content")


class TestConversationHistoryIncrementalFlatten(unittest.TestCase):

    def test_react_loop_flatten_integration(self):
        history = ConversationHistory()

        user_msg = HumanMessage(content="analyze this code")
        history.start_turn(user_msg)

        ai_msg1 = AIMessage(
            content="reading file",
            tool_calls=[{"id": "tc1", "name": "read_file", "args": {"path": "a.py"}}],
        )
        tool_msg1 = ToolMessage(content="file a content", tool_call_id="tc1")
        history.append_assistant_step(ai_msg1, [tool_msg1])

        ai_msg2 = AIMessage(
            content="reading another file",
            tool_calls=[{"id": "tc2", "name": "read_file", "args": {"path": "b.py"}}],
        )
        tool_msg2 = ToolMessage(content="file b content", tool_call_id="tc2")
        history.append_assistant_step(ai_msg2, [tool_msg2])

        ai_msg3 = AIMessage(content="here is my analysis")
        history.append_assistant_step(ai_msg3)

        turn = history.finish_turn()
        self.assertIsNotNone(turn)
        self.assertEqual(len(turn.assistant_steps), 3)

        messages = history.flatten_to_messages()
        self.assertEqual(len(messages), 6)
        self.assertIsInstance(messages[0], HumanMessage)
        self.assertEqual(messages[0].content, "analyze this code")
        self.assertIsInstance(messages[1], AIMessage)
        self.assertEqual(messages[1].content, "reading file")
        self.assertIsInstance(messages[2], ToolMessage)
        self.assertEqual(messages[2].content, "file a content")
        self.assertIsInstance(messages[3], AIMessage)
        self.assertEqual(messages[3].content, "reading another file")
        self.assertIsInstance(messages[4], ToolMessage)
        self.assertEqual(messages[4].content, "file b content")
        self.assertIsInstance(messages[5], AIMessage)
        self.assertEqual(messages[5].content, "here is my analysis")

    def test_multi_turn_incremental_flatten(self):
        history = ConversationHistory()

        history.start_turn(HumanMessage(content="turn 1 question"))
        history.append_assistant_step(AIMessage(content="turn 1 answer"))
        history.finish_turn()

        history.start_turn(HumanMessage(content="turn 2 question"))
        history.append_assistant_step(
            AIMessage(content="calling tool", tool_calls=[{"id": "tc1", "name": "search", "args": {}}]),
            [ToolMessage(content="search result", tool_call_id="tc1")],
        )
        history.append_assistant_step(AIMessage(content="turn 2 final answer"))
        history.finish_turn()

        messages = history.flatten_to_messages()
        self.assertEqual(len(messages), 6)
        self.assertEqual(messages[0].content, "turn 1 question")
        self.assertEqual(messages[1].content, "turn 1 answer")
        self.assertEqual(messages[2].content, "turn 2 question")
        self.assertEqual(messages[3].content, "calling tool")
        self.assertEqual(messages[4].content, "search result")
        self.assertEqual(messages[5].content, "turn 2 final answer")

    def test_flatten_with_compression_and_incremental(self):
        history = ConversationHistory()

        for i in range(8):
            turn_history_msg = HumanMessage(content=f"user {i}")
            ai_resp = AIMessage(content=f"assistant {i}")
            from src.context.conversation_history import AssistantStep, ConversationTurn
            step = AssistantStep(assistant_message=ai_resp)
            turn = ConversationTurn(user_message=turn_history_msg, assistant_steps=[step])
            history.add_turn(turn)

        history.compress_old_turns(summary="old summary", keep_recent=3)

        history.start_turn(HumanMessage(content="new question"))
        history.append_assistant_step(AIMessage(content="new answer"))
        history.finish_turn()

        messages = history.flatten_to_messages()
        self.assertIsInstance(messages[0], HumanMessage)
        self.assertIn("old summary", messages[0].content)
        self.assertEqual(messages[1].content, "user 5")
        self.assertEqual(messages[-2].content, "new question")
        self.assertEqual(messages[-1].content, "new answer")


class TestRegistryStaleSkillCleanup(unittest.TestCase):

    def test_stale_skill_removed_from_build(self):
        registry = SystemPromptRegistry()
        registry.add_static("base", "Base instruction")
        registry.add_skill("old_skill", "Old skill content")
        registry.add_skill("new_skill", "New skill content")

        registry._sections["skill_old_skill"].last_referenced = time.time() - 3600

        removed = registry.remove_stale_skills(1800)
        self.assertEqual(removed, ["old_skill"])

        built = registry.build()
        self.assertNotIn("Old skill content", built)
        self.assertIn("Base instruction", built)
        self.assertIn("New skill content", built)

    def test_stale_cleanup_preserves_order(self):
        registry = SystemPromptRegistry()
        registry.add_static("base", "Base")
        registry.add_skill("stale_skill", "Stale")
        registry.add_dynamic("env", "Env info")
        registry.add_skill("fresh_skill", "Fresh")

        registry._sections["skill_stale_skill"].last_referenced = time.time() - 7200

        registry.remove_stale_skills(3600)

        built = registry.build()
        self.assertEqual(built, "Base\n\nEnv info\n\nFresh")

    def test_all_skills_stale(self):
        registry = SystemPromptRegistry()
        registry.add_static("base", "Base")
        registry.add_skill("skill_a", "Content A")
        registry.add_skill("skill_b", "Content B")

        registry._sections["skill_skill_a"].last_referenced = time.time() - 7200
        registry._sections["skill_skill_b"].last_referenced = time.time() - 7200

        removed = registry.remove_stale_skills(3600)
        self.assertEqual(sorted(removed), ["skill_a", "skill_b"])

        built = registry.build()
        self.assertEqual(built, "Base")

    def test_no_skills_stale(self):
        registry = SystemPromptRegistry()
        registry.add_static("base", "Base")
        registry.add_skill("active_skill", "Active content")

        removed = registry.remove_stale_skills(3600)
        self.assertEqual(removed, [])

        built = registry.build()
        self.assertEqual(built, "Base\n\nActive content")


class TestContextManagerWithRegistry(unittest.TestCase):

    def test_is_skill_loaded_delegates_to_registry(self):
        registry = SystemPromptRegistry()
        registry.add_skill("search", "Search content")
        cm = ContextManager(system_prompt_registry=registry)

        self.assertTrue(cm.is_skill_loaded("search"))
        self.assertFalse(cm.is_skill_loaded("nonexistent"))

    def test_mark_skill_loaded_delegates_to_registry(self):
        registry = SystemPromptRegistry()
        registry.add_skill("search", "Search content")
        cm = ContextManager(system_prompt_registry=registry)

        old_ref = registry._sections["skill_search"].last_referenced
        time.sleep(0.01)
        cm.mark_skill_loaded("search")

        new_ref = registry._sections["skill_search"].last_referenced
        self.assertGreater(new_ref, old_ref)

    def test_is_skill_loaded_without_registry(self):
        cm = ContextManager(system_prompt_registry=None)
        cm.mark_skill_loaded("search")

        self.assertTrue(cm.is_skill_loaded("search"))
        self.assertFalse(cm.is_skill_loaded("other"))

    def test_set_registry_updates_delegation(self):
        registry = SystemPromptRegistry()
        registry.add_skill("code", "Code content")
        cm = ContextManager()

        self.assertFalse(cm.is_skill_loaded("code"))

        cm.set_registry(registry)
        self.assertTrue(cm.is_skill_loaded("code"))

    def test_mark_skill_loaded_adds_to_internal_list(self):
        registry = SystemPromptRegistry()
        registry.add_skill("search", "Search content")
        cm = ContextManager(system_prompt_registry=registry)

        cm.mark_skill_loaded("search")
        self.assertIn("search", cm.get_loaded_skills())

    def test_is_skill_loaded_internal_list_takes_precedence(self):
        registry = SystemPromptRegistry()
        cm = ContextManager(system_prompt_registry=registry)

        cm.mark_skill_loaded("cached_skill")
        self.assertFalse(registry.has_skill("cached_skill"))
        self.assertTrue(cm.is_skill_loaded("cached_skill"))


if __name__ == "__main__":
    unittest.main()
