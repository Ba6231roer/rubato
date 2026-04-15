import time
import unittest

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from src.context.conversation_history import AssistantStep, ConversationTurn, ConversationHistory


class TestAssistantStep(unittest.TestCase):

    def test_default_tool_results(self):
        ai_msg = AIMessage(content="hello")
        step = AssistantStep(assistant_message=ai_msg)
        self.assertEqual(step.assistant_message, ai_msg)
        self.assertEqual(step.tool_results, [])

    def test_with_tool_results(self):
        ai_msg = AIMessage(content="calling tool", tool_calls=[{"id": "tc1", "name": "search", "args": {"q": "test"}}])
        tool_msg = ToolMessage(content="result", tool_call_id="tc1")
        step = AssistantStep(assistant_message=ai_msg, tool_results=[tool_msg])
        self.assertEqual(len(step.tool_results), 1)
        self.assertEqual(step.tool_results[0].content, "result")


class TestConversationTurn(unittest.TestCase):

    def test_default_fields(self):
        user_msg = HumanMessage(content="hi")
        turn = ConversationTurn(user_message=user_msg)
        self.assertEqual(turn.user_message, user_msg)
        self.assertEqual(turn.assistant_steps, [])
        self.assertGreater(turn.timestamp, 0)

    def test_with_assistant_steps(self):
        user_msg = HumanMessage(content="hi")
        ai_msg = AIMessage(content="hello")
        step = AssistantStep(assistant_message=ai_msg)
        turn = ConversationTurn(user_message=user_msg, assistant_steps=[step])
        self.assertEqual(len(turn.assistant_steps), 1)

    def test_custom_timestamp(self):
        user_msg = HumanMessage(content="hi")
        ts = 1000000.0
        turn = ConversationTurn(user_message=user_msg, timestamp=ts)
        self.assertEqual(turn.timestamp, ts)


class TestConversationHistoryStartTurnFinishTurn(unittest.TestCase):

    def test_start_append_finish_full_flow(self):
        history = ConversationHistory()
        user_msg = HumanMessage(content="what is 1+1?")
        ai_msg = AIMessage(content="1+1=2")

        history.start_turn(user_msg)
        history.append_assistant_step(ai_msg)
        turn = history.finish_turn()

        self.assertIsNotNone(turn)
        self.assertEqual(turn.user_message.content, "what is 1+1?")
        self.assertEqual(len(turn.assistant_steps), 1)
        self.assertEqual(turn.assistant_steps[0].assistant_message.content, "1+1=2")
        self.assertEqual(history.get_turn_count(), 1)

    def test_finish_turn_without_start_returns_none(self):
        history = ConversationHistory()
        result = history.finish_turn()
        self.assertIsNone(result)

    def test_start_turn_auto_finishes_previous(self):
        history = ConversationHistory()
        user_msg1 = HumanMessage(content="first")
        user_msg2 = HumanMessage(content="second")
        ai_msg = AIMessage(content="response")

        history.start_turn(user_msg1)
        history.append_assistant_step(ai_msg)
        history.start_turn(user_msg2)

        self.assertEqual(history.get_turn_count(), 1)
        self.assertEqual(history._turns[0].user_message.content, "first")

    def test_multiple_assistant_steps(self):
        history = ConversationHistory()
        user_msg = HumanMessage(content="search and read")
        ai_msg1 = AIMessage(content="searching", tool_calls=[{"id": "tc1", "name": "search", "args": {}}])
        tool_msg1 = ToolMessage(content="found files", tool_call_id="tc1")
        ai_msg2 = AIMessage(content="reading file", tool_calls=[{"id": "tc2", "name": "read", "args": {}}])
        tool_msg2 = ToolMessage(content="file content", tool_call_id="tc2")
        ai_msg3 = AIMessage(content="here is the answer")

        history.start_turn(user_msg)
        history.append_assistant_step(ai_msg1, [tool_msg1])
        history.append_assistant_step(ai_msg2, [tool_msg2])
        history.append_assistant_step(ai_msg3)
        turn = history.finish_turn()

        self.assertEqual(len(turn.assistant_steps), 3)
        self.assertEqual(len(turn.assistant_steps[0].tool_results), 1)
        self.assertEqual(len(turn.assistant_steps[1].tool_results), 1)
        self.assertEqual(len(turn.assistant_steps[2].tool_results), 0)

    def test_append_assistant_step_with_none_tool_results(self):
        history = ConversationHistory()
        user_msg = HumanMessage(content="hi")
        ai_msg = AIMessage(content="hello")

        history.start_turn(user_msg)
        history.append_assistant_step(ai_msg, None)
        turn = history.finish_turn()

        self.assertEqual(turn.assistant_steps[0].tool_results, [])


class TestConversationHistoryAddTurn(unittest.TestCase):

    def test_add_turn_directly(self):
        history = ConversationHistory()
        user_msg = HumanMessage(content="hello")
        ai_msg = AIMessage(content="hi")
        step = AssistantStep(assistant_message=ai_msg)
        turn = ConversationTurn(user_message=user_msg, assistant_steps=[step])

        history.add_turn(turn)
        self.assertEqual(history.get_turn_count(), 1)
        self.assertEqual(history._turns[0].user_message.content, "hello")


