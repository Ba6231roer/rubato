from ..base import BaseCommand
from ..models import CommandResult, ResultType
from ..registry import command


@command
class PromptCommand(BaseCommand):
    name = "prompt"
    description = "提示词管理"
    usage = "/prompt show"
    
    async def execute(self, args: str, context) -> CommandResult:
        parts = args.split(maxsplit=1)
        sub_cmd = parts[0].lower() if parts else ""
        
        if sub_cmd == "show":
            return await self._show_prompt(context)
        else:
            return CommandResult(
                type=ResultType.INFO,
                message=self.usage
            )
    
    async def _show_prompt(self, context) -> CommandResult:
        if not context.agent:
            return CommandResult(
                type=ResultType.ERROR,
                message="Agent未初始化"
            )
        
        prompt = context.agent.get_system_prompt()
        truncated = len(prompt) > 500
        display_prompt = prompt[:500] + "..." if truncated else prompt
        
        lines = ["系统提示词：", "-" * 40]
        lines.append(display_prompt)
        
        return CommandResult(
            type=ResultType.INFO,
            message="\n".join(lines),
            data={
                "prompt": prompt,
                "truncated": truncated
            }
        )
