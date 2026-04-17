import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from io import StringIO

from src.cli.console import Console
from src.commands.dispatcher import CommandDispatcher
from src.commands.context import CommandContext
from src.commands.models import CommandResult, ResultType


def _make_mock_agent():
    agent = AsyncMock()
    agent.config = MagicMock()
    agent.config.model = MagicMock()
    agent.config.model.model = MagicMock()
    agent.config.model.model.name = "test-model"
    agent.config.model.model.provider = "test-provider"
    agent.run = AsyncMock(return_value="Agent response")
    return agent


def _make_mock_skill_loader():
    loader = MagicMock()
    loader.list_skills.return_value = []
    return loader


def _make_mock_mcp_manager(connected=False, browser_alive=False):
    mgr = MagicMock()
    mgr.is_connected = connected
    mgr.browser_alive = browser_alive
    return mgr


def _make_mock_config():
    config = MagicMock()
    config.model = MagicMock()
    config.model.model = MagicMock()
    config.model.model.name = "gpt-4"
    return config


def _make_console(
    agent=None,
    skill_loader=None,
    mcp_manager=None,
    config=None,
    role_manager=None,
    config_loader=None,
    app_state=None,
):
    agent = agent or _make_mock_agent()
    skill_loader = skill_loader or _make_mock_skill_loader()
    return Console(
        agent=agent,
        skill_loader=skill_loader,
        mcp_manager=mcp_manager,
        config=config,
        role_manager=role_manager,
        config_loader=config_loader,
        app_state=app_state,
    )


class TestInputParsing:
    def test_slash_prefix_recognized_as_command(self):
        dispatcher = CommandDispatcher(CommandContext())
        cmd_name, args = dispatcher.parse_input("/help")
        assert cmd_name == "help"
        assert args == ""

    def test_slash_prefix_with_args(self):
        dispatcher = CommandDispatcher(CommandContext())
        cmd_name, args = dispatcher.parse_input("/role list")
        assert cmd_name == "role"
        assert args == "list"

    def test_slash_prefix_with_multi_word_args(self):
        dispatcher = CommandDispatcher(CommandContext())
        cmd_name, args = dispatcher.parse_input("/skill show my_skill")
        assert cmd_name == "skill"
        assert args == "show my_skill"

    def test_natural_language_returns_none_cmd(self):
        dispatcher = CommandDispatcher(CommandContext())
        cmd_name, args = dispatcher.parse_input("hello world")
        assert cmd_name is None
        assert args == "hello world"

    def test_empty_input_returns_none_cmd(self):
        dispatcher = CommandDispatcher(CommandContext())
        cmd_name, args = dispatcher.parse_input("")
        assert cmd_name is None
        assert args == ""

    def test_whitespace_only_returns_none_cmd(self):
        dispatcher = CommandDispatcher(CommandContext())
        cmd_name, args = dispatcher.parse_input("   ")
        assert cmd_name is None
        assert args == ""

    def test_slash_command_case_insensitive(self):
        dispatcher = CommandDispatcher(CommandContext())
        cmd_name, args = dispatcher.parse_input("/HELP")
        assert cmd_name == "help"

    def test_slash_command_with_leading_whitespace(self):
        dispatcher = CommandDispatcher(CommandContext())
        cmd_name, args = dispatcher.parse_input("  /quit")
        assert cmd_name == "quit"

    def test_question_mark_not_command(self):
        dispatcher = CommandDispatcher(CommandContext())
        cmd_name, args = dispatcher.parse_input("what is this?")
        assert cmd_name is None
        assert args == "what is this?"


class TestCommandDispatch:
    @pytest.mark.asyncio
    async def test_dispatch_command_returns_result(self):
        dispatcher = CommandDispatcher(CommandContext())
        result = await dispatcher.dispatch("/help")
        assert result is not None
        assert isinstance(result, CommandResult)

    @pytest.mark.asyncio
    async def test_dispatch_natural_language_returns_none(self):
        dispatcher = CommandDispatcher(CommandContext())
        result = await dispatcher.dispatch("hello agent")
        assert result is None

    @pytest.mark.asyncio
    async def test_dispatch_empty_returns_none(self):
        dispatcher = CommandDispatcher(CommandContext())
        result = await dispatcher.dispatch("")
        assert result is None

    @pytest.mark.asyncio
    async def test_dispatch_unknown_command_returns_error(self):
        dispatcher = CommandDispatcher(CommandContext())
        result = await dispatcher.dispatch("/nonexistent")
        assert result is not None
        assert result.type == ResultType.ERROR
        assert "未知命令" in result.message

    @pytest.mark.asyncio
    async def test_dispatch_quit_stops_running(self):
        dispatcher = CommandDispatcher(CommandContext())
        assert dispatcher.is_running() is True
        await dispatcher.dispatch("/quit")
        assert dispatcher.is_running() is False