class TestConversationHistoryCompression(unittest.TestCase):

    def _build_history_with_n_turns(self, n):
        history = ConversationHistory()
        for i in range(n):
            user_msg = HumanMessage(content=f"user {i}")
            ai_msg = AIMessage(content=f"assistant {i}")
            step = AssistantStep(assistant_message=ai_msg)
            turn = ConversationTurn(user_message=user_msg, assistant_steps=[step])
            history.add_turn(turn)
        return history

    def test_get_turns_for_compression_returns_old_turns(self):
        history = self._build_history_with_n_turns(10)
        turns = history.get_turns_for_compression(keep_recent=5)
        self.assertEqual(len(turns), 5)
        self.assertEqual(turns[0].user_message.content, "user 0")
        self.assertEqual(turns[-1].user_message.content, "user 4")

    def test_get_turns_for_compression_when_fewer_than_keep(self):
        history = self._build_history_with_n_turns(3)
        turns = history.get_turns_for_compression(keep_recent=5)
        self.assertEqual(len(turns), 0)

    def test_compress_old_turns_sets_boundary(self):
        history = self._build_history_with_n_turns(10)
        history.compress_old_turns(summary="old conversation summary", keep_recent=5)

        self.assertEqual(history._summary, "old conversation summary")
        self.assertEqual(len(history.get_active_turns()), 5)
        self.assertEqual(history.get_active_turns()[0].user_message.content, "user 5")

    def test_compress_old_turns_when_nothing_to_compress(self):
        history = self._build_history_with_n_turns(3)
        history.compress_old_turns(summary="summary", keep_recent=5)
        self.assertIsNone(history._summary)

    def test_get_active_turns_without_compression(self):
        history = self._build_history_with_n_turns(5)
        active = history.get_active_turns()
        self.assertEqual(len(active), 5)

    def test_get_active_turns_after_compression(self):
        history = self._build_history_with_n_turns(10)
        history.compress_old_turns(summary="summary", keep_recent=3)
        active = history.get_active_turns()
        self.assertEqual(len(active), 3)
        self.assertEqual(active[0].user_message.content, "user 7")


class TestConversationHistoryFlattenToMessages(unittest.TestCase):

    def test_flatten_simple_turn(self):
        history = ConversationHistory()
        user_msg = HumanMessage(content="hello")
        ai_msg = AIMessage(content="hi there")
        step = AssistantStep(assistant_message=ai_msg)
        turn = ConversationTurn(user_message=user_msg, assistant_steps=[step])
        history.add_turn(turn)

        messages = history.flatten_to_messages()
        self.assertEqual(len(messages), 2)
        self.assertIsInstance(messages[0], HumanMessage)
        self.assertEqual(messages[0].content, "hello")
        self.assertIsInstance(messages[1], AIMessage)
        self.assertEqual(messages[1].content, "hi there")

    def test_flatten_with_tool_results(self):
        history = ConversationHistory()
        user_msg = HumanMessage(content="search")
        ai_msg = AIMessage(content="searching", tool_calls=[{"id": "tc1", "name": "search", "args": {}}])
        tool_msg = ToolMessage(content="results", tool_call_id="tc1")
        step = AssistantStep(assistant_message=ai_msg, tool_results=[tool_msg])
        turn = ConversationTurn(user_message=user_msg, assistant_steps=[step])
        history.add_turn(turn)

        messages = history.flatten_to_messages()
        self.assertEqual(len(messages), 3)
        self.assertIsInstance(messages[0], HumanMessage)
        self.assertIsInstance(messages[1], AIMessage)
        self.assertIsInstance(messages[2], ToolMessage)

    def test_flatten_with_summary(self):
        history = ConversationHistory()
        user_msg = HumanMessage(content="hello")
        ai_msg = AIMessage(content="hi")
        step = AssistantStep(assistant_message=ai_msg)
        turn = ConversationTurn(user_message=user_msg, assistant_steps=[step])
        history.add_turn(turn)
        history._summary = "previous conversation summary"

        messages = history.flatten_to_messages()
        self.assertEqual(len(messages), 3)
        self.assertIsInstance(messages[0], HumanMessage)
        self.assertEqual(messages[0].content, "[之前的对话摘要]\nprevious conversation summary")

    def test_flatten_empty_history(self):
        history = ConversationHistory()
        messages = history.flatten_to_messages()
        self.assertEqual(len(messages), 0)

    def test_flatten_after_compression_only_active_turns(self):
        history = ConversationHistory()
        for i in range(8):
            user_msg = HumanMessage(content=f"user {i}")
            ai_msg = AIMessage(content=f"assistant {i}")
            step = AssistantStep(assistant_message=ai_msg)
            turn = ConversationTurn(user_message=user_msg, assistant_steps=[step])
            history.add_turn(turn)

        history.compress_old_turns(summary="old summary", keep_recent=3)
        messages = history.flatten_to_messages()

        self.assertEqual(len(messages), 7)
        self.assertEqual(messages[0].content, "[之前的对话摘要]\nold summary")
        self.assertEqual(messages[1].content, "user 5")
        self.assertEqual(messages[2].content, "assistant 5")


