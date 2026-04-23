from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Optional
import json
import asyncio
import re
from pathlib import Path

from .schemas import WSMessage
from ..commands import CommandDispatcher, CommandContext
from ..commands import (
    HelpCommand, QuitCommand, ConfigCommand, RoleCommand,
    SkillCommand, ToolCommand, BrowserCommand, HistoryCommand,
    ClearCommand, NewCommand, ReloadCommand, PromptCommand,
    SessionCommand
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
_current_task: Optional[asyncio.Task] = None


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
    elif msg_type == "stop":
        await handle_stop(websocket)
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


async def handle_stop(websocket: WebSocket):
    global _current_task
    state = get_app_state()
    if state and hasattr(state, 'agent') and state.agent:
        state.agent.interrupt("用户中断")
    if _current_task and not _current_task.done():
        _current_task.cancel()
        try:
            await _current_task
        except asyncio.CancelledError:
            pass
    _current_task = None
    await manager.send_message(websocket, {
        "type": "interrupted",
        "content": "任务已中断"
    })


async def _resolve_file_references(content: str) -> str:
    pattern = r'@(workspace[/\\].+?\.(?:md|txt|docx|doc|pdf|pptx|xlsx|csv|json|yaml|yml|py|js|ts|html|css|xml|sql|sh|bat|ini|cfg|log|rst|tex))'
    matches = re.findall(pattern, content)
    
    if not matches:
        return content
    
    from ..tools.file_converter import is_text_based, convert_to_text
    
    resolved_parts = []
    remaining = content
    
    for match in matches:
        file_ref = f"@{match}"
        file_path = match.replace('\\', '/')
        
        path = Path(file_path)
        if not path.exists():
            resolved_parts.append(f'<file_content path="{file_path}">\n[文件不存在]\n</file_content>')
            remaining = remaining.replace(file_ref, '', 1)
            continue
        
        try:
            text_content = convert_to_text(str(path))
            resolved_parts.append(f'<file_content path="{file_path}">\n{text_content}\n</file_content>')
            remaining = remaining.replace(file_ref, '', 1)
        except Exception as e:
            resolved_parts.append(f'<file_content path="{file_path}">\n[文件读取失败: {str(e)}]\n</file_content>')
            remaining = remaining.replace(file_ref, '', 1)
    
    if resolved_parts:
        file_lines = '\n\n'.join(resolved_parts)
        return file_lines + '\n\n' + remaining.strip()
    return remaining


async def handle_task(websocket: WebSocket, task_content: str):
    global _current_task
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
    
    resolved_content = await _resolve_file_references(task_content)
    
    if resolved_content != task_content:
        await manager.send_message(websocket, {
            "type": "user_message_resolved",
            "content": resolved_content
        })
    
    async def run_task():
        try:
            full_response = ""
            
            async for sdk_msg in state.agent.run_stream_structured(resolved_content):
                if sdk_msg.type == "context_compressed":
                    await manager.send_message(websocket, {
                        "type": "context_compressed",
                        "content": sdk_msg.content
                    })
                    continue
                message = _sdk_message_to_structured(sdk_msg)
                await manager.send_message(websocket, {
                    "type": "chunk",
                    "message": message
                })
                if sdk_msg.type == "assistant" and isinstance(sdk_msg.content, str):
                    full_response += sdk_msg.content
            
            await manager.send_message(websocket, {
                "type": "done",
                "message": {"role": "assistant", "content": full_response, "streaming": False}
            })
        except asyncio.CancelledError:
            await manager.send_message(websocket, {
                "type": "interrupted",
                "content": "任务已中断"
            })
        except Exception as e:
            await manager.send_message(websocket, {
                "type": "error",
                "content": f"执行错误: {str(e)}"
            })
        finally:
            global _current_task
            _current_task = None
    
    _current_task = asyncio.create_task(run_task())


def _sdk_message_to_structured(sdk_msg) -> dict:
    if sdk_msg.type == "assistant":
        return {"role": "assistant", "content": sdk_msg.content, "streaming": True}
    elif sdk_msg.type == "tool_use":
        return {
            "role": "assistant",
            "tool_calls": [{
                "name": sdk_msg.content.get("name", ""),
                "args": sdk_msg.content.get("args", {}),
                "id": sdk_msg.content.get("id", "")
            }],
            "streaming": True
        }
    elif sdk_msg.type == "tool_result":
        return {
            "role": "tool",
            "content": str(sdk_msg.content.get("result", "")),
            "tool_call_id": sdk_msg.content.get("id", ""),
            "name": sdk_msg.content.get("name", "")
        }
    elif sdk_msg.type == "error":
        error_msg = sdk_msg.content.get("message", str(sdk_msg.content)) if isinstance(sdk_msg.content, dict) else str(sdk_msg.content)
        return {"role": "assistant", "content": f"[错误: {error_msg}]", "streaming": True}
    elif sdk_msg.type == "interrupt":
        reason = sdk_msg.content.get("reason", "") if isinstance(sdk_msg.content, dict) else str(sdk_msg.content)
        return {"role": "assistant", "content": f"[中断: {reason}]", "streaming": True}
    elif sdk_msg.type == "context_compressed":
        return {
            "role": "system",
            "type": "context_compressed",
            "content": sdk_msg.content,
            "streaming": False
        }
    else:
        return {"role": "assistant", "content": str(sdk_msg.content), "streaming": True}
