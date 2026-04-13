import asyncio
import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from src.core.llm_wrapper import LLMCaller, UsageStats


@pytest.fixture
def llm_caller():
    return LLMCaller(
        api_key="test-key",
        model="test-model",
        base_url="https://api.test.com/v1",
        timeout=5.0,
        retry_max_count=3,
        retry_initial_delay=0.01,
        retry_max_delay=0.05,
    )


class TestIsRetryableError:
    def test_connection_error_is_retryable(self):
        assert LLMCaller._is_retryable_error(ConnectionError("lost")) is True

    def test_connection_reset_error_is_retryable(self):
        assert LLMCaller._is_retryable_error(ConnectionResetError("reset")) is True

    def test_os_error_is_retryable(self):
        assert LLMCaller._is_retryable_error(OSError("broken pipe")) is True

    def test_openai_timeout_is_retryable(self):
        import openai
        assert LLMCaller._is_retryable_error(openai.APITimeoutError(request=MagicMock())) is True

    def test_openai_connection_error_is_retryable(self):
        import openai
        assert LLMCaller._is_retryable_error(openai.APIConnectionError(request=MagicMock())) is True

    def test_rate_limit_keyword_is_retryable(self):
        assert LLMCaller._is_retryable_error(Exception("Rate limit exceeded 429")) is True

    def test_500_keyword_is_retryable(self):
        assert LLMCaller._is_retryable_error(Exception("Server error 500")) is True

    def test_value_error_not_retryable(self):
        assert LLMCaller._is_retryable_error(ValueError("invalid input")) is False

    def test_generic_error_not_retryable(self):
        assert LLMCaller._is_retryable_error(RuntimeError("unknown")) is False


class TestConvertMessagesToOpenai:
    def test_system_message(self, llm_caller):
        msgs = [SystemMessage(content="You are helpful")]
        result = llm_caller._convert_messages_to_openai(msgs)
        assert result == [{"role": "system", "content": "You are helpful"}]

    def test_human_message(self, llm_caller):
        msgs = [HumanMessage(content="Hello")]
        result = llm_caller._convert_messages_to_openai(msgs)
        assert result == [{"role": "user", "content": "Hello"}]

    def test_ai_message_no_tool_calls(self, llm_caller):
        msgs = [AIMessage(content="Hi there")]
        result = llm_caller._convert_messages_to_openai(msgs)
        assert result == [{"role": "assistant", "content": "Hi there"}]

    def test_ai_message_with_tool_calls(self, llm_caller):
        msgs = [AIMessage(
            content="",
            tool_calls=[{"id": "tc1", "name": "search", "args": {"q": "test"}}]
        )]
        result = llm_caller._convert_messages_to_openai(msgs)
        assert len(result) == 1
        assert result[0]["role"] == "assistant"
        assert len(result[0]["tool_calls"]) == 1
        assert result[0]["tool_calls"][0]["id"] == "tc1"
        assert result[0]["tool_calls"][0]["function"]["name"] == "search"

    def test_tool_message(self, llm_caller):
        msgs = [ToolMessage(content="result data", tool_call_id="tc1")]
        result = llm_caller._convert_messages_to_openai(msgs)
        assert result == [{"role": "tool", "content": "result data", "tool_call_id": "tc1"}]

    def test_mixed_messages(self, llm_caller):
        msgs = [
            SystemMessage(content="System"),
            HumanMessage(content="Hello"),
            AIMessage(content="Hi"),
            HumanMessage(content="How are you?"),
        ]
        result = llm_caller._convert_messages_to_openai(msgs)
        assert len(result) == 4
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "user"
        assert result[2]["role"] == "assistant"
        assert result[3]["role"] == "user"


