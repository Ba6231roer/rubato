from ..base import BaseCommand
from ..models import CommandResult, ResultType
from ..registry import command


@command
class StatusCommand(BaseCommand):
    name = "status"
    description = "查看当前状态"
    usage = "/status [full|tools|prompt]"
    
    async def execute(self, args: str, context) -> CommandResult:
        parts = args.split(maxsplit=1)
        sub_cmd = parts[0].lower() if parts else ""
        
        if sub_cmd == "full":
            return await self._status_full(context)
        elif sub_cmd == "tools":
            return await self._status_tools(context)
        elif sub_cmd == "prompt":
            return await self._status_prompt(context)
        else:
            return await self._status_overview(context)
    
    async def _status_overview(self, context) -> CommandResult:
        current_role = context.role_manager.get_current_role() if context.role_manager else None
        role_name = current_role.name if current_role else "未设置"
        role_desc = current_role.description if current_role else ""
        
        tool_count = len(context.agent.tools) if context.agent else 0
        
        prompt = context.agent.get_current_system_prompt() if context.agent else ""
        prompt_length = len(prompt)
        
        lines = [
            "当前状态概览：",
            "=" * 50,
            f"角色: {role_name}",
            f"描述: {role_desc}",
            f"可用工具数量: {tool_count}",
            f"系统提示词长度: {prompt_length} 字符",
            "",
            "提示：使用 /status full 查看完整信息",
            "      使用 /status tools 查看工具列表",
            "      使用 /status prompt 查看完整提示词"
        ]
        
        return CommandResult(
            type=ResultType.INFO,
            message="\n".join(lines),
            data={
                "role": role_name,
                "role_description": role_desc,
                "tool_count": tool_count,
                "prompt_length": prompt_length
            }
        )
    
    async def _status_full(self, context) -> CommandResult:
        overview = await self._status_overview(context)
        tools = await self._status_tools(context)
        prompt = await self._status_prompt(context)
        
        lines = [
            overview.message,
            "\n" + "=" * 50,
            "\n可用工具：",
            tools.message,
            "\n" + "=" * 50,
            "\n系统提示词：",
            prompt.message
        ]
        
        return CommandResult(
            type=ResultType.INFO,
            message="\n".join(lines),
            data={
                **overview.data,
                "tools": tools.data.get("tools", []) if tools.data else [],
                "prompt": prompt.data.get("prompt", "") if prompt.data else ""
            }
        )
    
    async def _status_tools(self, context) -> CommandResult:
        tools = context.agent.tools if context.agent else []
        if not tools:
            return CommandResult(
                type=ResultType.INFO,
                message="没有可用的工具",
                data={"tools": []}
            )
        
        lines = ["可用工具列表："]
        tool_list = []
        for i, tool in enumerate(tools, 1):
            desc = tool.description[:100] + "..." if len(tool.description) > 100 else tool.description
            lines.append(f"  {i}. {tool.name}")
            lines.append(f"     描述: {desc}")
            tool_list.append({
                "name": tool.name,
                "description": tool.description
            })
        
        return CommandResult(
            type=ResultType.INFO,
            message="\n".join(lines),
            data={"tools": tool_list}
        )
    
    async def _status_prompt(self, context) -> CommandResult:
        prompt = context.agent.get_current_system_prompt() if context.agent else ""
        lines = [
            "当前系统提示词（包含工具说明）：",
            "=" * 50,
            prompt
        ]
        
        return CommandResult(
            type=ResultType.INFO,
            message="\n".join(lines),
            data={"prompt": prompt}
        )
