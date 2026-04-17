import pytest
from src.api.schemas import (
    ConfigInfo,
    ConfigContent,
    ConfigUpdateRequest,
    ConfigUpdateResponse,
    StatusResponse,
    SkillInfo,
    ToolInfo,
    WSMessage,
    TestCaseTreeNode,
    TestCaseFileContent,
    TestCaseFileUpdateRequest,
    TestCaseFileUpdateResponse,
    CommandRequest,
    CommandInfo,
    CommandResponse,
    SessionInfo,
    SessionDetail,
    SessionLoadResponse,
)


class TestConfigInfo:
    def test_valid_creation(self):
        info = ConfigInfo(name="model", file="model_config.yaml", description="模型配置")
        assert info.name == "model"
        assert info.file == "model_config.yaml"
        assert info.description == "模型配置"

    def test_serialization(self):
        info = ConfigInfo(name="mcp", file="mcp_config.yaml", description="MCP配置")
        data = info.model_dump()
        assert data == {"name": "mcp", "file": "mcp_config.yaml", "description": "MCP配置"}

    def test_json_serialization(self):
        info = ConfigInfo(name="test", file="test.yaml", description="测试")
        json_str = info.model_dump_json()
        restored = ConfigInfo.model_validate_json(json_str)
        assert restored == info

    def test_missing_required_field(self):
        with pytest.raises(Exception):
            ConfigInfo(name="model")


class TestConfigContent:
    def test_valid_creation(self):
        content = ConfigContent(name="model", content="key: value")
        assert content.name == "model"
        assert content.content == "key: value"

    def test_serialization(self):
        content = ConfigContent(name="prompt", content="system: test")
        data = content.model_dump()
        assert data == {"name": "prompt", "content": "system: test"}


class TestConfigUpdateRequest:
    def test_valid_creation(self):
        req = ConfigUpdateRequest(content="key: value")
        assert req.content == "key: value"

    def test_serialization(self):
        req = ConfigUpdateRequest(content="updated: true")
        data = req.model_dump()
        assert data == {"content": "updated: true"}


class TestConfigUpdateResponse:
    def test_success_response(self):
        resp = ConfigUpdateResponse(success=True, message="配置已保存")
        assert resp.success is True
        assert resp.message == "配置已保存"

    def test_failure_response(self):
        resp = ConfigUpdateResponse(success=False, message="保存失败")
        assert resp.success is False

    def test_serialization(self):
        resp = ConfigUpdateResponse(success=True, message="ok")
        data = resp.model_dump()
        assert data == {"success": True, "message": "ok"}


class TestStatusResponse:
    def test_valid_creation(self):
        resp = StatusResponse(
            model="gpt-4",
            mcp_enabled=True,
            mcp_connected=False,
            skills=["skill1", "skill2"],
        )
        assert resp.model == "gpt-4"
        assert resp.mcp_enabled is True
        assert resp.mcp_connected is False
        assert resp.skills == ["skill1", "skill2"]

    def test_browser_alive_default_none(self):
        resp = StatusResponse(model="gpt-4", mcp_enabled=False, mcp_connected=False, skills=[])
        assert resp.browser_alive is None

    def test_browser_alive_set(self):
        resp = StatusResponse(
            model="gpt-4", mcp_enabled=False, mcp_connected=False, skills=[], browser_alive=True
        )
        assert resp.browser_alive is True

    def test_serialization(self):
        resp = StatusResponse(model="test", mcp_enabled=True, mcp_connected=True, skills=["s1"])
        data = resp.model_dump()
        assert data["browser_alive"] is None
        assert data["skills"] == ["s1"]


class TestSkillInfo:
    def test_valid_creation(self):
        info = SkillInfo(name="query", description="查询引擎", version="1.0", triggers=["query", "search"])
        assert info.name == "query"
        assert info.triggers == ["query", "search"]

    def test_serialization(self):
        info = SkillInfo(name="test", description="desc", version="0.1", triggers=["t1"])
        data = info.model_dump()
        assert data == {"name": "test", "description": "desc", "version": "0.1", "triggers": ["t1"]}


class TestToolInfo:
    def test_valid_creation(self):
        info = ToolInfo(name="shell", description="执行shell命令")
        assert info.name == "shell"
        assert info.description == "执行shell命令"

    def test_serialization(self):
        info = ToolInfo(name="file_read", description="读取文件")
        data = info.model_dump()
        assert data == {"name": "file_read", "description": "读取文件"}


class TestWSMessage:
    def test_valid_creation(self):
        msg = WSMessage(type="ping", content="")
        assert msg.type == "ping"
        assert msg.content == ""

    def test_serialization(self):
        msg = WSMessage(type="command", content="/help")
        data = msg.model_dump()
        assert data == {"type": "command", "content": "/help"}


class TestTestCaseTreeNode:
    def test_file_node(self):
        node = TestCaseTreeNode(name="test.md", type="file", path="cases/test.md")
        assert node.type == "file"
        assert node.children is None

    def test_folder_node(self):
        child = TestCaseTreeNode(name="sub.md", type="file", path="cases/dir/sub.md")
        folder = TestCaseTreeNode(name="dir", type="folder", path="cases/dir", children=[child])
        assert folder.type == "folder"
        assert len(folder.children) == 1

    def test_children_default_none(self):
        node = TestCaseTreeNode(name="test.md", type="file", path="test.md")
        assert node.children is None

    def test_recursive_serialization(self):
        child = TestCaseTreeNode(name="a.md", type="file", path="dir/a.md")
        folder = TestCaseTreeNode(name="dir", type="folder", path="dir", children=[child])
        data = folder.model_dump()
        assert data["children"][0]["name"] == "a.md"

    def test_missing_required_field(self):
        with pytest.raises(Exception):
            TestCaseTreeNode(name="test")


