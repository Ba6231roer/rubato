import json
import logging
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from src.utils.logger import (
    LLMLogger,
    LLMRequestCallbackHandler,
    _role_context,
    get_llm_logger,
    _llm_logger as _global_logger_ref,
)


@pytest.fixture(autouse=True)
def reset_global_logger():
    import src.utils.logger as mod
    original = mod._llm_logger
    mod._llm_logger = None
    yield
    mod._llm_logger = original


@pytest.fixture
def logger(tmp_path):
    return LLMLogger(log_dir=str(tmp_path / "test_logs"))


@pytest.fixture
def logger_detailed(tmp_path):
    return LLMLogger(log_dir=str(tmp_path / "test_logs"), log_format="detailed")


class TestLLMLoggerInit:
    def test_creates_log_directory(self, tmp_path):
        log_dir = tmp_path / "new_logs"
        LLMLogger(log_dir=str(log_dir))
        assert log_dir.exists()

    def test_creates_nested_log_directory(self, tmp_path):
        log_dir = tmp_path / "a" / "b" / "c"
        LLMLogger(log_dir=str(log_dir))
        assert log_dir.exists()

    def test_three_loggers_created(self, logger):
        assert logger.llm_logger is not None
        assert logger.tool_logger is not None
        assert logger.agent_logger is not None

    def test_logger_names(self, logger):
        assert logger.llm_logger.name == "llm"
        assert logger.tool_logger.name == "tool"
        assert logger.agent_logger.name == "agent"

    def test_log_files_created(self, tmp_path):
        log_dir = tmp_path / "file_logs"
        lg = LLMLogger(log_dir=str(log_dir))
        lg.llm_logger.info("init")
        lg.tool_logger.info("init")
        lg.agent_logger.info("init")
        assert (log_dir / "llm.log").exists()
        assert (log_dir / "tool.log").exists()
        assert (log_dir / "agent.log").exists()

    def test_default_settings(self, logger):
        assert logger.tool_log_mode == "summary"
        assert logger.log_format == "compact"


class TestDualFormatOutput:
    def test_log_request_compact(self, logger):
        with patch.object(logger.llm_logger, "info") as mock_info:
            logger.log_request([], "gpt-4")
            msg = mock_info.call_args[0][0]
            assert "REQUEST" in msg
            assert "gpt-4" in msg
            assert "\n" in msg

    def test_log_request_detailed(self, logger_detailed):
        with patch.object(logger_detailed.llm_logger, "info") as mock_info:
            logger_detailed.log_request([], "gpt-4")
            msg = mock_info.call_args[0][0]
            assert "REQUEST" in msg
            parsed = json.loads(msg.split("REQUEST: ", 1)[1])
            assert parsed["type"] == "request"
            assert parsed["model"] == "gpt-4"

    def test_log_response_compact(self, logger):
        resp = MagicMock()
        resp.content = "hello"
        resp.tool_calls = None
        with patch.object(logger.llm_logger, "info") as mock_info:
            logger.log_response(resp, "gpt-4")
            msg = mock_info.call_args[0][0]
            assert "RESPONSE" in msg
            assert "hello" in msg

    def test_log_response_detailed(self, logger_detailed):
        resp = MagicMock()
        resp.content = "hello"
        resp.tool_calls = None
        with patch.object(logger_detailed.llm_logger, "info") as mock_info:
            logger_detailed.log_response(resp, "gpt-4")
            msg = mock_info.call_args[0][0]
            parsed = json.loads(msg.split("RESPONSE: ", 1)[1])
            assert parsed["type"] == "response"

    def test_log_tool_call_compact(self, logger):
        with patch.object(logger.tool_logger, "info") as mock_info:
            logger.log_tool_call("shell_tool", {"cmd": "ls"})
            msg = mock_info.call_args[0][0]
            assert "TOOL_CALL" in msg
            assert "shell_tool" in msg

    def test_log_tool_call_detailed(self, logger_detailed):
        with patch.object(logger_detailed.tool_logger, "info") as mock_info:
            logger_detailed.log_tool_call("shell_tool", {"cmd": "ls"})
            msg = mock_info.call_args[0][0]
            parsed = json.loads(msg.split("TOOL_CALL: ", 1)[1])
            assert parsed["type"] == "tool_call"
            assert parsed["tool"] == "shell_tool"

    def test_log_tool_result_compact(self, logger):
        with patch.object(logger.tool_logger, "info") as mock_info:
            logger.log_tool_result("shell_tool", "output")
            msg = mock_info.call_args[0][0]
            assert "TOOL_RESULT" in msg
            assert "shell_tool" in msg

    def test_log_tool_result_detailed(self, logger_detailed):
        with patch.object(logger_detailed.tool_logger, "info") as mock_info:
            logger_detailed.log_tool_result("shell_tool", "output")
            msg = mock_info.call_args[0][0]
            parsed = json.loads(msg.split("TOOL_RESULT: ", 1)[1])
            assert parsed["type"] == "tool_result"

    def test_log_agent_action_compact(self, logger):
        with patch.object(logger.agent_logger, "info") as mock_info:
            logger.log_agent_action("start", {"task": "run"})
            msg = mock_info.call_args[0][0]
            assert "ACTION" in msg
            assert "start" in msg

    def test_log_agent_action_detailed(self, logger_detailed):
        with patch.object(logger_detailed.agent_logger, "info") as mock_info:
            logger_detailed.log_agent_action("start", {"task": "run"})
            msg = mock_info.call_args[0][0]
            parsed = json.loads(msg.split("ACTION: ", 1)[1])
            assert parsed["action"] == "start"

    def test_log_error_compact(self, logger):
        with patch.object(logger.agent_logger, "error") as mock_error:
            logger.log_error("test_source", ValueError("bad"))
            msg = mock_error.call_args[0][0]
            assert "ERROR" in msg
            assert "ValueError" in msg

    def test_log_error_detailed(self, logger_detailed):
        with patch.object(logger_detailed.agent_logger, "error") as mock_error:
            logger_detailed.log_error("test_source", ValueError("bad"))
            msg = mock_error.call_args[0][0]
            parsed = json.loads(msg.split("ERROR: ", 1)[1])
            assert parsed["error_type"] == "ValueError"

    def test_set_log_format_switches_output(self, logger):
        logger.set_log_format("detailed")
        with patch.object(logger.llm_logger, "info") as mock_info:
            logger.log_request([], "gpt-4")
            msg = mock_info.call_args[0][0]
            assert "type" in msg
            assert "request" in msg

    def test_set_tool_log_mode(self, logger):
        logger.set_tool_log_mode("detailed")
        assert logger.tool_log_mode == "detailed"


