import pytest
import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from langchain_core.tools import BaseTool, StructuredTool

from src.tools.provider import ToolProvider, LocalToolProvider, ShellToolProvider


class TestToolProviderABC:
    """ToolProvider 抽象基类测试"""

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            ToolProvider()

    def test_incomplete_subclass_cannot_instantiate(self):
        class IncompleteProvider(ToolProvider):
            def get_tools(self):
                return []

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_complete_subclass_can_instantiate(self):
        class CompleteProvider(ToolProvider):
            def get_tools(self):
                return []

            def is_available(self):
                return True

        provider = CompleteProvider()
        assert provider.get_tools() == []
        assert provider.is_available() is True


class TestLocalToolProvider:
    """LocalToolProvider 测试"""

    def test_init_with_empty_list(self):
        provider = LocalToolProvider()
        assert provider.get_tools() == []
        assert provider.is_available() is True

    def test_init_with_tool_instance(self):
        mock_tool = Mock(spec=BaseTool)
        provider = LocalToolProvider(tool_classes=[mock_tool])
        tools = provider.get_tools()
        assert len(tools) == 1
        assert tools[0] is mock_tool

    def test_init_with_tool_class(self):
        class FakeTool(BaseTool):
            name: str = "fake_tool"
            description: str = "fake tool for testing"

            def _run(self, *args, **kwargs):
                return "ok"

        provider = LocalToolProvider(tool_classes=[FakeTool])
        tools = provider.get_tools()
        assert len(tools) == 1
        assert isinstance(tools[0], FakeTool)
        assert tools[0].name == "fake_tool"

    def test_add_tool_instance(self):
        mock_tool = Mock(spec=BaseTool)
        provider = LocalToolProvider()
        provider.add_tool(mock_tool)
        tools = provider.get_tools()
        assert len(tools) == 1
        assert tools[0] is mock_tool

    def test_add_tool_class(self):
        class AnotherTool(BaseTool):
            name: str = "another_tool"
            description: str = "another tool for testing"

            def _run(self, *args, **kwargs):
                return "ok"

        provider = LocalToolProvider()
        provider.add_tool(AnotherTool)
        tools = provider.get_tools()
        assert len(tools) == 1
        assert isinstance(tools[0], AnotherTool)

    def test_is_available_always_true(self):
        provider = LocalToolProvider()
        assert provider.is_available() is True


class TestShellToolProvider:
    """ShellToolProvider 测试"""

    def test_get_tools_returns_list(self):
        provider = ShellToolProvider()
        tools = provider.get_tools()
        assert isinstance(tools, list)
        assert len(tools) == 1

    def test_tool_name_is_terminal(self):
        provider = ShellToolProvider()
        tools = provider.get_tools()
        assert tools[0].name == "terminal"

    def test_is_available(self):
        provider = ShellToolProvider()
        assert provider.is_available() is True