class TestMainLoopFlow:
    @pytest.mark.asyncio
    async def test_command_input_dispatched_to_dispatcher(self):
        console = _make_console()
        mock_result = CommandResult(type=ResultType.SUCCESS, message="ok")
        with patch.object(
            console.dispatcher, "dispatch", new_callable=AsyncMock, return_value=mock_result
        ) as mock_dispatch:
            with patch("builtins.input", return_value="/help"):
                with patch("builtins.print"):
                    console.dispatcher._running = False
                    await console.run()
            mock_dispatch.assert_awaited_once_with("/help")

    @pytest.mark.asyncio
    async def test_natural_language_dispatched_to_agent(self):
        agent = _make_mock_agent()
        console = _make_console(agent=agent)
        with patch.object(
            console.dispatcher, "dispatch", new_callable=AsyncMock, return_value=None
        ):
            with patch("builtins.input", return_value="hello"):
                with patch("builtins.print"):
                    console.dispatcher._running = False
                    await console.run()
            agent.run.assert_awaited_once_with("hello")

    @pytest.mark.asyncio
    async def test_empty_input_skipped(self):
        agent = _make_mock_agent()
        console = _make_console(agent=agent)
        call_count = 0
        original_dispatch = console.dispatcher.dispatch

        async def dispatch_side_effect(user_input):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                console.dispatcher._running = False
            return await original_dispatch(user_input)

        with patch.object(
            console.dispatcher, "dispatch", side_effect=dispatch_side_effect
        ):
            with patch("builtins.input", return_value="   "):
                with patch("builtins.print"):
                    await console.run()
            agent.run.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_keyboard_interrupt_handled(self):
        console = _make_console()

        async def run_once_then_interrupt(user_input):
            console.dispatcher._running = False
            raise KeyboardInterrupt()

        with patch.object(
            console.dispatcher, "dispatch", new_callable=AsyncMock
        ) as mock_dispatch:
            mock_dispatch.side_effect = run_once_then_interrupt
            with patch("builtins.input", return_value="/help"):
                with patch("builtins.print"):
                    await console.run()

    @pytest.mark.asyncio
    async def test_eof_error_exits_loop(self):
        console = _make_console()
        with patch("builtins.input", side_effect=EOFError):
            with patch("builtins.print"):
                await console.run()

    @pytest.mark.asyncio
    async def test_generic_exception_handled(self):
        console = _make_console()
        call_count = 0

        async def dispatch_then_stop(user_input):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                console.dispatcher._running = False
            raise RuntimeError("test error")

        with patch.object(
            console.dispatcher, "dispatch", side_effect=dispatch_then_stop
        ):
            with patch("builtins.input", return_value="/help"):
                with patch("builtins.print"):
                    await console.run()


class TestBannerGeneration:
    def test_banner_contains_rubato_title(self, capsys):
        console = _make_console()
        console._print_banner()
        captured = capsys.readouterr()
        assert "Rubato" in captured.out

    def test_banner_with_config_shows_model(self, capsys):
        config = _make_mock_config()
        console = _make_console(config=config)
        console._print_banner()
        captured = capsys.readouterr()
        assert "gpt-4" in captured.out

    def test_banner_without_config_no_model(self, capsys):
        console = _make_console(config=None)
        console._print_banner()
        captured = capsys.readouterr()
        assert "模型:" not in captured.out

    def test_banner_with_connected_mcp(self, capsys):
        mcp = _make_mock_mcp_manager(connected=True, browser_alive=True)
        console = _make_console(mcp_manager=mcp)
        console._print_banner()
        captured = capsys.readouterr()
        assert "已连接" in captured.out
        assert "运行中" in captured.out

    def test_banner_with_disconnected_mcp(self, capsys):
        mcp = _make_mock_mcp_manager(connected=False)
        console = _make_console(mcp_manager=mcp)
        console._print_banner()
        captured = capsys.readouterr()
        assert "未连接" in captured.out

    def test_banner_without_mcp_no_status(self, capsys):
        console = _make_console(mcp_manager=None)
        console._print_banner()
        captured = capsys.readouterr()
        assert "MCP:" not in captured.out

    def test_banner_with_skills(self, capsys):
        skill_loader = _make_mock_skill_loader()
        mock_skill = MagicMock()
        mock_skill.name = "test_skill"
        skill_loader.list_skills.return_value = [mock_skill]
        console = _make_console(skill_loader=skill_loader)
        console._print_banner()
        captured = capsys.readouterr()
        assert "test_skill" in captured.out

    def test_banner_shows_help_hint(self, capsys):
        console = _make_console()
        console._print_banner()
        captured = capsys.readouterr()
        assert "/help" in captured.out
        assert "/quit" in captured.out

    def test_banner_has_box_drawing(self, capsys):
        console = _make_console()
        console._print_banner()
        captured = capsys.readouterr()
        assert "╔" in captured.out
        assert "╚" in captured.out


