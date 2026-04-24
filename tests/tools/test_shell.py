import pytest
import sys
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.tools.shell import RubatoShellInput, RubatoShellTool, _SYSTEM_ENCODING
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


class TestDecodeOutput:
    """_decode_output 编码解码测试"""

    def test_decode_utf8_output(self):
        raw = "你好世界".encode("utf-8")
        result = RubatoShellTool._decode_output(raw)
        assert result == "你好世界"

    def test_decode_system_encoding_output(self):
        raw = "你好世界".encode(_SYSTEM_ENCODING)
        result = RubatoShellTool._decode_output(raw)
        assert result == "你好世界"

    def test_decode_invalid_bytes_fallback_to_replace(self):
        raw = b'\xc7\xec\xbd\xe7'
        result = RubatoShellTool._decode_output(raw)
        assert isinstance(result, str)

    def test_decode_empty_bytes(self):
        result = RubatoShellTool._decode_output(b"")
        assert result == ""


class TestRubatoShellTool:
    """RubatoShellTool 测试"""

    def test_tool_name(self):
        tool = RubatoShellTool()
        assert tool.name == "terminal"

    def test_tool_args_schema(self):
        tool = RubatoShellTool()
        assert tool.args_schema == RubatoShellInput

    @patch("src.tools.shell.subprocess.run")
    def test_run_string_command(self, mock_run):
        mock_run.return_value = Mock(stdout=b"output")

        tool = RubatoShellTool()
        result = tool._run(commands="git status")

        mock_run.assert_called_once()
        assert "git status" in mock_run.call_args[0][0]
        assert result == "output"

    @patch("src.tools.shell.subprocess.run")
    def test_run_joins_list_commands(self, mock_run):
        mock_run.return_value = Mock(stdout=b"output")

        tool = RubatoShellTool()
        result = tool._run(commands=["git status", "git log"])

        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == "git status && git log"
        assert result == "output"

    @patch("src.tools.shell.subprocess.run")
    def test_run_returns_error_output_on_failure(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "cmd", output=b"error details"
        )

        tool = RubatoShellTool()
        result = tool._run(commands="bad_command")

        assert result == "error details"

    @patch("src.tools.shell.subprocess.run")
    def test_run_handles_gbk_encoded_output(self, mock_run):
        mock_run.return_value = Mock(stdout="中文输出".encode("gbk"))

        tool = RubatoShellTool()
        result = tool._run(commands="echo 中文输出")

        assert "中文" in result


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