class TestConversationHistoryClear(unittest.TestCase):

    def test_clear_resets_all_state(self):
        history = ConversationHistory()
        user_msg = HumanMessage(content="hello")
        ai_msg = AIMessage(content="hi")
        step = AssistantStep(assistant_message=ai_msg)
        turn = ConversationTurn(user_message=user_msg, assistant_steps=[step])
        history.add_turn(turn)
        history._summary = "some summary"
        history._compact_boundary_turn_idx = 1

        history.clear()

        self.assertEqual(history.get_turn_count(), 0)
        self.assertIsNone(history._summary)
        self.assertEqual(history._compact_boundary_turn_idx, 0)
        self.assertIsNone(history._pending_user_message)
        self.assertEqual(history._pending_assistant_steps, [])

    def test_clear_after_pending_start(self):
        history = ConversationHistory()
        history.start_turn(HumanMessage(content="hi"))
        history.append_assistant_step(AIMessage(content="hello"))

        history.clear()

        self.assertIsNone(history._pending_user_message)
        self.assertEqual(history._pending_assistant_steps, [])


class TestConversationHistoryIncrementalMode(unittest.TestCase):

    def test_react_loop_multi_tool_calls(self):
        history = ConversationHistory()
        user_msg = HumanMessage(content="analyze this code")

        history.start_turn(user_msg)

        ai_msg1 = AIMessage(content="reading file", tool_calls=[{"id": "tc1", "name": "read_file", "args": {"path": "a.py"}}])
        tool_msg1 = ToolMessage(content="file a content", tool_call_id="tc1")
        history.append_assistant_step(ai_msg1, [tool_msg1])

        ai_msg2 = AIMessage(content="reading another file", tool_calls=[{"id": "tc2", "name": "read_file", "args": {"path": "b.py"}}])
        tool_msg2 = ToolMessage(content="file b content", tool_call_id="tc2")
        history.append_assistant_step(ai_msg2, [tool_msg2])

        ai_msg3 = AIMessage(content="here is my analysis")
        history.append_assistant_step(ai_msg3)

        turn = history.finish_turn()

        self.assertEqual(len(turn.assistant_steps), 3)
        self.assertEqual(turn.assistant_steps[0].assistant_message.content, "reading file")
        self.assertEqual(turn.assistant_steps[1].assistant_message.content, "reading another file")
        self.assertEqual(turn.assistant_steps[2].assistant_message.content, "here is my analysis")
        self.assertEqual(len(turn.assistant_steps[0].tool_results), 1)
        self.assertEqual(len(turn.assistant_steps[1].tool_results), 1)
        self.assertEqual(len(turn.assistant_steps[2].tool_results), 0)

        messages = history.flatten_to_messages()
        self.assertEqual(len(messages), 6)
        self.assertIsInstance(messages[0], HumanMessage)
        self.assertIsInstance(messages[1], AIMessage)
        self.assertIsInstance(messages[2], ToolMessage)
        self.assertIsInstance(messages[3], AIMessage)
        self.assertIsInstance(messages[4], ToolMessage)
        self.assertIsInstance(messages[5], AIMessage)

    def test_multiple_turns_incremental(self):
        history = ConversationHistory()

        history.start_turn(HumanMessage(content="turn 1"))
        history.append_assistant_step(AIMessage(content="response 1"))
        turn1 = history.finish_turn()

        history.start_turn(HumanMessage(content="turn 2"))
        history.append_assistant_step(AIMessage(content="response 2"))
        turn2 = history.finish_turn()

        self.assertEqual(history.get_turn_count(), 2)
        self.assertEqual(turn1.user_message.content, "turn 1")
        self.assertEqual(turn2.user_message.content, "turn 2")

    def test_finish_then_start_new_turn(self):
        history = ConversationHistory()

        history.start_turn(HumanMessage(content="first"))
        history.append_assistant_step(AIMessage(content="first response"))
        history.finish_turn()

        self.assertIsNone(history._pending_user_message)
        self.assertEqual(history._pending_assistant_steps, [])

        history.start_turn(HumanMessage(content="second"))
        history.append_assistant_step(AIMessage(content="second response"))
        turn = history.finish_turn()

        self.assertEqual(history.get_turn_count(), 2)
        self.assertEqual(turn.user_message.content, "second")


class TestConversationHistoryGetTurnCount(unittest.TestCase):

    def test_empty_history(self):
        history = ConversationHistory()
        self.assertEqual(history.get_turn_count(), 0)

    def test_after_adding_turns(self):
        history = ConversationHistory()
        for i in range(5):
            turn = ConversationTurn(
                user_message=HumanMessage(content=f"msg {i}"),
                assistant_steps=[AssistantStep(assistant_message=AIMessage(content=f"resp {i}"))],
            )
            history.add_turn(turn)
        self.assertEqual(history.get_turn_count(), 5)


if __name__ == "__main__":
    unittest.main()
