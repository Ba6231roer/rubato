from abc import ABC, abstractmethod
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .context import CommandContext
    from .models import CommandResult


class BaseCommand(ABC):
    name: str = ""
    aliases: List[str] = []
    description: str = ""
    usage: str = ""
    
    @abstractmethod
    async def execute(
        self, 
        args: str, 
        context: 'CommandContext'
    ) -> 'CommandResult':
        pass
    
    def validate_args(self, args: str) -> Optional[str]:
        return None
    
    def get_help(self) -> str:
        help_text = f"/{self.name}"
        if self.aliases:
            help_text += f" ({', '.join('/' + a for a in self.aliases)})"
        help_text += f" - {self.description}"
        if self.usage:
            help_text += f"\n  用法: {self.usage}"
        return help_text
