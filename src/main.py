import asyncio
import sys
import argparse
from pathlib import Path
from typing import Optional

from src.config.loader import ConfigLoader
from src.config.validators import ConfigValidationError
from src.mcp.client import MCPManager
from src.mcp.tools import register_mcp_tools
from src.skills.loader import SkillLoader
from src.context.manager import ContextManager
from src.core.agent import RubatoAgent
from src.cli.console import Console


class AppState:
    def __init__(self):
        self.config = None
        self.skill_loader = None
        self.context_manager = None
        self.agent = None
        self.mcp_manager = None
    
    async def reload_config(self, config_name: str):
        if not self.config:
            return
        
        config_loader = ConfigLoader("config")
        try:
            new_config = config_loader.load_all()
            self.config = new_config
        except Exception as e:
            print(f"配置重载失败: {e}")


async def run_with_mcp(config, skill_loader, context_manager) -> None:
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
            context_manager=context_manager,
            mcp_manager=mcp_manager
        )
        
        console = Console(
            agent=agent,
            skill_loader=skill_loader,
            mcp_manager=mcp_manager,
            config=config
        )
        
        await console.run()


async def run_without_mcp(config, skill_loader, context_manager) -> None:
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


async def run_web_mode(port: int = 8000) -> None:
    import uvicorn
    from src.api.app import create_app
    from src.api.routes.configs import set_app_state as set_config_state
    from src.api.websocket import set_app_state as set_ws_state
    
    print()
    print("=" * 60)
    print("  Rubato - HTTP控制台模式")
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
    
    app_state = AppState()
    app_state.config = config
    app_state.skill_loader = skill_loader
    app_state.context_manager = context_manager
    
    if config.mcp.playwright.enabled:
        print("正在连接MCP服务器...")
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
        
        try:
            mcp_manager = MCPManager(mcp_config)
            await mcp_manager.connect()
            tools = mcp_manager.get_tools()
            register_mcp_tools(tools)
            print(f"MCP已连接，加载了 {len(tools)} 个工具")
            
            app_state.mcp_manager = mcp_manager
        except Exception as e:
            print(f"MCP连接失败: {e}")
            print("将以无MCP模式运行...")
    
    print("正在初始化Agent...")
    agent = RubatoAgent(
        config=config,
        skill_loader=skill_loader,
        context_manager=context_manager,
        mcp_manager=app_state.mcp_manager
    )
    app_state.agent = agent
    
    set_config_state(app_state)
    set_ws_state(app_state)
    
    app = create_app()
    
    print()
    print(f"HTTP服务已启动: http://127.0.0.1:{port}")
    print("按 Ctrl+C 停止服务")
    print()
    
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info"
    )
    server = uvicorn.Server(config)
    
    try:
        await server.serve()
    except KeyboardInterrupt:
        print("\n正在关闭服务...")
        if app_state.mcp_manager:
            await app_state.mcp_manager.disconnect()


async def main_async() -> None:
    parser = argparse.ArgumentParser(description="Rubato - 自然语言驱动的自动化测试执行框架")
    parser.add_argument("--web", action="store_true", help="启动HTTP控制台模式")
    parser.add_argument("--port", type=int, default=8000, help="HTTP服务端口（默认8000）")
    
    args = parser.parse_args()
    
    if args.web:
        await run_web_mode(args.port)
        return
    
    print()
    print("=" * 60)
    print("  Rubato - 自然语言驱动的自动化测试执行框架")
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
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n\n程序已退出")


if __name__ == "__main__":
    main()