class TestRoleContext:
    def test_set_role_context_role_only(self, logger):
        logger.set_role_context("executor")
        assert logger.get_role_prefix() == "[role: executor]"

    def test_set_role_context_with_parent(self, logger):
        logger.set_role_context("case-executor", parent_role="suite-executor")
        assert logger.get_role_prefix() == "[role: case-executor, parent: suite-executor]"

    def test_clear_role_context(self, logger):
        logger.set_role_context("executor")
        logger.clear_role_context()
        assert logger.get_role_prefix() == ""

    def test_get_role_prefix_empty(self, logger):
        logger.clear_role_context()
        assert logger.get_role_prefix() == ""

    def test_role_prefix_in_log_request(self, logger):
        logger.set_role_context("executor")
        with patch.object(logger.llm_logger, "info") as mock_info:
            logger.log_request([], "gpt-4")
            msg = mock_info.call_args[0][0]
            assert "[role: executor]" in msg

    def test_role_prefix_with_parent_in_log(self, logger):
        logger.set_role_context("case-executor", parent_role="suite-executor")
        with patch.object(logger.llm_logger, "info") as mock_info:
            logger.log_request([], "gpt-4")
            msg = mock_info.call_args[0][0]
            assert "[role: case-executor, parent: suite-executor]" in msg

    @pytest.mark.asyncio
    async def test_contextvar_async_isolation(self, logger):
        results = {}

        async def task_a():
            logger.set_role_context("role-a")
            await asyncio.sleep(0.05)
            results["a"] = logger.get_role_prefix()

        async def task_b():
            logger.set_role_context("role-b", parent_role="parent-b")
            await asyncio.sleep(0.05)
            results["b"] = logger.get_role_prefix()

        await asyncio.gather(task_a(), task_b())
        assert results["a"] == "[role: role-a]"
        assert results["b"] == "[role: role-b, parent: parent-b]"


