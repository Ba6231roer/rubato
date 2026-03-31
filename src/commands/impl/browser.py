from ..base import BaseCommand
from ..models import CommandResult, ResultType
from ..registry import command


@command
class BrowserCommand(BaseCommand):
    name = "browser"
    description = "浏览器管理"
    usage = "/browser status | /browser close | /browser reopen"
    
    async def execute(self, args: str, context) -> CommandResult:
        if not context.mcp_manager:
            return CommandResult(
                type=ResultType.ERROR,
                message="MCP未启用，无法管理浏览器"
            )
        
        parts = args.split(maxsplit=1)
        sub_cmd = parts[0].lower() if parts else ""
        
        if sub_cmd == "status":
            return await self._status(context)
        elif sub_cmd == "close":
            return await self._close(context)
        elif sub_cmd == "reopen":
            return await self._reopen(context)
        else:
            return CommandResult(
                type=ResultType.INFO,
                message=self.usage
            )
    
    async def _status(self, context) -> CommandResult:
        if not context.mcp_manager.is_connected:
            return CommandResult(
                type=ResultType.INFO,
                message="MCP未连接",
                data={"mcp_connected": False, "browser_alive": None}
            )
        
        alive = await context.mcp_manager.check_browser_alive()
        status = "运行中" if alive else "已关闭"
        
        return CommandResult(
            type=ResultType.INFO,
            message=f"浏览器状态: {status}",
            data={"mcp_connected": True, "browser_alive": alive}
        )
    
    async def _close(self, context) -> CommandResult:
        if not context.mcp_manager.is_connected:
            return CommandResult(
                type=ResultType.ERROR,
                message="MCP未连接"
            )
        
        success = await context.mcp_manager.close_browser()
        if success:
            return CommandResult(
                type=ResultType.SUCCESS,
                message="浏览器已关闭",
                data={"action": "close", "success": True}
            )
        else:
            return CommandResult(
                type=ResultType.ERROR,
                message="关闭浏览器失败",
                data={"action": "close", "success": False}
            )
    
    async def _reopen(self, context) -> CommandResult:
        if not context.mcp_manager.is_connected:
            return CommandResult(
                type=ResultType.ERROR,
                message="MCP未连接"
            )
        
        success = await context.mcp_manager.ensure_browser()
        if success:
            return CommandResult(
                type=ResultType.SUCCESS,
                message="浏览器已重新打开",
                data={"action": "reopen", "success": True}
            )
        else:
            return CommandResult(
                type=ResultType.ERROR,
                message="重新打开浏览器失败",
                data={"action": "reopen", "success": False}
            )
