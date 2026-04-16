import pytest
from pathlib import Path
from src.context.session_storage import SessionStorage, SessionMetadata, SubSessionRef, MessageSerializer
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage


class TestSessionPersistenceIntegration:

    def test_full_session_lifecycle(self, tmp_path):
        storage = SessionStorage(storage_dir=str(tmp_path))

        session_id = "test-lifecycle-001"
        messages = [HumanMessage(content="Hello")]
        storage.save_session(session_id, messages, metadata={"role": "default", "model": "test-model"})

        metadata, loaded_messages = storage.load_session_with_meta(session_id)
        assert metadata.role == "default"
        assert metadata.model == "test-model"
        assert len(loaded_messages) == 1

        new_messages = [AIMessage(content="Hi there!"), HumanMessage(content="How are you?")]
        storage.append_messages(session_id, new_messages, metadata={})

        metadata, loaded_messages = storage.load_session_with_meta(session_id)
        assert len(loaded_messages) == 3
        assert loaded_messages[0].content == "Hello"
        assert loaded_messages[1].content == "Hi there!"
        assert loaded_messages[2].content == "How are you?"

    def test_session_list(self, tmp_path):
        storage = SessionStorage(storage_dir=str(tmp_path))

        storage.save_session("session-1", [HumanMessage(content="Hi")], metadata={"role": "default"})
        storage.save_session("session-2", [HumanMessage(content="Hello")], metadata={"role": "tester"})

        sessions = storage.list_sessions()
        assert len(sessions) == 2

    def test_session_delete(self, tmp_path):
        storage = SessionStorage(storage_dir=str(tmp_path))

        storage.save_session("to-delete", [HumanMessage(content="Bye")], metadata={})
        assert storage.session_exists("to-delete")

        storage.delete_session("to-delete")
        assert not storage.session_exists("to-delete")

    def test_subagent_session_association(self, tmp_path):
        storage = SessionStorage(storage_dir=str(tmp_path))

        parent_id = "parent-session-001"
        storage.save_session(parent_id, [HumanMessage(content="Run tests")], metadata={"role": "default"})

        child_id = "child-session-001"
        storage.save_session(child_id, [HumanMessage(content="Execute test case")],
                           metadata={"role": "test-executor", "parent_session_id": parent_id})

        from datetime import datetime
        sub_ref = SubSessionRef(
            session_id=child_id,
            agent_name="test-executor",
            relation="spawn",
            timestamp=datetime.now().isoformat()
        )
        storage.save_sub_session_ref(parent_id, sub_ref)

        parent_meta, _ = storage.load_session_with_meta(parent_id)
        assert len(parent_meta.sub_sessions) == 1
        assert parent_meta.sub_sessions[0].session_id == child_id
        assert parent_meta.sub_sessions[0].agent_name == "test-executor"

        child_meta, _ = storage.load_session_with_meta(child_id)
        assert child_meta.parent_session_id == parent_id

    def test_multi_level_nesting(self, tmp_path):
        storage = SessionStorage(storage_dir=str(tmp_path))

        main_id = "main-001"
        sub1_id = "sub1-001"
        sub2_id = "sub2-001"

        storage.save_session(main_id, [], metadata={"role": "default"})
        storage.save_session(sub1_id, [], metadata={"role": "worker", "parent_session_id": main_id})
        storage.save_session(sub2_id, [], metadata={"role": "worker", "parent_session_id": sub1_id})

        from datetime import datetime
        ts = datetime.now().isoformat()
        storage.save_sub_session_ref(main_id, SubSessionRef(session_id=sub1_id, agent_name="worker", relation="spawn", timestamp=ts))
        storage.save_sub_session_ref(sub1_id, SubSessionRef(session_id=sub2_id, agent_name="worker", relation="spawn", timestamp=ts))

        main_meta, _ = storage.load_session_with_meta(main_id)
        assert main_meta.sub_sessions[0].session_id == sub1_id

        sub1_meta, _ = storage.load_session_with_meta(sub1_id)
        assert sub1_meta.parent_session_id == main_id
        assert sub1_meta.sub_sessions[0].session_id == sub2_id

        sub2_meta, _ = storage.load_session_with_meta(sub2_id)
        assert sub2_meta.parent_session_id == sub1_id

    def test_message_serializer_roundtrip_with_all_types(self, tmp_path):
        storage = SessionStorage(storage_dir=str(tmp_path))

        messages = [
            HumanMessage(content="Analyze this code"),
            AIMessage(content="Let me read the file.", tool_calls=[{
                "name": "file_read", "args": {"path": "main.py"}, "id": "tc_001",
                "type": "tool_call"
            }]),
            ToolMessage(content="def main(): pass", tool_call_id="tc_001", name="file_read"),
            AIMessage(content="The code looks simple."),
            SystemMessage(content="You are a helpful assistant"),
        ]

        session_id = "roundtrip-001"
        storage.save_session(session_id, messages, metadata={"role": "default", "model": "test"})

        metadata, loaded = storage.load_session_with_meta(session_id)
        assert len(loaded) == 5
        assert isinstance(loaded[0], HumanMessage)
        assert isinstance(loaded[1], AIMessage)
        assert isinstance(loaded[2], ToolMessage)
        assert isinstance(loaded[3], AIMessage)
        assert isinstance(loaded[4], SystemMessage)
        assert loaded[1].tool_calls is not None
        assert loaded[2].tool_call_id == "tc_001"

    def test_session_metadata_update(self, tmp_path):
        storage = SessionStorage(storage_dir=str(tmp_path))

        session_id = "meta-update-001"
        storage.save_session(session_id, [HumanMessage(content="test")], metadata={"role": "default"})

        storage.append_messages(session_id, [AIMessage(content="ok")],
                              metadata={"description": "updated description"})

        metadata, _ = storage.load_session_with_meta(session_id)
        assert metadata.description == "updated description"
        assert metadata.message_count == 2

    def test_concurrent_sessions(self, tmp_path):
        storage = SessionStorage(storage_dir=str(tmp_path))

        for i in range(5):
            sid = f"concurrent-{i}"
            storage.save_session(sid, [HumanMessage(content=f"Message {i}")],
                               metadata={"role": f"role-{i}", "description": f"Session {i}"})

        sessions = storage.list_sessions()
        assert len(sessions) == 5

        for i in range(5):
            sid = f"concurrent-{i}"
            meta, msgs = storage.load_session_with_meta(sid)
            assert meta.role == f"role-{i}"
            assert len(msgs) == 1
