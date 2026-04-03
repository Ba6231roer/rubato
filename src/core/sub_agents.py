from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from typing import Optional, List, Dict, Any
import yaml
import asyncio
from pathlib import Path

from ..utils.logger import get_llm_logger
from ..tools.docs import generate_tool_docs_for_prompt


class SubAgentManager:
    """子Agent管理器（实例级别）"""
    
    def __init__(self, llm, parent_agent, sub_agents_dir: str = "sub_agents", recursion_limit: int = 50):
        self.llm = llm
        self.parent_agent = parent_agent
        self.sub_agents_dir = Path(sub_agents_dir)
        self.recursion_limit = recursion_limit
        self.agent_configs: dict = {}
        self._load_agent_configs()
        self._logger = get_llm_logger()
        self._session_depths: Dict[str, int] = {}
    
    def _load_agent_configs(self) -> None:
        """加载所有预定义的子Agent配置"""
        if not self.sub_agents_dir.exists():
            return
        
        for config_file in self.sub_agents_dir.glob("*.yaml"):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    if config and 'name' in config:
                        self.agent_configs[config['name']] = config
            except Exception as e:
                print(f"加载子Agent配置失败 {config_file}: {e}")
    
    def get_agent_config(self, agent_name: str) -> Optional[dict]:
        """获取子Agent配置"""
        return self.agent_configs.get(agent_name)
    
    def create_agent(self, system_prompt: str, available_tools: Optional[List[str]] = None, parent_tools: Optional[List] = None):
        """创建子Agent
        
        Args:
            system_prompt: 系统提示词
            available_tools: 指定的工具名称列表（预定义配置）
            parent_tools: 父角色的工具列表（用于继承）
        """
        if parent_tools is not None:
            tools = parent_tools
        elif available_tools:
            tools = self.parent_agent.tool_registry.get_tools_by_names(available_tools)
        else:
            tools = self.parent_agent.tools
        
        tool_docs = self._generate_tool_docs_for_sub_agent(tools)
        if tool_docs:
            enhanced_prompt = f"{system_prompt}\n\n{tool_docs}"
        else:
            enhanced_prompt = system_prompt
        
        return create_react_agent(
            model=self.llm,
            tools=tools,
            prompt=enhanced_prompt
        )
    
    def _generate_tool_docs_for_sub_agent(self, tools: List) -> str:
        """为子Agent生成工具说明文档"""
        builtin_tools = []
        mcp_tools = []
        
        builtin_names = {'spawn_agent', 'shell_tool', 'file_read', 'file_write', 
                        'file_list', 'file_search', 'file_exists', 'file_mkdir', 
                        'file_replace', 'file_delete'}
        
        for tool in tools:
            tool_name = tool.name if hasattr(tool, 'name') else str(tool)
            if tool_name in builtin_names:
                builtin_tools.append(tool_name)
            else:
                mcp_tools.append({
                    "name": tool_name,
                    "description": tool.description if hasattr(tool, 'description') else "",
                    "parameters": []
                })
        
        return generate_tool_docs_for_prompt(
            builtin_tools=builtin_tools,
            mcp_tools=mcp_tools,
            skills=None,
            include_examples=True
        )
    
    def list_agents(self) -> List[str]:
        """列出所有预定义的子Agent"""
        return list(self.agent_configs.keys())
    
    def check_recursion_depth(self, session_id: str, max_depth: int) -> bool:
        """检查递归深度是否超过限制
        
        Args:
            session_id: 会话ID
            max_depth: 最大递归深度
            
        Returns:
            True表示可以继续创建子Agent，False表示超过限制
        """
        current = self._session_depths.get(session_id, 0)
        return current < max_depth
    
    def increment_depth(self, session_id: str) -> None:
        """增加递归深度"""
        old_depth = self._session_depths.get(session_id, 0)
        new_depth = old_depth + 1
        self._session_depths[session_id] = new_depth
        self._logger.log_agent_action("recursion_depth_incremented", {
            "session_id": session_id,
            "old_depth": old_depth,
            "new_depth": new_depth
        })
    
    def decrement_depth(self, session_id: str) -> None:
        """减少递归深度"""
        old_depth = self._session_depths.get(session_id, 0)
        if old_depth > 0:
            new_depth = old_depth - 1
            self._session_depths[session_id] = new_depth
            self._logger.log_agent_action("recursion_depth_decremented", {
                "session_id": session_id,
                "old_depth": old_depth,
                "new_depth": new_depth
            })
            if new_depth == 0:
                del self._session_depths[session_id]
                self._logger.log_agent_action("recursion_depth_cleared", {
                    "session_id": session_id
                })


