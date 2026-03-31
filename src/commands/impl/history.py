from ..base import BaseCommand
from ..models import CommandResult, ResultType
from ..registry import command


@command
class HistoryCommand(BaseCommand):
    name = "history"
    description = "显示对话历史"
    
    async def execute(self, args: str, context) -> CommandResult:
        if not context.agent:
            return CommandResult(
                type=ResultType.ERROR,
                message="Agent未初始化"
            )
        
        messages = context.agent.context_manager.get_messages()
        
        if not messages:
            return CommandResult(
                type=ResultType.INFO,
                message="对话历史为空"
            )
        
        history_list = []
        lines = ["对话历史："]
        for i, msg in enumerate(messages, 1):
            msg_type = type(msg).__name__
            content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            lines.append(f"  [{i}] {msg_type}: {content}")
            history_list.append({
                "index": i,
                "type": msg_type,
                "content": msg.content
            })
        
        return CommandResult(
            type=ResultType.INFO,
            message="\n".join(lines),
            data={"history": history_list}
        )
