from ..base import BaseCommand
from ..models import CommandResult, ResultType
from ..registry import command


@command
class QuitCommand(BaseCommand):
    name = "quit"
    aliases = ["exit"]
    description = "退出程序"
    
    async def execute(self, args: str, context) -> CommandResult:
        return CommandResult(
            type=ResultType.EXIT,
            message="再见！"
        )