class TestExtractToolName:
    def test_openai_dict_format(self):
        tool = {"function": {"name": "shell_tool"}, "type": "function"}
        assert LLMLogger._extract_tool_name(tool) == "shell_tool"

    def test_openai_dict_missing_name(self):
        tool = {"function": {}}
        assert LLMLogger._extract_tool_name(tool) == "unknown"

    def test_plain_dict_with_name(self):
        tool = {"name": "my_tool"}
        assert LLMLogger._extract_tool_name(tool) == "my_tool"

    def test_plain_dict_without_name(self):
        tool = {"key": "value"}
        assert LLMLogger._extract_tool_name(tool) == "unknown"

    def test_object_with_name_attr(self):
        obj = MagicMock()
        obj.name = "obj_tool"
        assert LLMLogger._extract_tool_name(obj) == "obj_tool"

    def test_string_tool(self):
        assert LLMLogger._extract_tool_name("some_tool_name") == "some_tool_name"

    def test_integer_tool(self):
        assert LLMLogger._extract_tool_name(42) == "42"

    def test_function_dict_non_dict_value(self):
        tool = {"function": "not_a_dict"}
        assert LLMLogger._extract_tool_name(tool) == "unknown"


class TestCallbackHandler:
    def test_on_llm_start_calls_log_request_raw(self):
        real_logger = LLMLogger(log_dir=str(Path(__file__).parent / "_cb_test0"))
        handler = LLMRequestCallbackHandler(real_logger)

        with patch.object(real_logger, "log_request_raw") as mock_raw:
            handler.on_llm_start(
                serialized={},
                prompts=[],
                invocation_params={"model": "gpt-4", "temperature": 0.7},
                messages=[],
            )
            mock_raw.assert_called_once()
            call_args = mock_raw.call_args
            request_body = call_args[0][0]
            assert request_body["model"] == "gpt-4"
            assert request_body["temperature"] == 0.7

    def test_on_llm_start_with_messages(self):
        real_logger = LLMLogger(log_dir=str(Path(__file__).parent / "_cb_test1"))
        handler = LLMRequestCallbackHandler(real_logger)

        msg = MagicMock()
        msg.type = "human"
        msg.content = "hello"
        msg.tool_calls = []
        del msg.tool_call_id

        with patch.object(real_logger, "log_request_raw") as mock_raw:
            handler.on_llm_start(
                serialized={},
                prompts=[],
                invocation_params={"model": "gpt-4"},
                messages=[msg],
            )
            mock_raw.assert_called_once()

    def test_on_llm_start_with_prompts_fallback(self):
        real_logger = LLMLogger(log_dir=str(Path(__file__).parent / "_cb_test3"))
        handler = LLMRequestCallbackHandler(real_logger)

        with patch.object(real_logger, "log_request_raw") as mock_raw:
            handler.on_llm_start(
                serialized={},
                prompts=["test prompt"],
            )
            mock_raw.assert_called_once()
            call_args = mock_raw.call_args
            request_body = call_args[0][0]
            assert request_body["messages"] == ["test prompt"]

    def test_format_messages_with_type(self):
        real_logger = LLMLogger(log_dir=str(Path(__file__).parent / "_cb_test2"))
        handler = LLMRequestCallbackHandler(real_logger)

        msg = MagicMock()
        msg.type = "human"
        msg.content = "hello"
        msg.tool_calls = [{"name": "tc1", "args": {}}]
        msg.tool_call_id = "call_123"

        result = handler._format_messages([msg])
        assert len(result) == 1
        assert result[0]["role"] == "human"
        assert result[0]["tool_calls"] == [{"name": "tc1", "args": {}}]
        assert result[0]["tool_call_id"] == "call_123"

    def test_format_messages_without_type(self):
        logger = MagicMock(spec=LLMLogger)
        logger._truncate = LLMLogger._truncate
        logger._get_content = LLMLogger._get_content
        handler = LLMRequestCallbackHandler(logger)

        result = handler._format_messages(["plain string message"])
        assert result == ["plain string message"]


class TestGetLlmLogger:
    def test_singleton_returns_same_instance(self, tmp_path):
        import src.utils.logger as mod
        mod._llm_logger = None
        logger1 = get_llm_logger(log_dir=str(tmp_path / "logs1"))
        logger2 = get_llm_logger(log_dir=str(tmp_path / "logs2"))
        assert logger1 is logger2

    def test_creates_instance_on_first_call(self, tmp_path):
        import src.utils.logger as mod
        mod._llm_logger = None
        logger = get_llm_logger(log_dir=str(tmp_path / "logs"))
        assert isinstance(logger, LLMLogger)