class TestOutputFormatting:
    def test_command_result_to_text(self):
        result = CommandResult(type=ResultType.SUCCESS, message="操作成功")
        assert result.to_text() == "操作成功"

    def test_command_result_to_dict(self):
        result = CommandResult(
            type=ResultType.SUCCESS,
            message="ok",
            data={"key": "value"},
            actions=["action1"],
        )
        d = result.to_dict()
        assert d["type"] == "success"
        assert d["message"] == "ok"
        assert d["data"]["key"] == "value"
        assert d["actions"] == ["action1"]

    def test_error_result_to_text(self):
        result = CommandResult(type=ResultType.ERROR, message="未知命令：foo")
        assert "未知命令" in result.to_text()

    def test_exit_result_to_text(self):
        result = CommandResult(type=ResultType.EXIT, message="再见！")
        assert result.to_text() == "再见！"

    @pytest.mark.asyncio
    async def test_command_result_printed_via_to_text(self, capsys):
        console = _make_console()
        mock_result = CommandResult(type=ResultType.SUCCESS, message="hello output")
        with patch.object(
            console.dispatcher, "dispatch", new_callable=AsyncMock, return_value=mock_result
        ):
            with patch("builtins.input", return_value="/help"):
                with patch("builtins.print") as mock_print:
                    console.dispatcher._running = False
                    await console.run()
        mock_print.assert_any_call("hello output")

    @pytest.mark.asyncio
    async def test_agent_response_printed(self, capsys):
        agent = _make_mock_agent()
        agent.run = AsyncMock(return_value="Agent says hi")
        console = _make_console(agent=agent)
        with patch.object(
            console.dispatcher, "dispatch", new_callable=AsyncMock, return_value=None
        ):
            with patch("builtins.input", return_value="hello"):
                with patch("builtins.print") as mock_print:
                    console.dispatcher._running = False
                    await console.run()
        mock_print.assert_any_call("\nAgent says hi")


class TestConsoleInit:
    def test_console_creates_dispatcher(self):
        console = _make_console()
        assert isinstance(console.dispatcher, CommandDispatcher)

    def test_console_stores_agent(self):
        agent = _make_mock_agent()
        console = _make_console(agent=agent)
        assert console.agent is agent

    def test_console_stores_skill_loader(self):
        loader = _make_mock_skill_loader()
        console = _make_console(skill_loader=loader)
        assert console.skill_loader is loader

    def test_console_stores_config(self):
        config = _make_mock_config()
        console = _make_console(config=config)
        assert console.config is config

    def test_console_stores_mcp_manager(self):
        mcp = _make_mock_mcp_manager()
        console = _make_console(mcp_manager=mcp)
        assert console.mcp_manager is mcp

    def test_console_dispatcher_context_has_agent(self):
        agent = _make_mock_agent()
        console = _make_console(agent=agent)
        assert console.dispatcher.context.agent is agent

    def test_console_with_app_state_passes_agent_pool(self):
        app_state = MagicMock()
        app_state.agent_pool = MagicMock()
        console = _make_console(app_state=app_state)
        assert console.dispatcher.context.agent_pool is app_state.agent_pool


class TestRunSync:
    def test_run_sync_calls_asyncio_run(self):
        console = _make_console()
        with patch("asyncio.run") as mock_run:
            console.run_sync()
            mock_run.assert_called_once()
