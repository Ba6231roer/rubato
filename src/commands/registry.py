from typing import Dict, List, Optional, Type

from .base import BaseCommand


class CommandRegistry:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._commands: Dict[str, Type[BaseCommand]] = {}
            cls._instance._aliases: Dict[str, str] = {}
        return cls._instance
    
    def register(self, command_class: Type[BaseCommand]) -> None:
        cmd = command_class()
        self._commands[cmd.name] = command_class
        
        for alias in cmd.aliases:
            self._aliases[alias] = cmd.name
    
    def get(self, name: str) -> Optional[Type[BaseCommand]]:
        if name in self._commands:
            return self._commands[name]
        if name in self._aliases:
            return self._commands[self._aliases[name]]
        return None
    
    def list_commands(self) -> List[str]:
        return list(self._commands.keys())
    
    def get_all_help(self) -> str:
        lines = ["可用命令："]
        for name, cmd_class in sorted(self._commands.items()):
            cmd = cmd_class()
            lines.append(f"  /{name:<12} - {cmd.description}")
        return "\n".join(lines)


def command(cls: Type[BaseCommand]) -> Type[BaseCommand]:
    registry = CommandRegistry()
    registry.register(cls)
    return cls
