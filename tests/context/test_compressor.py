import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
)

from src.context.compressor import ContextCompressor
from src.context.tool_result_storage import (
    ToolResultStorage,
    ContentReplacementState,
    apply_tool_result_budget,
    TOOL_RESULT_CLEARED_MESSAGE,
    PERSISTED_OUTPUT_TAG,
)
from src.context.task_intent_manager import TaskIntentManager


def _make_compressor(**overrides):
    defaults = dict(
        llm_caller=None,
        max_context_tokens=80000,
        autocompact_buffer_tokens=13000,
        manual_compact_buffer_tokens=3000,
        warning_threshold_buffer_tokens=20000,
        keep_recent=6,
        summary_max_length=300,
        history_summary_count=10,
        snip_keep_recent=6,
        max_consecutive_failures=3,
        tool_result_storage=None,
        content_replacement_state=None,
        logger=MagicMock(),
        task_intent_manager=None,
    )
    defaults.update(overrides)
    return ContextCompressor(**defaults)


def _build_messages(n_pairs=10, content_prefix="msg"):
    messages = []
    for i in range(n_pairs):
        messages.append(HumanMessage(content=f"{content_prefix}_user_{i}"))
        messages.append(AIMessage(content=f"{content_prefix}_ai_{i}"))
    return messages


def _build_messages_with_tools(n_rounds=5):
    messages = []
    for i in range(n_rounds):
        messages.append(HumanMessage(content=f"request_{i}"))
        tc_id = f"tc_{i}"
        messages.append(
            AIMessage(
                content=f"calling tool {i}",
                tool_calls=[{"id": tc_id, "name": f"tool_{i}", "args": {}}],
            )
        )
        messages.append(ToolMessage(content=f"tool_result_{i}" * 100, tool_call_id=tc_id, name=f"tool_{i}"))
        messages.append(AIMessage(content=f"summary_{i}"))
    return messages


class TestCountTokens:
    def test_count_tokens_string_content(self):
        compressor = _make_compressor()
        messages = [HumanMessage(content="Hello world")]
        tokens = compressor.count_tokens(messages)
        assert tokens > 0

    def test_count_tokens_list_content(self):
        compressor = _make_compressor()
        messages = [HumanMessage(content=[{"type": "text", "text": "Hello world"}])]
        tokens = compressor.count_tokens(messages)
        assert tokens > 0

    def test_count_text_tokens(self):
        compressor = _make_compressor()
        tokens = compressor.count_text_tokens("Hello world")
        assert tokens > 0

    def test_estimate_tokens_fallback_to_count(self):
        compressor = _make_compressor()
        messages = [HumanMessage(content="test")]
        assert compressor.estimate_tokens(messages) == compressor.count_tokens(messages)

    def test_estimate_tokens_uses_api_usage(self):
        compressor = _make_compressor()
        compressor._last_api_usage_tokens = 500
        messages = [HumanMessage(content="test")]
        assert compressor.estimate_tokens(messages) == 500


class TestUpdateUsageFromResponse:
    def test_update_from_usage_metadata(self):
        compressor = _make_compressor()
        response = AIMessage(content="hi")
        response.usage_metadata = {"input_tokens": 1234, "total_tokens": 2000}
        compressor.update_usage_from_response(response)
        assert compressor._last_api_usage_tokens == 1234

    def test_update_from_response_metadata(self):
        compressor = _make_compressor()
        response = AIMessage(content="hi")
        response.response_metadata = {"token_usage": {"prompt_tokens": 5678}}
        compressor.update_usage_from_response(response)
        assert compressor._last_api_usage_tokens == 5678

    def test_response_metadata_overwrites_usage_metadata(self):
        compressor = _make_compressor()
        response = AIMessage(content="hi")
        response.usage_metadata = {"input_tokens": 100}
        response.response_metadata = {"token_usage": {"prompt_tokens": 200}}
        compressor.update_usage_from_response(response)
        assert compressor._last_api_usage_tokens == 200

    def test_no_metadata_no_crash(self):
        compressor = _make_compressor()
        response = AIMessage(content="hi")
        compressor.update_usage_from_response(response)
        assert compressor._last_api_usage_tokens == 0