class TestLogMethods:
    def test_log_request_with_messages(self, logger):
        msg = MagicMock()
        msg.type = "human"
        msg.content = "test message"

        with patch.object(logger.llm_logger, "info") as mock_info:
            logger.log_request([msg], "gpt-4", extra_key="extra_val")
            mock_info.assert_called_once()
            call_msg = mock_info.call_args[0][0]
            assert "REQUEST" in call_msg
            assert "gpt-4" in call_msg

    def test_log_request_detailed_with_messages(self, logger_detailed):
        msg = MagicMock()
        msg.type = "human"
        msg.content = "test message"
        msg.tool_calls = None
        del msg.tool_call_id

        with patch.object(logger_detailed.llm_logger, "info") as mock_info:
            logger_detailed.log_request([msg], "gpt-4")
            mock_info.assert_called_once()

    def test_log_response_with_tool_calls(self, logger):
        resp = MagicMock()
        resp.content = "using tool"
        resp.tool_calls = [{"name": "shell_tool", "args": {"cmd": "ls"}}]

        with patch.object(logger.llm_logger, "info") as mock_info:
            logger.log_response(resp, "gpt-4")
            msg = mock_info.call_args[0][0]
            assert "shell_tool" in msg

    def test_log_response_without_content(self, logger):
        resp = "raw string response"
        with patch.object(logger.llm_logger, "info") as mock_info:
            logger.log_response(resp, "gpt-4")
            mock_info.assert_called_once()

    def test_log_tool_call_no_args(self, logger):
        with patch.object(logger.tool_logger, "info") as mock_info:
            logger.log_tool_call("shell_tool", {})
            msg = mock_info.call_args[0][0]
            assert "shell_tool" in msg

    def test_log_tool_result_with_error(self, logger):
        with patch.object(logger.tool_logger, "info") as mock_info:
            logger.log_tool_result("shell_tool", None, error="permission denied")
            msg = mock_info.call_args[0][0]
            assert "permission denied" in msg

    def test_log_tool_result_detailed_with_error(self, logger_detailed):
        logger_detailed.clear_role_context()
        with patch.object(logger_detailed.tool_logger, "info") as mock_info:
            logger_detailed.log_tool_result("shell_tool", None, error="denied")
            msg = mock_info.call_args[0][0]
            parsed = json.loads(msg.split("TOOL_RESULT: ", 1)[1])
            assert parsed["error"] == "denied"

    def test_log_agent_thinking(self, logger):
        with patch.object(logger.agent_logger, "info") as mock_info:
            logger.log_agent_thinking("I should check the files")
            mock_info.assert_called_once()
            msg = mock_info.call_args[0][0]
            assert "THINKING" in msg
            assert "I should check the files" in msg

    def test_log_agent_action_no_details(self, logger):
        with patch.object(logger.agent_logger, "info") as mock_info:
            logger.log_agent_action("start")
            msg = mock_info.call_args[0][0]
            assert "ACTION" in msg
            assert "start" in msg

    def test_log_error(self, logger):
        with patch.object(logger.agent_logger, "error") as mock_error:
            logger.log_error("llm_call", RuntimeError("timeout"))
            msg = mock_error.call_args[0][0]
            assert "ERROR" in msg
            assert "RuntimeError" in msg
            assert "timeout" in msg

    def test_log_request_raw_compact(self, logger):
        body = {"model": "gpt-4", "temperature": 0.5, "messages": ["a", "b"]}
        with patch.object(logger.llm_logger, "debug") as mock_debug:
            logger.log_request_raw(body, "gpt-4")
            msg = mock_debug.call_args[0][0]
            assert "REQUEST_RAW" in msg
            assert "gpt-4" in msg

    def test_log_request_raw_detailed(self, logger_detailed):
        body = {"model": "gpt-4", "temperature": 0.5}
        with patch.object(logger_detailed.llm_logger, "debug") as mock_debug:
            logger_detailed.log_request_raw(body, "gpt-4")
            msg = mock_debug.call_args[0][0]
            assert "REQUEST_RAW" in msg

    def test_log_request_raw_compact_with_tools_summary(self, logger):
        tools = [
            {"function": {"name": "shell_tool"}, "type": "function"},
            {"function": {"name": "file_read"}, "type": "function"},
        ]
        body = {"model": "gpt-4", "tools": tools}
        with patch.object(logger.llm_logger, "debug") as mock_debug:
            logger.log_request_raw(body, "gpt-4")
            msg = mock_debug.call_args[0][0]
            assert "工具加载完成" in msg

    def test_log_request_raw_compact_with_tools_detailed_mode(self, tmp_path):
        lg = LLMLogger(log_dir=str(tmp_path / "logs"), tool_log_mode="detailed")
        tools = [
            {"function": {"name": "shell_tool"}, "type": "function"},
        ]
        body = {"model": "gpt-4", "tools": tools}
        with patch.object(lg.llm_logger, "debug") as mock_debug:
            lg.log_request_raw(body, "gpt-4")
            msg = mock_debug.call_args[0][0]
            assert "shell_tool" in msg


