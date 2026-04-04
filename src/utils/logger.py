import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, List, Dict
import sys
from langchain_core.callbacks import BaseCallbackHandler


class LLMRequestCallbackHandler(BaseCallbackHandler):
    """LangChain回调处理器，用于捕获LLM请求"""
    
    def __init__(self, logger: 'LLMLogger'):
        self.logger = logger
    
    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs: Any
    ) -> None:
        """LLM开始调用时记录请求"""
        invocation_params = kwargs.get("invocation_params", {})
        messages = kwargs.get("messages", [])
        
        request_body = {
            "model": invocation_params.get("model", "unknown"),
            "temperature": invocation_params.get("temperature"),
            "max_tokens": invocation_params.get("max_tokens"),
            "messages": self._format_messages(messages) if messages else prompts,
            "tools": invocation_params.get("tools"),
            "tool_choice": invocation_params.get("tool_choice"),
        }
        
        request_body = {k: v for k, v in request_body.items() if v is not None}
        
        self.logger.log_request_raw(request_body, request_body.get("model", "unknown"))
    
    def _format_messages(self, messages: List) -> List[Dict]:
        """格式化消息列表"""
        result = []
        for msg in messages:
            if hasattr(msg, "type"):
                msg_dict = {
                    "role": msg.type,
                    "content": self.logger._truncate(self.logger._get_content(msg), 500)
                }
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    msg_dict["tool_calls"] = msg.tool_calls
                if hasattr(msg, "tool_call_id"):
                    msg_dict["tool_call_id"] = msg.tool_call_id
                result.append(msg_dict)
            else:
                result.append(str(msg)[:500])
        return result


