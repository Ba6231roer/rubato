from datetime import datetime

from ..base import BaseCommand
from ..models import CommandResult, ResultType
from ..registry import command


@command
class SessionCommand(BaseCommand):
    name = "session"
    description = "会话管理（list/load/save/current/delete）"
    usage = "/session <list|load|save|current|delete> [参数]"

    async def execute(self, args: str, context) -> CommandResult:
        if not context.agent:
            return CommandResult(
                type=ResultType.ERROR,
                message="Agent未初始化"
            )

        parts = args.strip().split(maxsplit=1)
        subcommand = parts[0] if parts else ""
        sub_args = parts[1] if len(parts) > 1 else ""

        if not subcommand:
            return CommandResult(
                type=ResultType.ERROR,
                message="请指定子命令：list / load / save / current / delete"
            )

        handlers = {
            "list": self._handle_list,
            "load": self._handle_load,
            "save": self._handle_save,
            "current": self._handle_current,
            "delete": self._handle_delete,
        }

        handler = handlers.get(subcommand)
        if not handler:
            return CommandResult(
                type=ResultType.ERROR,
                message=f"未知子命令：{subcommand}。可用：list / load / save / current / delete"
            )

        return await handler(sub_args, context)

    async def _handle_list(self, args: str, context) -> CommandResult:
        storage = context.agent._query_engine._session_storage
        if not storage:
            return CommandResult(
                type=ResultType.ERROR,
                message="会话存储未初始化"
            )

        sessions = storage.list_sessions()
        if not sessions:
            return CommandResult(
                type=ResultType.INFO,
                message="没有已保存的会话"
            )

        lines = ["会话列表："]
        session_list = []
        for i, meta in enumerate(sessions, 1):
            sid = meta.session_id
            role = meta.role or "-"
            msg_count = meta.message_count
            updated = self._format_datetime(meta.updated_at)
            desc = meta.description or ""
            lines.append(f"  [{i}] ID: {sid}  角色: {role}  消息: {msg_count}  更新: {updated}  描述: {desc}")
            session_list.append({
                "index": i,
                "session_id": meta.session_id,
                "role": meta.role,
                "message_count": meta.message_count,
                "updated_at": meta.updated_at,
                "description": meta.description,
            })

        return CommandResult(
            type=ResultType.INFO,
            message="\n".join(lines),
            data={"sessions": session_list}
        )

    async def _handle_load(self, args: str, context) -> CommandResult:
        session_id = args.strip()
        if not session_id:
            return CommandResult(
                type=ResultType.ERROR,
                message="请指定要加载的会话ID。用法：/session load <session_id>"
            )

        success = context.agent.load_session(session_id)
        if success:
            return CommandResult(
                type=ResultType.SUCCESS,
                message=f"会话 {session_id[:6]}... 已加载"
            )
        else:
            return CommandResult(
                type=ResultType.ERROR,
                message=f"加载会话失败：会话不存在或存储未初始化"
            )

    async def _handle_save(self, args: str, context) -> CommandResult:
        storage = context.agent._query_engine._session_storage
        if not storage:
            return CommandResult(
                type=ResultType.ERROR,
                message="会话存储未初始化"
            )

        description = args.strip()
        session_id = context.agent._query_engine.get_session_id()
        messages = context.agent._query_engine.get_messages()
        storage.append_messages(session_id, messages, metadata={"description": description})

        return CommandResult(
            type=ResultType.SUCCESS,
            message=f"会话已保存" + (f"，描述：{description}" if description else "")
        )

    async def _handle_current(self, args: str, context) -> CommandResult:
        session_id = context.agent._query_engine.get_session_id()
        metadata = context.agent._query_engine.get_session_metadata()
        messages = context.agent._query_engine.get_messages()

        if metadata:
            lines = [
                f"当前会话信息：",
                f"  ID: {session_id[:6]}...",
                f"  角色: {metadata.role or '-'}",
                f"  消息数: {len(messages)}",
                f"  创建时间: {self._format_datetime(metadata.created_at)}",
                f"  更新时间: {self._format_datetime(metadata.updated_at)}",
                f"  描述: {metadata.description or '-'}",
            ]
            data = {
                "session_id": session_id,
                "role": metadata.role,
                "message_count": len(messages),
                "created_at": metadata.created_at,
                "updated_at": metadata.updated_at,
                "description": metadata.description,
            }
        else:
            lines = [
                f"当前会话信息：",
                f"  ID: {session_id[:6]}...",
                f"  消息数: {len(messages)}",
            ]
            data = {
                "session_id": session_id,
                "message_count": len(messages),
            }

        return CommandResult(
            type=ResultType.INFO,
            message="\n".join(lines),
            data=data
        )

    async def _handle_delete(self, args: str, context) -> CommandResult:
        session_id = args.strip()
        if not session_id:
            return CommandResult(
                type=ResultType.ERROR,
                message="请指定要删除的会话ID。用法：/session delete <session_id>"
            )

        storage = context.agent._query_engine._session_storage
        if not storage:
            return CommandResult(
                type=ResultType.ERROR,
                message="会话存储未初始化"
            )

        current_id = context.agent._query_engine.get_session_id()
        if session_id == current_id:
            return CommandResult(
                type=ResultType.ERROR,
                message="不能删除当前正在使用的会话"
            )

        success = storage.delete_session(session_id)
        if success:
            return CommandResult(
                type=ResultType.SUCCESS,
                message=f"会话 {session_id[:6]}... 已删除"
            )
        else:
            return CommandResult(
                type=ResultType.ERROR,
                message=f"删除会话失败：会话不存在或删除出错"
            )

    @staticmethod
    def _format_datetime(iso_str: str) -> str:
        if not iso_str:
            return "-"
        try:
            dt = datetime.fromisoformat(iso_str)
            return dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return iso_str
