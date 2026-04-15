import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage

from src.core.llm_wrapper import LLMCaller


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


@pytest.mark.asyncio
async def test_retry_on_timeout(llm_caller):
    call_count = 0

    async def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise asyncio.TimeoutError()
        
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = "hello"
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
    assert len(retry_chunks) == 2
    assert retry_chunks[0]["attempt"] == 1
    assert retry_chunks[1]["attempt"] == 2

    complete_chunks = [c for c in chunks if c["type"] == "complete"]
    assert len(complete_chunks) == 1
    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_exhausted(llm_caller):
    async def mock_create(**kwargs):
        raise asyncio.TimeoutError()

    llm_caller.client.chat.completions.create = mock_create

    chunks = []
    async for chunk in llm_caller.stream_call([HumanMessage(content="test")]):
        chunks.append(chunk)

    retry_chunks = [c for c in chunks if c["type"] == "retry"]
    assert len(retry_chunks) == 3

    error_chunks = [c for c in chunks if c["type"] == "error"]
    assert len(error_chunks) == 1
    assert "已重试3次" in error_chunks[0]["message"]


@pytest.mark.asyncio
async def test_no_retry_on_non_retryable_error(llm_caller):
    async def mock_create(**kwargs):
        raise ValueError("API error")

    llm_caller.client.chat.completions.create = mock_create

    chunks = []
    async for chunk in llm_caller.stream_call([HumanMessage(content="test")]):
        chunks.append(chunk)

    retry_chunks = [c for c in chunks if c["type"] == "retry"]
    assert len(retry_chunks) == 0

    error_chunks = [c for c in chunks if c["type"] == "error"]
    assert len(error_chunks) == 1
    assert "API error" in error_chunks[0]["message"]


def test_exponential_backoff_delay_calculation():
    caller = LLMCaller(
        api_key="test-key",
        model="test-model",
        retry_max_count=3,
        retry_initial_delay=10.0,
        retry_max_delay=30.0,
    )

    delay = caller.retry_initial_delay
    delays = []
    for i in range(caller.retry_max_count):
        delays.append(delay)
        delay = min(delay * 2, caller.retry_max_delay)

    assert delays == [10.0, 20.0, 30.0]


def test_exponential_backoff_delay_no_cap():
    caller = LLMCaller(
        api_key="test-key",
        model="test-model",
        retry_max_count=4,
        retry_initial_delay=5.0,
        retry_max_delay=100.0,
    )

    delay = caller.retry_initial_delay
    delays = []
    for i in range(caller.retry_max_count):
        delays.append(delay)
        delay = min(delay * 2, caller.retry_max_delay)

    assert delays == [5.0, 10.0, 20.0, 40.0]


def test_default_retry_params():
    caller = LLMCaller(api_key="test-key", model="test-model")
    assert caller.retry_max_count == 3
    assert caller.retry_initial_delay == 10.0
    assert caller.retry_max_delay == 60.0


def test_custom_retry_params():
    caller = LLMCaller(
        api_key="test-key",
        model="test-model",
        retry_max_count=5,
        retry_initial_delay=15.0,
        retry_max_delay=120.0,
    )
    assert caller.retry_max_count == 5
    assert caller.retry_initial_delay == 15.0
    assert caller.retry_max_delay == 120.0
