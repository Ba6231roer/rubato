from ..base import BaseCommand
from ..models import CommandResult, ResultType
from ..registry import command


@command
class ClearCommand(BaseCommand):
    name = "clear"
    description = "清空对话历史"
    
    async def execute(self, args: str, context) -> CommandResult:
        if not context.agent:
            return CommandResult(
                type=ResultType.ERROR,
                message="Agent未初始化"
            )
        
        context.agent.clear_context()
        
        return CommandResult(
            type=ResultType.SUCCESS,
            message="对话历史已清空"
        )