class TestNeedsCompression:
    def test_below_threshold(self):
        compressor = _make_compressor(max_context_tokens=1000, autocompact_buffer_tokens=200)
        messages = [HumanMessage(content="short")]
        assert not compressor.needs_compression(messages)

    def test_above_threshold(self):
        compressor = _make_compressor(max_context_tokens=100, autocompact_buffer_tokens=10)
        long_content = "word " * 200
        messages = [HumanMessage(content=long_content)]
        assert compressor.needs_compression(messages)


class TestCompress:
    def test_no_compression_needed(self):
        compressor = _make_compressor(max_context_tokens=100000)
        messages = [HumanMessage(content="hello"), AIMessage(content="hi")]
        result = compressor.compress(messages)
        assert result == messages

    def test_compress_preserves_system_messages(self):
        compressor = _make_compressor(max_context_tokens=200, autocompact_buffer_tokens=50, keep_recent=2)
        system = SystemMessage(content="system prompt")
        messages = [system] + _build_messages(n_pairs=20)
        result = compressor.compress(messages)
        system_in_result = [m for m in result if isinstance(m, SystemMessage)]
        assert len(system_in_result) >= 1
        assert system_in_result[0].content == "system prompt"

    def test_compress_creates_summary(self):
        compressor = _make_compressor(max_context_tokens=50, autocompact_buffer_tokens=10, keep_recent=2)
        messages = _build_messages(n_pairs=20)
        result = compressor.compress(messages)
        summary_msgs = [m for m in result if isinstance(m, HumanMessage) and "[历史摘要]" in m.content]
        assert len(summary_msgs) == 1

    def test_compress_keeps_recent_messages(self):
        compressor = _make_compressor(max_context_tokens=300, autocompact_buffer_tokens=50, keep_recent=2)
        messages = _build_messages(n_pairs=20)
        result = compressor.compress(messages)
        recent_content = result[-1].content
        assert "msg_ai_19" in recent_content

    def test_compress_too_few_messages_returns_unchanged(self):
        compressor = _make_compressor(max_context_tokens=10, autocompact_buffer_tokens=5, keep_recent=6)
        messages = [HumanMessage(content="a"), AIMessage(content="b")]
        result = compressor.compress(messages)
        assert result == messages


class TestSnipCompact:
    def test_no_tool_messages(self):
        compressor = _make_compressor()
        messages = [HumanMessage(content="hello"), AIMessage(content="hi")]
        result, freed = compressor.snip_compact(messages)
        assert result == messages
        assert freed == 0

    def test_snip_replaces_old_tool_results(self):
        compressor = _make_compressor(snip_keep_recent=2)
        messages = _build_messages_with_tools(n_rounds=5)
        result, freed = compressor.snip_compact(messages)
        assert freed > 0
        tool_msgs = [m for m in result if isinstance(m, ToolMessage)]
        cleared = [m for m in tool_msgs if m.content == TOOL_RESULT_CLEARED_MESSAGE]
        assert len(cleared) > 0

    def test_snip_keeps_recent_tool_results(self):
        compressor = _make_compressor(snip_keep_recent=2)
        messages = _build_messages_with_tools(n_rounds=5)
        result, freed = compressor.snip_compact(messages)
        tool_msgs = [m for m in result if isinstance(m, ToolMessage)]
        recent_tool_ids = {m.tool_call_id for m in tool_msgs[-2:]}
        for msg in tool_msgs[-2:]:
            assert msg.content != TOOL_RESULT_CLEARED_MESSAGE

    def test_snip_preserves_non_tool_messages(self):
        compressor = _make_compressor(snip_keep_recent=2)
        messages = _build_messages_with_tools(n_rounds=5)
        result, freed = compressor.snip_compact(messages)
        human_msgs = [m for m in result if isinstance(m, HumanMessage)]
        ai_msgs = [m for m in result if isinstance(m, AIMessage)]
        assert len(human_msgs) == 5
        assert len(ai_msgs) == 10


