from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
import json
import asyncio

from .schemas import WSMessage
from ..commands import CommandDispatcher, CommandContext
from ..commands import (
    HelpCommand, QuitCommand, ConfigCommand, RoleCommand,
    SkillCommand, ToolCommand, BrowserCommand, HistoryCommand,
    ClearCommand, NewCommand, ReloadCommand, PromptCommand
)

websocket_router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def send_message(self, websocket: WebSocket, message: dict):
        await websocket.send_json(message)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)


manager = ConnectionManager()
_app_state = None
_dispatcher: CommandDispatcher = None


def set_app_state(state):
    global _app_state
    _app_state = state


def get_app_state():
    return _app_state


def init_command_dispatcher(context: CommandContext):
    global _dispatcher
    _dispatcher = CommandDispatcher(context)


def get_dispatcher() -> CommandDispatcher:
    return _dispatcher


@websocket_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await manager.send_message(websocket, {
            "type": "connected",
            "content": "WebSocket连接已建立"
        })
        
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                await handle_message(websocket, message)
            except json.JSONDecodeError:
                await manager.send_message(websocket, {
                    "type": "error",
                    "content": "无效的消息格式"
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        await manager.send_message(websocket, {
            "type": "error",
            "content": f"连接错误: {str(e)}"
        })
        manager.disconnect(websocket)


async def handle_message(websocket: WebSocket, message: dict):
    msg_type = message.get("type")
    content = message.get("content", "")
    
    if msg_type == "command":
        await handle_command(websocket, content)
    elif msg_type == "task":
        result = await try_dispatch_command(content)
        if result:
            await manager.send_message(websocket, {
                "type": "command_result",
                "content": result.to_dict()
            })
        else:
            await handle_task(websocket, content)
    elif msg_type == "ping":
        await manager.send_message(websocket, {"type": "pong", "content": ""})
    else:
        await manager.send_message(websocket, {
            "type": "error",
            "content": f"未知消息类型: {msg_type}"
        })


async def try_dispatch_command(user_input: str):
    """尝试将用户输入作为命令处理"""
    if _dispatcher and user_input.strip().startswith('/'):
        return await _dispatcher.dispatch(user_input)
    return None


async def handle_command(websocket: WebSocket, command: str):
    """处理命令消息"""
    if not _dispatcher:
        await manager.send_message(websocket, {
            "type": "error",
            "content": "命令分发器未初始化"
        })
        return
    
    result = await _dispatcher.dispatch(command)
    
    if result is None:
        await manager.send_message(websocket, {
            "type": "error",
            "content": "无效的命令格式。命令必须以 '/' 开头"
        })
    else:
        await manager.send_message(websocket, {
            "type": "command_result",
            "content": result.to_dict()
        })


async def handle_task(websocket: WebSocket, task_content: str):
    state = get_app_state()
    
    if not state:
        await manager.send_message(websocket, {
            "type": "error",
            "content": "应用状态未初始化"
        })
        return
    
    if not hasattr(state, 'agent') or not state.agent:
        await manager.send_message(websocket, {
            "type": "error",
            "content": "Agent未初始化"
        })
        return
    
    try:
        full_response = ""
        
        async for chunk in state.agent.run_stream(task_content):
            if chunk:
                full_response += chunk
                await manager.send_message(websocket, {
                    "type": "chunk",
                    "content": chunk
                })
        
        await manager.send_message(websocket, {
            "type": "done",
            "content": full_response
        })
    except Exception as e:
        await manager.send_message(websocket, {
            "type": "error",
            "content": f"执行错误: {str(e)}"
        })
