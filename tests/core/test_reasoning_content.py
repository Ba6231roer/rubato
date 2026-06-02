import pytest
import asyncio
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage

from src.core.llm_wrapper import LLMCaller
from src.context.session_storage import MessageSerializer


class TestLLMCallerReasoningContent:

    def test_convert_messages_to_openai_with_reasoning_content(self):
        caller = LLMCaller(api_key="test-key", model="test-model", base_url="http://localhost:8000")
        messages = [AIMessage(
            content="result",
            additional_kwargs={"reasoning_content": "Let me think step by step..."}
        )]
        result = caller._convert_messages_to_openai(messages)
        assert len(result) == 1
        assert result[0]["role"] == "assistant"
        assert result[0]["content"] == "result"
        assert result[0]["reasoning_content"] == "Let me think step by step..."

    def test_convert_messages_to_openai_without_reasoning_content(self):
        caller = LLMCaller(api_key="test-key", model="test-model", base_url="http://localhost:8000")
        messages = [AIMessage(content="result")]
        result = caller._convert_messages_to_openai(messages)
        assert len(result) == 1
        assert result[0]["role"] == "assistant"
        assert "reasoning_content" not in result[0]

    def test_convert_openai_response_to_aimessage_with_reasoning(self):
        caller = LLMCaller(api_key="test-key", model="test-model", base_url="http://localhost:8000")
        mock_message = MagicMock()
        mock_message.content = "response text"
        mock_message.reasoning_content = "thinking..."
        mock_message.tool_calls = []
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock(
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )
        result = caller._convert_openai_response_to_aimessage(mock_response)
        assert isinstance(result, AIMessage)
        assert result.content == "response text"
        assert result.additional_kwargs["reasoning_content"] == "thinking..."

    def test_convert_openai_response_to_aimessage_without_reasoning(self):
        caller = LLMCaller(api_key="test-key", model="test-model", base_url="http://localhost:8000")
        mock_message = MagicMock()
        mock_message.content = "response text"
        del mock_message.reasoning_content
        mock_message.tool_calls = []
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock(
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )
        result = caller._convert_openai_response_to_aimessage(mock_response)
        assert isinstance(result, AIMessage)
        assert "reasoning_content" not in result.additional_kwargs

    @pytest.mark.asyncio
    async def test_stream_call_captures_reasoning_content(self):
        caller = LLMCaller(api_key="test-key", model="test-model", base_url="http://localhost:8000")

        class MockDelta:
            def __init__(self, content=None, reasoning_content=None, tool_calls=None):
                self.content = content
                self.tool_calls = tool_calls
                if reasoning_content is not None:
                    self.reasoning_content = reasoning_content

        class MockChoice:
            def __init__(self, delta):
                self.delta = delta

        class MockChunk:
            def __init__(self, choices=None, usage=None):
                self.choices = choices or []
                self.usage = usage

        chunks = [
            MockChunk(choices=[MockChoice(MockDelta(reasoning_content="reasoning part"))]),
            MockChunk(choices=[MockChoice(MockDelta(content="actual response"))]),
            MockChunk(choices=[], usage=MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)),
        ]

        class MockCompletions:
            async def create(self, **kwargs):
                async def gen():
                    for c in chunks:
                        yield c
                return gen()

        class MockChat:
            completions = MockCompletions()

        caller.client = type("Client", (), {"chat": MockChat()})()

        collected = []
        async for event in caller.stream_call(messages=[]):
            collected.append(event)

        complete_events = [e for e in collected if e["type"] == "complete"]
        assert len(complete_events) == 1
        final_response = complete_events[0]["response"]
        assert isinstance(final_response, AIMessage)
        assert final_response.additional_kwargs["reasoning_content"] == "reasoning part"
        assert final_response.content == "actual response"


class TestMessageSerializerReasoningContent:

    def test_serialize_aimessage_with_reasoning_content(self):
        msg = AIMessage(
            content="hello",
            additional_kwargs={"reasoning_content": "thinking text"}
        )
        result = MessageSerializer.serialize(msg)
        assert result["reasoning_content"] == "thinking text"
        assert result["type"] == "ai"
        assert result["content"] == "hello"

    def test_serialize_aimessage_without_reasoning_content(self):
        msg = AIMessage(content="hello")
        result = MessageSerializer.serialize(msg)
        assert "reasoning_content" not in result

    def test_deserialize_aimessage_with_reasoning_content(self):
        msg_dict = {
            "type": "ai",
            "content": "hello",
            "reasoning_content": "thinking text",
        }
        result = MessageSerializer.deserialize(msg_dict)
        assert isinstance(result, AIMessage)
        assert result.content == "hello"
        assert result.additional_kwargs["reasoning_content"] == "thinking text"

    def test_deserialize_aimessage_without_reasoning_content(self):
        msg_dict = {
            "type": "ai",
            "content": "hello",
        }
        result = MessageSerializer.deserialize(msg_dict)
        assert isinstance(result, AIMessage)
        assert "reasoning_content" not in result.additional_kwargs

    def test_roundtrip_reasoning_content(self):
        original = AIMessage(
            content="hello",
            additional_kwargs={"reasoning_content": "thinking text"}
        )
        serialized = MessageSerializer.serialize(original)
        deserialized = MessageSerializer.deserialize(serialized)
        assert isinstance(deserialized, AIMessage)
        assert deserialized.content == "hello"
        assert deserialized.additional_kwargs["reasoning_content"] == "thinking text"

    def test_serialize_deserialize_preserves_other_fields(self):
        original = AIMessage(
            content="hello",
            tool_calls=[{"id": "call_1", "name": "search", "args": {"q": "test"}}],
            additional_kwargs={"reasoning_content": "thinking text"}
        )
        serialized = MessageSerializer.serialize(original)
        assert serialized["reasoning_content"] == "thinking text"
        assert len(serialized["tool_calls"]) == 1
        deserialized = MessageSerializer.deserialize(serialized)
        assert isinstance(deserialized, AIMessage)
        assert deserialized.additional_kwargs["reasoning_content"] == "thinking text"
        assert len(deserialized.tool_calls) == 1
        assert deserialized.tool_calls[0]["name"] == "search"
