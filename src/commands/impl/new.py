from ..base import BaseCommand
from ..models import CommandResult, ResultType
from ..registry import command


@command
class NewCommand(BaseCommand):
    name = "new"
    description = "开始新对话（清空上下文，保留角色和系统提示词）"
    
    async def execute(self, args: str, context) -> CommandResult:
        if not context.agent:
            return CommandResult(
                type=ResultType.ERROR,
                message="Agent未初始化"
            )
        
        try:
            context.agent.context_manager.clear()
            
            current_role = context.role_manager.get_current_role() if context.role_manager else None
            if current_role:
                system_prompt = context.role_manager.load_system_prompt(current_role.name)
                context.agent.system_prompt = system_prompt
                context.agent._current_system_prompt = system_prompt
                context.agent.agent = context.agent._create_agent(system_prompt)
            
            return CommandResult(
                type=ResultType.SUCCESS,
                message="新对话已开始。当前角色和系统提示词已保留，浏览器状态保持不变。"
            )
            
        except Exception as e:
            return CommandResult(
                type=ResultType.ERROR,
                message=f"开始新对话时发生错误：{str(e)}"
            )