class TestTestCaseFileContent:
    def test_valid_creation(self):
        content = TestCaseFileContent(path="cases/test.md", content="# Test")
        assert content.path == "cases/test.md"
        assert content.content == "# Test"

    def test_serialization(self):
        content = TestCaseFileContent(path="a.md", content="hello")
        data = content.model_dump()
        assert data == {"path": "a.md", "content": "hello"}


class TestTestCaseFileUpdateRequest:
    def test_valid_creation(self):
        req = TestCaseFileUpdateRequest(path="test.md", content="updated")
        assert req.path == "test.md"
        assert req.content == "updated"


class TestTestCaseFileUpdateResponse:
    def test_success(self):
        resp = TestCaseFileUpdateResponse(success=True, message="文件已保存")
        assert resp.success is True

    def test_failure(self):
        resp = TestCaseFileUpdateResponse(success=False, message="保存失败")
        assert resp.success is False


class TestCommandRequest:
    def test_valid_creation(self):
        req = CommandRequest(command="/help")
        assert req.command == "/help"

    def test_serialization(self):
        req = CommandRequest(command="/status full")
        data = req.model_dump()
        assert data == {"command": "/status full"}


class TestCommandInfo:
    def test_valid_creation(self):
        info = CommandInfo(name="help", aliases=["?", "h"], description="帮助", usage="/help")
        assert info.name == "help"
        assert info.aliases == ["?", "h"]

    def test_serialization(self):
        info = CommandInfo(name="quit", aliases=["exit"], description="退出", usage="/quit")
        data = info.model_dump()
        assert data["aliases"] == ["exit"]


class TestCommandResponse:
    def test_with_data(self):
        resp = CommandResponse(type="info", message="result", data={"key": "val"}, actions=["action1"])
        assert resp.type == "info"
        assert resp.data == {"key": "val"}
        assert resp.actions == ["action1"]

    def test_default_values(self):
        resp = CommandResponse(type="success", message="ok")
        assert resp.data is None
        assert resp.actions == []

    def test_serialization(self):
        resp = CommandResponse(type="error", message="fail", data=None, actions=[])
        data = resp.model_dump()
        assert data["data"] is None
        assert data["actions"] == []


class TestSessionInfo:
    def test_required_field_only(self):
        info = SessionInfo(session_id="abc-123")
        assert info.session_id == "abc-123"
        assert info.role == ""
        assert info.model == ""
        assert info.message_count == 0
        assert info.created_at == ""
        assert info.updated_at == ""
        assert info.description == ""
        assert info.parent_session_id is None

    def test_all_fields(self):
        info = SessionInfo(
            session_id="s1",
            role="tester",
            model="gpt-4",
            message_count=5,
            created_at="2025-01-01T00:00:00",
            updated_at="2025-01-02T00:00:00",
            description="test session",
            parent_session_id="parent-1",
        )
        assert info.role == "tester"
        assert info.message_count == 5
        assert info.parent_session_id == "parent-1"

    def test_serialization(self):
        info = SessionInfo(session_id="s1", role="dev", model="gpt-4", message_count=3)
        data = info.model_dump()
        assert data["session_id"] == "s1"
        assert data["parent_session_id"] is None

    def test_missing_session_id(self):
        with pytest.raises(Exception):
            SessionInfo()


class TestSessionDetail:
    def test_required_field_only(self):
        detail = SessionDetail(session_id="s1")
        assert detail.session_id == "s1"
        assert detail.sub_sessions == []
        assert detail.messages == []
        assert detail.parent_session_id is None

    def test_with_sub_sessions_and_messages(self):
        detail = SessionDetail(
            session_id="s1",
            sub_sessions=[{"session_id": "sub1", "agent_name": "child"}],
            messages=[{"role": "user", "content": "hello"}],
        )
        assert len(detail.sub_sessions) == 1
        assert len(detail.messages) == 1
        assert detail.messages[0]["role"] == "user"

    def test_default_values(self):
        detail = SessionDetail(session_id="x")
        assert detail.role == ""
        assert detail.model == ""
        assert detail.message_count == 0
        assert detail.description == ""
        assert detail.sub_sessions == []
        assert detail.messages == []

    def test_serialization(self):
        detail = SessionDetail(
            session_id="s1",
            messages=[{"role": "assistant", "content": "hi"}],
        )
        data = detail.model_dump()
        assert data["messages"][0]["content"] == "hi"


class TestSessionLoadResponse:
    def test_success_with_defaults(self):
        resp = SessionLoadResponse(success=True, message="会话已加载")
        assert resp.success is True
        assert resp.session_id == ""
        assert resp.messages == []

    def test_success_with_data(self):
        resp = SessionLoadResponse(
            success=True,
            message="会话已加载",
            session_id="s1",
            messages=[{"role": "user", "content": "hello"}],
        )
        assert resp.session_id == "s1"
        assert len(resp.messages) == 1

    def test_failure(self):
        resp = SessionLoadResponse(success=False, message="加载失败")
        assert resp.success is False
        assert resp.session_id == ""

    def test_default_values(self):
        resp = SessionLoadResponse(success=False, message="err")
        assert resp.session_id == ""
        assert resp.messages == []

    def test_serialization(self):
        resp = SessionLoadResponse(success=True, message="ok", session_id="abc", messages=[])
        data = resp.model_dump()
        assert data == {"success": True, "message": "ok", "session_id": "abc", "messages": []}
