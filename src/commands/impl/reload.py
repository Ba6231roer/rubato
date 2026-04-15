from ..base import BaseCommand
from ..models import CommandResult, ResultType
from ..registry import command


@command
class ReloadCommand(BaseCommand):
    name = "reload"
    description = "重新加载所有配置（模型、角色、Skill）"
    
    async def execute(self, args: str, context) -> CommandResult:
        results = []
        
        try:
            if context.role_manager:
                context.role_manager.reload_roles()
                results.append("✓ 角色配置已重新加载")
            
            if context.config_loader:
                context.config_loader.load_all()
                results.append("✓ 模型配置已重新加载")
            
            if context.skill_loader:
                await context.skill_loader.load_skill_metadata()
                results.append("✓ Skill配置已重新加载")
            
            if not results:
                return CommandResult(
                    type=ResultType.INFO,
                    message="没有可重新加载的配置"
                )
            
            context.agent._rebuild_query_engine()
            
            return CommandResult(
                type=ResultType.SUCCESS,
                message="配置重新加载完成：\n" + "\n".join(results)
            )
            
        except Exception as e:
            return CommandResult(
                type=ResultType.ERROR,
                message=f"重新加载配置时发生错误：{str(e)}"
            )
