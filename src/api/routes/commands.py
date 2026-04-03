from fastapi import APIRouter, HTTPException
from typing import List

from ..schemas import CommandRequest, CommandInfo, CommandResponse
from ...commands import CommandRegistry, CommandDispatcher, CommandContext
from ...commands import (
    HelpCommand, QuitCommand, ConfigCommand, RoleCommand,
    SkillCommand, ToolCommand, BrowserCommand, HistoryCommand,
    ClearCommand, NewCommand, ReloadCommand, PromptCommand,
    StatusCommand
)

router = APIRouter()

_dispatcher: CommandDispatcher = None


def init_dispatcher(context: CommandContext):
    global _dispatcher
    _dispatcher = CommandDispatcher(context)


def get_dispatcher() -> CommandDispatcher:
    return _dispatcher


@router.post("/command", response_model=CommandResponse)
async def execute_command(request: CommandRequest):
    """执行控制台命令"""
    if not _dispatcher:
        raise HTTPException(
            status_code=500,
            detail="Command dispatcher not initialized"
        )
    
    result = await _dispatcher.dispatch(request.command)
    
    if result is None:
        raise HTTPException(
            status_code=400,
            detail="Not a valid command. Commands must start with '/'"
        )
    
    return CommandResponse(**result.to_dict())


@router.get("/commands", response_model=List[CommandInfo])
async def list_commands():
    """列出所有可用命令"""
    registry = CommandRegistry()
    commands = []
    for name in registry.list_commands():
        cmd_class = registry.get(name)
        if cmd_class:
            cmd = cmd_class()
            commands.append(CommandInfo(
                name=name,
                aliases=cmd.aliases,
                description=cmd.description,
                usage=cmd.usage
            ))
    return commands
