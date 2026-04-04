"""会话持久化存储模块"""
import json
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
)


@dataclass
class SessionMetadata:
    """会话元数据"""
    session_id: str
    created_at: str
    updated_at: str
    message_count: int
    total_tokens: int = 0
    tags: List[str] = field(default_factory=list)
    description: str = ""


class MessageSerializer:
    """消息序列化器"""
    
    MESSAGE_TYPE_MAP = {
        "human": HumanMessage,
        "ai": AIMessage,
        "tool": ToolMessage,
        "system": SystemMessage,
    }
    
    @staticmethod
    def serialize(message: BaseMessage) -> Dict[str, Any]:
        """序列化消息对象为字典"""
        msg_dict = {
            "type": message.type,
            "content": message.content,
        }
        
        if isinstance(message, AIMessage):
            if hasattr(message, "tool_calls") and message.tool_calls:
                msg_dict["tool_calls"] = message.tool_calls
            if hasattr(message, "response_metadata"):
                msg_dict["response_metadata"] = message.response_metadata
            if hasattr(message, "id") and message.id:
                msg_dict["id"] = message.id
        
        if isinstance(message, ToolMessage):
            if hasattr(message, "tool_call_id"):
                msg_dict["tool_call_id"] = message.tool_call_id
            if hasattr(message, "name"):
                msg_dict["name"] = message.name
        
        return msg_dict
    
    @staticmethod
    def deserialize(msg_dict: Dict[str, Any]) -> BaseMessage:
        """反序列化字典为消息对象"""
        msg_type = msg_dict.get("type", "human")
        content = msg_dict.get("content", "")
        
        if msg_type == "ai":
            tool_calls = msg_dict.get("tool_calls", [])
            response_metadata = msg_dict.get("response_metadata", {})
            msg_id = msg_dict.get("id")
            return AIMessage(
                content=content,
                tool_calls=tool_calls,
                response_metadata=response_metadata,
                id=msg_id,
            )
        elif msg_type == "tool":
            tool_call_id = msg_dict.get("tool_call_id", "")
            name = msg_dict.get("name")
            return ToolMessage(
                content=content,
                tool_call_id=tool_call_id,
                name=name,
            )
        elif msg_type == "system":
            return SystemMessage(content=content)
        else:
            return HumanMessage(content=content)
    
    @staticmethod
    def serialize_list(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """序列化消息列表"""
        return [MessageSerializer.serialize(msg) for msg in messages]
    
    @staticmethod
    def deserialize_list(msg_dicts: List[Dict[str, Any]]) -> List[BaseMessage]:
        """反序列化消息列表"""
        return [MessageSerializer.deserialize(msg_dict) for msg_dict in msg_dicts]


class SessionStorage:
    """会话持久化存储"""
    
    def __init__(self, storage_dir: str = "./sessions"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
    
    def save_session(
        self,
        session_id: str,
        messages: List[BaseMessage],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SessionMetadata:
        """保存会话消息历史到存储
        
        Args:
            session_id: 会话ID
            messages: 消息列表
            metadata: 可选的元数据
        
        Returns:
            SessionMetadata: 会话元数据
        """
        with self._lock:
            session_file = self.storage_dir / f"{session_id}.json"
            
            existing_metadata = None
            if session_file.exists():
                try:
                    with open(session_file, "r", encoding="utf-8") as f:
                        existing_data = json.load(f)
                        existing_metadata = existing_data.get("metadata", {})
                except Exception:
                    pass
            
            now = datetime.now().isoformat()
            created_at = existing_metadata.get("created_at", now) if existing_metadata else now
            
            session_metadata = SessionMetadata(
                session_id=session_id,
                created_at=created_at,
                updated_at=now,
                message_count=len(messages),
                total_tokens=metadata.get("total_tokens", 0) if metadata else 0,
                tags=metadata.get("tags", []) if metadata else [],
                description=metadata.get("description", "") if metadata else "",
            )
            
            session_data = {
                "metadata": asdict(session_metadata),
                "messages": MessageSerializer.serialize_list(messages),
            }
            
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
            
            return session_metadata
    
    def load_session(self, session_id: str) -> List[BaseMessage]:
        """加载会话消息历史
        
        Args:
            session_id: 会话ID
        
        Returns:
            List[BaseMessage]: 消息列表
        
        Raises:
            FileNotFoundError: 会话文件不存在
        """
        with self._lock:
            session_file = self.storage_dir / f"{session_id}.json"
            
            if not session_file.exists():
                raise FileNotFoundError(f"Session not found: {session_id}")
            
            with open(session_file, "r", encoding="utf-8") as f:
                session_data = json.load(f)
            
            messages = MessageSerializer.deserialize_list(
                session_data.get("messages", [])
            )
            
            return messages
    
    def list_sessions(self) -> List[SessionMetadata]:
        """列出所有保存的会话
        
        Returns:
            List[SessionMetadata]: 会话元数据列表
        """
        with self._lock:
            sessions = []
            
            for session_file in self.storage_dir.glob("*.json"):
                try:
                    with open(session_file, "r", encoding="utf-8") as f:
                        session_data = json.load(f)
                    
                    metadata_dict = session_data.get("metadata", {})
                    metadata = SessionMetadata(
                        session_id=metadata_dict.get("session_id", session_file.stem),
                        created_at=metadata_dict.get("created_at", ""),
                        updated_at=metadata_dict.get("updated_at", ""),
                        message_count=metadata_dict.get("message_count", 0),
                        total_tokens=metadata_dict.get("total_tokens", 0),
                        tags=metadata_dict.get("tags", []),
                        description=metadata_dict.get("description", ""),
                    )
                    sessions.append(metadata)
                except Exception:
                    continue
            
            sessions.sort(key=lambda x: x.updated_at, reverse=True)
            return sessions
    
    def delete_session(self, session_id: str) -> bool:
        """删除指定会话
        
        Args:
            session_id: 会话ID
        
        Returns:
            bool: 是否删除成功
        """
        with self._lock:
            session_file = self.storage_dir / f"{session_id}.json"
            
            if not session_file.exists():
                return False
            
            try:
                session_file.unlink()
                return True
            except Exception:
                return False
    
    def get_session_metadata(self, session_id: str) -> Optional[SessionMetadata]:
        """获取会话元数据
        
        Args:
            session_id: 会话ID
        
        Returns:
            Optional[SessionMetadata]: 会话元数据，如果不存在则返回None
        """
        with self._lock:
            session_file = self.storage_dir / f"{session_id}.json"
            
            if not session_file.exists():
                return None
            
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    session_data = json.load(f)
                
                metadata_dict = session_data.get("metadata", {})
                metadata = SessionMetadata(
                    session_id=metadata_dict.get("session_id", session_id),
                    created_at=metadata_dict.get("created_at", ""),
                    updated_at=metadata_dict.get("updated_at", ""),
                    message_count=metadata_dict.get("message_count", 0),
                    total_tokens=metadata_dict.get("total_tokens", 0),
                    tags=metadata_dict.get("tags", []),
                    description=metadata_dict.get("description", ""),
                )
                return metadata
            except Exception:
                return None
    
    def session_exists(self, session_id: str) -> bool:
        """检查会话是否存在
        
        Args:
            session_id: 会话ID
        
        Returns:
            bool: 会话是否存在
        """
        session_file = self.storage_dir / f"{session_id}.json"
        return session_file.exists()
