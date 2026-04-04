from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, AIMessage, AIMessageChunk, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.tools import BaseTool
from typing import List, Optional, Any, Dict, AsyncGenerator
from dataclasses import dataclass, field
import time
import asyncio


@dataclass
class UsageStats:
    """使用量统计"""
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


class RobustChatOpenAI(ChatOpenAI):
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                result = super()._generate(messages, stop, run_manager, **kwargs)
                
                if result.generations and len(result.generations) > 0:
                    return result
                else:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    else:
                        return ChatResult(
                            generations=[ChatGeneration(
                                message=BaseMessage(content="API返回空响应，请重试", type="ai")
                            )]
                        )
                        
            except TypeError as e:
                if "null value for 'choices'" in str(e):
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    else:
                        return ChatResult(
                            generations=[ChatGeneration(
                                message=BaseMessage(
                                    content="API响应格式异常(choices为null)，已达到最大重试次数",
                                    type="ai"
                                )
                            )]
                        )
                else:
                    raise
            except Exception as e:
                raise
        
        return ChatResult(
            generations=[ChatGeneration(
                message=BaseMessage(content="生成失败，请重试", type="ai")
            )]
        )

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                result = await super()._agenerate(messages, stop, run_manager, **kwargs)
                
                if result.generations and len(result.generations) > 0:
                    return result
                else:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        return ChatResult(
                            generations=[ChatGeneration(
                                message=BaseMessage(content="API返回空响应，请重试", type="ai")
                            )]
                        )
                        
            except TypeError as e:
                if "null value for 'choices'" in str(e):
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        return ChatResult(
                            generations=[ChatGeneration(
                                message=BaseMessage(
                                    content="API响应格式异常(choices为null)，已达到最大重试次数",
                                    type="ai"
                                )
                            )]
                        )
                else:
                    raise
            except Exception as e:
                raise
        
        return ChatResult(
            generations=[ChatGeneration(
                message=BaseMessage(content="生成失败，请重试", type="ai")
            )]
        )

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> Any:
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                has_content = False
                async for chunk in super()._astream(messages, stop, run_manager, **kwargs):
                    has_content = True
                    yield chunk
                
                if has_content:
                    return
                else:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        yield BaseMessage(content="API返回空响应，请重试", type="ai")
                        return
                        
            except TypeError as e:
                if "null value for 'choices'" in str(e):
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        yield BaseMessage(
                            content="API响应格式异常(choices为null)，已达到最大重试次数",
                            type="ai"
                        )
                        return
                else:
                    raise
            except Exception as e:
                raise
        
        yield BaseMessage(content="生成失败，请重试", type="ai")