class TestAutoCompact:
    @pytest.mark.asyncio
    async def test_auto_compact_produces_boundary(self):
        mock_llm = AsyncMock()
        mock_llm.invoke = AsyncMock(return_value=AIMessage(content="<summary>Test summary</summary>"))
        compressor = _make_compressor(llm_caller=mock_llm, keep_recent=3)
        messages = [SystemMessage(content="system")] + _build_messages(n_pairs=10)
        result = await compressor.auto_compact(messages)
        boundary_msgs = [m for m in result if isinstance(m, SystemMessage) and m.content.startswith("[compact_boundary]")]
        assert len(boundary_msgs) == 1
        assert "trigger=auto" in boundary_msgs[0].content

    @pytest.mark.asyncio
    async def test_auto_compact_preserves_system_messages(self):
        mock_llm = AsyncMock()
        mock_llm.invoke = AsyncMock(return_value=AIMessage(content="<summary>Summary</summary>"))
        compressor = _make_compressor(llm_caller=mock_llm, keep_recent=3)
        messages = [SystemMessage(content="system prompt")] + _build_messages(n_pairs=10)
        result = await compressor.auto_compact(messages)
        non_boundary_system = [m for m in result if isinstance(m, SystemMessage) and not m.content.startswith("[compact_boundary]")]
        assert len(non_boundary_system) == 1
        assert non_boundary_system[0].content == "system prompt"

    @pytest.mark.asyncio
    async def test_auto_compact_keeps_recent_messages(self):
        mock_llm = AsyncMock()
        mock_llm.invoke = AsyncMock(return_value=AIMessage(content="<summary>Summary</summary>"))
        compressor = _make_compressor(llm_caller=mock_llm, keep_recent=3)
        messages = [SystemMessage(content="system")] + _build_messages(n_pairs=10)
        result = await compressor.auto_compact(messages)
        human_msgs = [m for m in result if isinstance(m, HumanMessage) and not m.content.startswith("This session")]
        assert len(human_msgs) > 0

    @pytest.mark.asyncio
    async def test_auto_compact_with_task_intent(self, tmp_path):
        mock_llm = AsyncMock()
        mock_llm.invoke = AsyncMock(return_value=AIMessage(content="<summary>Summary</summary>"))
        task_intent = TaskIntentManager(session_dir=str(tmp_path))
        task_intent.extract_task_intent("Build a test framework")
        compressor = _make_compressor(llm_caller=mock_llm, keep_recent=3, task_intent_manager=task_intent)
        messages = [SystemMessage(content="system")] + _build_messages(n_pairs=10)
        result = await compressor.auto_compact(messages)
        intent_msgs = [m for m in result if isinstance(m, HumanMessage) and "[Task Intent - PRESERVED]" in m.content]
        assert len(intent_msgs) == 1

    @pytest.mark.asyncio
    async def test_auto_compact_clears_read_file_state(self):
        mock_llm = AsyncMock()
        mock_llm.invoke = AsyncMock(return_value=AIMessage(content="<summary>Summary</summary>"))
        mock_storage = MagicMock()
        mock_storage.read_file_state = {"file1.txt": "content1", "file2.txt": "content2"}
        compressor = _make_compressor(llm_caller=mock_llm, keep_recent=3, tool_result_storage=mock_storage)
        messages = [SystemMessage(content="system")] + _build_messages(n_pairs=10)
        result = await compressor.auto_compact(messages)
        assert len(mock_storage.read_file_state) == 0


class TestAutoCompactIfNeeded:
    @pytest.mark.asyncio
    async def test_below_threshold_no_compact(self):
        compressor = _make_compressor(max_context_tokens=100000, autocompact_buffer_tokens=13000)
        messages = [HumanMessage(content="hello")]
        result = await compressor.auto_compact_if_needed(messages)
        assert result == messages

    @pytest.mark.asyncio
    async def test_above_threshold_triggers_compact(self):
        mock_llm = AsyncMock()
        mock_llm.invoke = AsyncMock(return_value=AIMessage(content="<summary>Summary</summary>"))
        compressor = _make_compressor(
            llm_caller=mock_llm,
            max_context_tokens=200,
            autocompact_buffer_tokens=50,
            keep_recent=2,
        )
        messages = _build_messages(n_pairs=20)
        result = await compressor.auto_compact_if_needed(messages)
        assert len(result) < len(messages)

    @pytest.mark.asyncio
    async def test_consecutive_failures_skips_compact(self):
        compressor = _make_compressor(max_context_tokens=200, autocompact_buffer_tokens=50, max_consecutive_failures=3)
        compressor._consecutive_failures = 3
        messages = _build_messages(n_pairs=20)
        result = await compressor.auto_compact_if_needed(messages)
        assert result == messages

    @pytest.mark.asyncio
    async def test_failure_increments_counter(self):
        mock_llm = AsyncMock()
        mock_llm.invoke = AsyncMock(side_effect=Exception("LLM error"))
        compressor = _make_compressor(
            llm_caller=mock_llm,
            max_context_tokens=200,
            autocompact_buffer_tokens=50,
        )
        messages = _build_messages(n_pairs=20)
        result = await compressor.auto_compact_if_needed(messages)
        assert compressor._consecutive_failures == 1
        assert result == messages

    @pytest.mark.asyncio
    async def test_success_resets_failure_counter(self):
        mock_llm = AsyncMock()
        mock_llm.invoke = AsyncMock(return_value=AIMessage(content="<summary>Summary</summary>"))
        compressor = _make_compressor(
            llm_caller=mock_llm,
            max_context_tokens=200,
            autocompact_buffer_tokens=50,
            keep_recent=2,
        )
        compressor._consecutive_failures = 2
        messages = _build_messages(n_pairs=20)
        await compressor.auto_compact_if_needed(messages)
        assert compressor._consecutive_failures == 0


