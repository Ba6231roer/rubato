import os

import pytest
from unittest.mock import MagicMock

from langchain_core.messages import HumanMessage

from src.context.task_intent_manager import TaskIntentManager, TASK_INTENT_FILENAME


class TestExtractTaskIntent:
    def test_short_message_full_mode(self):
        manager = TaskIntentManager(full_threshold=2000)
        manager.extract_task_intent("Build a test framework")
        assert manager._mode == "full"
        assert manager._full_content == "Build a test framework"
        assert manager._preview is None
        assert manager._file_path is None

    def test_long_message_persisted_mode(self, tmp_path):
        manager = TaskIntentManager(session_dir=str(tmp_path), full_threshold=100)
        long_msg = "A" * 200
        manager.extract_task_intent(long_msg)
        assert manager._mode == "persisted"
        assert manager._full_content == long_msg
        assert manager._preview == long_msg[:100]
        assert manager._file_path is not None
        assert os.path.exists(manager._file_path)
        with open(manager._file_path, "r", encoding="utf-8") as f:
            assert f.read() == long_msg

    def test_extract_only_once(self):
        manager = TaskIntentManager(full_threshold=2000)
        manager.extract_task_intent("First intent")
        manager.extract_task_intent("Second intent")
        assert manager._full_content == "First intent"

    def test_long_message_without_session_dir(self):
        manager = TaskIntentManager(session_dir="", full_threshold=100)
        long_msg = "A" * 200
        manager.extract_task_intent(long_msg)
        assert manager._mode == "persisted"
        assert manager._file_path is None

    def test_exactly_at_threshold(self):
        manager = TaskIntentManager(full_threshold=10)
        msg = "A" * 10
        manager.extract_task_intent(msg)
        assert manager._mode == "full"

    def test_one_over_threshold(self, tmp_path):
        manager = TaskIntentManager(session_dir=str(tmp_path), full_threshold=10)
        msg = "A" * 11
        manager.extract_task_intent(msg)
        assert manager._mode == "persisted"


class TestBuildRecoveryMessage:
    def test_no_intent_returns_none(self):
        manager = TaskIntentManager()
        result = manager.build_recovery_message()
        assert result is None

    def test_full_mode_recovery(self):
        manager = TaskIntentManager(full_threshold=2000)
        manager.extract_task_intent("Build a test framework")
        result = manager.build_recovery_message()
        assert isinstance(result, HumanMessage)
        assert "[Task Intent - PRESERVED]" in result.content
        assert "Build a test framework" in result.content

    def test_persisted_mode_recovery(self, tmp_path):
        manager = TaskIntentManager(session_dir=str(tmp_path), full_threshold=100)
        long_msg = "A" * 200
        manager.extract_task_intent(long_msg)
        result = manager.build_recovery_message()
        assert isinstance(result, HumanMessage)
        assert "[Task Intent - PRESERVED]" in result.content
        assert "Full task specification persisted to:" in result.content
        assert manager._file_path in result.content

    def test_recovery_with_compressor_within_budget(self):
        manager = TaskIntentManager(full_threshold=2000, token_budget=10000)
        manager.extract_task_intent("Short task")
        mock_compressor = MagicMock()
        mock_compressor.count_text_tokens.side_effect = lambda text: len(text) // 4
        result = manager.build_recovery_message(compressor=mock_compressor)
        assert "[Task Intent - PRESERVED]" in result.content
        assert "Short task" in result.content

    def test_recovery_with_compressor_exceeds_budget(self, tmp_path):
        manager = TaskIntentManager(
            session_dir=str(tmp_path),
            full_threshold=2000,
            token_budget=20,
        )
        long_msg = "Build a comprehensive test framework with many features " * 20
        manager.extract_task_intent(long_msg)
        mock_compressor = MagicMock()
        mock_compressor.count_text_tokens.side_effect = lambda text: len(text) // 2
        result = manager.build_recovery_message(compressor=mock_compressor)
        assert "[Task Intent - PRESERVED]" in result.content
        assert "truncated" in result.content.lower() or "persisted" in result.content.lower()

    def test_recovery_truncation_creates_file_for_full_mode(self, tmp_path):
        manager = TaskIntentManager(
            session_dir=str(tmp_path),
            full_threshold=2000,
            token_budget=20,
        )
        long_msg = "Build a comprehensive test framework with many features " * 20
        manager.extract_task_intent(long_msg)
        assert manager._mode == "full"
        assert manager._file_path is None
        mock_compressor = MagicMock()
        mock_compressor.count_text_tokens.side_effect = lambda text: len(text) // 2
        result = manager.build_recovery_message(compressor=mock_compressor)
        assert manager._file_path is not None
        assert os.path.exists(manager._file_path)

    def test_recovery_with_zero_budget(self, tmp_path):
        manager = TaskIntentManager(
            session_dir=str(tmp_path),
            full_threshold=2000,
            token_budget=0,
        )
        manager.extract_task_intent("Some task description")
        mock_compressor = MagicMock()
        mock_compressor.count_text_tokens.side_effect = lambda text: len(text)
        result = manager.build_recovery_message(compressor=mock_compressor)
        assert result is not None
        assert "[Task Intent - PRESERVED]" in result.content


