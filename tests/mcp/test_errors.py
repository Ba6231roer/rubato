import pytest
from src.mcp.errors import MCPError, MCPConnectionError, MCPToolCallError


class TestMCPErrorHierarchy:
    def test_mcp_error_is_exception(self):
        assert issubclass(MCPError, Exception)

    def test_mcp_connection_error_inherits_mcp_error(self):
        assert issubclass(MCPConnectionError, MCPError)

    def test_mcp_tool_call_error_inherits_mcp_error(self):
        assert issubclass(MCPToolCallError, MCPError)

    def test_mcp_connection_error_is_not_mcp_tool_call_error(self):
        assert not issubclass(MCPConnectionError, MCPToolCallError)

    def test_mcp_tool_call_error_is_not_mcp_connection_error(self):
        assert not issubclass(MCPToolCallError, MCPConnectionError)


class TestMCPErrorMessages:
    def test_mcp_error_message(self):
        err = MCPError("基础错误")
        assert str(err) == "基础错误"

    def test_mcp_connection_error_message(self):
        err = MCPConnectionError("连接失败")
        assert str(err) == "连接失败"

    def test_mcp_tool_call_error_message(self):
        err = MCPToolCallError("工具调用失败")
        assert str(err) == "工具调用失败"

    def test_mcp_error_empty_message(self):
        err = MCPError()
        assert str(err) == ""


class TestMCPErrorCatching:
    def test_catch_connection_error_as_mcp_error(self):
        with pytest.raises(MCPError):
            raise MCPConnectionError("连接错误")

    def test_catch_tool_call_error_as_mcp_error(self):
        with pytest.raises(MCPError):
            raise MCPToolCallError("工具错误")

    def test_catch_connection_error_as_exception(self):
        with pytest.raises(Exception):
            raise MCPConnectionError("连接错误")

    def test_catch_specific_not_cross(self):
        with pytest.raises(MCPConnectionError):
            raise MCPConnectionError("连接错误")

        with pytest.raises(MCPToolCallError):
            raise MCPToolCallError("工具错误")

    def test_mcp_error_not_caught_by_subclass(self):
        with pytest.raises(MCPError):
            raise MCPError("基础错误")

        with pytest.raises(MCPError):
            try:
                raise MCPError("基础错误")
            except MCPConnectionError:
                pytest.fail("MCPError 不应被 MCPConnectionError 捕获")


class TestMCPErrorAttributes:
    def test_mcp_error_args(self):
        err = MCPError("test message")
        assert err.args == ("test message",)

    def test_mcp_connection_error_is_instance_of_mcp_error(self):
        err = MCPConnectionError("连接失败")
        assert isinstance(err, MCPError)

    def test_mcp_tool_call_error_is_instance_of_mcp_error(self):
        err = MCPToolCallError("工具错误")
        assert isinstance(err, MCPError)

    def test_mcp_error_is_not_instance_of_subclass(self):
        err = MCPError("基础")
        assert not isinstance(err, MCPConnectionError)
        assert not isinstance(err, MCPToolCallError)
