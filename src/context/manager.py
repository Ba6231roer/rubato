from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from typing import List, Optional
from .compressor import ContextCompressor


class ContextManager:
    """上下文管理器"""
    
    def __init__(
        self, 
        max_tokens: int = 4000,
        keep_recent: int = 4,
        auto_compress: bool = True
    ):
        self.messages: List[BaseMessage] = []
        self.compressor = ContextCompressor(max_tokens, keep_recent)
        self.auto_compress = auto_compress
        self._loaded_skills: List[str] = []
    
    def add_message(self, message: BaseMessage) -> None:
        """添加消息"""
        self.messages.append(message)
        
        if self.auto_compress:
            self._check_and_compress()
    
    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        self.add_message(HumanMessage(content=content))
    
    def add_ai_message(self, content: str) -> None:
        """添加AI消息"""
        self.add_message(AIMessage(content=content))
    
    def add_tool_message(self, content: str, tool_call_id: str) -> None:
        """添加工具消息"""
        self.add_message(ToolMessage(content=content, tool_call_id=tool_call_id))
    
    def add_system_message(self, content: str) -> None:
        """添加系统消息"""
        self.messages.insert(0, SystemMessage(content=content))
    
    def get_messages(self) -> List[BaseMessage]:
        """获取所有消息"""
        return self.messages
    
    def get_token_count(self) -> int:
        """获取当前token数量"""
        return self.compressor.count_tokens(self.messages)
    
    def _check_and_compress(self) -> None:
        """检查并压缩"""
        if self.compressor.needs_compression(self.messages):
            self.messages = self.compressor.compress(self.messages)
    
    def compress_now(self) -> None:
        """立即压缩"""
        self.messages = self.compressor.compress(self.messages)
    
    def clear(self) -> None:
        """清空消息"""
        self.messages = []
        self._loaded_skills = []
    
    def get_history(self, limit: Optional[int] = None) -> List[BaseMessage]:
        """获取历史消息"""
        if limit:
            return self.messages[-limit:]
        return self.messages
    
    def get_last_n_turns(self, n: int) -> List[BaseMessage]:
        """获取最近n轮对话"""
        return self.messages[-n * 2:]
    
    def mark_skill_loaded(self, skill_name: str) -> None:
        """标记Skill已加载"""
        if skill_name not in self._loaded_skills:
            self._loaded_skills.append(skill_name)
    
    def get_loaded_skills(self) -> List[str]:
        """获取已加载的Skills"""
        return self._loaded_skills.copy()
    
    def is_skill_loaded(self, skill_name: str) -> bool:
        """检查Skill是否已加载"""
        return skill_name in self._loaded_skills