class TestTruncateToTokenBudget:
    def test_within_budget(self):
        manager = TaskIntentManager()
        mock_compressor = MagicMock()
        mock_compressor.count_text_tokens.return_value = 5
        result = manager._truncate_to_token_budget("hello world", mock_compressor, 10)
        assert result == "hello world"

    def test_exceeds_budget(self):
        manager = TaskIntentManager()
        mock_compressor = MagicMock()

        def count_tokens(text):
            return len(text) // 4

        mock_compressor.count_text_tokens.side_effect = count_tokens
        result = manager._truncate_to_token_budget("A" * 100, mock_compressor, 10)
        assert len(result) < 100

    def test_zero_budget(self):
        manager = TaskIntentManager()
        mock_compressor = MagicMock()
        result = manager._truncate_to_token_budget("hello", mock_compressor, 0)
        assert result == ""

    def test_negative_budget(self):
        manager = TaskIntentManager()
        mock_compressor = MagicMock()
        result = manager._truncate_to_token_budget("hello", mock_compressor, -1)
        assert result == ""


class TestHasTaskIntent:
    def test_no_intent(self):
        manager = TaskIntentManager()
        assert not manager.has_task_intent()

    def test_after_extract(self):
        manager = TaskIntentManager()
        manager.extract_task_intent("Do something")
        assert manager.has_task_intent()

    def test_after_clear(self):
        manager = TaskIntentManager()
        manager.extract_task_intent("Do something")
        manager.clear()
        assert not manager.has_task_intent()


class TestClear:
    def test_clear_resets_all_state(self, tmp_path):
        manager = TaskIntentManager(session_dir=str(tmp_path), full_threshold=100)
        long_msg = "A" * 200
        manager.extract_task_intent(long_msg)
        assert manager.has_task_intent()
        manager.clear()
        assert manager._mode is None
        assert manager._full_content is None
        assert manager._preview is None
        assert manager._file_path is None
        assert not manager.has_task_intent()

    def test_clear_when_no_intent(self):
        manager = TaskIntentManager()
        manager.clear()
        assert not manager.has_task_intent()

    def test_re_extract_after_clear(self):
        manager = TaskIntentManager(full_threshold=2000)
        manager.extract_task_intent("First task")
        manager.clear()
        manager.extract_task_intent("Second task")
        assert manager._full_content == "Second task"
        assert manager._mode == "full"