class TestConvertOpenaiResponseToAimessage:
    def test_simple_response(self, llm_caller):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello world"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        result = llm_caller._convert_openai_response_to_aimessage(mock_response)
        assert isinstance(result, AIMessage)
        assert result.content == "Hello world"
        assert result.tool_calls == []
        assert result.usage_metadata["input_tokens"] == 10
        assert result.usage_metadata["output_tokens"] == 5

    def test_response_with_tool_calls(self, llm_caller):
        mock_tc = MagicMock()
        mock_tc.id = "tc1"
        mock_tc.function.name = "search"
        mock_tc.function.arguments = '{"q": "test"}'

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = ""
        mock_response.choices[0].message.tool_calls = [mock_tc]
        mock_response.usage = None

        result = llm_caller._convert_openai_response_to_aimessage(mock_response)
        assert isinstance(result, AIMessage)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "search"
        assert result.tool_calls[0]["args"] == {"q": "test"}

    def test_empty_choices(self, llm_caller):
        mock_response = MagicMock()
        mock_response.choices = []

        result = llm_caller._convert_openai_response_to_aimessage(mock_response)
        assert isinstance(result, AIMessage)
        assert result.content == ""


class TestBuildRequestParams:
    def test_basic_params(self, llm_caller):
        msgs = [{"role": "user", "content": "Hi"}]
        params = llm_caller._build_request_params(msgs, use_tools=False)
        assert params["model"] == "test-model"
        assert params["messages"] == msgs
        assert params["temperature"] == 0.7
        assert params["max_tokens"] == 80000
        assert "stream" not in params
        assert "tools" not in params

    def test_stream_params(self, llm_caller):
        msgs = [{"role": "user", "content": "Hi"}]
        params = llm_caller._build_request_params(msgs, use_tools=False, stream=True)
        assert params["stream"] is True


class TestDumpErrorRequestData:
    def test_creates_log_file(self, llm_caller, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        
        request_params = {
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hi"}],
            "temperature": 0.7,
            "max_tokens": 80000,
        }
        error = Exception("test error")
        
        llm_caller._dump_error_request_data(request_params, error)
        
        logs_dir = tmp_path / "logs"
        assert logs_dir.exists()
        
        log_files = list(logs_dir.glob("llm_error_req_data_*.log"))
        assert len(log_files) == 1
        
        with open(log_files[0], "r", encoding="utf-8") as f:
            data = json.load(f)
        
        assert data["error_type"] == "Exception"
        assert data["error_message"] == "test error"
        assert data["request"]["model"] == "test-model"
        assert len(data["request"]["messages"]) == 1


class TestStreamCallRetry:
    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self, llm_caller):
        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                raise ConnectionError("Connection reset")
            
            mock_chunk = MagicMock()
            mock_chunk.choices = [MagicMock()]
            mock_chunk.choices[0].delta.content = "recovered"
            mock_chunk.choices[0].delta.tool_calls = None
            
            mock_chunk2 = MagicMock()
            mock_chunk2.choices = []
            
            async def aiter():
                yield mock_chunk
                yield mock_chunk2
            
            return aiter()

        llm_caller.client.chat.completions.create = mock_create

        chunks = []
        async for chunk in llm_caller.stream_call([HumanMessage(content="test")]):
            chunks.append(chunk)

        retry_chunks = [c for c in chunks if c["type"] == "retry"]
        assert len(retry_chunks) == 1

        complete_chunks = [c for c in chunks if c["type"] == "complete"]
        assert len(complete_chunks) == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_error(self, llm_caller):
        async def mock_create(**kwargs):
            raise ValueError("invalid input")

        llm_caller.client.chat.completions.create = mock_create

        chunks = []
        async for chunk in llm_caller.stream_call([HumanMessage(content="test")]):
            chunks.append(chunk)

        retry_chunks = [c for c in chunks if c["type"] == "retry"]
        assert len(retry_chunks) == 0

        error_chunks = [c for c in chunks if c["type"] == "error"]
        assert len(error_chunks) == 1


class TestPrepareMessages:
    def test_adds_system_prompt(self, llm_caller):
        llm_caller.system_prompt = "You are helpful"
        msgs = [HumanMessage(content="Hello")]
        result = llm_caller._prepare_messages(msgs)
        assert len(result) == 2
        assert isinstance(result[0], SystemMessage)
        assert result[0].content == "You are helpful"

    def test_no_system_prompt(self, llm_caller):
        llm_caller.system_prompt = None
        msgs = [HumanMessage(content="Hello")]
        result = llm_caller._prepare_messages(msgs)
        assert len(result) == 1
