import asyncio
from typing import Optional
from ..core.agent import RubatoAgent
from ..skills.loader import SkillLoader
from ..mcp.client import MCPManager
from ..config.models import AppConfig
from ..commands import CommandDispatcher, CommandContext


class Console:
    """控制台UI"""
    
    def __init__(
        self,
        agent: RubatoAgent,
        skill_loader: SkillLoader,
        mcp_manager: Optional[MCPManager] = None,
        config: Optional[AppConfig] = None,
        role_manager: Optional['RoleManager'] = None,
        config_loader: Optional['ConfigLoader'] = None,
        app_state: Optional['AppState'] = None
    ):
        self.agent = agent
        self.skill_loader = skill_loader
        self.mcp_manager = mcp_manager
        self.config = config
        self.app_state = app_state
        
        context = CommandContext(
            agent=agent,
            skill_loader=skill_loader,
            mcp_manager=mcp_manager,
            role_manager=role_manager,
            config_loader=config_loader,
            config=config,
            agent_pool=self.app_state.agent_pool if self.app_state else None
        )
        self.dispatcher = CommandDispatcher(context)

        def _on_compression(info):
            original = info.get("original_count", "?")
            compressed = info.get("compressed_count", "?")
            print(f"\n⚠️ 上下文已压缩（压缩前{original}条消息 → 压缩后{compressed}条消息）")

        agent.set_compression_callback(_on_compression)
    
    def _print_banner(self) -> None:
        """打印欢迎横幅"""
        print()
        print("╔══════════════════════════════════════════════════════════╗")
        print("║                       Rubato                             ║")
        print("╠══════════════════════════════════════════════════════════╣")
        
        status_parts = []
        if self.config:
            status_parts.append(f"模型: {self.config.model.model.name}")
        if self.mcp_manager:
            mcp_status = "已连接" if self.mcp_manager.is_connected else "未连接"
            status_parts.append(f"MCP: {mcp_status}")
            if self.mcp_manager.is_connected:
                browser_status = "运行中" if self.mcp_manager.browser_alive else "已关闭"
                status_parts.append(f"浏览器: {browser_status}")
        
        if status_parts:
            print(f"║ 状态: {' | '.join(status_parts)}")
        
        skills = self.skill_loader.list_skills()
        if skills:
            skill_names = ", ".join(s.name for s in skills[:3])
            print(f"║ 已加载Skills: {skill_names}")
        
        print("╚══════════════════════════════════════════════════════════╝")
        print()
        print("输入 '/help' 查看帮助，'/quit' 退出")
        print()
    
    def _print_prompt(self) -> None:
        """打印输入提示"""
        print("\n> ", end="", flush=True)
    
    async def run(self) -> None:
        """运行控制台"""
        self._print_banner()
        
        while self.dispatcher.is_running():
            try:
                self._print_prompt()
                user_input = input().strip()
                
                if not user_input:
                    continue
                
                result = await self.dispatcher.dispatch(user_input)
                if result is not None:
                    print(result.to_text())
                    continue
                
                print("\n[Agent思考中...]")
                
                response = await self.agent.run(user_input)
                
                print(f"\n{response}")
                
            except KeyboardInterrupt:
                print("\n\n已中断。输入 '/quit' 退出。")
            except EOFError:
                print("\n再见！")
                break
            except Exception as e:
                print(f"\n错误: {e}")
    
    def run_sync(self) -> None:
        """同步运行控制台"""
        asyncio.run(self.run())
