import logging
import json
from pathlib import Path
from typing import Any, Optional, List, Dict
import sys
from contextvars import ContextVar
from langchain_core.callbacks import BaseCallbackHandler


_role_context: ContextVar[Dict[str, Optional[str]]] = ContextVar('role_context', default={})


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
    
    _LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"
    
    def __init__(self, log_dir: str = "logs", tool_log_mode: str = "summary", log_format: str = "compact"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.tool_log_mode = tool_log_mode
        self.log_format = log_format
        
        self._setup_loggers()
    
    def _setup_loggers(self):
        """设置多个日志记录器"""
        self.llm_logger = self._create_logger("llm", self.log_dir / "llm.log")
        self.tool_logger = self._create_logger("tool", self.log_dir / "tool.log")
        self.agent_logger = self._create_logger("agent", self.log_dir / "agent.log")
    
    def set_tool_log_mode(self, mode: str) -> None:
        """设置工具日志模式
        
        Args:
            mode: "summary"（摘要模式）或 "detailed"（详细模式）
        """
        self.tool_log_mode = mode
    
    def set_log_format(self, format_type: str) -> None:
        """设置日志格式
        
        Args:
            format_type: "compact"（紧凑模式）或 "detailed"（详细模式）
        """
        self.log_format = format_type
    
    def set_role_context(self, role_name: str, parent_role: Optional[str] = None) -> None:
        """设置当前角色上下文
        
        Args:
            role_name: 当前角色名称
            parent_role: 父角色名称（可选）
        """
        _role_context.set({"role": role_name, "parent": parent_role})
    
    def clear_role_context(self) -> None:
        """清除角色上下文"""
        _role_context.set({})
    
    def get_role_prefix(self) -> str:
        """获取角色前缀字符串
        
        Returns:
            角色前缀，如 "[role: test-suite-executor]" 或 "[role: test-case-executor, parent: test-suite-executor]"
        """
        ctx = _role_context.get()
        role = ctx.get("role")
        parent = ctx.get("parent")
        
        if not role:
            return ""
        
        if parent:
            return f"[role: {role}, parent: {parent}]"
        return f"[role: {role}]"
    
    def _get_role_str(self) -> str:
        """获取格式化的角色字符串，用于日志前缀"""
        role_prefix = self.get_role_prefix()
        return f" {role_prefix}" if role_prefix else ""
    
    @staticmethod
    def _extract_tool_name(tool) -> str:
        """从各种工具表示中提取工具名称
        
        支持的格式：
        - dict with 'function' key (OpenAI format): {"function": {"name": "..."}}
        - dict with 'name' key: {"name": "..."}
        - object with 'name' attribute
        - 其他类型转为字符串
        """
        if isinstance(tool, dict):
            if 'function' in tool and isinstance(tool.get('function'), dict):
                return tool.get('function', {}).get('name', 'unknown')
            elif 'name' in tool:
                return tool.get('name', 'unknown')
            else:
                return 'unknown'
        elif hasattr(tool, 'name'):
            return tool.name
        else:
            return str(tool)
    
    def _format_compact(self, data: dict, indent: int = 0) -> str:
        """格式化字典为紧凑键值对
        
        Args:
            data: 要格式化的字典
            indent: 缩进级别
            
        Returns:
            紧凑格式的字符串
        """
        lines = []
        prefix = "  " * indent
        
        for key, value in data.items():
            if isinstance(value, dict):
                if self._is_simple_dict(value):
                    lines.append(f"{prefix}{key}: {self._format_simple_dict(value)}")
                else:
                    lines.append(f"{prefix}{key}:")
                    lines.append(self._format_compact(value, indent + 1))
            elif isinstance(value, list):
                formatted_list = self._format_list(value, key)
                lines.append(f"{prefix}{formatted_list}")
            else:
                lines.append(f"{prefix}{key}: {self._format_value(value)}")
        
        return "\n".join(lines)
    
    def _is_simple_dict(self, d: dict) -> bool:
        """检查字典是否简单（所有值都是基本类型）"""
        return all(not isinstance(v, (dict, list)) for v in d.values())
    
    def _format_simple_dict(self, d: dict) -> str:
        """格式化简单字典为单行"""
        items = [f"{k}={self._format_value(v, 100)}" for k, v in d.items()]
        return ", ".join(items)
    
    def _format_value(self, value: Any, max_len: int = 200) -> str:
        """格式化值，支持截断
        
        Args:
            value: 要格式化的值
            max_len: 最大长度
            
        Returns:
            格式化后的字符串
        """
        if value is None:
            return "null"
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            if len(value) > max_len:
                return f'"{value[:max_len]}..."'
            return f'"{value}"'
        else:
            s = str(value)
            if len(s) > max_len:
                return f"{s[:max_len]}..."
            return s
    
    def _format_list(self, items: list, key: str, max_items: int = 5) -> str:
        """格式化列表，支持截断
        
        Args:
            items: 列表项
            key: 键名
            max_items: 最大显示项数
            
        Returns:
            格式化后的字符串
        """
        if not items:
            return f"{key}: []"
        
        if len(items) <= max_items:
            formatted_items = []
            for i, item in enumerate(items):
                if isinstance(item, dict):
                    if "name" in item:
                        formatted_items.append(f"{key}[{i}]: name={item.get('name')}, " + 
                                             self._format_simple_dict({k: v for k, v in item.items() if k != "name"}))
                    else:
                        formatted_items.append(f"{key}[{i}]: {self._format_simple_dict(item)}")
                else:
                    formatted_items.append(f"{key}[{i}]: {self._format_value(item)}")
            return "\n  ".join(formatted_items) if formatted_items else f"{key}: []"
        else:
            return f"{key}: [{len(items)} items, showing first {max_items}]"
    
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
            tool_name = self._extract_tool_name(tool)
            
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
    
    def _create_logger(self, name: str, file_path: Path) -> logging.Logger:
        """创建日志记录器"""
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        logger.handlers = []
        
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(self._LOG_FORMAT))
        logger.addHandler(file_handler)
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(self._LOG_FORMAT))
        logger.addHandler(console_handler)
        
        return logger
    
    def log_request(self, messages: list, model: str, **kwargs):
        """记录LLM请求"""
        role_str = self._get_role_str()
        
        if self.log_format == "compact":
            request_data = {
                "model": model,
                "message_count": len(messages),
            }
            
            messages_summary = []
            for i, msg in enumerate(messages[:5]):
                msg_type = getattr(msg, "type", "unknown")
                content = self._truncate(self._get_content(msg), 100)
                messages_summary.append(f"type={msg_type}, content=\"{content}\"")
            
            request_data["messages_summary"] = messages_summary
            if kwargs:
                request_data["extra"] = kwargs
            
            log_message = f"REQUEST{role_str}:\n{self._format_compact(request_data)}"
        else:
            request_data = {
                "type": "request",
                "model": model,
                "message_count": len(messages),
                "messages": self._serialize_messages(messages),
                "extra": kwargs
            }
            log_message = f"REQUEST{role_str}: {json.dumps(request_data, ensure_ascii=False, indent=2)}"
        
        self.llm_logger.info(log_message)
    
    def log_request_raw(self, request_body: dict, model: str):
        """记录LLM原始请求报文"""
        role_str = self._get_role_str()
        
        if self.log_format == "compact":
            compact_data = {
                "model": request_body.get("model", model),
            }
            
            if "temperature" in request_body:
                compact_data["temperature"] = request_body["temperature"]
            if "max_tokens" in request_body:
                compact_data["max_tokens"] = request_body["max_tokens"]
            
            if "tools" in request_body:
                if self.tool_log_mode == "summary":
                    compact_data["tools_summary"] = self._format_tools_summary(request_body["tools"])
                else:
                    compact_data["tools"] = [self._extract_tool_name(t) for t in request_body["tools"]]
            
            if "messages" in request_body:
                messages = request_body["messages"]
                if isinstance(messages, list):
                    compact_data["messages_count"] = len(messages)
            
            log_message = f"REQUEST_RAW{role_str}:\n{self._format_compact(compact_data)}"
        else:
            if self.tool_log_mode == "summary" and "tools" in request_body:
                tools = request_body.get("tools", [])
                tools_summary = self._format_tools_summary(tools)
                log_body = {k: v for k, v in request_body.items() if k != "tools"}
                log_body["tools_summary"] = tools_summary
                log_message = f"REQUEST_RAW{role_str}: {json.dumps(log_body, ensure_ascii=False, indent=2)}"
            else:
                log_message = f"REQUEST_RAW{role_str}: {json.dumps(request_body, ensure_ascii=False, indent=2)}"
        
        self.llm_logger.debug(log_message)
    
    def log_response(self, response: Any, model: str):
        """记录LLM响应"""
        role_str = self._get_role_str()
        
        if self.log_format == "compact":
            response_data = {
                "model": model,
            }
            
            if hasattr(response, "content"):
                content = str(response.content)
                response_data["content"] = self._truncate(content, 200)
            
            if hasattr(response, "tool_calls") and response.tool_calls:
                tool_calls_summary = []
                for tc in response.tool_calls:
                    tool_calls_summary.append(f"name={tc.get('name', 'unknown')}")
                response_data["tool_calls"] = tool_calls_summary
            
            log_message = f"RESPONSE{role_str}:\n{self._format_compact(response_data)}"
        else:
            response_data = {
                "type": "response",
                "model": model,
                "response": self._serialize_response(response)
            }
            log_message = f"RESPONSE{role_str}: {json.dumps(response_data, ensure_ascii=False, indent=2)}"
        
        self.llm_logger.info(log_message)
    
    def log_tool_call(self, tool_name: str, arguments: dict):
        """记录工具调用"""
        role_str = self._get_role_str()
        
        if self.log_format == "compact":
            call_data = {
                "tool": tool_name,
            }
            
            if arguments:
                for key, value in list(arguments.items())[:5]:
                    call_data[f"args.{key}"] = self._format_value(value, 150)
            
            log_message = f"TOOL_CALL{role_str}:\n{self._format_compact(call_data)}"
        else:
            call_data = {
                "type": "tool_call",
                "tool": tool_name,
                "arguments": arguments
            }
            log_message = f"TOOL_CALL{role_str}: {json.dumps(call_data, ensure_ascii=False, indent=2)}"
        
        self.tool_logger.info(log_message)
    
    def log_tool_result(self, tool_name: str, result: Any, error: Optional[str] = None):
        """记录工具结果"""
        role_str = self._get_role_str()
        
        if self.log_format == "compact":
            result_data = {
                "tool": tool_name,
            }
            
            if error:
                result_data["error"] = error
            else:
                result_str = str(result)
                result_data["result"] = self._truncate(result_str, 300)
            
            log_message = f"TOOL_RESULT{role_str}:\n{self._format_compact(result_data)}"
        else:
            result_data = {
                "type": "tool_result",
                "tool": tool_name,
                "error": error,
                "result": self._truncate(str(result), 2000)
            }
            log_message = f"TOOL_RESULT{role_str}: {json.dumps(result_data, ensure_ascii=False, indent=2)}"
        
        self.tool_logger.info(log_message)
    
    def log_agent_thinking(self, thought: str):
        """记录Agent思考过程"""
        role_str = self._get_role_str()
        self.agent_logger.info(f"THINKING{role_str}: {thought}")
    
    def log_agent_action(self, action: str, details: dict = None):
        """记录Agent行动"""
        role_str = self._get_role_str()
        
        if self.log_format == "compact":
            action_data = {"action": action}
            if details:
                for key, value in list(details.items())[:5]:
                    action_data[key] = self._format_value(value, 150)
            log_message = f"ACTION{role_str}: {self._format_simple_dict(action_data)}"
        else:
            action_data = {
                "action": action,
                "details": details or {}
            }
            log_message = f"ACTION{role_str}: {json.dumps(action_data, ensure_ascii=False)}"
        
        self.agent_logger.info(log_message)
    
    def log_error(self, source: str, error: Exception):
        """记录错误"""
        role_str = self._get_role_str()
        
        if self.log_format == "compact":
            error_data = {
                "source": source,
                "error_type": type(error).__name__,
                "error_message": self._truncate(str(error), 300)
            }
            log_message = f"ERROR{role_str}:\n{self._format_compact(error_data)}"
        else:
            error_data = {
                "source": source,
                "error_type": type(error).__name__,
                "error_message": str(error)
            }
            log_message = f"ERROR{role_str}: {json.dumps(error_data, ensure_ascii=False)}"
        
        self.agent_logger.error(log_message)
    
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
            return text[:max_len] + "..."
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
