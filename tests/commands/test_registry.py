import pytest

from src.commands.base import BaseCommand
from src.commands.models import CommandResult, ResultType
from src.commands.registry import CommandRegistry, command
from src.commands.context import CommandContext


class _DummyCommand(BaseCommand):
    name = "dummy"
    aliases = ["d"]
    description = "A dummy command for testing"

    async def execute(self, args, context):
        return CommandResult(type=ResultType.SUCCESS, message="dummy executed")


class _AnotherCommand(BaseCommand):
    name = "another"
    aliases = ["a", "alt"]
    description = "Another test command"

    async def execute(self, args, context):
        return CommandResult(type=ResultType.SUCCESS, message="another executed")


class _AliasCommand(BaseCommand):
    name = "aliased"
    aliases = ["al1", "al2"]
    description = "Command with multiple aliases"

    async def execute(self, args, context):
        return CommandResult(type=ResultType.SUCCESS, message="aliased executed")


@pytest.fixture(autouse=True)
def _reset_registry():
    CommandRegistry._instance = None
    yield
    CommandRegistry._instance = None


class TestCommandRegistrySingleton:
    def test_singleton_returns_same_instance(self):
        r1 = CommandRegistry()
        r2 = CommandRegistry()
        assert r1 is r2

    def test_fresh_instance_has_no_commands(self):
        registry = CommandRegistry()
        assert registry.list_commands() == []


class TestRegister:
    def test_register_command(self):
        registry = CommandRegistry()
        registry.register(_DummyCommand)
        assert "dummy" in registry.list_commands()

    def test_register_multiple_commands(self):
        registry = CommandRegistry()
        registry.register(_DummyCommand)
        registry.register(_AnotherCommand)
        names = registry.list_commands()
        assert "dummy" in names
        assert "another" in names

    def test_register_stores_aliases(self):
        registry = CommandRegistry()
        registry.register(_AliasCommand)
        assert registry.get("al1") is _AliasCommand
        assert registry.get("al2") is _AliasCommand


class TestGet:
    def test_get_by_name(self):
        registry = CommandRegistry()
        registry.register(_DummyCommand)
        assert registry.get("dummy") is _DummyCommand

    def test_get_by_alias(self):
        registry = CommandRegistry()
        registry.register(_DummyCommand)
        assert registry.get("d") is _DummyCommand

    def test_get_nonexistent_returns_none(self):
        registry = CommandRegistry()
        assert registry.get("nonexistent") is None

    def test_get_alias_returns_correct_class(self):
        registry = CommandRegistry()
        registry.register(_AliasCommand)
        result = registry.get("al1")
        assert result is _AliasCommand
        result = registry.get("al2")
        assert result is _AliasCommand


class TestListCommands:
    def test_list_empty(self):
        registry = CommandRegistry()
        assert registry.list_commands() == []

    def test_list_returns_command_names(self):
        registry = CommandRegistry()
        registry.register(_DummyCommand)
        registry.register(_AnotherCommand)
        names = registry.list_commands()
        assert set(names) == {"dummy", "another"}


class TestGetAllHelp:
    def test_help_includes_command_names(self):
        registry = CommandRegistry()
        registry.register(_DummyCommand)
        help_text = registry.get_all_help()
        assert "dummy" in help_text
        assert "A dummy command for testing" in help_text

    def test_help_empty_registry(self):
        registry = CommandRegistry()
        help_text = registry.get_all_help()
        assert "可用命令" in help_text


class TestCommandDecorator:
    def test_decorator_registers_command(self):
        @command
        class _DecoratedCmd(BaseCommand):
            name = "decorated"
            description = "Decorated command"

            async def execute(self, args, context):
                return CommandResult(type=ResultType.SUCCESS)

        registry = CommandRegistry()
        assert registry.get("decorated") is _DecoratedCmd

    def test_decorator_returns_class(self):
        @command
        class _ReturnCheckCmd(BaseCommand):
            name = "returncheck"
            description = "Return check"

            async def execute(self, args, context):
                return CommandResult(type=ResultType.SUCCESS)

        assert issubclass(_ReturnCheckCmd, BaseCommand)


class TestDuplicateRegister:
    def test_register_same_name_overwrites(self):
        registry = CommandRegistry()

        class _V1(BaseCommand):
            name = "dup"
            description = "Version 1"

            async def execute(self, args, context):
                return CommandResult(type=ResultType.SUCCESS, message="v1")

        class _V2(BaseCommand):
            name = "dup"
            description = "Version 2"

            async def execute(self, args, context):
                return CommandResult(type=ResultType.SUCCESS, message="v2")

        registry.register(_V1)
        registry.register(_V2)
        result = registry.get("dup")
        assert result is _V2

    def test_register_same_name_updates_aliases(self):
        registry = CommandRegistry()

        class _OldAlias(BaseCommand):
            name = "cmd"
            aliases = ["old"]
            description = "Old alias"

            async def execute(self, args, context):
                return CommandResult(type=ResultType.SUCCESS)

        class _NewAlias(BaseCommand):
            name = "cmd"
            aliases = ["new"]
            description = "New alias"

            async def execute(self, args, context):
                return CommandResult(type=ResultType.SUCCESS)

        registry.register(_OldAlias)
        registry.register(_NewAlias)
        assert registry.get("new") is _NewAlias
