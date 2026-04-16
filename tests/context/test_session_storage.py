import json
import os
import tempfile
import unittest

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

from src.context.session_storage import (
    SessionStorage,
    SessionMetadata,
    MessageSerializer,
    SubSessionRef,
)


class TestSubSessionRef(unittest.TestCase):

    def test_creation(self):
        ref = SubSessionRef(
            session_id="sub-1",
            agent_name="test_agent",
            relation="spawn",
            timestamp="2026-01-01T00:00:00",
        )
        self.assertEqual(ref.session_id, "sub-1")
        self.assertEqual(ref.agent_name, "test_agent")
        self.assertEqual(ref.relation, "spawn")
        self.assertEqual(ref.timestamp, "2026-01-01T00:00:00")

    def test_asdict(self):
        ref = SubSessionRef(
            session_id="sub-1",
            agent_name="agent",
            relation="tool_call",
            timestamp="2026-01-01T00:00:00",
        )
        d = ref.__dict__
        self.assertEqual(d["session_id"], "sub-1")
        self.assertEqual(d["relation"], "tool_call")


class TestSessionMetadata(unittest.TestCase):

    def test_default_new_fields(self):
        meta = SessionMetadata(
            session_id="test",
            created_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:00",
            message_count=0,
        )
        self.assertEqual(meta.role, "")
        self.assertEqual(meta.model, "")
        self.assertIsNone(meta.parent_session_id)
        self.assertEqual(meta.sub_sessions, [])

    def test_with_new_fields(self):
        ref = SubSessionRef(
            session_id="sub-1",
            agent_name="agent",
            relation="spawn",
            timestamp="2026-01-01T00:00:00",
        )
        meta = SessionMetadata(
            session_id="test",
            created_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:00",
            message_count=5,
            role="tester",
            model="gpt-4",
            parent_session_id="parent-1",
            sub_sessions=[ref],
        )
        self.assertEqual(meta.role, "tester")
        self.assertEqual(meta.model, "gpt-4")
        self.assertEqual(meta.parent_session_id, "parent-1")
        self.assertEqual(len(meta.sub_sessions), 1)
        self.assertEqual(meta.sub_sessions[0].session_id, "sub-1")


class TestMessageSerializer(unittest.TestCase):

    def test_serialize_human_message(self):
        msg = HumanMessage(content="hello")
        d = MessageSerializer.serialize(msg)
        self.assertEqual(d["type"], "human")
        self.assertEqual(d["role"], "user")
        self.assertEqual(d["content"], "hello")
        self.assertIn("timestamp", d)

    def test_serialize_ai_message(self):
        msg = AIMessage(content="hi", tool_calls=[], response_metadata={}, id="ai-1")
        d = MessageSerializer.serialize(msg)
        self.assertEqual(d["type"], "ai")
        self.assertEqual(d["role"], "assistant")
        self.assertIn("timestamp", d)

    def test_serialize_tool_message(self):
        msg = ToolMessage(content="result", tool_call_id="tc1", name="search")
        d = MessageSerializer.serialize(msg)
        self.assertEqual(d["type"], "tool")
        self.assertEqual(d["role"], "tool")
        self.assertIn("timestamp", d)

    def test_serialize_system_message(self):
        msg = SystemMessage(content="system prompt")
        d = MessageSerializer.serialize(msg)
        self.assertEqual(d["type"], "system")
        self.assertEqual(d["role"], "system")
        self.assertIn("timestamp", d)

    def test_timestamp_from_message_attribute(self):
        msg = HumanMessage(content="hello")
        msg.timestamp = "2026-03-15T10:00:00"
        d = MessageSerializer.serialize(msg)
        self.assertEqual(d["timestamp"], "2026-03-15T10:00:00")

    def test_deserialize_backward_compat(self):
        old_dict = {"type": "human", "content": "hello"}
        msg = MessageSerializer.deserialize(old_dict)
        self.assertIsInstance(msg, HumanMessage)
        self.assertEqual(msg.content, "hello")

    def test_roundtrip(self):
        msgs = [
            SystemMessage(content="system"),
            HumanMessage(content="hello"),
            AIMessage(content="hi", tool_calls=[], response_metadata={}, id="ai-1"),
            ToolMessage(content="result", tool_call_id="tc1"),
        ]
        serialized = MessageSerializer.serialize_list(msgs)
        deserialized = MessageSerializer.deserialize_list(serialized)
        self.assertEqual(len(deserialized), 4)
        self.assertIsInstance(deserialized[0], SystemMessage)
        self.assertIsInstance(deserialized[1], HumanMessage)
        self.assertIsInstance(deserialized[2], AIMessage)
        self.assertIsInstance(deserialized[3], ToolMessage)