class TestGetMessagesAfterCompactBoundary:
    def test_no_boundary_returns_all(self):
        compressor = _make_compressor()
        messages = [HumanMessage(content="hello"), AIMessage(content="hi")]
        result = compressor.get_messages_after_compact_boundary(messages)
        assert result == messages

    def test_with_boundary_returns_after(self):
        compressor = _make_compressor()
        messages = [
            HumanMessage(content="old"),
            SystemMessage(content="[compact_boundary] trigger=auto pre_tokens=1000"),
            HumanMessage(content="recent"),
            AIMessage(content="response"),
        ]
        result = compressor.get_messages_after_compact_boundary(messages)
        assert len(result) == 2
        assert result[0].content == "recent"

    def test_multiple_boundaries_uses_last(self):
        compressor = _make_compressor()
        messages = [
            SystemMessage(content="[compact_boundary] trigger=auto pre_tokens=500"),
            HumanMessage(content="mid"),
            SystemMessage(content="[compact_boundary] trigger=auto pre_tokens=800"),
            HumanMessage(content="latest"),
        ]
        result = compressor.get_messages_after_compact_boundary(messages)
        assert len(result) == 1
        assert result[0].content == "latest"


class TestEnsureMessageChainValid:
    def test_empty_messages(self):
        compressor = _make_compressor()
        assert compressor._ensure_message_chain_valid([]) == []

    def test_valid_chain_unchanged(self):
        compressor = _make_compressor()
        messages = [
            AIMessage(content="calling", tool_calls=[{"id": "tc1", "name": "tool", "args": {}}]),
            ToolMessage(content="result", tool_call_id="tc1"),
        ]
        result = compressor._ensure_message_chain_valid(messages)
        assert len(result) == 2
        assert isinstance(result[1], ToolMessage)

    def test_orphan_tool_result_converted(self):
        compressor = _make_compressor()
        messages = [
            ToolMessage(content="orphan result", tool_call_id="tc_unknown"),
        ]
        result = compressor._ensure_message_chain_valid(messages)
        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)
        assert "[工具结果摘要]" in result[0].content

    def test_human_message_preserved(self):
        compressor = _make_compressor()
        messages = [HumanMessage(content="hello")]
        result = compressor._ensure_message_chain_valid(messages)
        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)


