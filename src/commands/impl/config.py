from ..base import BaseCommand
from ..models import CommandResult, ResultType
from ..registry import command


@command
class ConfigCommand(BaseCommand):
    name = "config"
    description = "显示当前配置"
    
    async def execute(self, args: str, context) -> CommandResult:
        config = context.config
        if not config:
            return CommandResult(
                type=ResultType.ERROR,
                message="配置未加载"
            )
        
        model = config.model.model
        
        lines = [
            "当前配置：",
            f"  模型: {model.provider}/{model.name}",
            f"  Temperature: {model.temperature}",
            f"  Max Tokens: {model.max_tokens}",
        ]
        
        if context.mcp_manager:
            status = "已连接" if context.mcp_manager.is_connected else "未连接"
            lines.append(f"  MCP状态: {status}")
        
        return CommandResult(
            type=ResultType.INFO,
            message="\n".join(lines),
            data={
                "model": {
                    "provider": model.provider,
                    "name": model.name,
                    "temperature": model.temperature,
                    "max_tokens": model.max_tokens
                },
                "mcp_connected": context.mcp_manager.is_connected if context.mcp_manager else None
            }
        )
