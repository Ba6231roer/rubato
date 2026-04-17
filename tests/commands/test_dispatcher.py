import pytest

from src.commands.base import BaseCommand
from src.commands.context import CommandContext
from src.commands.dispatcher import CommandDispatcher
from src.commands.models import CommandResult, ResultType
from src.commands.registry import CommandRegistry


class _TestCmd(BaseCommand):
    name = "test"
    aliases = ["t"]
    description = "Test command"

    async def execute(self, args, context):
        return CommandResult(type=ResultType.SUCCESS, message=f"test:{args}")


class _ExitCmd(BaseCommand):
    name = "exitcmd"
    description = "Exit command"

    async def execute(self, args, context):
        return CommandResult(type=ResultType.EXIT, message="bye")


class _ValidateCmd(BaseCommand):
    name = "validate"
    description = "Command with validation"

    def validate_args(self, args):
        if not args:
            return "参数不能为空"
        return None

    async def execute(self, args, context):
        return CommandResult(type=ResultType.SUCCESS, message=f"valid:{args}")


@pytest.fixture(autouse=True)
def _reset_registry():
    CommandRegistry._instance = None
    yield
    CommandRegistry._instance = None


@pytest.fixture
def context():
    return CommandContext()


@pytest.fixture
def dispatcher(context):
    return CommandDispatcher(context)


class TestParseInput:
    def test_parse_command_with_args(self, dispatcher):
        cmd, args = dispatcher.parse_input("/test hello world")
        assert cmd == "test"
        assert args == "hello world"

    def test_parse_command_without_args(self, dispatcher):
        cmd, args = dispatcher.parse_input("/test")
        assert cmd == "test"
        assert args == ""

    def test_parse_command_case_insensitive(self, dispatcher):
        cmd, args = dispatcher.parse_input("/TEST")
        assert cmd == "test"

    def test_parse_non_command_returns_none(self, dispatcher):
        cmd, args = dispatcher.parse_input("hello world")
        assert cmd is None
        assert args == "hello world"

    def test_parse_empty_input(self, dispatcher):
        cmd, args = dispatcher.parse_input("")
        assert cmd is None
        assert args == ""

    def test_parse_whitespace_only(self, dispatcher):
        cmd, args = dispatcher.parse_input("   ")
        assert cmd is None
        assert args == ""

    def test_parse_command_with_leading_whitespace(self, dispatcher):
        cmd, args = dispatcher.parse_input("  /test arg1")
        assert cmd == "test"
        assert args == "arg1"

    def test_parse_slash_only(self, dispatcher):
        with pytest.raises(IndexError):
            dispatcher.parse_input("/")


class TestDispatch:
    async def test_dispatch_registered_command(self, dispatcher):
        registry = CommandRegistry()
        registry.register(_TestCmd)
        result = await dispatcher.dispatch("/test hello")
        assert result is not None
        assert result.type == ResultType.SUCCESS
        assert result.message == "test:hello"

    async def test_dispatch_command_without_args(self, dispatcher):
        registry = CommandRegistry()
        registry.register(_TestCmd)
        result = await dispatcher.dispatch("/test")
        assert result is not None
        assert result.message == "test:"

    async def test_dispatch_non_command_returns_none(self, dispatcher):
        result = await dispatcher.dispatch("hello world")
        assert result is None

    async def test_dispatch_empty_input_returns_none(self, dispatcher):
        result = await dispatcher.dispatch("")
        assert result is None


class TestUnknownCommand:
    async def test_dispatch_unknown_command(self, dispatcher):
        result = await dispatcher.dispatch("/unknown")
        assert result is not None
        assert result.type == ResultType.ERROR
        assert "未知命令" in result.message

    async def test_unknown_command_suggests_help(self, dispatcher):
        result = await dispatcher.dispatch("/nonexistent")
        assert "/help" in result.message


class TestExitCommand:
    async def test_exit_sets_running_false(self, dispatcher):
        registry = CommandRegistry()
        registry.register(_ExitCmd)
        assert dispatcher.is_running() is True
        await dispatcher.dispatch("/exitcmd")
        assert dispatcher.is_running() is False

    async def test_normal_command_keeps_running(self, dispatcher):
        registry = CommandRegistry()
        registry.register(_TestCmd)
        assert dispatcher.is_running() is True
        await dispatcher.dispatch("/test")
        assert dispatcher.is_running() is True


class TestValidation:
    async def test_validation_error_returns_error_result(self, dispatcher):
        registry = CommandRegistry()
        registry.register(_ValidateCmd)
        result = await dispatcher.dispatch("/validate")
        assert result is not None
        assert result.type == ResultType.ERROR
        assert "参数不能为空" in result.message

    async def test_validation_pass_dispatches(self, dispatcher):
        registry = CommandRegistry()
        registry.register(_ValidateCmd)
        result = await dispatcher.dispatch("/validate ok")
        assert result is not None
        assert result.type == ResultType.SUCCESS
        assert result.message == "valid:ok"


class TestContextPassing:
    async def test_context_is_passed_to_command(self):
        ctx = CommandContext(session_id="test-session-123")
        registry = CommandRegistry()

        class _ContextCheck(BaseCommand):
            name = "ctxcheck"
            description = "Context check"

            async def execute(self, args, context):
                return CommandResult(
                    type=ResultType.SUCCESS,
                    message=context.session_id or "no-session"
                )

        registry.register(_ContextCheck)
        disp = CommandDispatcher(ctx)
        result = await disp.dispatch("/ctxcheck")
        assert result.message == "test-session-123"
