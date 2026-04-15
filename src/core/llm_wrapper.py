from langchain_core.messages import (
    BaseMessage, AIMessage, AIMessageChunk, SystemMessage,
    HumanMessage, ToolMessage
)
from langchain_core.tools import BaseTool
from typing import List, Optional, Any, Dict, AsyncGenerator
from dataclasses import dataclass
import json
import os
import time
import asyncio
import tiktoken
from datetime import datetime
from openai import AsyncOpenAI
import openai


@dataclass
class UsageStats:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    call_count: int = 0
    
    def update(self, prompt_tokens: int = 0, completion_tokens: int = 0, total_tokens: int = 0):
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens += total_tokens
        self.call_count += 1
    
    def to_dict(self) -> Dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "call_count": self.call_count
        }
    
    def reset(self):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.call_count = 0


class LLMCaller:
    """LLM 调用封装器
    
    直接使用 openai.AsyncOpenAI SDK 进行 LLM 调用，
    不依赖 LangChain 的 ChatOpenAI，避免类型契约问题。
    输入输出仍使用 LangChain 消息类型以保持兼容性。
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4",
        base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 80000,
        default_headers: Optional[Dict[str, str]] = None,
        tools: Optional[List[BaseTool]] = None,
        system_prompt: Optional[str] = None,
        logger: Optional[Any] = None,
        timeout: float = 300.0,
        max_context_tokens: Optional[int] = None,
        retry_max_count: int = 3,
        retry_initial_delay: float = 10.0,
        retry_max_delay: float = 60.0
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.tools = tools or []
        self.system_prompt = system_prompt
        self.usage_stats = UsageStats()
        self._tool_schemas: Optional[List[Dict[str, Any]]] = None
        self.logger = logger
        self.timeout = timeout
        self.max_context_tokens = max_context_tokens
        self.retry_max_count = retry_max_count
        self.retry_initial_delay = retry_initial_delay
        self.retry_max_delay = retry_max_delay
        
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        if default_headers:
            client_kwargs["default_headers"] = default_headers
        
        self.client = AsyncOpenAI(**client_kwargs)
    
    def bind_tools(self, tools: Optional[List[BaseTool]] = None) -> 'LLMCaller':
        tools_to_bind = tools if tools is not None else self.tools
        
        if tools_to_bind:
            self._tool_schemas = self._get_tool_schemas(tools_to_bind)
            
            if self.logger:
                tool_names = [s.get('function', {}).get('name', 'unknown') for s in self._tool_schemas]
                self.logger.log_agent_action("bind_tools", {
                    "tool_count": len(self._tool_schemas),
                    "tool_names": tool_names,
                    "sample_schema": self._tool_schemas[0] if self._tool_schemas else None
                })
        else:
            self._tool_schemas = None
        
        return self
    
    async def invoke(
        self,
        messages: List[BaseMessage],
        use_tools: bool = True
    ) -> AIMessage:
        full_messages = self._prepare_messages(messages)
        openai_messages = self._convert_messages_to_openai(full_messages)
        
        request_params = self._build_request_params(openai_messages, use_tools)
        
        if self.logger:
            self.logger.log_request(full_messages, self.model)
        
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(**request_params),
                timeout=self.timeout
            )
            
            aimessage = self._convert_openai_response_to_aimessage(response)
            self._update_usage(aimessage)
            
            if self.logger:
                self.logger.log_response(aimessage, self.model)
            
            return aimessage
            
        except Exception as e:
            self._dump_error_request_data(request_params, e)
            raise
    
    async def stream(
        self,
        messages: List[BaseMessage],
        use_tools: bool = True
    ) -> AsyncGenerator[AIMessageChunk, None]:
        full_messages = self._prepare_messages(messages)
        openai_messages = self._convert_messages_to_openai(full_messages)
        request_params = self._build_request_params(openai_messages, use_tools, stream=True)
        
        accumulated_content = ""
        accumulated_tool_calls: Dict[int, Dict] = {}
        
        try:
            stream = await self.client.chat.completions.create(**request_params)
            async for chunk in stream:
                if not chunk.choices:
                    continue
                
                delta = chunk.choices[0].delta
                
                if delta.content:
                    accumulated_content += delta.content
                    yield AIMessageChunk(content=delta.content)
                
                if delta.tool_calls:
                    for tc_chunk in delta.tool_calls:
                        idx = tc_chunk.index
                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {
                                "id": tc_chunk.id or "",
                                "name": "",
                                "args": ""
                            }
                        if tc_chunk.id:
                            accumulated_tool_calls[idx]["id"] = tc_chunk.id
                        if tc_chunk.function and tc_chunk.function.name:
                            accumulated_tool_calls[idx]["name"] = tc_chunk.function.name
                        if tc_chunk.function and tc_chunk.function.arguments:
                            accumulated_tool_calls[idx]["args"] += tc_chunk.function.arguments
        except Exception as e:
            self._dump_error_request_data(request_params, e)
            raise
        
        tool_calls = []
        for idx in sorted(accumulated_tool_calls.keys()):
            tc_data = accumulated_tool_calls[idx]
            try:
                args = json.loads(tc_data["args"]) if tc_data["args"] else {}
            except json.JSONDecodeError:
                args = {}
            tool_calls.append({
                "id": tc_data["id"],
                "name": tc_data["name"],
                "args": args
            })
        
        final_message = AIMessage(content=accumulated_content)
        if tool_calls:
            final_message = AIMessage(content=accumulated_content, tool_calls=tool_calls)
        
        self._update_usage(final_message)
    
    async def stream_call(
        self,
        messages: List[BaseMessage],
        use_tools: bool = True
    ) -> AsyncGenerator[Dict[str, Any], None]:
        from langchain_core.messages import ToolCall
        
        full_messages = self._prepare_messages(messages)
        openai_messages = self._convert_messages_to_openai(full_messages)
        
        if self.logger:
            self.logger.log_request(full_messages, self.model)
        
        accumulated_content = ""
        accumulated_tool_call_chunks: Dict[int, Dict] = {}
        has_content = False
        
        delay = self.retry_initial_delay
        for retry_attempt in range(self.retry_max_count + 1):
            request_params = self._build_request_params(openai_messages, use_tools, stream=True)
            
            try:
                stream = await asyncio.wait_for(
                    self.client.chat.completions.create(**request_params),
                    timeout=self.timeout
                )
                
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    
                    delta = chunk.choices[0].delta
                    has_content = True
                    
                    if delta.content:
                        accumulated_content += delta.content
                        yield {
                            "type": "text_delta",
                            "text": delta.content
                        }
                    
                    if delta.tool_calls:
                        for tc_chunk in delta.tool_calls:
                            index = tc_chunk.index
                            
                            if index not in accumulated_tool_call_chunks:
                                accumulated_tool_call_chunks[index] = {
                                    "id": tc_chunk.id or "",
                                    "name": "",
                                    "args": ""
                                }
                            
                            if tc_chunk.id:
                                accumulated_tool_call_chunks[index]["id"] = tc_chunk.id
                            if tc_chunk.function and tc_chunk.function.name:
                                accumulated_tool_call_chunks[index]["name"] = tc_chunk.function.name
                            if tc_chunk.function and tc_chunk.function.arguments:
                                accumulated_tool_call_chunks[index]["args"] += tc_chunk.function.arguments
                
                if not has_content:
                    if retry_attempt < self.retry_max_count:
                        if self.logger:
                            self.logger.log_error("stream_call_retry", Exception(
                                f"LLM 返回空响应，第{retry_attempt + 1}次重试，等待{delay}秒"
                            ))
                        yield {
                            "type": "retry",
                            "attempt": retry_attempt + 1,
                            "delay": delay,
                            "message": f"LLM 返回空响应，{delay}秒后重试"
                        }
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, self.retry_max_delay)
                        accumulated_content = ""
                        accumulated_tool_call_chunks = {}
                        has_content = False
                        continue
                    else:
                        if self.logger:
                            self.logger.log_error("stream_call", Exception("LLM returned empty response"))
                        yield {
                            "type": "error",
                            "message": f"LLM 返回空响应，已重试{self.retry_max_count}次"
                        }
                        return
                
                tool_calls = []
                for index in sorted(accumulated_tool_call_chunks.keys()):
                    chunk_data = accumulated_tool_call_chunks[index]
                    args_str = chunk_data.get("args", "{}")
                    try:
                        args = json.loads(args_str) if args_str else {}
                    except json.JSONDecodeError:
                        args = {}
                    
                    tool_call = ToolCall(
                        id=chunk_data.get("id", f"tool_{index}"),
                        name=chunk_data.get("name", ""),
                        args=args
                    )
                    tool_calls.append(tool_call)
                    
                    yield {
                        "type": "tool_call_start",
                        "tool": {
                            "id": tool_call["id"],
                            "name": tool_call["name"],
                            "args": tool_call["args"]
                        }
                    }
                
                final_message = AIMessage(
                    content=accumulated_content,
                    tool_calls=tool_calls
                )
                
                self._update_usage(final_message)
                
                if self.logger:
                    self.logger.log_response(final_message, self.model)
                
                usage_data = {}
                if hasattr(final_message, 'usage_metadata') and final_message.usage_metadata:
                    usage_data = {
                        "input_tokens": final_message.usage_metadata.get("input_tokens", 0),
                        "output_tokens": final_message.usage_metadata.get("output_tokens", 0),
                        "total_tokens": final_message.usage_metadata.get("total_tokens", 0),
                    }
                
                yield {
                    "type": "complete",
                    "response": final_message,
                    "usage": usage_data,
                }
                return
                
            except asyncio.TimeoutError:
                self._dump_error_request_data(request_params, asyncio.TimeoutError(f"LLM 调用超时（{self.timeout}秒）"))
                if retry_attempt < self.retry_max_count:
                    if self.logger:
                        self.logger.log_error("stream_call_retry", Exception(
                            f"LLM 调用超时（{self.timeout}秒），第{retry_attempt + 1}次重试，等待{delay}秒"
                        ))
                    yield {
                        "type": "retry",
                        "attempt": retry_attempt + 1,
                        "delay": delay,
                        "message": f"LLM 调用超时（{self.timeout}秒），{delay}秒后重试"
                    }
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, self.retry_max_delay)
                    accumulated_content = ""
                    accumulated_tool_call_chunks = {}
                    has_content = False
                else:
                    error_msg = f"LLM 调用超时（{self.timeout}秒），已重试{self.retry_max_count}次"
                    if self.logger:
                        self.logger.log_error("stream_call", Exception(error_msg))
                    yield {
                        "type": "error",
                        "message": error_msg
                    }
                    return
            except Exception as e:
                self._dump_error_request_data(request_params, e)
                if self._is_retryable_error(e) and retry_attempt < self.retry_max_count:
                    if self.logger:
                        self.logger.log_error("stream_call_retry", Exception(
                            f"LLM 调用异常（{type(e).__name__}: {str(e)[:100]}），第{retry_attempt + 1}次重试，等待{delay}秒"
                        ))
                    yield {
                        "type": "retry",
                        "attempt": retry_attempt + 1,
                        "delay": delay,
                        "message": f"LLM 调用异常（{type(e).__name__}），{delay}秒后重试"
                    }
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, self.retry_max_delay)
                    accumulated_content = ""
                    accumulated_tool_call_chunks = {}
                    has_content = False
                else:
                    if self.logger:
                        self.logger.log_error("stream_call", e)
                    yield {
                        "type": "error",
                        "message": str(e)
                    }
                    return
    
    def get_usage_stats(self) -> Dict[str, int]:
        return self.usage_stats.to_dict()
    
    def reset_usage_stats(self):
        self.usage_stats.reset()
    
    @staticmethod
    def _is_retryable_error(e: Exception) -> bool:
        try:
            if isinstance(e, (openai.APITimeoutError, openai.APIConnectionError,
                              openai.RateLimitError)):
                return True
        except AttributeError:
            pass
        
        if isinstance(e, (ConnectionError, ConnectionResetError, ConnectionAbortedError,
                          BrokenPipeError, OSError)):
            return True
        
        try:
            if isinstance(e, openai.APIStatusError) and e.status_code >= 500:
                return True
        except AttributeError:
            pass
        
        error_str = str(e).lower()
        retryable_keywords = [
            "rate limit", "rate_limit", "429",
            "timeout", "timed out",
            "connection", "network",
            "server error", "500", "502", "503", "504",
            "overloaded", "capacity",
            "null value for 'choices'",
        ]
        return any(kw in error_str for kw in retryable_keywords)
    
    def _convert_messages_to_openai(self, messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        result = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                result.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                result.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                entry: Dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    openai_tool_calls = []
                    for tc in msg.tool_calls:
                        if isinstance(tc, dict):
                            openai_tool_calls.append({
                                "id": tc.get("id", ""),
                                "type": "function",
                                "function": {
                                    "name": tc.get("name", ""),
                                    "arguments": json.dumps(tc.get("args", {}), ensure_ascii=False)
                                }
                            })
                        else:
                            openai_tool_calls.append({
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": json.dumps(tc["args"], ensure_ascii=False)
                                }
                            })
                    entry["tool_calls"] = openai_tool_calls
                result.append(entry)
            elif isinstance(msg, ToolMessage):
                content = msg.content
                if not isinstance(content, str):
                    content = json.dumps(content, ensure_ascii=False)
                result.append({
                    "role": "tool",
                    "content": content,
                    "tool_call_id": msg.tool_call_id or ""
                })
            else:
                result.append({"role": getattr(msg, 'type', 'user'), "content": msg.content})
        
        return result
    
    def _convert_openai_response_to_aimessage(self, response) -> AIMessage:
        choice = response.choices[0] if response.choices else None
        if not choice:
            return AIMessage(content="")
        
        message = choice.message
        content = message.content or ""
        
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "args": args
                })
        
        usage_metadata = {}
        if response.usage:
            usage_metadata = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        
        aimessage = AIMessage(content=content, tool_calls=tool_calls)
        if usage_metadata:
            aimessage.usage_metadata = usage_metadata
        
        return aimessage
    
    def _build_request_params(
        self,
        openai_messages: List[Dict[str, Any]],
        use_tools: bool,
        stream: bool = False
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        
        if stream:
            params["stream"] = True
        
        if use_tools and self.tools:
            if self._tool_schemas is None:
                self.bind_tools()
            if self._tool_schemas:
                params["tools"] = self._tool_schemas
        
        return params
    
    def _dump_error_request_data(self, request_params: Dict[str, Any], error: Exception) -> None:
        try:
            logs_dir = os.path.join(os.getcwd(), "logs")
            os.makedirs(logs_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"llm_error_req_data_{timestamp}.log"
            filepath = os.path.join(logs_dir, filename)
            
            dump_data = {
                "error_type": type(error).__name__,
                "error_message": str(error),
                "timestamp": datetime.now().isoformat(),
                "request": request_params
            }
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(dump_data, f, ensure_ascii=False, indent=2, default=str)
        except Exception:
            pass
    
    def _prepare_messages(
        self,
        messages: List[BaseMessage]
    ) -> List[BaseMessage]:
        full_messages = []
        
        if self.system_prompt:
            full_messages.append(SystemMessage(content=self.system_prompt))
        
        full_messages.extend(messages)

        total_chars = sum(len(str(m.content)) for m in full_messages)
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            estimated_tokens = sum(len(encoding.encode(str(m.content))) for m in full_messages)
        except Exception:
            estimated_tokens = total_chars // 4

        if self.logger:
            self.logger.log_agent_action("token_estimation", {
                "message_count": len(full_messages),
                "estimated_tokens": estimated_tokens,
                "total_chars": total_chars,
            })
        
        if self.max_context_tokens and estimated_tokens >= self.max_context_tokens - 3000:
            if self.logger:
                self.logger.log_agent_action("blocking_limit_warning", {
                    "estimated_tokens": estimated_tokens,
                    "blocking_limit": self.max_context_tokens - 3000,
                    "message": "Token count exceeds blocking limit, but proceeding - QueryEngine handles this",
                })
        
        return full_messages
    
    def _get_tool_schemas(self, tools: List[BaseTool]) -> List[Dict[str, Any]]:
        schemas = []
        for tool in tools:
            tool_def = None
            
            if hasattr(tool, 'tool_call_schema') and tool.tool_call_schema is not None:
                tcs = tool.tool_call_schema
                if isinstance(tcs, dict):
                    if 'type' in tcs and 'function' in tcs:
                        tool_def = tcs
                    else:
                        tool_def = {
                            "type": "function",
                            "function": tcs
                        }
                elif hasattr(tcs, 'model_json_schema'):
                    try:
                        schema = tcs.model_json_schema()
                        cleaned_schema = self._clean_schema(schema)
                        tool_def = {
                            "type": "function",
                            "function": {
                                "name": tool.name,
                                "description": tool.description or f"Execute {tool.name}",
                                "parameters": cleaned_schema
                            }
                        }
                    except Exception:
                        pass
            
            if tool_def is None and hasattr(tool, 'args_schema') and tool.args_schema is not None:
                try:
                    if hasattr(tool.args_schema, 'model_json_schema'):
                        schema = tool.args_schema.model_json_schema()
                    elif hasattr(tool.args_schema, 'schema'):
                        schema = tool.args_schema.schema()
                    else:
                        schema = {"type": "object", "properties": {}}
                    
                    if isinstance(schema, dict):
                        cleaned_schema = self._clean_schema(schema)
                    else:
                        cleaned_schema = {"type": "object", "properties": {}}
                    
                    tool_def = {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or f"Execute {tool.name}",
                            "parameters": cleaned_schema
                        }
                    }
                except Exception:
                    tool_def = {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or f"Execute {tool.name}",
                            "parameters": {"type": "object", "properties": {}}
                        }
                    }
            
            if tool_def is None:
                tool_def = {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or f"Execute {tool.name}",
                        "parameters": {"type": "object", "properties": {}}
                    }
                }
            
            schemas.append(tool_def)
        
        return schemas
    
    def _clean_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = {}
        
        if 'type' in schema:
            cleaned['type'] = schema['type']
        else:
            cleaned['type'] = 'object'
        
        if 'properties' in schema:
            cleaned['properties'] = schema['properties']
        else:
            cleaned['properties'] = {}
        
        if 'required' in schema:
            cleaned['required'] = schema['required']
        
        if 'description' in schema:
            cleaned['description'] = schema['description']
        
        return cleaned
    
    def _update_usage(self, response: AIMessage) -> None:
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            self.usage_stats.update(
                prompt_tokens=response.usage_metadata.get("input_tokens", 0),
                completion_tokens=response.usage_metadata.get("output_tokens", 0),
                total_tokens=response.usage_metadata.get("total_tokens", 0)
            )
