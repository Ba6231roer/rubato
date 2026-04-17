import pytest
from datetime import datetime
from unittest.mock import MagicMock

from src.core.query_engine import (
    FileStateCache,
    PermissionDenial,
    AbortController,
    Usage,
    SDKMessage,
)


class TestFileStateCache:
    def test_empty_cache(self):
        cache = FileStateCache()
        assert cache.cache == {}

    def test_set_and_get(self):
        cache = FileStateCache()
        cache.set("/path/to/file", {"content": "hello", "hash": "abc"})
        result = cache.get("/path/to/file")
        assert result is not None
        assert result["content"] == "hello"
        assert result["hash"] == "abc"

    def test_get_nonexistent(self):
        cache = FileStateCache()
        assert cache.get("/nonexistent") is None

    def test_remove(self):
        cache = FileStateCache()
        cache.set("/path/to/file", {"content": "hello"})
        cache.remove("/path/to/file")
        assert cache.get("/path/to/file") is None

    def test_remove_nonexistent_no_error(self):
        cache = FileStateCache()
        cache.remove("/nonexistent")

    def test_clear(self):
        cache = FileStateCache()
        cache.set("/file1", {"a": 1})
        cache.set("/file2", {"b": 2})
        cache.clear()
        assert cache.cache == {}

    def test_has(self):
        cache = FileStateCache()
        cache.set("/file1", {"a": 1})
        assert cache.has("/file1") is True
        assert cache.has("/file2") is False

    def test_overwrite(self):
        cache = FileStateCache()
        cache.set("/file1", {"version": 1})
        cache.set("/file1", {"version": 2})
        assert cache.get("/file1")["version"] == 2


class TestPermissionDenial:
    def test_creation(self):
        denial = PermissionDenial(
            tool_name="shell_tool",
            reason="Permission denied by policy"
        )
        assert denial.tool_name == "shell_tool"
        assert denial.reason == "Permission denied by policy"
        assert isinstance(denial.timestamp, datetime)

    def test_custom_timestamp(self):
        ts = datetime(2025, 1, 1, 12, 0, 0)
        denial = PermissionDenial(
            tool_name="file_write",
            reason="Read-only mode",
            timestamp=ts
        )
        assert denial.timestamp == ts


class TestAbortController:
    def test_initial_state(self):
        controller = AbortController()
        assert controller.is_aborted() is False
        assert controller.get_reason() is None

    def test_abort_without_reason(self):
        controller = AbortController()
        controller.abort()
        assert controller.is_aborted() is True
        assert controller.get_reason() is None

    def test_abort_with_reason(self):
        controller = AbortController()
        controller.abort("User cancelled")
        assert controller.is_aborted() is True
        assert controller.get_reason() == "User cancelled"

    def test_reset(self):
        controller = AbortController()
        controller.abort("reason")
        controller.reset()
        assert controller.is_aborted() is False
        assert controller.get_reason() is None

    def test_abort_multiple_times(self):
        controller = AbortController()
        controller.abort("first")
        controller.abort("second")
        assert controller.get_reason() == "second"


class TestUsage:
    def test_default_values(self):
        usage = Usage()
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_tokens == 0
        assert usage.cost_usd == 0.0

    def test_add(self):
        usage1 = Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150, cost_usd=0.01)
        usage2 = Usage(prompt_tokens=200, completion_tokens=100, total_tokens=300, cost_usd=0.02)
        usage1.add(usage2)
        assert usage1.prompt_tokens == 300
        assert usage1.completion_tokens == 150
        assert usage1.total_tokens == 450
        assert usage1.cost_usd == pytest.approx(0.03)

    def test_add_zero_usage(self):
        usage = Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150, cost_usd=0.01)
        usage.add(Usage())
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50

    def test_add_to_empty(self):
        usage = Usage()
        usage.add(Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150))
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150


class TestSDKMessage:
    def test_assistant_factory(self):
        msg = SDKMessage.assistant("Hello world", session_id="s1")
        assert msg.type == "assistant"
        assert msg.content == "Hello world"
        assert msg.metadata["session_id"] == "s1"

    def test_tool_use_factory(self):
        msg = SDKMessage.tool_use(
            tool_name="shell_tool",
            tool_args={"command": "ls"},
            tool_call_id="call_1",
            turn=1,
        )
        assert msg.type == "tool_use"
        assert msg.content["name"] == "shell_tool"
        assert msg.content["args"] == {"command": "ls"}
        assert msg.content["id"] == "call_1"
        assert msg.metadata["turn"] == 1

    def test_tool_result_factory(self):
        msg = SDKMessage.tool_result(
            tool_name="shell_tool",
            result="file1.txt\nfile2.txt",
            tool_call_id="call_1",
            status="success",
        )
        assert msg.type == "tool_result"
        assert msg.content["name"] == "shell_tool"
        assert msg.content["result"] == "file1.txt\nfile2.txt"
        assert msg.content["id"] == "call_1"
        assert msg.metadata["status"] == "success"

    def test_error_factory(self):
        msg = SDKMessage.error(
            message="Something went wrong",
            error_type="timeout",
        )
        assert msg.type == "error"
        assert msg.content["message"] == "Something went wrong"
        assert msg.content["error_type"] == "timeout"

    def test_interrupt_factory(self):
        msg = SDKMessage.interrupt(reason="User cancelled")
        assert msg.type == "interrupt"
        assert msg.content["reason"] == "User cancelled"

    def test_interrupt_factory_no_reason(self):
        msg = SDKMessage.interrupt()
        assert msg.type == "interrupt"
        assert msg.content["reason"] is None

    def test_result_factory(self):
        msg = SDKMessage.result(result="Task completed")
        assert msg.type == "result"
        assert msg.content == "Task completed"

    def test_result_factory_with_metadata(self):
        msg = SDKMessage.result(
            result="Done",
            session_id="s1",
            total_turns=5,
        )
        assert msg.metadata["session_id"] == "s1"
        assert msg.metadata["total_turns"] == 5

    def test_direct_construction(self):
        msg = SDKMessage(type="custom", content="data", metadata={"key": "val"})
        assert msg.type == "custom"
        assert msg.content == "data"
        assert msg.metadata == {"key": "val"}

    def test_default_metadata(self):
        msg = SDKMessage(type="test", content="data")
        assert msg.metadata == {}