class TestFormatCompact:
    def test_simple_key_value(self, logger):
        result = logger._format_compact({"key": "value"})
        assert 'key: "value"' in result

    def test_nested_dict(self, logger):
        result = logger._format_compact({"outer": {"inner": "val"}})
        assert "outer:" in result
        assert "inner=" in result
        assert '"val"' in result

    def test_simple_dict_inline(self, logger):
        result = logger._format_compact({"meta": {"a": 1, "b": 2}})
        assert "meta:" in result

    def test_list_value(self, logger):
        result = logger._format_compact({"items": [1, 2, 3]})
        assert "items" in result

    def test_empty_dict(self, logger):
        result = logger._format_compact({})
        assert result == ""

    def test_indent(self, logger):
        result = logger._format_compact({"outer": {"inner_key": "inner_val"}}, indent=1)
        assert "  outer:" in result


class TestFormatValue:
    def test_none(self, logger):
        assert logger._format_value(None) == "null"

    def test_bool_true(self, logger):
        assert logger._format_value(True) == "true"

    def test_bool_false(self, logger):
        assert logger._format_value(False) == "false"

    def test_int(self, logger):
        assert logger._format_value(42) == "42"

    def test_float(self, logger):
        assert logger._format_value(3.14) == "3.14"

    def test_short_string(self, logger):
        assert logger._format_value("hello") == '"hello"'

    def test_long_string_truncated(self, logger):
        long_str = "a" * 300
        result = logger._format_value(long_str)
        assert "..." in result
        assert len(result) < 300

    def test_custom_max_len(self, logger):
        result = logger._format_value("a" * 50, max_len=10)
        assert "..." in result

    def test_other_type(self, logger):
        result = logger._format_value([1, 2, 3])
        assert "[1, 2, 3]" in result

    def test_other_type_long(self, logger):
        obj = "x" * 300
        result = logger._format_value(obj)
        assert "..." in result


class TestTruncate:
    def test_short_text(self, logger):
        assert logger._truncate("hello", 100) == "hello"

    def test_long_text(self, logger):
        text = "a" * 200
        result = logger._truncate(text, 100)
        assert result == "a" * 100 + "..."
        assert len(result) == 103

    def test_exact_length(self, logger):
        text = "a" * 100
        result = logger._truncate(text, 100)
        assert result == text


class TestFormatToolsSummary:
    def test_empty_tools(self, logger):
        assert logger._format_tools_summary([]) == "无工具"

    def test_builtin_tools(self, logger):
        tools = [
            {"function": {"name": "shell_tool"}},
            {"function": {"name": "file_read"}},
        ]
        result = logger._format_tools_summary(tools)
        assert "2个工具" in result
        assert "内置工具" in result
        assert "shell_tool" in result

    def test_mcp_tools(self, logger):
        tools = [{"name": "mcp_search"}, {"name": "browser_click"}]
        result = logger._format_tools_summary(tools)
        assert "MCP工具" in result
        assert "mcp_search" in result
        assert "browser_click" in result

    def test_other_tools(self, logger):
        tools = [{"name": "custom_skill"}]
        result = logger._format_tools_summary(tools)
        assert "其他工具" in result
        assert "custom_skill" in result

    def test_mixed_tools(self, logger):
        tools = [
            {"function": {"name": "shell_tool"}},
            {"name": "mcp_search"},
            {"name": "custom_skill"},
        ]
        result = logger._format_tools_summary(tools)
        assert "3个工具" in result
        assert "内置工具" in result
        assert "MCP工具" in result
        assert "其他工具" in result