def create_spawn_agent_tool(sub_agent_manager: SubAgentManager):
    """创建绑定到特定 Agent 实例的 spawn_agent 工具
    
    Args:
        sub_agent_manager: 子Agent管理器实例
        
    Returns:
        绑定到当前 Agent 实例的 spawn_agent 工具
    """
    @tool
    async def spawn_agent(
        agent_name: str,
        task: str,
        system_prompt: Optional[str] = None,
        inherit_parent_tools: bool = True,
        session_id: Optional[str] = None,
        max_recursion_depth: int = 5
    ) -> str:
        """生成并运行一个子智能体
        
        这是一个通用的子智能体调用工具。子智能体有独立的系统提示词和上下文，
        不会污染主智能体的对话历史。
        
        子智能体默认继承父角色的所有工具权限和配置。
        
        Args:
            agent_name: 子智能体名称
                - 如果是预定义的子智能体（如"snapshot-analyzer"），会加载对应配置
                - 如果是自定义名称，需要提供system_prompt参数
            task: 要执行的任务描述
            system_prompt: 可选的系统提示词
                - 如果提供，会使用这个提示词创建子智能体
                - 如果不提供，会从配置文件加载预定义的提示词
            inherit_parent_tools: 是否继承父角色的工具（默认True）
            session_id: 会话ID（用于递归深度控制）
            max_recursion_depth: 最大递归深度（默认5）
        
        Returns:
            子智能体的执行结果
        
        Examples:
            spawn_agent("snapshot-analyzer", "分析这个页面快照：...")
            spawn_agent("my-agent", "分析数据", system_prompt="你是数据分析专家...")
        """
        if session_id:
            if not sub_agent_manager.check_recursion_depth(session_id, max_recursion_depth):
                return f"错误：已达到最大递归深度限制（{max_recursion_depth}），无法创建更多子智能体"
            sub_agent_manager.increment_depth(session_id)
        
        try:
            parent_tools = None
            if inherit_parent_tools:
                parent_tools = sub_agent_manager.parent_agent.tools
            
            if system_prompt:
                prompt = system_prompt
                available_tools = None
                timeout = 120
                max_retries = 0
            else:
                config = sub_agent_manager.get_agent_config(agent_name)
                if not config:
                    if not inherit_parent_tools:
                        return f"错误：未找到名为 '{agent_name}' 的预定义子智能体，请提供system_prompt参数"
                    prompt = f"你是一个名为{agent_name}的子智能体，负责执行特定任务。"
                    available_tools = None
                    timeout = 120
                    max_retries = 0
                else:
                    prompt = config.get('system_prompt', '')
                    available_tools = config.get('available_tools')
                    execution_config = config.get('execution', {})
                    timeout = execution_config.get('timeout', 120)
                    max_retries = execution_config.get('max_retries', 0)
            
            sub_agent = sub_agent_manager.create_agent(prompt, available_tools, parent_tools)
            
            sub_agent_manager._logger.log_agent_action("spawn_agent_created", {
                "agent_name": agent_name,
                "inherit_parent_tools": inherit_parent_tools,
                "session_id": session_id,
                "timeout": timeout
            })
            
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    result = await asyncio.wait_for(
                        sub_agent.ainvoke(
                            {"messages": [HumanMessage(content=task)]},
                            config={"recursion_limit": sub_agent_manager.recursion_limit}
                        ),
                        timeout=timeout
                    )
                    return result["messages"][-1].content
                except asyncio.TimeoutError:
                    last_error = f"子智能体执行超时（{timeout}秒）"
                except Exception as e:
                    last_error = f"子智能体执行失败：{str(e)}"
                
                if attempt < max_retries:
                    await asyncio.sleep(1)
            
            return f"错误：{last_error}，已重试{max_retries}次"
        
        finally:
            if session_id:
                sub_agent_manager.decrement_depth(session_id)
    
    return spawn_agent
