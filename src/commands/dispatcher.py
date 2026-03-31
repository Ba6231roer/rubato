from typing import Optional, Tuple

from .base import BaseCommand
from .registry import CommandRegistry
from .context import CommandContext
from .models import CommandResult, ResultType


class CommandDispatcher:
    def __init__(self, context: CommandContext):
        self.context = context
        self.registry = CommandRegistry()
        self._running = True
    
    def is_running(self) -> bool:
        return self._running
    
    def parse_input(self, user_input: str) -> Tuple[Optional[str], str]:
        user_input = user_input.strip()
        
        if not user_input:
            return None, ""
        
        if user_input.startswith('/'):
            parts = user_input[1:].split(maxsplit=1)
            cmd_name = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            return cmd_name, args
        
        return None, user_input
    
    async def dispatch(self, user_input: str) -> Optional[CommandResult]:
        cmd_name, args = self.parse_input(user_input)
        
        if cmd_name is None:
            return None
        
        cmd_class = self.registry.get(cmd_name)
        
        if cmd_class is None:
            return CommandResult(
                type=ResultType.ERROR,
                message=f"未知命令：{cmd_name}。输入 /help 查看帮助。"
            )
        
        cmd = cmd_class()
        
        validation_error = cmd.validate_args(args)
        if validation_error:
            return CommandResult(
                type=ResultType.ERROR,
                message=validation_error
            )
        
        result = await cmd.execute(args, self.context)
        
        if result.type == ResultType.EXIT:
            self._running = False
        
        return result