class LLMCaller:
    """LLM 调用封装器
    
    封装 LangChain 的 LLM 调用，提供统一的接口。
    复用现有的 RobustChatOpenAI 实现。
    """
    
    def __init__(
        self,
        llm,
        tools: Optional[List[BaseTool]] = None,
        system_prompt: Optional[str] = None,
        logger: Optional[Any] = None,
        timeout: float = 300.0
    ):
        self.llm = llm
        self.tools = tools or []
        self.system_prompt = system_prompt
        self.usage_stats = UsageStats()
        self._bound_llm = None
        self.logger = logger
        self.timeout = timeout
    
    def bind_tools(self, tools: Optional[List[BaseTool]] = None) -> 'LLMCaller':
        """绑定工具到 LLM
        
        Args:
            tools: 要绑定的工具列表，如果为 None 则使用初始化时的工具
            
        Returns:
            LLMCaller: 返回自身以支持链式调用
        """
        tools_to_bind = tools if tools is not None else self.tools
        
        if tools_to_bind:
            tool_schemas = self._get_tool_schemas(tools_to_bind)
            
            if self.logger:
                tool_names = [s.get('function', {}).get('name', 'unknown') for s in tool_schemas]
                self.logger.log_agent_action("bind_tools", {
                    "tool_count": len(tool_schemas),
                    "tool_names": tool_names,
                    "sample_schema": tool_schemas[0] if tool_schemas else None
                })
            
            self._bound_llm = self.llm.bind_tools(tool_schemas)
        else:
            self._bound_llm = None
        
        return self
    
    async def invoke(
        self,
        messages: List[BaseMessage],
        use_tools: bool = True
    ) -> AIMessage:
        """非流式调用 LLM
        
        Args:
            messages: 消息列表
            use_tools: 是否使用工具
            
        Returns:
            AIMessage: AI 响应消息
        """
        full_messages = self._prepare_messages(messages)
        
        llm_to_use = self._get_llm_with_tools(use_tools)
        response = await llm_to_use.ainvoke(full_messages)
        
        self._update_usage(response)
        
        return response
    
    async def stream(
        self,
        messages: List[BaseMessage],
        use_tools: bool = True
    ) -> AsyncGenerator[AIMessageChunk, None]:
        """流式调用 LLM
        
        Args:
            messages: 消息列表
            use_tools: 是否使用工具
            
        Yields:
            AIMessageChunk: 流式响应块
        """
        full_messages = self._prepare_messages(messages)
        llm_to_use = self._get_llm_with_tools(use_tools)
        
        accumulated_content = ""
        accumulated_tool_calls = []
        current_tool_call = None
        
        async for chunk in llm_to_use.astream(full_messages):
            if isinstance(chunk, AIMessageChunk):
                if chunk.content:
                    accumulated_content += chunk.content
                    yield chunk
                
                if hasattr(chunk, 'tool_call_chunks') and chunk.tool_call_chunks:
                    for tool_chunk in chunk.tool_call_chunks:
                        if isinstance(tool_chunk, dict):
                            if tool_chunk.get("type") == "tool_call_start":
                                current_tool_call = {
                                    "id": tool_chunk.get("id"),
                                    "name": tool_chunk.get("name"),
                                    "args": {}
                                }
                                accumulated_tool_calls.append(current_tool_call)
                            elif tool_chunk.get("type") == "tool_call_arg":
                                if current_tool_call:
                                    arg_key = tool_chunk.get("arg_name")
                                    arg_value = tool_chunk.get("arg_value")
                                    if arg_key and arg_value:
                                        current_tool_call["args"][arg_key] = arg_value
        
        final_message = AIMessage(
            content=accumulated_content
        )
        
        if accumulated_tool_calls:
            final_message = AIMessage(
                content=accumulated_content,
                tool_calls=accumulated_tool_calls
            )
        
        self._update_usage(final_message)
    
    async def stream_call(
        self,
        messages: List[BaseMessage],
        use_tools: bool = True
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式调用 LLM 并返回结构化数据
        
        Args:
            messages: 消息列表
            use_tools: 是否使用工具
            
        Yields:
            Dict[str, Any]: 流式响应块，包含 type 和相关数据
        """
        import json
        from langchain_core.messages import ToolCall
        
        full_messages = self._prepare_messages(messages)
        llm_to_use = self._get_llm_with_tools(use_tools)
        
        if self.logger:
            self.logger.log_request(full_messages, self.llm.model_name if hasattr(self.llm, 'model_name') else 'unknown')
        
        accumulated_content = ""
        accumulated_tool_call_chunks: Dict[int, Dict] = {}
        has_content = False
        
        try:
            async with asyncio.timeout(self.timeout):
                async for chunk in llm_to_use.astream(full_messages):
                    has_content = True
                    if isinstance(chunk, AIMessageChunk):
                        if chunk.content:
                            accumulated_content += chunk.content
                            yield {
                                "type": "text_delta",
                                "text": chunk.content
                            }
                        
                        if hasattr(chunk, 'tool_call_chunks') and chunk.tool_call_chunks:
                            for tool_chunk in chunk.tool_call_chunks:
                                if isinstance(tool_chunk, dict):
                                    index = tool_chunk.get("index", 0)
                                    
                                    if index not in accumulated_tool_call_chunks:
                                        accumulated_tool_call_chunks[index] = {
                                            "id": tool_chunk.get("id", ""),
                                            "name": tool_chunk.get("name", ""),
                                            "args": ""
                                        }
                                    
                                    if tool_chunk.get("id"):
                                        accumulated_tool_call_chunks[index]["id"] = tool_chunk["id"]
                                    if tool_chunk.get("name"):
                                        accumulated_tool_call_chunks[index]["name"] = tool_chunk["name"]
                                    if tool_chunk.get("args"):
                                        accumulated_tool_call_chunks[index]["args"] += tool_chunk["args"]
            
            if not has_content:
                if self.logger:
                    self.logger.log_error("stream_call", Exception("LLM returned empty response"))
                yield {
                    "type": "error",
                    "message": "LLM 返回空响应"
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
                self.logger.log_response(final_message, self.llm.model_name if hasattr(self.llm, 'model_name') else 'unknown')
            
            yield {
                "type": "complete",
                "response": final_message
            }
            
        except asyncio.TimeoutError:
            error_msg = f"LLM 调用超时（{self.timeout}秒）"
            if self.logger:
                self.logger.log_error("stream_call", Exception(error_msg))
            yield {
                "type": "error",
                "message": error_msg
            }
        except Exception as e:
            if self.logger:
                self.logger.log_error("stream_call", e)
            yield {
                "type": "error",
                "message": str(e)
            }
    
    def get_usage_stats(self) -> Dict[str, int]:
        """获取使用量统计
        
        Returns:
            Dict[str, int]: 使用量统计字典
        """
        return self.usage_stats.to_dict()
    
    def reset_usage_stats(self):
        """重置使用量统计"""
        self.usage_stats.reset()
    
    def _prepare_messages(
        self,
        messages: List[BaseMessage]
    ) -> List[BaseMessage]:
        """准备消息列表
        
        Args:
            messages: 原始消息列表
            
        Returns:
            List[BaseMessage]: 准备好的消息列表
        """
        full_messages = []
        
        if self.system_prompt:
            full_messages.append(SystemMessage(content=self.system_prompt))
        
        full_messages.extend(messages)
        
        return full_messages
    
    def _get_llm_with_tools(self, use_tools: bool):
        """获取带工具绑定的 LLM
        
        Args:
            use_tools: 是否使用工具
            
        Returns:
            LLM 实例（可能绑定了工具）
        """
        if use_tools and self.tools:
            if self._bound_llm is None:
                self.bind_tools()
            return self._bound_llm if self._bound_llm else self.llm
        return self.llm
    
    def _get_tool_schemas(self, tools: List[BaseTool]) -> List[Dict[str, Any]]:
        """获取工具 schema 列表
        
        Args:
            tools: 工具列表
            
        Returns:
            List[Dict[str, Any]]: 工具 schema
        """
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
        """清理 schema，移除不需要的字段
        
        Args:
            schema: 原始 schema
            
        Returns:
            Dict[str, Any]: 清理后的 schema
        """
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
        """更新使用量统计
        
        Args:
            response: AI 响应
        """
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            self.usage_stats.update(
                prompt_tokens=response.usage_metadata.get("input_tokens", 0),
                completion_tokens=response.usage_metadata.get("output_tokens", 0),
                total_tokens=response.usage_metadata.get("total_tokens", 0)
            )
