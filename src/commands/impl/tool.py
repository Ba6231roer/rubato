from ..base import BaseCommand
from ..models import CommandResult, ResultType
from ..registry import command


@command
class ToolCommand(BaseCommand):
    name = "tool"
    description = "工具管理"
    usage = "/tool list"
    
    async def execute(self, args: str, context) -> CommandResult:
        parts = args.split(maxsplit=1)
        sub_cmd = parts[0].lower() if parts else ""
        
        if sub_cmd == "list":
            return await self._list_tools(context)
        else:
            return CommandResult(
                type=ResultType.INFO,
                message=self.usage
            )
    
    async def _list_tools(self, context) -> CommandResult:
        tools = context.agent.tools if context.agent else []
        if not tools:
            return CommandResult(
                type=ResultType.INFO,
                message="没有可用的工具"
            )
        
        tool_list = []
        lines = ["可用工具："]
        for tool in tools:
            desc = tool.description[:50] + "..." if len(tool.description) > 50 else tool.description
            lines.append(f"  - {tool.name}: {desc}")
            tool_list.append({
                "name": tool.name,
                "description": tool.description
            })
        
        return CommandResult(
            type=ResultType.INFO,
            message="\n".join(lines),
            data={"tools": tool_list}
        )