class TestSessionStorage(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.storage = SessionStorage(storage_dir=self.tmpdir)

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_save_and_load_session(self):
        msgs = [HumanMessage(content="hello"), AIMessage(content="hi")]
        meta = self.storage.save_session("s1", msgs, {"role": "tester", "model": "gpt-4"})
        self.assertEqual(meta.session_id, "s1")
        self.assertEqual(meta.role, "tester")
        self.assertEqual(meta.model, "gpt-4")
        self.assertEqual(meta.message_count, 2)

        loaded = self.storage.load_session("s1")
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0].content, "hello")
        self.assertEqual(loaded[1].content, "hi")

    def test_save_preserves_existing_metadata(self):
        msgs = [HumanMessage(content="hello")]
        self.storage.save_session("s1", msgs, {"role": "tester", "model": "gpt-4"})

        msgs2 = [AIMessage(content="hi")]
        self.storage.save_session("s1", msgs + msgs2, {"total_tokens": 100})

        meta = self.storage.get_session_metadata("s1")
        self.assertEqual(meta.role, "tester")
        self.assertEqual(meta.model, "gpt-4")
        self.assertEqual(meta.total_tokens, 100)

    def test_append_messages(self):
        msgs = [HumanMessage(content="hello")]
        self.storage.save_session("s1", msgs, {"role": "tester"})

        new_msgs = [AIMessage(content="hi"), HumanMessage(content="how are you")]
        meta = self.storage.append_messages("s1", new_msgs)

        self.assertEqual(meta.message_count, 3)
        self.assertEqual(meta.role, "tester")

        loaded = self.storage.load_session("s1")
        self.assertEqual(len(loaded), 3)
        self.assertEqual(loaded[0].content, "hello")
        self.assertEqual(loaded[1].content, "hi")
        self.assertEqual(loaded[2].content, "how are you")

    def test_append_messages_to_new_session(self):
        new_msgs = [HumanMessage(content="first")]
        meta = self.storage.append_messages("s1", new_msgs)
        self.assertEqual(meta.message_count, 1)

        loaded = self.storage.load_session("s1")
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].content, "first")

    def test_save_sub_session_ref(self):
        msgs = [HumanMessage(content="hello")]
        self.storage.save_session("parent-1", msgs)

        ref = SubSessionRef(
            session_id="sub-1",
            agent_name="child_agent",
            relation="spawn",
            timestamp="2026-01-01T00:00:00",
        )
        self.storage.save_sub_session_ref("parent-1", ref)

        meta = self.storage.get_session_metadata("parent-1")
        self.assertEqual(len(meta.sub_sessions), 1)
        self.assertEqual(meta.sub_sessions[0].session_id, "sub-1")
        self.assertEqual(meta.sub_sessions[0].agent_name, "child_agent")
        self.assertEqual(meta.sub_sessions[0].relation, "spawn")

    def test_save_sub_session_ref_parent_not_found(self):
        ref = SubSessionRef(
            session_id="sub-1",
            agent_name="child_agent",
            relation="spawn",
            timestamp="2026-01-01T00:00:00",
        )
        with self.assertRaises(FileNotFoundError):
            self.storage.save_sub_session_ref("nonexistent", ref)

    def test_load_session_with_meta(self):
        msgs = [HumanMessage(content="hello"), AIMessage(content="hi")]
        self.storage.save_session(
            "s1", msgs,
            {"role": "tester", "model": "gpt-4", "parent_session_id": "p1"},
        )

        meta, loaded = self.storage.load_session_with_meta("s1")
        self.assertEqual(meta.session_id, "s1")
        self.assertEqual(meta.role, "tester")
        self.assertEqual(meta.model, "gpt-4")
        self.assertEqual(meta.parent_session_id, "p1")
        self.assertEqual(len(loaded), 2)

    def test_load_session_with_meta_not_found(self):
        with self.assertRaises(FileNotFoundError):
            self.storage.load_session_with_meta("nonexistent")

    def test_backward_compat_old_file(self):
        session_file = os.path.join(self.tmpdir, "old-session.json")
        old_data = {
            "metadata": {
                "session_id": "old-session",
                "created_at": "2026-01-01T00:00:00",
                "updated_at": "2026-01-01T00:00:00",
                "message_count": 1,
                "total_tokens": 0,
                "tags": [],
                "description": "",
            },
            "messages": [
                {"type": "human", "content": "old message"},
            ],
        }
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(old_data, f, ensure_ascii=False)

        meta, msgs = self.storage.load_session_with_meta("old-session")
        self.assertEqual(meta.role, "")
        self.assertEqual(meta.model, "")
        self.assertIsNone(meta.parent_session_id)
        self.assertEqual(meta.sub_sessions, [])
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].content, "old message")

    def test_metadata_from_dict_with_sub_sessions(self):
        metadata_dict = {
            "session_id": "s1",
            "created_at": "2026-01-01",
            "updated_at": "2026-01-01",
            "message_count": 1,
            "sub_sessions": [
                {"session_id": "sub-1", "agent_name": "a", "relation": "spawn", "timestamp": "2026-01-01"},
            ],
        }
        meta = SessionStorage._metadata_from_dict(metadata_dict)
        self.assertEqual(len(meta.sub_sessions), 1)
        self.assertIsInstance(meta.sub_sessions[0], SubSessionRef)
        self.assertEqual(meta.sub_sessions[0].session_id, "sub-1")

    def test_multiple_sub_session_refs(self):
        msgs = [HumanMessage(content="hello")]
        self.storage.save_session("parent-1", msgs)

        ref1 = SubSessionRef(
            session_id="sub-1", agent_name="a1", relation="spawn",
            timestamp="2026-01-01T00:00:00",
        )
        ref2 = SubSessionRef(
            session_id="sub-2", agent_name="a2", relation="tool_call",
            timestamp="2026-01-01T00:01:00",
        )
        self.storage.save_sub_session_ref("parent-1", ref1)
        self.storage.save_sub_session_ref("parent-1", ref2)

        meta = self.storage.get_session_metadata("parent-1")
        self.assertEqual(len(meta.sub_sessions), 2)
        self.assertEqual(meta.sub_sessions[0].session_id, "sub-1")
        self.assertEqual(meta.sub_sessions[1].session_id, "sub-2")
        self.assertEqual(meta.sub_sessions[1].relation, "tool_call")


if __name__ == "__main__":
    unittest.main()
