from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_community.tools import ShellTool
from typing import List, Optional
import time

from ..config.loader import ConfigLoader
from ..config.models import AppConfig
from ..mcp.tools import get_all_tools
from ..skills.loader import SkillLoader
from ..context.manager import ContextManager
from .sub_agents import spawn_agent, init_sub_agent_manager
from ..utils.logger import get_llm_logger


def _content_to_str(content) -> str:
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


def _estimate_tokens(messages: List) -> int:
    """估算消息的token数量（粗略估计：1 token ≈ 4 字符）"""
    total = 0
    for msg in messages:
        content_str = _content_to_str(msg.content)
        total += len(content_str) // 4
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            for tc in msg.tool_calls:
                total += len(str(tc.get('name', ''))) // 4
                total += len(str(tc.get('args', {}))) // 4
    return total


def _compress_messages(messages: List, max_tokens: int = 50000) -> List:
    """压缩消息列表，保持在token限制内"""
    current_tokens = _estimate_tokens(messages)
    
    if current_tokens <= max_tokens:
        return messages
    
    system_messages = [m for m in messages if isinstance(m, SystemMessage)]
    other_messages = [m for m in messages if not isinstance(m, SystemMessage)]
    
    if len(other_messages) <= 4:
        return messages
    
    keep_recent = 6
    recent_messages = other_messages[-keep_recent:]
    old_messages = other_messages[:-keep_recent]
    
    summary_parts = []
    for i, msg in enumerate(old_messages):
        role = "用户" if isinstance(msg, HumanMessage) else "AI" if isinstance(msg, AIMessage) else "工具"
        content_str = _content_to_str(msg.content)
        content = content_str[:300] + "..." if len(content_str) > 300 else content_str
        
        if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
            tool_names = [tc.get('name', 'unknown') for tc in msg.tool_calls]
            summary_parts.append(f"[{role}]: 调用工具: {', '.join(tool_names)}")
        else:
            summary_parts.append(f"[{role}]: {content}")
    
    summary = HumanMessage(content=f"[历史摘要]\n" + "\n".join(summary_parts[-10:]))
    
    return system_messages + [summary] + recent_messages


def _convert_messages_for_api(messages: List) -> List:
    """转换消息格式以兼容DeepSeek API"""
    converted = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            converted.append(ToolMessage(
                content=_content_to_str(msg.content),
                tool_call_id=msg.tool_call_id
            ))
        elif isinstance(msg, AIMessage):
            converted.append(AIMessage(
                content=_content_to_str(msg.content),
                tool_calls=msg.tool_calls if hasattr(msg, 'tool_calls') else []
            ))
        else:
            converted.append(msg)
    return converted


