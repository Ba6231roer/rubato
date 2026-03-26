from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from typing import Optional, List
import yaml
import asyncio
from pathlib import Path

from ..mcp.tools import get_all_tools, get_tools_by_names


class SubAgentManager:
    """子Agent管理器"""
    
    def __init__(self, llm, sub_agents_dir: str = "sub_agents", recursion_limit: int = 50):
        self.llm = llm
        self.sub_agents_dir = Path(sub_agents_dir)
        self.recursion_limit = recursion_limit
        self.agent_configs: dict = {}
        self._load_agent_configs()
    
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
    
    def create_agent(self, system_prompt: str, available_tools: Optional[List[str]] = None):
        """创建子Agent"""
        if available_tools:
            tools = get_tools_by_names(available_tools)
        else:
            tools = get_all_tools()
        
        return create_react_agent(
            model=self.llm,
            tools=tools,
            prompt=system_prompt
        )
    
    def list_agents(self) -> List[str]:
        """列出所有预定义的子Agent"""
        return list(self.agent_configs.keys())


_sub_agent_manager: Optional[SubAgentManager] = None


def init_sub_agent_manager(llm, sub_agents_dir: str = "sub_agents", recursion_limit: int = 50) -> None:
    """初始化子Agent管理器"""
    global _sub_agent_manager
    _sub_agent_manager = SubAgentManager(llm, sub_agents_dir, recursion_limit)


def get_sub_agent_manager() -> Optional[SubAgentManager]:
    """获取子Agent管理器"""
    return _sub_agent_manager


@tool
async def spawn_agent(
    agent_name: str,
    task: str,
    system_prompt: Optional[str] = None
) -> str:
    """生成并运行一个子智能体
    
    这是一个通用的子智能体调用工具。子智能体有独立的系统提示词和上下文，
    不会污染主智能体的对话历史。
    
    Args:
        agent_name: 子智能体名称
            - 如果是预定义的子智能体（如"snapshot-analyzer"），会加载对应配置
            - 如果是自定义名称，需要提供system_prompt参数
        task: 要执行的任务描述
        system_prompt: 可选的系统提示词
            - 如果提供，会使用这个提示词创建子智能体
            - 如果不提供，会从配置文件加载预定义的提示词
    
    Returns:
        子智能体的执行结果
    
    Examples:
        spawn_agent("snapshot-analyzer", "分析这个页面快照：...")
        spawn_agent("my-agent", "分析数据", system_prompt="你是数据分析专家...")
    """
    global _sub_agent_manager
    
    if _sub_agent_manager is None:
        return "错误：子Agent管理器未初始化"
    
    if system_prompt:
        prompt = system_prompt
        available_tools = None
        timeout = 120
        max_retries = 0
    else:
        config = _sub_agent_manager.get_agent_config(agent_name)
        if not config:
            return f"错误：未找到名为 '{agent_name}' 的预定义子智能体，请提供system_prompt参数"
        
        prompt = config.get('system_prompt', '')
        available_tools = config.get('available_tools')
        execution_config = config.get('execution', {})
        timeout = execution_config.get('timeout', 120)
        max_retries = execution_config.get('max_retries', 0)
    
    sub_agent = _sub_agent_manager.create_agent(prompt, available_tools)
    
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            result = await asyncio.wait_for(
                sub_agent.ainvoke(
                    {"messages": [HumanMessage(content=task)]},
                    config={"recursion_limit": _sub_agent_manager.recursion_limit}
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