class TestCalculateTokenWarningState:
    def test_all_below(self):
        compressor = _make_compressor(
            max_context_tokens=1000,
            warning_threshold_buffer_tokens=200,
            autocompact_buffer_tokens=100,
            manual_compact_buffer_tokens=50,
        )
        state = compressor.calculate_token_warning_state(700)
        assert not state["is_above_warning_threshold"]
        assert not state["is_above_autocompact_threshold"]
        assert not state["is_at_blocking_limit"]

    def test_above_warning(self):
        compressor = _make_compressor(
            max_context_tokens=1000,
            warning_threshold_buffer_tokens=200,
            autocompact_buffer_tokens=100,
            manual_compact_buffer_tokens=50,
        )
        state = compressor.calculate_token_warning_state(850)
        assert state["is_above_warning_threshold"]
        assert not state["is_above_autocompact_threshold"]

    def test_above_autocompact(self):
        compressor = _make_compressor(
            max_context_tokens=1000,
            warning_threshold_buffer_tokens=200,
            autocompact_buffer_tokens=100,
            manual_compact_buffer_tokens=50,
        )
        state = compressor.calculate_token_warning_state(920)
        assert state["is_above_warning_threshold"]
        assert state["is_above_autocompact_threshold"]

    def test_at_blocking_limit(self):
        compressor = _make_compressor(
            max_context_tokens=1000,
            warning_threshold_buffer_tokens=200,
            autocompact_buffer_tokens=100,
            manual_compact_buffer_tokens=50,
        )
        state = compressor.calculate_token_warning_state(960)
        assert state["is_above_warning_threshold"]
        assert state["is_above_autocompact_threshold"]
        assert state["is_at_blocking_limit"]


class TestApplyToolResultBudget:
    def test_no_storage_returns_unchanged(self):
        compressor = _make_compressor(tool_result_storage=None, content_replacement_state=None)
        messages = [ToolMessage(content="result", tool_call_id="tc1")]
        result, replaced = compressor.apply_tool_result_budget(messages)
        assert result == messages
        assert replaced == []

    def test_with_storage_and_state(self, tmp_path):
        storage = ToolResultStorage(session_dir=str(tmp_path))
        state = ContentReplacementState()
        compressor = _make_compressor(tool_result_storage=storage, content_replacement_state=state)
        messages = [ToolMessage(content="small result", tool_call_id="tc1", name="tool1")]
        result, replaced = compressor.apply_tool_result_budget(messages)
        assert len(result) == 1
        assert replaced == []