class RubatoAgent:
    """自然语言驱动的自动化测试执行 Agent"""
    
    MAX_CONTEXT_TOKENS = 80000
    
    def __init__(
        self, 
        config: AppConfig,
        skill_loader: SkillLoader,
        context_manager: ContextManager,
        mcp_manager = None
    ):
        self.config = config
        self.skill_loader = skill_loader
        self.context_manager = context_manager
        self.mcp_manager = mcp_manager
        self.logger = get_llm_logger()
        
        self.llm = self._create_llm()
        self.system_prompt = self._load_system_prompt()
        self._current_system_prompt = self.system_prompt
        
        init_sub_agent_manager(self.llm, "sub_agents")
        
        self.tools = get_all_tools() + [spawn_agent, ShellTool()]
        
        self.agent = self._create_agent(self.system_prompt)
        
        self.logger.log_agent_action("agent_initialized", {
            "model": config.model.model.name,
            "tool_count": len(self.tools),
            "max_context_tokens": self.MAX_CONTEXT_TOKENS
        })
    
    def _create_agent(self, system_prompt: str):
        """创建Agent实例"""
        def pre_model_hook(state):
            messages = state.get("messages", [])
            
            compressed = _compress_messages(messages, self.MAX_CONTEXT_TOKENS)
            converted = _convert_messages_for_api(compressed)
            
            token_estimate = _estimate_tokens(compressed)
            self.logger.log_agent_action("pre_model_hook", {
                "original_messages": len(messages),
                "compressed_messages": len(compressed),
                "estimated_tokens": token_estimate
            })
            
            return {"llm_input_messages": converted}
        
        return create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=system_prompt,
            pre_model_hook=pre_model_hook
        )
    
    def _create_llm(self):
        """创建LLM实例"""
        model_config = self.config.model.model

        llm_kwargs = {
            "model": model_config.name,
            "api_key": model_config.api_key,
            "base_url": model_config.base_url,
            "temperature": model_config.temperature,
            "max_tokens": model_config.max_tokens,
            "default_headers": {"Authorization": model_config.auth} if model_config.auth else None
        }
        
        return ChatOpenAI(
            **llm_kwargs
        )
    
    def _load_system_prompt(self) -> str:
        """加载系统提示词"""
        prompt_file = self.config.prompts.system_prompt_file
        
        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return self._get_default_system_prompt()
    
    def _get_default_system_prompt(self) -> str:
        """获取默认系统提示词"""
        return """你是Rubato，一个专业的自动化测试执行助手。

# 角色
你是一个能够自主规划和执行测试任务的智能体。

# 目标
根据用户的自然语言描述，执行浏览器自动化测试，并返回测试结果。

# 工作模式
你采用ReAct模式工作：推理（Reason）→ 行动（Act）→ 观察（Observe）

# 可用工具
- browser_navigate: 导航到URL
- browser_click: 点击元素
- browser_type: 输入文本
- browser_snapshot: 获取页面快照
- browser_take_screenshot: 截图
- spawn_agent: 调用子智能体处理复杂任务

# 工作原则
1. 自主规划：根据任务自主决定执行步骤
2. 逐步执行：一次执行一个步骤，观察结果后再决定下一步
3. 错误处理：遇到错误时尝试调整策略
4. 结果导向：确保完成用户的目标
"""
    
    async def run(self, user_input: str) -> str:
        """运行Agent，使用流式处理记录每个步骤"""
        self.logger.log_agent_thinking(f"收到用户输入: {user_input}")
        
        if self.mcp_manager and self.mcp_manager.is_connected:
            browser_ok = await self.mcp_manager.ensure_browser()
            if not browser_ok:
                return "浏览器初始化失败，请检查 MCP 连接"
        
        skill_name = self.skill_loader.find_matching_skill(user_input)
        
        if skill_name and not self.context_manager.is_skill_loaded(skill_name):
            self.logger.log_agent_action("loading_skill", {"skill": skill_name})
            enhanced_prompt = await self._inject_skill(skill_name)
            self._current_system_prompt = enhanced_prompt
            self.agent = self._create_agent(enhanced_prompt)
            self.context_manager.mark_skill_loaded(skill_name)
        
        self.context_manager.add_user_message(user_input)
        
        messages = self.context_manager.get_messages()
        
        self.logger.log_request(messages, self.config.model.model.name)
        
        start_time = time.time()
        step_count = 0
        
        try:
            final_content = ""
            
            async for event in self.agent.astream(
                {"messages": messages},
                stream_mode="updates"
            ):
                step_count += 1
                self.logger.log_agent_action("stream_event", {
                    "step": step_count,
                    "event_keys": list(event.keys())
                })
                
                for node_name, node_output in event.items():
                    self.logger.log_agent_action("node_output", {
                        "step": step_count,
                        "node": node_name
                    })
                    
                    if "messages" in node_output:
                        for msg in node_output["messages"]:
                            if isinstance(msg, AIMessage):
                                content_str = _content_to_str(msg.content)
                                self.context_manager.add_ai_message(content_str)
                                self.logger.log_response(msg, self.config.model.model.name)
                                
                                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                                    for tc in msg.tool_calls:
                                        self.logger.log_tool_call(tc["name"], tc["args"])
                                
                                if content_str:
                                    final_content = content_str
                                    
                            elif isinstance(msg, ToolMessage):
                                content_str = _content_to_str(msg.content)
                                self.context_manager.add_tool_message(content_str, msg.tool_call_id)
                                self.logger.log_tool_result("tool_message", content_str)
            
            elapsed = time.time() - start_time
            self.logger.log_agent_action("stream_complete", {
                "elapsed_seconds": round(elapsed, 2),
                "total_steps": step_count
            })
            
            return final_content if final_content else "任务已完成"
            
        except Exception as e:
            self.logger.log_error("agent_invoke", e)
            raise
    
    async def _inject_skill(self, skill_name: str) -> str:
        """将Skill内容注入到提示词中"""
        skill_content = await self.skill_loader.load_full_skill(skill_name)
        
        return f"{self.system_prompt}\n\n# 当前加载的Skill\n\n## {skill_name}\n\n{skill_content}\n\n---\n请根据这个Skill的指导，处理用户的请求。"
    
    def get_system_prompt(self) -> str:
        """获取当前系统提示词"""
        return self.system_prompt
    
    def get_loaded_skills(self) -> List[str]:
        """获取已加载的Skills"""
        return self.context_manager.get_loaded_skills()
    
    def clear_context(self) -> None:
        """清空上下文"""
        self.context_manager.clear()
