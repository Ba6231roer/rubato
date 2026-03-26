import tiktoken
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from typing import List, Optional, Set


class ContextCompressor:
    """上下文压缩器"""
    
    def __init__(self, max_tokens: int = 4000, keep_recent: int = 4):
        self.max_tokens = max_tokens
        self.keep_recent = keep_recent
        self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def _get_content_str(self, content) -> str:
        """将消息内容转换为字符串"""
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    if 'text' in item:
                        parts.append(item['text'])
                    else:
                        parts.append(str(item))
                else:
                    parts.append(str(item))
            return " ".join(parts)
        else:
            return str(content)
    
    def count_tokens(self, messages: List[BaseMessage]) -> int:
        """计算消息列表的token数量"""
        total = 0
        for message in messages:
            content_str = self._get_content_str(message.content)
            total += len(self.encoding.encode(content_str))
        return total
    
    def count_text_tokens(self, text: str) -> int:
        """计算文本的token数量"""
        return len(self.encoding.encode(text))
    
    def needs_compression(self, messages: List[BaseMessage]) -> bool:
        """检查是否需要压缩"""
        return self.count_tokens(messages) > self.max_tokens
    
    def compress(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """压缩对话历史，确保消息链完整性"""
        if not self.needs_compression(messages):
            return messages
        
        system_messages = [m for m in messages if isinstance(m, SystemMessage)]
        non_system_messages = [m for m in messages if not isinstance(m, SystemMessage)]
        
        if len(non_system_messages) <= self.keep_recent * 2:
            return messages
        
        recent_messages = non_system_messages[-self.keep_recent * 2:]
        middle_messages = non_system_messages[:-self.keep_recent * 2]
        
        valid_recent = self._ensure_message_chain_valid(recent_messages)
        
        summary = self._create_summary(middle_messages)
        
        return system_messages + [summary] + valid_recent
    
    def _ensure_message_chain_valid(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """确保消息链有效：ToolMessage必须紧跟在带tool_calls的AIMessage之后"""
        if not messages:
            return messages
        
        valid_messages = []
        pending_tool_call_ids: Set[str] = set()
        
        for msg in messages:
            if isinstance(msg, AIMessage):
                valid_messages.append(msg)
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tc in msg.tool_calls:
                        pending_tool_call_ids.add(tc.get('id'))
            elif isinstance(msg, ToolMessage):
                if msg.tool_call_id in pending_tool_call_ids:
                    valid_messages.append(msg)
                    pending_tool_call_ids.discard(msg.tool_call_id)
                else:
                    content_str = self._get_content_str(msg.content)
                    content = content_str[:200] + "..." if len(content_str) > 200 else content_str
                    valid_messages.append(HumanMessage(content=f"[工具结果摘要]: {content}"))
            else:
                valid_messages.append(msg)
        
        return valid_messages
    
    def _create_summary(self, messages: List[BaseMessage]) -> HumanMessage:
        """创建历史摘要"""
        summary_parts = []
        for msg in messages:
            role = "用户" if isinstance(msg, HumanMessage) else "助手"
            content_str = self._get_content_str(msg.content)
            content = content_str[:200] + "..." if len(content_str) > 200 else content_str
            summary_parts.append(f"[{role}]: {content}")
        
        summary_content = f"[历史摘要]\n" + "\n".join(summary_parts)
        return HumanMessage(content=summary_content)
    
    def selective_compress(
        self, 
        messages: List[BaseMessage],
        preserve_types: Optional[List[str]] = None
    ) -> List[BaseMessage]:
        """选择性压缩，保留特定类型的消息"""
        preserve_types = preserve_types or ['system']
        
        preserved = []
        to_compress = []
        
        for msg in messages:
            msg_type = self._get_message_type(msg)
            if msg_type in preserve_types:
                preserved.append(msg)
            else:
                to_compress.append(msg)
        
        if self.count_tokens(to_compress) > self.max_tokens:
            compressed = self.compress(to_compress)
            return preserved + compressed
        
        return messages
    
    def _get_message_type(self, msg: BaseMessage) -> str:
        """获取消息类型"""
        if isinstance(msg, SystemMessage):
            return 'system'
        elif isinstance(msg, HumanMessage):
            return 'human'
        elif isinstance(msg, AIMessage):
            return 'ai'
        return 'other'