class LLMLogger:
    """LLM请求/响应日志记录器"""
    
    def __init__(self, log_dir: str = "logs", tool_log_mode: str = "summary"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.tool_log_mode = tool_log_mode
        
        self._setup_loggers()
    
    def _setup_loggers(self):
        """设置多个日志记录器"""
        self.llm_logger = self._create_logger(
            "llm",
            self.log_dir / "llm.log",
            "%(asctime)s | %(levelname)s | %(message)s"
        )
        
        self.tool_logger = self._create_logger(
            "tool",
            self.log_dir / "tool.log",
            "%(asctime)s | %(levelname)s | %(message)s"
        )
        
        self.agent_logger = self._create_logger(
            "agent",
            self.log_dir / "agent.log",
            "%(asctime)s | %(levelname)s | %(message)s"
        )
    
    def set_tool_log_mode(self, mode: str) -> None:
        """设置工具日志模式
        
        Args:
            mode: "summary"（摘要模式）或 "detailed"（详细模式）
        """
        self.tool_log_mode = mode
    
    def _format_tools_summary(self, tools: list) -> str:
        """格式化工具列表摘要
        
        Args:
            tools: 工具列表
            
        Returns:
            摘要字符串
        """
        if not tools:
            return "无工具"
        
        builtin_tools = []
        mcp_tools = []
        other_tools = []
        
        builtin_names = {'spawn_agent', 'shell_tool', 'file_read', 'file_write', 
                        'file_list', 'file_search', 'file_exists', 'file_mkdir', 
                        'file_replace', 'file_delete'}
        
        for tool in tools:
            if isinstance(tool, dict):
                if 'function' in tool and isinstance(tool.get('function'), dict):
                    tool_name = tool.get('function', {}).get('name', 'unknown')
                elif 'name' in tool:
                    tool_name = tool.get('name', 'unknown')
                else:
                    tool_name = 'unknown'
            elif hasattr(tool, 'name'):
                tool_name = tool.name
            else:
                tool_name = str(tool)
            
            if tool_name in builtin_names:
                builtin_tools.append(tool_name)
            elif tool_name.startswith('browser_') or tool_name.startswith('mcp_'):
                mcp_tools.append(tool_name)
            else:
                other_tools.append(tool_name)
        
        lines = [f"工具加载完成: {len(tools)}个工具"]
        if builtin_tools:
            lines.append(f"  - 内置工具: {', '.join(builtin_tools)}")
        if mcp_tools:
            lines.append(f"  - MCP工具: {', '.join(mcp_tools)}")
        if other_tools:
            lines.append(f"  - 其他工具: {', '.join(other_tools)}")
        
        return "\n".join(lines)
    
    def _create_logger(self, name: str, file_path: Path, format_str: str) -> logging.Logger:
        """创建日志记录器"""
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        logger.handlers = []
        
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(format_str))
        logger.addHandler(file_handler)
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(format_str))
        logger.addHandler(console_handler)
        
        return logger
    
    def log_request(self, messages: list, model: str, **kwargs):
        """记录LLM请求"""
        request_data = {
            "type": "request",
            "model": model,
            "message_count": len(messages),
            "messages": self._serialize_messages(messages),
            "extra": kwargs
        }
        self.llm_logger.info(f"REQUEST: {json.dumps(request_data, ensure_ascii=False, indent=2)}")
    
    def log_request_raw(self, request_body: dict, model: str):
        """记录LLM原始请求报文"""
        if self.tool_log_mode == "summary" and "tools" in request_body:
            tools = request_body.get("tools", [])
            tools_summary = self._format_tools_summary(tools)
            log_body = {k: v for k, v in request_body.items() if k != "tools"}
            log_body["tools_summary"] = tools_summary
            self.llm_logger.debug(f"REQUEST_RAW: {json.dumps(log_body, ensure_ascii=False, indent=2)}")
        else:
            self.llm_logger.debug(f"REQUEST_RAW: {json.dumps(request_body, ensure_ascii=False, indent=2)}")
    
    def log_response(self, response: Any, model: str):
        """记录LLM响应"""
        response_data = {
            "type": "response",
            "model": model,
            "response": self._serialize_response(response)
        }
        self.llm_logger.info(f"RESPONSE: {json.dumps(response_data, ensure_ascii=False, indent=2)}")
    
    def log_tool_call(self, tool_name: str, arguments: dict):
        """记录工具调用"""
        call_data = {
            "type": "tool_call",
            "tool": tool_name,
            "arguments": arguments
        }
        self.tool_logger.info(f"TOOL_CALL: {json.dumps(call_data, ensure_ascii=False, indent=2)}")
    
    def log_tool_result(self, tool_name: str, result: Any, error: Optional[str] = None):
        """记录工具结果"""
        result_data = {
            "type": "tool_result",
            "tool": tool_name,
            "error": error,
            "result": self._truncate(str(result), 2000)
        }
        self.tool_logger.info(f"TOOL_RESULT: {json.dumps(result_data, ensure_ascii=False, indent=2)}")
    
    def log_agent_thinking(self, thought: str):
        """记录Agent思考过程"""
        self.agent_logger.info(f"THINKING: {thought}")
    
    def log_agent_action(self, action: str, details: dict = None):
        """记录Agent行动"""
        action_data = {
            "action": action,
            "details": details or {}
        }
        self.agent_logger.info(f"ACTION: {json.dumps(action_data, ensure_ascii=False)}")
    
    def log_error(self, source: str, error: Exception):
        """记录错误"""
        error_data = {
            "source": source,
            "error_type": type(error).__name__,
            "error_message": str(error)
        }
        self.agent_logger.error(f"ERROR: {json.dumps(error_data, ensure_ascii=False)}")
    
    def _serialize_messages(self, messages: list) -> list:
        """序列化消息列表"""
        result = []
        for msg in messages:
            msg_dict = {
                "type": getattr(msg, "type", "unknown"),
                "content": self._truncate(self._get_content(msg), 500)
            }
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                msg_dict["tool_calls"] = [
                    {"name": tc["name"], "args": tc["args"]}
                    for tc in msg.tool_calls
                ]
            if hasattr(msg, "tool_call_id"):
                msg_dict["tool_call_id"] = msg.tool_call_id
            result.append(msg_dict)
        return result
    
    def _serialize_response(self, response: Any) -> dict:
        """序列化响应"""
        if hasattr(response, "content"):
            return {
                "content": self._truncate(str(response.content), 1000),
                "tool_calls": [
                    {"name": tc["name"], "args": tc["args"]}
                    for tc in (response.tool_calls or [])
                ] if hasattr(response, "tool_calls") else []
            }
        return {"raw": self._truncate(str(response), 1000)}
    
    def _get_content(self, msg) -> str:
        """获取消息内容"""
        if hasattr(msg, "content"):
            content = msg.content
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, str):
                        parts.append(item)
                    elif isinstance(item, dict) and "text" in item:
                        parts.append(item["text"])
                return " ".join(parts)
            return str(content)
        return str(msg)
    
    def _truncate(self, text: str, max_len: int) -> str:
        """截断文本"""
        if len(text) > max_len:
            return text[:max_len] + "...[truncated]"
        return text
    
    def get_callback_handler(self) -> LLMRequestCallbackHandler:
        """获取LangChain回调处理器"""
        return LLMRequestCallbackHandler(self)


_llm_logger: Optional[LLMLogger] = None


def get_llm_logger(log_dir: str = "logs") -> LLMLogger:
    """获取全局LLM日志记录器"""
    global _llm_logger
    if _llm_logger is None:
        _llm_logger = LLMLogger(log_dir)
    return _llm_logger
