from ..base import BaseCommand
from ..models import CommandResult, ResultType
from ..registry import CommandRegistry, command


@command
class HelpCommand(BaseCommand):
    name = "help"
    aliases = ["?", "h"]
    description = "显示帮助信息"
    
    async def execute(self, args: str, context) -> CommandResult:
        registry = CommandRegistry()
        help_text = registry.get_all_help()
        
        additional_help = """
角色管理：
  /role <name>   - 切换到指定角色
  /role list     - 列出所有可用角色
  /role show <name> - 显示角色详细信息

Skill管理：
  /skill list    - 列出所有可用Skills
  /skill show <name> - 显示Skill详情

工具管理：
  /tool list     - 列出所有可用工具
  /prompt show   - 显示当前系统提示词

浏览器管理：
  /browser status - 查看浏览器状态
  /browser close  - 关闭浏览器
  /browser reopen - 重新打开浏览器

直接输入问题与Agent对话。
"""
        return CommandResult(
            type=ResultType.INFO,
            message=help_text + additional_help
        )
