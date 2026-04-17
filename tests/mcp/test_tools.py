import pytest
from unittest.mock import MagicMock
from src.mcp.tools import ToolRegistry, ToolProvider, ProviderType


def _make_tool(name: str, description: str = ""):
    tool = MagicMock()
    tool.name = name
    tool.description = description or f"{name} tool"
    return tool


class TestToolRegistryRegister:
    def test_register_single_tool(self):
        registry = ToolRegistry()
        tool = _make_tool("tool_a")
        registry.register(tool)
        assert registry.get_tool("tool_a") is tool

    def test_register_multiple_tools(self):
        registry = ToolRegistry()
        tool_a = _make_tool("tool_a")
        tool_b = _make_tool("tool_b")
        registry.register(tool_a)
        registry.register(tool_b)
        assert registry.get_tool("tool_a") is tool_a
        assert registry.get_tool("tool_b") is tool_b

    def test_register_duplicate_name_overwrites(self):
        registry = ToolRegistry()
        tool_v1 = _make_tool("tool_a", "v1")
        tool_v2 = _make_tool("tool_a", "v2")
        registry.register(tool_v1)
        registry.register(tool_v2)
        assert registry.get_tool("tool_a") is tool_v2

    def test_register_all(self):
        registry = ToolRegistry()
        tools = [_make_tool("t1"), _make_tool("t2"), _make_tool("t3")]
        registry.register_all(tools)
        assert len(registry.get_all_tools()) == 3


class TestToolRegistryUnregister:
    def test_unregister_existing_tool(self):
        registry = ToolRegistry()
        registry.register(_make_tool("tool_a"))
        registry.unregister("tool_a")
        assert registry.get_tool("tool_a") is None

    def test_unregister_nonexistent_tool_no_error(self):
        registry = ToolRegistry()
        registry.unregister("nonexistent")

    def test_unregister_then_reregister(self):
        registry = ToolRegistry()
        tool = _make_tool("tool_a")
        registry.register(tool)
        registry.unregister("tool_a")
        assert registry.get_tool("tool_a") is None
        tool2 = _make_tool("tool_a")
        registry.register(tool2)
        assert registry.get_tool("tool_a") is tool2


class TestToolRegistryGetTool:
    def test_get_tool_existing(self):
        registry = ToolRegistry()
        tool = _make_tool("my_tool")
        registry.register(tool)
        assert registry.get_tool("my_tool") is tool

    def test_get_tool_nonexistent_returns_none(self):
        registry = ToolRegistry()
        assert registry.get_tool("no_such_tool") is None

    def test_get_tool_after_unregister(self):
        registry = ToolRegistry()
        registry.register(_make_tool("tool_a"))
        registry.unregister("tool_a")
        assert registry.get_tool("tool_a") is None


class TestToolRegistryGetAllTools:
    def test_empty_registry(self):
        registry = ToolRegistry()
        assert registry.get_all_tools() == []

    def test_returns_all_registered_tools(self):
        registry = ToolRegistry()
        t1 = _make_tool("t1")
        t2 = _make_tool("t2")
        registry.register(t1)
        registry.register(t2)
        tools = registry.get_all_tools()
        assert len(tools) == 2
        names = {t.name for t in tools}
        assert names == {"t1", "t2"}

    def test_dedup_with_provider(self):
        registry = ToolRegistry()
        direct_tool = _make_tool("shared_name", "direct")
        provider_tool = _make_tool("shared_name", "from_provider")
        registry.register(direct_tool)
        registry.register_provider(_FakeProvider([provider_tool]))
        tools = registry.get_all_tools()
        names = [t.name for t in tools]
        assert names.count("shared_name") == 1
        assert registry.get_tool("shared_name") is direct_tool

    def test_provider_tools_not_overwriting_direct(self):
        registry = ToolRegistry()
        direct = _make_tool("t1", "direct")
        registry.register(direct)
        registry.register_provider(_FakeProvider([_make_tool("t1", "provider")]))
        tools = registry.get_all_tools()
        assert len(tools) == 1
        assert tools[0].description == "direct"


class TestToolRegistryListToolNames:
    def test_empty(self):
        registry = ToolRegistry()
        assert registry.list_tool_names() == []

    def test_returns_names(self):
        registry = ToolRegistry()
        registry.register(_make_tool("alpha"))
        registry.register(_make_tool("beta"))
        names = registry.list_tool_names()
        assert set(names) == {"alpha", "beta"}


class TestToolRegistryGetToolsByNames:
    def test_empty_registry(self):
        registry = ToolRegistry()
        assert registry.get_tools_by_names(["a"]) == []

    def test_select_subset(self):
        registry = ToolRegistry()
        registry.register(_make_tool("t1"))
        registry.register(_make_tool("t2"))
        registry.register(_make_tool("t3"))
        result = registry.get_tools_by_names(["t1", "t3"])
        assert len(result) == 2
        names = {t.name for t in result}
        assert names == {"t1", "t3"}

    def test_nonexistent_names_ignored(self):
        registry = ToolRegistry()
        registry.register(_make_tool("t1"))
        result = registry.get_tools_by_names(["t1", "nope"])
        assert len(result) == 1
        assert result[0].name == "t1"


class _FakeProvider:
    def __init__(self, tools):
        self._tools = tools

    def get_tools(self):
        return self._tools


class TestToolRegistryProvider:
    def test_register_callable_provider(self):
        registry = ToolRegistry()
        tool = _make_tool("from_callable")
        registry.register_provider(lambda: [tool])
        tools = registry.get_all_tools()
        assert len(tools) == 1
        assert tools[0].name == "from_callable"

    def test_register_protocol_provider(self):
        registry = ToolRegistry()
        provider = _FakeProvider([_make_tool("from_protocol")])
        registry.register_provider(provider)
        tools = registry.get_all_tools()
        assert len(tools) == 1
        assert tools[0].name == "from_protocol"

    def test_multiple_providers(self):
        registry = ToolRegistry()
        registry.register_provider(lambda: [_make_tool("p1_t1")])
        registry.register_provider(_FakeProvider([_make_tool("p2_t1")]))
        tools = registry.get_all_tools()
        assert len(tools) == 2

    def test_provider_and_direct_combined(self):
        registry = ToolRegistry()
        registry.register(_make_tool("direct_tool"))
        registry.register_provider(lambda: [_make_tool("provider_tool")])
        tools = registry.get_all_tools()
        assert len(tools) == 2
        names = {t.name for t in tools}
        assert names == {"direct_tool", "provider_tool"}


class TestToolProviderProtocol:
    def test_protocol_compliance(self):
        class MyProvider:
            def get_tools(self):
                return []

        provider = MyProvider()
        assert isinstance(provider, ToolProvider)

    def test_protocol_non_compliance(self):
        class NotAProvider:
            pass

        obj = NotAProvider()
        assert not isinstance(obj, ToolProvider)

    def test_callable_is_valid_provider_type(self):
        def my_func():
            return [_make_tool("x")]

        assert callable(my_func)
        tools = my_func()
        assert len(tools) == 1
