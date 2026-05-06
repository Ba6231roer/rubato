import pytest
from unittest.mock import MagicMock
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from src.context.session_storage import SessionStorage
from src.core.agent import RubatoAgent


def _make_agent():
    agent = object.__new__(RubatoAgent)
    agent._session_storage = None
    agent._query_engine = None
    from src.utils.logger import get_llm_logger
    agent.logger = get_llm_logger()
    return agent


class TestLoadPreCompressionMessages:
    def test_fallback_when_no_session_storage(self):
        agent = _make_agent()
        fallback = [HumanMessage(content="hello")]
        result = agent._load_pre_compression_messages(fallback)
        assert len(result) == 1
        assert result[0].content == "hello"

    def test_fallback_when_no_query_engine(self):
        agent = _make_agent()
        agent._session_storage = MagicMock()
        agent._query_engine = None
        fallback = [HumanMessage(content="hello")]
        result = agent._load_pre_compression_messages(fallback)
        assert len(result) == 1
        assert result[0].content == "hello"

    def test_fallback_when_no_session_id(self):
        agent = _make_agent()
        agent._session_storage = MagicMock()
        agent._query_engine = MagicMock(spec=[])
        fallback = [HumanMessage(content="hello")]
        result = agent._load_pre_compression_messages(fallback)
        assert len(result) == 1
        assert result[0].content == "hello"

    def test_loads_from_session_storage(self, tmp_path):
        agent = _make_agent()
        storage = SessionStorage(storage_dir=str(tmp_path / "sessions"))
        agent._session_storage = storage
        agent._query_engine = MagicMock()
        agent._query_engine._session_id = "test-session-123"

        full_messages = [
            HumanMessage(content="user question"),
            AIMessage(content="assistant response with full tool result"),
            ToolMessage(content="full tool output that would be compressed", tool_call_id="tc1"),
        ]
        storage.save_session("test-session-123", full_messages, metadata={"role": "test"})

        compressed_fallback = [
            HumanMessage(content="user question"),
            AIMessage(content="assistant response with full tool result"),
            ToolMessage(content="[Old tool result content cleared]", tool_call_id="tc1"),
        ]

        result = agent._load_pre_compression_messages(compressed_fallback)
        assert len(result) == 3
        assert result[2].content == "full tool output that would be compressed"

    def test_fallback_when_session_not_found(self, tmp_path):
        agent = _make_agent()
        storage = SessionStorage(storage_dir=str(tmp_path / "sessions"))
        agent._session_storage = storage
        agent._query_engine = MagicMock()
        agent._query_engine._session_id = "nonexistent-session"

        fallback = [HumanMessage(content="hello")]
        result = agent._load_pre_compression_messages(fallback)
        assert len(result) == 1
        assert result[0].content == "hello"

    def test_fallback_when_load_session_raises(self):
        agent = _make_agent()
        agent._session_storage = MagicMock()
        agent._session_storage.load_session.side_effect = Exception("disk error")
        agent._query_engine = MagicMock()
        agent._query_engine._session_id = "test-session"

        fallback = [HumanMessage(content="hello")]
        result = agent._load_pre_compression_messages(fallback)
        assert len(result) == 1
        assert result[0].content == "hello"

    def test_fallback_returns_copy(self):
        agent = _make_agent()
        fallback = [HumanMessage(content="hello")]
        result = agent._load_pre_compression_messages(fallback)
        assert result is not fallback
        assert result == fallback
