import asyncio
import sys
from pathlib import Path

from src.config.loader import ConfigLoader
from src.config.validators import ConfigValidationError
from src.mcp.client import MCPManager
from src.mcp.tools import register_mcp_tools
from src.skills.loader import SkillLoader
from src.context.manager import ContextManager
from src.core.agent import RubatoAgent
from src.cli.console import Console


async def run_with_mcp(config, skill_loader, context_manager) -> None:
    """在 MCP 上下文中运行应用
    
    关键：整个应用生命周期必须在 MCPManager 的 async with 上下文中，
    这样 MCP 连接才能在整个 Agent 执行期间保持活跃，浏览器会话才能持续共享。
    """
    mcp_config = {
        "playwright": {
            "command": config.mcp.playwright.command,
            "args": config.mcp.playwright.args,
            "connection": {
                "retry_times": config.mcp.playwright.connection.retry_times,
                "retry_delay": config.mcp.playwright.connection.retry_delay,
                "timeout": config.mcp.playwright.connection.timeout,
            }
        }
    }
    
    async with MCPManager(mcp_config) as mcp_manager:
        tools = mcp_manager.get_tools()
        register_mcp_tools(tools)
        print(f"MCP已连接，加载了 {len(tools)} 个工具")
        
        print("正在初始化Agent...")
        agent = RubatoAgent(
            config=config,
            skill_loader=skill_loader,
            context_manager=context_manager
        )
        
        console = Console(
            agent=agent,
            skill_loader=skill_loader,
            mcp_manager=mcp_manager,
            config=config
        )
        
        await console.run()


async def run_without_mcp(config, skill_loader, context_manager) -> None:
    """无 MCP 模式运行应用"""
    print("正在初始化Agent...")
    agent = RubatoAgent(
        config=config,
        skill_loader=skill_loader,
        context_manager=context_manager
    )
    
    console = Console(
        agent=agent,
        skill_loader=skill_loader,
        mcp_manager=None,
        config=config
    )
    
    await console.run()


async def main_async() -> None:
    """异步主函数"""
    
    print()
    print("=" * 60)
    print("  Rubato - 基于LangGraph的提示词驱动智能体框架")
    print("=" * 60)
    print()
    
    print("正在加载配置...")
    config_loader = ConfigLoader("config")
    try:
        config = config_loader.load_all()
    except ConfigValidationError as e:
        print(f"配置加载失败: {e}")
        sys.exit(1)
    
    print("正在加载Skills...")
    skill_loader = SkillLoader(config.skills.directory)
    await skill_loader.load_skill_metadata()
    
    print("正在初始化上下文管理器...")
    context_manager = ContextManager(
        max_tokens=4000,
        keep_recent=4,
        auto_compress=True
    )
    
    if config.mcp.playwright.enabled:
        print("正在连接MCP服务器...")
        try:
            await run_with_mcp(config, skill_loader, context_manager)
        except Exception as e:
            print(f"MCP连接失败: {e}")
            print("将以无MCP模式运行...")
            await run_without_mcp(config, skill_loader, context_manager)
    else:
        await run_without_mcp(config, skill_loader, context_manager)


def main() -> None:
    """程序入口"""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n\n程序已退出")


if __name__ == "__main__":
    main()