class TestStripImagesFromMessages:
    def test_strips_image_blocks(self):
        compressor = _make_compressor()
        messages = [
            HumanMessage(content=[
                {"type": "text", "text": "Look at this"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
            ])
        ]
        result = compressor._strip_images_from_messages(messages)
        assert len(result) == 1
        blocks = result[0].content
        image_blocks = [b for b in blocks if b.get("type") == "image_url"]
        text_blocks = [b for b in blocks if b.get("type") == "text" and b.get("text") == "[image]"]
        assert len(image_blocks) == 0
        assert len(text_blocks) == 1

    def test_strips_document_blocks(self):
        compressor = _make_compressor()
        messages = [
            HumanMessage(content=[
                {"type": "text", "text": "Read this"},
                {"type": "document", "source": {"type": "base64", "data": "abc"}},
            ])
        ]
        result = compressor._strip_images_from_messages(messages)
        doc_blocks = [b for b in result[0].content if b.get("type") == "document"]
        assert len(doc_blocks) == 0

    def test_string_content_unchanged(self):
        compressor = _make_compressor()
        messages = [HumanMessage(content="plain text")]
        result = compressor._strip_images_from_messages(messages)
        assert result[0].content == "plain text"


class TestTruncateContent:
    def test_short_content_unchanged(self):
        result = ContextCompressor._truncate_content("short", max_len=200)
        assert result == "short"

    def test_long_content_truncated(self):
        long_text = "a" * 300
        result = ContextCompressor._truncate_content(long_text, max_len=200)
        assert result.endswith("...")
        assert len(result) == 203


class TestGetContentStr:
    def test_string_content(self):
        assert ContextCompressor._get_content_str("hello") == "hello"

    def test_list_content_with_text(self):
        content = [{"type": "text", "text": "hello"}, {"type": "text", "text": "world"}]
        result = ContextCompressor._get_content_str(content)
        assert "hello" in result
        assert "world" in result

    def test_list_content_with_dict_no_text(self):
        content = [{"key": "value"}]
        result = ContextCompressor._get_content_str(content)
        assert "value" in result

    def test_other_type(self):
        result = ContextCompressor._get_content_str(42)
        assert result == "42"


class TestToolResultStorageIntegration:
    def test_persist_large_result(self, tmp_path):
        storage = ToolResultStorage(session_dir=str(tmp_path), persist_threshold=100)
        large_content = "x" * 200
        result = storage.maybe_persist_large_tool_result(large_content, "read_file", "tc_001")
        assert PERSISTED_OUTPUT_TAG in result
        assert "persisted to:" in result

    def test_small_result_kept_in_memory(self, tmp_path):
        storage = ToolResultStorage(session_dir=str(tmp_path), persist_threshold=100)
        small_content = "small result"
        result = storage.maybe_persist_large_tool_result(small_content, "read_file", "tc_002")
        assert result == small_content

    def test_empty_content(self, tmp_path):
        storage = ToolResultStorage(session_dir=str(tmp_path))
        result = storage.maybe_persist_large_tool_result("", "read_file", "tc_003")
        assert "no output" in result

    def test_persisted_file_exists(self, tmp_path):
        storage = ToolResultStorage(session_dir=str(tmp_path), persist_threshold=50)
        content = "a" * 100
        storage.maybe_persist_large_tool_result(content, "read_file", "tc_004")
        import os
        result_file = os.path.join(str(tmp_path), "tool-results", "tc_004.txt")
        assert os.path.exists(result_file)
        with open(result_file, "r", encoding="utf-8") as f:
            assert f.read() == content


class TestApplyToolResultBudgetFunction:
    def test_within_budget_no_replacement(self, tmp_path):
        storage = ToolResultStorage(session_dir=str(tmp_path), message_budget=100000)
        state = ContentReplacementState()
        messages = [
            AIMessage(content="calling", tool_calls=[{"id": "tc1", "name": "tool", "args": {}}]),
            ToolMessage(content="small result", tool_call_id="tc1", name="tool"),
        ]
        result, replaced = apply_tool_result_budget(messages, state, storage)
        assert len(replaced) == 0
        assert result[1].content == "small result"

    def test_exceeds_budget_replaces_largest(self, tmp_path):
        storage = ToolResultStorage(session_dir=str(tmp_path), message_budget=50)
        state = ContentReplacementState()
        messages = [
            AIMessage(content="calling", tool_calls=[{"id": "tc1", "name": "tool", "args": {}}]),
            ToolMessage(content="a" * 200, tool_call_id="tc1", name="tool"),
            AIMessage(content="calling2", tool_calls=[{"id": "tc2", "name": "tool", "args": {}}]),
            ToolMessage(content="b" * 100, tool_call_id="tc2", name="tool"),
        ]
        result, replaced = apply_tool_result_budget(messages, state, storage)
        assert len(replaced) > 0
        assert PERSISTED_OUTPUT_TAG in result[1].content

    def test_replacement_state_persisted(self, tmp_path):
        storage = ToolResultStorage(session_dir=str(tmp_path), message_budget=50)
        state = ContentReplacementState()
        messages = [
            AIMessage(content="calling", tool_calls=[{"id": "tc1", "name": "tool", "args": {}}]),
            ToolMessage(content="a" * 200, tool_call_id="tc1", name="tool"),
        ]
        result, replaced = apply_tool_result_budget(messages, state, storage)
        assert state.is_replaced("tc1")

    def test_already_replaced_uses_cache(self, tmp_path):
        storage = ToolResultStorage(session_dir=str(tmp_path), message_budget=100000)
        state = ContentReplacementState()
        state.mark_seen("tc1")
        state.set_replacement("tc1", "cached replacement")
        messages = [
            ToolMessage(content="original", tool_call_id="tc1", name="tool"),
        ]
        result, replaced = apply_tool_result_budget(messages, state, storage)
        assert result[0].content == "cached replacement"

    def test_skip_tool_names(self, tmp_path):
        storage = ToolResultStorage(session_dir=str(tmp_path), message_budget=10)
        state = ContentReplacementState()
        messages = [
            AIMessage(content="calling", tool_calls=[{"id": "tc1", "name": "shell_tool", "args": {}}]),
            ToolMessage(content="a" * 200, tool_call_id="tc1", name="shell_tool"),
        ]
        result, replaced = apply_tool_result_budget(messages, state, storage, skip_tool_names={"shell_tool"})
        assert len(replaced) == 0


class TestContentReplacementState:
    def test_mark_seen(self):
        state = ContentReplacementState()
        state.mark_seen("tc1")
        assert state.is_seen("tc1")
        assert not state.is_seen("tc2")

    def test_set_and_get_replacement(self):
        state = ContentReplacementState()
        state.set_replacement("tc1", "replaced content")
        assert state.get_replacement("tc1") == "replaced content"
        assert state.is_replaced("tc1")
        assert not state.is_replaced("tc2")

    def test_get_replacement_not_found(self):
        state = ContentReplacementState()
        assert state.get_replacement("nonexistent") is None


class TestCompactPromptModule:
    def test_get_compact_prompt(self):
        from src.context.compact_prompt import get_compact_prompt
        prompt = get_compact_prompt()
        assert "TEXT ONLY" in prompt
        assert "<analysis>" in prompt
        assert "<summary>" in prompt

    def test_get_compact_prompt_with_custom_instructions(self):
        from src.context.compact_prompt import get_compact_prompt
        prompt = get_compact_prompt(custom_instructions="Focus on code changes")
        assert "Focus on code changes" in prompt

    def test_get_partial_compact_prompt_from(self):
        from src.context.compact_prompt import get_partial_compact_prompt
        prompt = get_partial_compact_prompt(direction="from")
        assert "recent messages" in prompt

    def test_get_partial_compact_prompt_up_to(self):
        from src.context.compact_prompt import get_partial_compact_prompt
        prompt = get_partial_compact_prompt(direction="up_to")
        assert "earlier messages" in prompt

    def test_get_partial_compact_prompt_invalid_direction(self):
        from src.context.compact_prompt import get_partial_compact_prompt
        with pytest.raises(ValueError, match="Invalid direction"):
            get_partial_compact_prompt(direction="invalid")

    def test_format_compact_summary_strips_analysis(self):
        from src.context.compact_prompt import format_compact_summary
        raw = "<analysis>thinking</analysis><summary>actual summary</summary>"
        result = format_compact_summary(raw)
        assert "<analysis>" not in result
        assert "thinking" not in result
        assert "actual summary" in result

    def test_format_compact_summary_adds_prefix(self):
        from src.context.compact_prompt import format_compact_summary
        raw = "Some summary content"
        result = format_compact_summary(raw)
        assert result.startswith("Summary:")

    def test_get_compact_user_summary_message(self):
        from src.context.compact_prompt import get_compact_user_summary_message
        result = get_compact_user_summary_message(
            "Test summary",
            suppress_follow_up_questions=True,
            recent_messages_preserved=True,
        )
        assert "Test summary" in result
        assert "Recent messages are preserved" in result
        assert "without asking any follow-up questions" in result


class TestGroupMessagesByApiRound:
    def test_human_then_ai_creates_two_groups(self):
        compressor = _make_compressor()
        messages = [HumanMessage(content="hi"), AIMessage(content="hello", id="ai1")]
        groups = compressor._group_messages_by_api_round(messages)
        assert len(groups) == 2
        assert isinstance(groups[0][0], HumanMessage)
        assert isinstance(groups[1][0], AIMessage)

    def test_multiple_ai_ids_create_multiple_groups(self):
        compressor = _make_compressor()
        messages = [
            HumanMessage(content="hi"),
            AIMessage(content="hello", id="ai1"),
            HumanMessage(content="how are you"),
            AIMessage(content="fine", id="ai2"),
        ]
        groups = compressor._group_messages_by_api_round(messages)
        assert len(groups) == 3

    def test_empty_messages(self):
        compressor = _make_compressor()
        groups = compressor._group_messages_by_api_round([])
        assert groups == [[]]

    def test_messages_without_ai_id(self):
        compressor = _make_compressor()
        messages = [HumanMessage(content="hi"), AIMessage(content="hello")]
        groups = compressor._group_messages_by_api_round(messages)
        assert len(groups) == 1


class TestTruncateHeadForPtlRetry:
    def test_single_group_returns_unchanged(self):
        compressor = _make_compressor()
        messages = [HumanMessage(content="hi"), AIMessage(content="hello")]
        result = compressor._truncate_head_for_ptl_retry(messages)
        assert result == messages

    def test_multiple_groups_drops_first(self):
        compressor = _make_compressor()
        messages = [
            HumanMessage(content="first"),
            AIMessage(content="resp1", id="ai1"),
            HumanMessage(content="second"),
            AIMessage(content="resp2", id="ai2"),
        ]
        result = compressor._truncate_head_for_ptl_retry(messages)
        assert len(result) < len(messages)
        assert "resp1" in [m.content for m in result]
