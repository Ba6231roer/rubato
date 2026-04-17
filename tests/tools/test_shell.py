import pytest
import sys
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.tools.shell import RubatoShellInput, RubatoShellTool
from src.tools.provider import ShellToolProvider


class TestRubatoShellInput:
    """RubatoShellInput 模型验证测试"""

    def test_plain_command(self):
        inp = RubatoShellInput(commands="git status")
        assert inp.commands == "git status"

    def test_single_element_json_array_unwrap(self):
        inp = RubatoShellInput(commands='["git status"]')
        assert inp.commands == "git status"

    def test_multi_element_json_array_join(self):
        inp = RubatoShellInput(commands='["git status", "git log"]')
        assert inp.commands == "git status && git log"

    def test_invalid_json_stays_unchanged(self):
        inp = RubatoShellInput(commands="[invalid json")
        assert inp.commands == "[invalid json"

    def test_json_object_stays_unchanged(self):
        inp = RubatoShellInput(commands='{"key": "value"}')
        assert inp.commands == '{"key": "value"}'

    def test_empty_string_stays_unchanged(self):
        inp = RubatoShellInput(commands="")
        assert inp.commands == ""

    def test_non_json_bracket_stays(self):
        inp = RubatoShellInput(commands="[not a json array")
        assert inp.commands == "[not a json array"


class TestRubatoShellTool:
    """RubatoShellTool 测试"""

    def test_tool_name(self):
        tool = RubatoShellTool()
        assert tool.name == "terminal"

    def test_tool_args_schema(self):
        tool = RubatoShellTool()
        assert tool.args_schema == RubatoShellInput

    def test_run_converts_string_to_list(self):
        tool = RubatoShellTool()
        mock_process = Mock()
        mock_process.run.return_value = "output"
        tool.process = mock_process

        result = tool._run(commands="git status")
        mock_process.run.assert_called_once_with(["git status"])
        assert result == "output"

    def test_run_with_list_commands(self):
        tool = RubatoShellTool()
        mock_process = Mock()
        mock_process.run.return_value = "output"
        tool.process = mock_process

        result = tool._run(commands=["git status", "git log"])
        mock_process.run.assert_called_once_with(["git status", "git log"])
        assert result == "output"


class TestShellToolProviderIntegration:
    """ShellToolProvider 集成测试"""

    def test_provider_returns_terminal_tool(self):
        provider = ShellToolProvider()
        tools = provider.get_tools()
        assert len(tools) == 1
        assert tools[0].name == "terminal"

    def test_provider_tool_description(self):
        provider = ShellToolProvider()
        tools = provider.get_tools()
        tool = tools[0]
        assert tool.args_schema == RubatoShellInput

    def test_provider_is_available(self):
        provider = ShellToolProvider()
        assert provider.is_available() is True
