import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import (
    SystemMessage, HumanMessage, AIMessage, ToolMessage
)
from langchain_core.tools import BaseTool

from src.core.llm_wrapper import LLMCaller, UsageStats


class TestUsageStats:
    def test_default_values(self):
        stats = UsageStats()
        assert stats.prompt_tokens == 0
        assert stats.completion_tokens == 0
        assert stats.total_tokens == 0
        assert stats.call_count == 0

    def test_update(self):
        stats = UsageStats()
        stats.update(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        assert stats.prompt_tokens == 100
        assert stats.completion_tokens == 50
        assert stats.total_tokens == 150
        assert stats.call_count == 1

    def test_update_accumulates(self):
        stats = UsageStats()
        stats.update(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        stats.update(prompt_tokens=200, completion_tokens=100, total_tokens=300)
        assert stats.prompt_tokens == 300
        assert stats.completion_tokens == 150
        assert stats.total_tokens == 450
        assert stats.call_count == 2

    def test_to_dict(self):
        stats = UsageStats()
        stats.update(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        d = stats.to_dict()
        assert d == {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "call_count": 1,
        }

    def test_reset(self):
        stats = UsageStats()
        stats.update(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        stats.reset()
        assert stats.prompt_tokens == 0
        assert stats.completion_tokens == 0
        assert stats.total_tokens == 0
        assert stats.call_count == 0


class TestLLMCallerInit:
    def test_default_initialization(self):
        caller = LLMCaller(api_key="test-key")
        assert caller.model == "gpt-4"
        assert caller.temperature == 0.7
        assert caller.max_tokens == 80000
        assert caller.tools == []
        assert caller.system_prompt is None
        assert caller.system_prompt_registry is None
        assert caller.timeout == 300.0
        assert caller.retry_max_count == 3
        assert caller.retry_initial_delay == 10.0
        assert caller.retry_max_delay == 60.0
        assert caller._tool_schemas is None

    def test_custom_initialization(self):
        caller = LLMCaller(
            api_key="my-key",
            model="gpt-3.5-turbo",
            base_url="https://api.example.com",
            temperature=0.5,
            max_tokens=4000,
            system_prompt="You are a helper.",
            timeout=120.0,
            retry_max_count=5,
            retry_initial_delay=5.0,
            retry_max_delay=30.0,
        )
        assert caller.model == "gpt-3.5-turbo"
        assert caller.temperature == 0.5
        assert caller.max_tokens == 4000
        assert caller.system_prompt == "You are a helper."
        assert caller.timeout == 120.0
        assert caller.retry_max_count == 5
        assert caller.retry_initial_delay == 5.0
        assert caller.retry_max_delay == 30.0

    def test_usage_stats_initialized(self):
        caller = LLMCaller(api_key="test-key")
        assert isinstance(caller.usage_stats, UsageStats)
        assert caller.usage_stats.call_count == 0

    def test_client_created_with_base_url(self):
        caller = LLMCaller(api_key="test-key", base_url="https://api.example.com")
        assert caller.client is not None
        assert caller.client.base_url == "https://api.example.com"


class TestBindTools:
    def test_bind_tools_with_empty_list(self):
        caller = LLMCaller(api_key="test-key")
        result = caller.bind_tools([])
        assert result is caller
        assert caller._tool_schemas is None

    def test_bind_tools_with_none(self):
        caller = LLMCaller(api_key="test-key", tools=[])
        result = caller.bind_tools(None)
        assert result is caller
        assert caller._tool_schemas is None

    def test_bind_tools_returns_self(self):
        caller = LLMCaller(api_key="test-key")
        result = caller.bind_tools()
        assert result is caller

    def test_bind_tools_with_mock_tool(self):
        mock_tool = MagicMock(spec=BaseTool)
        mock_tool.name = "test_tool"
        mock_tool.description = "A test tool"
        mock_tool.tool_call_schema = None
        mock_tool.args_schema = None

        caller = LLMCaller(api_key="test-key", tools=[mock_tool])
        result = caller.bind_tools()
        assert result is caller
        assert caller._tool_schemas is not None
        assert len(caller._tool_schemas) == 1
        assert caller._tool_schemas[0]["type"] == "function"
        assert caller._tool_schemas[0]["function"]["name"] == "test_tool"


class TestConvertMessagesToOpenai:
    def test_system_message(self):
        caller = LLMCaller(api_key="test-key")
        messages = [SystemMessage(content="You are a helper.")]
        result = caller._convert_messages_to_openai(messages)
        assert len(result) == 1
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "You are a helper."

    def test_human_message(self):
        caller = LLMCaller(api_key="test-key")
        messages = [HumanMessage(content="Hello")]
        result = caller._convert_messages_to_openai(messages)
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"

    def test_ai_message_simple(self):
        caller = LLMCaller(api_key="test-key")
        messages = [AIMessage(content="Hi there")]
        result = caller._convert_messages_to_openai(messages)
        assert len(result) == 1
        assert result[0]["role"] == "assistant"
        assert result[0]["content"] == "Hi there"

    def test_ai_message_with_dict_tool_calls(self):
        caller = LLMCaller(api_key="test-key")
        messages = [AIMessage(
            content="",
            tool_calls=[{
                "id": "call_1",
                "name": "search",
                "args": {"query": "test"}
            }]
        )]
        result = caller._convert_messages_to_openai(messages)
        assert len(result) == 1
        assert result[0]["role"] == "assistant"
        assert "tool_calls" in result[0]
        assert len(result[0]["tool_calls"]) == 1
        assert result[0]["tool_calls"][0]["function"]["name"] == "search"

    def test_tool_message(self):
        caller = LLMCaller(api_key="test-key")
        messages = [ToolMessage(content="result data", tool_call_id="call_1")]
        result = caller._convert_messages_to_openai(messages)
        assert len(result) == 1
        assert result[0]["role"] == "tool"
        assert result[0]["content"] == "result data"
        assert result[0]["tool_call_id"] == "call_1"

    def test_tool_message_with_dict_content(self):
        caller = LLMCaller(api_key="test-key")
        messages = [ToolMessage(content={"key": "value"}, tool_call_id="call_1")]
        result = caller._convert_messages_to_openai(messages)
        assert len(result) == 1
        assert result[0]["role"] == "tool"
        assert isinstance(result[0]["content"], str)

    def test_mixed_messages(self):
        caller = LLMCaller(api_key="test-key")
        messages = [
            SystemMessage(content="System"),
            HumanMessage(content="Hello"),
            AIMessage(content="Hi"),
        ]
        result = caller._convert_messages_to_openai(messages)
        assert len(result) == 3
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "user"
        assert result[2]["role"] == "assistant"

    def test_ai_message_with_empty_content(self):
        caller = LLMCaller(api_key="test-key")
        messages = [AIMessage(content="")]
        result = caller._convert_messages_to_openai(messages)
        assert result[0]["content"] == ""


class TestIsRetryableError:
    def test_connection_error(self):
        assert LLMCaller._is_retryable_error(ConnectionError("lost")) is True

    def test_connection_reset_error(self):
        assert LLMCaller._is_retryable_error(ConnectionResetError("reset")) is True

    def test_os_error(self):
        assert LLMCaller._is_retryable_error(OSError("os err")) is True

    def test_broken_pipe_error(self):
        assert LLMCaller._is_retryable_error(BrokenPipeError()) is True

    def test_generic_error(self):
        assert LLMCaller._is_retryable_error(ValueError("bad value")) is False

    def test_rate_limit_keyword(self):
        assert LLMCaller._is_retryable_error(Exception("rate limit exceeded")) is True

    def test_timeout_keyword(self):
        assert LLMCaller._is_retryable_error(Exception("request timed out")) is True

    def test_server_error_keyword(self):
        assert LLMCaller._is_retryable_error(Exception("server error 500")) is True

    def test_503_keyword(self):
        assert LLMCaller._is_retryable_error(Exception("503 Service Unavailable")) is True

    def test_null_choices_keyword(self):
        assert LLMCaller._is_retryable_error(Exception("null value for 'choices'")) is True

    def test_non_retryable_keyword(self):
        assert LLMCaller._is_retryable_error(Exception("invalid api key")) is False

    @patch("src.core.llm_wrapper.openai")
    def test_openai_rate_limit_error(self, mock_openai):
        mock_openai.RateLimitError = type("RateLimitError", (Exception,), {})
        mock_openai.APITimeoutError = type("APITimeoutError", (Exception,), {})
        mock_openai.APIConnectionError = type("APIConnectionError", (Exception,), {})
        err = mock_openai.RateLimitError("rate limited")
        assert LLMCaller._is_retryable_error(err) is True


class TestPrepareMessages:
    def test_with_system_prompt(self):
        caller = LLMCaller(api_key="test-key", system_prompt="You are a helper.")
        messages = [HumanMessage(content="Hello")]
        result = caller._prepare_messages(messages)
        assert len(result) == 2
        assert isinstance(result[0], SystemMessage)
        assert result[0].content == "You are a helper."
        assert isinstance(result[1], HumanMessage)

    def test_with_system_prompt_registry(self):
        mock_registry = MagicMock()
        mock_registry.build.return_value = "Registry prompt"
        caller = LLMCaller(
            api_key="test-key",
            system_prompt="Static prompt",
            system_prompt_registry=mock_registry,
        )
        messages = [HumanMessage(content="Hello")]
        result = caller._prepare_messages(messages)
        assert len(result) == 2
        assert isinstance(result[0], SystemMessage)
        assert result[0].content == "Registry prompt"
        mock_registry.build.assert_called_once()

    def test_registry_takes_priority_over_static_prompt(self):
        mock_registry = MagicMock()
        mock_registry.build.return_value = "From registry"
        caller = LLMCaller(
            api_key="test-key",
            system_prompt="Static prompt",
            system_prompt_registry=mock_registry,
        )
        messages = [HumanMessage(content="Hello")]
        result = caller._prepare_messages(messages)
        assert result[0].content == "From registry"

    def test_no_system_prompt(self):
        caller = LLMCaller(api_key="test-key")
        messages = [HumanMessage(content="Hello")]
        result = caller._prepare_messages(messages)
        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)

    def test_messages_preserved(self):
        caller = LLMCaller(api_key="test-key", system_prompt="System")
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi"),
            HumanMessage(content="How are you?"),
        ]
        result = caller._prepare_messages(messages)
        assert len(result) == 4
        assert isinstance(result[0], SystemMessage)
        assert isinstance(result[1], HumanMessage)
        assert isinstance(result[2], AIMessage)
        assert isinstance(result[3], HumanMessage)


class TestGetUsageStats:
    def test_get_usage_stats(self):
        caller = LLMCaller(api_key="test-key")
        caller.usage_stats.update(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        stats = caller.get_usage_stats()
        assert stats["prompt_tokens"] == 100
        assert stats["completion_tokens"] == 50
        assert stats["total_tokens"] == 150
        assert stats["call_count"] == 1

    def test_reset_usage_stats(self):
        caller = LLMCaller(api_key="test-key")
        caller.usage_stats.update(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        caller.reset_usage_stats()
        stats = caller.get_usage_stats()
        assert stats["prompt_tokens"] == 0
        assert stats["call_count"] == 0