class TestPersistedFilePath:
    def test_file_path_uses_session_dir(self, tmp_path):
        manager = TaskIntentManager(session_dir=str(tmp_path), full_threshold=100)
        manager.extract_task_intent("A" * 200)
        expected_path = os.path.join(str(tmp_path), TASK_INTENT_FILENAME)
        assert manager._file_path == expected_path

    def test_file_content_matches(self, tmp_path):
        manager = TaskIntentManager(session_dir=str(tmp_path), full_threshold=100)
        content = "Detailed task specification " * 10
        manager.extract_task_intent(content)
        with open(manager._file_path, "r", encoding="utf-8") as f:
            assert f.read() == content

    def test_session_dir_created_if_missing(self, tmp_path):
        new_dir = os.path.join(str(tmp_path), "subdir", "nested")
        manager = TaskIntentManager(session_dir=new_dir, full_threshold=100)
        manager.extract_task_intent("A" * 200)
        assert os.path.isdir(new_dir)


class TestLargeInputTokenThreshold:
    def test_large_input_forces_persisted_mode(self, tmp_path):
        manager = TaskIntentManager(
            session_dir=str(tmp_path),
            full_threshold=100000,
            large_input_token_threshold=10,
        )
        msg = "A" * 500
        manager.extract_task_intent(msg)
        assert manager._mode == "persisted"
        assert manager._preview == msg[:100000]
        assert manager._file_path is not None
        assert os.path.exists(manager._file_path)
        with open(manager._file_path, "r", encoding="utf-8") as f:
            assert f.read() == msg

    def test_below_token_threshold_stays_full_mode(self):
        manager = TaskIntentManager(
            full_threshold=100000,
            large_input_token_threshold=10000,
        )
        msg = "A" * 500
        manager.extract_task_intent(msg)
        assert manager._mode == "full"
        assert manager._token_count < 10000

    def test_token_count_recorded(self):
        manager = TaskIntentManager()
        msg = "Hello world"
        manager.extract_task_intent(msg)
        assert manager._token_count > 0

    def test_recovery_message_for_large_input(self, tmp_path):
        manager = TaskIntentManager(
            session_dir=str(tmp_path),
            full_threshold=50,
            large_input_token_threshold=10,
        )
        msg = "A" * 500
        manager.extract_task_intent(msg)
        result = manager.build_recovery_message()
        assert isinstance(result, HumanMessage)
        assert "[Task Intent - PRESERVED]" in result.content
        assert "Full task specification persisted to:" in result.content
        assert manager._file_path in result.content
        assert "A" * 500 not in result.content

    def test_recovery_message_for_large_input_persists_if_not_yet(self, tmp_path):
        manager = TaskIntentManager(
            session_dir=str(tmp_path),
            full_threshold=100000,
            large_input_token_threshold=10,
        )
        msg = "A" * 500
        manager.extract_task_intent(msg)
        manager._file_path = None
        result = manager.build_recovery_message()
        assert manager._file_path is not None
        assert os.path.exists(manager._file_path)
        with open(manager._file_path, "r", encoding="utf-8") as f:
            assert f.read() == msg

    def test_large_input_recovery_skips_compressor_path(self, tmp_path):
        manager = TaskIntentManager(
            session_dir=str(tmp_path),
            full_threshold=100000,
            large_input_token_threshold=10,
            token_budget=5,
        )
        msg = "A" * 500
        manager.extract_task_intent(msg)
        mock_compressor = MagicMock()
        mock_compressor.count_text_tokens.side_effect = lambda text: len(text) // 4
        result = manager.build_recovery_message(compressor=mock_compressor)
        assert "[Task Intent - PRESERVED]" in result.content
        assert "Full task specification persisted to:" in result.content
        mock_compressor.count_text_tokens.assert_not_called()

    def test_clear_resets_token_count(self, tmp_path):
        manager = TaskIntentManager(
            session_dir=str(tmp_path),
            large_input_token_threshold=10,
        )
        manager.extract_task_intent("A" * 500)
        assert manager._token_count > 0
        manager.clear()
        assert manager._token_count == 0
