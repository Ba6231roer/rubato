import os
import tempfile
from unittest.mock import MagicMock

import pytest

from src.context.task_intent_manager import TaskIntentManager, TASK_INTENT_FILENAME


class TestExtractTaskIntentFullMode:

    def test_short_message_stored_as_full(self):
        manager = TaskIntentManager()
        msg = "Hello, this is a short task"
        manager.extract_task_intent(msg)

        assert manager.has_task_intent() is True
        assert manager._mode == "full"
        assert manager._full_content == msg
        assert manager._preview is None
        assert manager._file_path is None

    def test_message_at_threshold_stored_as_full(self):
        manager = TaskIntentManager(full_threshold=100)
        msg = "a" * 100
        manager.extract_task_intent(msg)

        assert manager._mode == "full"

    def test_no_session_dir_full_mode(self):
        manager = TaskIntentManager(session_dir="")
        msg = "short message"
        manager.extract_task_intent(msg)

        assert manager._mode == "full"
        assert manager._file_path is None


class TestExtractTaskIntentPersistedMode:

    def test_long_message_stored_as_persisted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = TaskIntentManager(session_dir=tmpdir, full_threshold=100)
            msg = "a" * 200
            manager.extract_task_intent(msg)

            assert manager._mode == "persisted"
            assert manager._full_content == msg
            assert manager._preview == msg[:100]
            assert manager._file_path == os.path.join(tmpdir, TASK_INTENT_FILENAME)

            assert os.path.exists(manager._file_path)
            with open(manager._file_path, "r", encoding="utf-8") as f:
                assert f.read() == msg

    def test_message_just_above_threshold(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = TaskIntentManager(session_dir=tmpdir, full_threshold=100)
            msg = "a" * 101
            manager.extract_task_intent(msg)

            assert manager._mode == "persisted"

    def test_no_session_dir_persisted_mode_no_file(self):
        manager = TaskIntentManager(session_dir="", full_threshold=100)
        msg = "a" * 200
        manager.extract_task_intent(msg)

        assert manager._mode == "persisted"
        assert manager._file_path is None


class TestSubsequentExtractionNoOverwrite:

    def test_second_extract_does_not_overwrite(self):
        manager = TaskIntentManager()
        first_msg = "First task intent"
        second_msg = "Second task intent that should be ignored"

        manager.extract_task_intent(first_msg)
        manager.extract_task_intent(second_msg)

        assert manager._full_content == first_msg
        assert manager._mode == "full"


class TestBuildRecoveryMessageFullMode:

    def test_returns_human_message_with_full_content(self):
        manager = TaskIntentManager()
        msg = "Do something important"
        manager.extract_task_intent(msg)

        result = manager.build_recovery_message()

        assert result is not None
        assert isinstance(result, MagicMock) or result.__class__.__name__ == "HumanMessage"
        assert "[Task Intent - PRESERVED]" in result.content
        assert msg in result.content

    def test_content_format_full_mode(self):
        manager = TaskIntentManager()
        msg = "My task description"
        manager.extract_task_intent(msg)

        result = manager.build_recovery_message()

        expected = f"[Task Intent - PRESERVED]\n{msg}"
        assert result.content == expected


class TestBuildRecoveryMessagePersistedMode:

    def test_returns_human_message_with_preview(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = TaskIntentManager(session_dir=tmpdir, full_threshold=50)
            msg = "a" * 100
            manager.extract_task_intent(msg)

            result = manager.build_recovery_message()

            assert result is not None
            assert "[Task Intent - PRESERVED]" in result.content
            assert manager._preview in result.content
            assert "..." in result.content
            assert f"[Full task specification persisted to: {manager._file_path}]" in result.content

    def test_content_format_persisted_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = TaskIntentManager(session_dir=tmpdir, full_threshold=50)
            msg = "a" * 100
            manager.extract_task_intent(msg)

            result = manager.build_recovery_message()

            expected_preview = msg[:50]
            expected = (
                f"[Task Intent - PRESERVED]\n"
                f"{expected_preview}\n"
                f"...\n"
                f"[Full task specification persisted to: {manager._file_path}]"
            )
            assert result.content == expected


class TestBuildRecoveryMessageNoIntent:

    def test_returns_none_when_no_intent(self):
        manager = TaskIntentManager()
        result = manager.build_recovery_message()
        assert result is None

    def test_returns_none_after_clear(self):
        manager = TaskIntentManager()
        manager.extract_task_intent("some task")
        manager.clear()
        result = manager.build_recovery_message()
        assert result is None


class TestTokenBudgetTruncation:

    def test_truncation_when_tokens_exceed_budget(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = TaskIntentManager(
                session_dir=tmpdir,
                full_threshold=100,
                token_budget=20,
            )
            msg = "a" * 200
            manager.extract_task_intent(msg)

            compressor = MagicMock()
            call_count = [0]

            def mock_count_tokens(text):
                call_count[0] += 1
                return len(text) // 4 + 1

            compressor.count_text_tokens = mock_count_tokens

            result = manager.build_recovery_message(compressor=compressor)

            assert result is not None
            assert "[Task intent truncated, full content at:" in result.content
            assert manager._file_path in result.content

    def test_no_truncation_when_within_budget(self):
        manager = TaskIntentManager(token_budget=10000)
        msg = "Short task"
        manager.extract_task_intent(msg)

        compressor = MagicMock()
        compressor.count_text_tokens.return_value = 5

        result = manager.build_recovery_message(compressor=compressor)

        assert "[Task intent truncated" not in result.content

    def test_full_mode_persists_file_on_truncation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = TaskIntentManager(
                session_dir=tmpdir,
                full_threshold=10000,
                token_budget=10,
            )
            msg = "This is a task that is long enough to exceed the very small token budget"
            manager.extract_task_intent(msg)

            assert manager._mode == "full"
            assert manager._file_path is None

            compressor = MagicMock()

            def mock_count_tokens(text):
                return len(text) // 2

            compressor.count_text_tokens = mock_count_tokens

            result = manager.build_recovery_message(compressor=compressor)

            assert manager._file_path is not None
            assert os.path.exists(manager._file_path)
            with open(manager._file_path, "r", encoding="utf-8") as f:
                assert f.read() == msg
            assert "[Task intent truncated, full content at:" in result.content


class TestHasTaskIntent:

    def test_false_initially(self):
        manager = TaskIntentManager()
        assert manager.has_task_intent() is False

    def test_true_after_extraction(self):
        manager = TaskIntentManager()
        manager.extract_task_intent("task")
        assert manager.has_task_intent() is True

    def test_false_after_clear(self):
        manager = TaskIntentManager()
        manager.extract_task_intent("task")
        manager.clear()
        assert manager.has_task_intent() is False


class TestClear:

    def test_clear_resets_all_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = TaskIntentManager(session_dir=tmpdir, full_threshold=50)
            msg = "a" * 100
            manager.extract_task_intent(msg)

            assert manager.has_task_intent() is True

            manager.clear()

            assert manager._mode is None
            assert manager._full_content is None
            assert manager._preview is None
            assert manager._file_path is None
            assert manager.has_task_intent() is False

    def test_can_extract_again_after_clear(self):
        manager = TaskIntentManager()
        manager.extract_task_intent("first task")
        manager.clear()

        manager.extract_task_intent("second task")
        assert manager._full_content == "second task"
        assert manager.has_task_intent() is True