class TestGetContent:
    def test_string_content(self, logger):
        msg = MagicMock()
        msg.content = "hello"
        assert logger._get_content(msg) == "hello"

    def test_list_content_with_strings(self, logger):
        msg = MagicMock()
        msg.content = ["hello", "world"]
        assert logger._get_content(msg) == "hello world"

    def test_list_content_with_dicts(self, logger):
        msg = MagicMock()
        msg.content = [{"text": "hello"}, {"text": "world"}]
        assert logger._get_content(msg) == "hello world"

    def test_list_content_mixed(self, logger):
        msg = MagicMock()
        msg.content = ["hello", {"text": "world"}]
        assert logger._get_content(msg) == "hello world"

    def test_no_content_attr(self, logger):
        msg = "just a string"
        assert logger._get_content(msg) == "just a string"


class TestFormatList:
    def test_empty_list(self, logger):
        result = logger._format_list([], "items")
        assert result == "items: []"

    def test_short_list_with_dicts(self, logger):
        items = [{"name": "a", "size": 1}, {"name": "b", "size": 2}]
        result = logger._format_list(items, "tools")
        assert "a" in result
        assert "b" in result

    def test_short_list_with_plain_items(self, logger):
        items = ["x", "y"]
        result = logger._format_list(items, "tags")
        assert "x" in result
        assert "y" in result

    def test_long_list_truncated(self, logger):
        items = list(range(10))
        result = logger._format_list(items, "nums", max_items=5)
        assert "10 items" in result
        assert "showing first 5" in result

    def test_dict_without_name_key(self, logger):
        items = [{"type": "a", "value": 1}]
        result = logger._format_list(items, "items")
        assert "items[0]:" in result


class TestSerializeMessages:
    def test_basic_message(self, logger):
        msg = MagicMock()
        msg.type = "human"
        msg.content = "hello"
        msg.tool_calls = None
        del msg.tool_call_id

        result = logger._serialize_messages([msg])
        assert len(result) == 1
        assert result[0]["type"] == "human"
        assert result[0]["content"] == "hello"

    def test_message_with_tool_calls(self, logger):
        msg = MagicMock()
        msg.type = "ai"
        msg.content = ""
        msg.tool_calls = [{"name": "shell_tool", "args": {"cmd": "ls"}}]
        del msg.tool_call_id

        result = logger._serialize_messages([msg])
        assert result[0]["tool_calls"][0]["name"] == "shell_tool"

    def test_message_with_tool_call_id(self, logger):
        msg = MagicMock()
        msg.type = "tool"
        msg.content = "result"
        msg.tool_calls = None
        msg.tool_call_id = "call_123"

        result = logger._serialize_messages([msg])
        assert result[0]["tool_call_id"] == "call_123"


class TestSerializeResponse:
    def test_response_with_content(self, logger):
        resp = MagicMock()
        resp.content = "hello"
        resp.tool_calls = None

        result = logger._serialize_response(resp)
        assert result["content"] == "hello"

    def test_response_with_tool_calls(self, logger):
        resp = MagicMock()
        resp.content = ""
        resp.tool_calls = [{"name": "shell_tool", "args": {"cmd": "ls"}}]

        result = logger._serialize_response(resp)
        assert result["tool_calls"][0]["name"] == "shell_tool"

    def test_response_without_content_attr(self, logger):
        resp = "raw string"
        result = logger._serialize_response(resp)
        assert "raw" in result["raw"]


class TestGetCallbackHandler:
    def test_returns_callback_handler(self, logger):
        handler = logger.get_callback_handler()
        assert isinstance(handler, LLMRequestCallbackHandler)
        assert handler.logger is logger


class TestIsSimpleDict:
    def test_simple_dict(self, logger):
        assert logger._is_simple_dict({"a": 1, "b": "x"}) is True

    def test_nested_dict(self, logger):
        assert logger._is_simple_dict({"a": {"b": 1}}) is False

    def test_dict_with_list(self, logger):
        assert logger._is_simple_dict({"a": [1, 2]}) is False

    def test_empty_dict(self, logger):
        assert logger._is_simple_dict({}) is True


class TestFormatSimpleDict:
    def test_basic(self, logger):
        result = logger._format_simple_dict({"a": 1, "b": "x"})
        assert "a=" in result
        assert "b=" in result

    def test_empty(self, logger):
        assert logger._format_simple_dict({}) == ""
