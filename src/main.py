import asyncio
import sys
import argparse
import uuid
from pathlib import Path
from typing import Optional, Dict, List, Any

from src.config.loader import ConfigLoader
from src.config.validators import ConfigValidationError
from src.mcp.client import MCPManager
from src.mcp.tools import register_mcp_tools
from src.skills.loader import SkillLoader
from src.context.manager import ContextManager
from src.core.agent import RubatoAgent
from src.core.agent_pool import AgentPool, AgentInstance, InstanceStatus
from src.core.role_manager import RoleManager
from src.cli.console import Console


def build_mcp_config(config) -> Dict[str, Any]:
    """构建MCP配置字典
    
    从 config.mcp.servers 中提取启用的服务器配置
    
    Args:
        config: 应用配置对象
        
    Returns:
        Dict: MCP配置字典，格式为 {server_name: {command, args, connection, ...}, ...}
    """
    if not config.mcp or not config.mcp.servers:
        return {}
    
    mcp_config = {}
    for server_name, server_config in config.mcp.servers.items():
        if not server_config.enabled:
            continue
        
        server_cfg = {
            "command": server_config.command,
            "args": server_config.args or [],
        }
        
        if server_config.connection:
            server_cfg["connection"] = server_config.connection
        else:
            server_cfg["connection"] = {
                "retry_times": 3,
                "retry_delay": 5,
                "timeout": 30,
            }
        
        if server_config.browser:
            server_cfg["browser"] = server_config.browser
        
        if server_config.execution:
            server_cfg["execution"] = server_config.execution
        
        mcp_config[server_name] = server_cfg
    
    return mcp_config


def has_enabled_mcp_servers(config) -> bool:
    """检查是否有启用的MCP服务器
    
    Args:
        config: 应用配置对象
        
    Returns:
        bool: 是否有启用的MCP服务器
    """
    mcp_config = build_mcp_config(config)
    return bool(mcp_config)


class AppState:
    """应用状态管理器，支持多Agent实例"""
    
    DEFAULT_INSTANCE_ID = "default"
    
    def __init__(self):
        self.config = None
        self.skill_loader = None
        self.context_manager = None
        self.agent = None
        self.mcp_manager = None
        self._is_reloading = False
        
        self._agent_pool: Optional[AgentPool] = None
        self._role_manager: Optional[RoleManager] = None
        self._active_instance_id: Optional[str] = None
        self._instances: Dict[str, AgentInstance] = {}
        self._initialized = False
    
    @property
    def agent_pool(self) -> Optional[AgentPool]:
        return self._agent_pool
    
    @property
    def role_manager(self) -> Optional[RoleManager]:
        return self._role_manager
    
    async def initialize(
        self,
        config,
        skill_loader: SkillLoader,
        context_manager: ContextManager,
        mcp_manager: Optional[MCPManager] = None,
        max_instances: int = 5,
        roles_dir: str = "config/roles",
        skills_dir: str = "skills"
    ) -> None:
        """初始化应用状态
        
        Args:
            config: 应用配置
            skill_loader: 技能加载器
            context_manager: 上下文管理器
            mcp_manager: MCP管理器（可选）
            max_instances: 最大实例数
            roles_dir: 角色配置目录
            skills_dir: 技能目录
        """
        if self._initialized:
            return
        
        self.config = config
        self.skill_loader = skill_loader
        self.context_manager = context_manager
        self.mcp_manager = mcp_manager
        
        self._role_manager = RoleManager(
            roles_dir=roles_dir,
            default_model_config=config.model
        )
        self._role_manager.load_roles()
        
        self._agent_pool = AgentPool(
            config=config,
            max_instances=max_instances,
            roles_dir=roles_dir,
            skills_dir=skills_dir
        )
        await self._agent_pool.initialize()
        
        default_instance = await self.create_agent_instance(
            instance_id=self.DEFAULT_INSTANCE_ID
        )
        self._active_instance_id = default_instance.instance_id
        self.agent = default_instance.agent
        
        self._initialized = True
    
    async def create_agent_instance(
        self,
        instance_id: Optional[str] = None,
        role_name: Optional[str] = None
    ) -> AgentInstance:
        """创建新的Agent实例
        
        Args:
            instance_id: 实例ID（可选，自动生成UUID）
            role_name: 角色名称（可选）
            
        Returns:
            AgentInstance: 创建的实例
            
        Raises:
            RuntimeError: 已达到最大实例数限制
        """
        if not self._agent_pool:
            raise RuntimeError("AgentPool未初始化")
        
        inst_id = instance_id or str(uuid.uuid4())
        
        if inst_id in self._instances:
            raise ValueError(f"实例ID已存在: {inst_id}")
        
        instance = await self._agent_pool.create_instance(
            instance_id=inst_id,
            role_name=role_name
        )
        
        if self.mcp_manager:
            instance.agent._mcp_manager = self.mcp_manager
        
        self._instances[inst_id] = instance
        
        return instance
    
    def get_agent_instance(self, instance_id: str) -> Optional[AgentInstance]:
        """按ID获取Agent实例
        
        Args:
            instance_id: 实例ID
            
        Returns:
            AgentInstance 或 None
        """
        return self._instances.get(instance_id)
    
    def get_agent_instance_by_role(self, role_name: str) -> Optional[AgentInstance]:
        """按角色名获取可用的Agent实例
        
        Args:
            role_name: 角色名称
            
        Returns:
            AgentInstance 或 None
        """
        for instance in self._instances.values():
            if instance.role_name == role_name and instance.is_available():
                return instance
        return None
    
    def get_active_instance(self) -> Optional[AgentInstance]:
        """获取当前活跃的Agent实例
        
        Returns:
            AgentInstance 或 None
        """
        if self._active_instance_id:
            return self._instances.get(self._active_instance_id)
        return None
    
    def set_active_instance(self, instance_id: str) -> bool:
        """设置当前活跃的Agent实例
        
        Args:
            instance_id: 实例ID
            
        Returns:
            bool: 是否设置成功
        """
        if instance_id in self._instances:
            self._active_instance_id = instance_id
            self.agent = self._instances[instance_id].agent
            return True
        return False
    
    def destroy_agent_instance(self, instance_id: str) -> bool:
        """销毁Agent实例
        
        Args:
            instance_id: 实例ID
            
        Returns:
            bool: 是否销毁成功
        """
        if instance_id == self.DEFAULT_INSTANCE_ID:
            return False
        
        instance = self._instances.pop(instance_id, None)
        if instance:
            instance.dispose()
            
            if self._agent_pool:
                self._agent_pool.destroy_instance(instance_id)
            
            if self._active_instance_id == instance_id:
                default_instance = self._instances.get(self.DEFAULT_INSTANCE_ID)
                if default_instance:
                    self._active_instance_id = self.DEFAULT_INSTANCE_ID
                    self.agent = default_instance.agent
                else:
                    self._active_instance_id = None
                    self.agent = None
            
            return True
        return False
    
    def list_agent_instances(self) -> List[Dict[str, Any]]:
        """列出所有Agent实例
        
        Returns:
            List[Dict]: 实例信息列表
        """
        return [
            {
                "instance_id": inst.instance_id,
                "role_name": inst.role_name,
                "status": inst.status.value,
                "is_active": inst.instance_id == self._active_instance_id,
                "created_at": inst.created_at.isoformat(),
                "last_used_at": inst.last_used_at.isoformat() if inst.last_used_at else None,
                "task_count": inst.task_count,
                "error_message": inst.error_message
            }
            for inst in self._instances.values()
        ]
    
    def get_instance_count(self) -> int:
        """获取实例总数"""
        return len(self._instances)
    
    def get_available_instance_count(self) -> int:
        """获取可用实例数"""
        return sum(1 for inst in self._instances.values() if inst.is_available())
    
    async def cleanup(self) -> None:
        """清理所有资源"""
        for instance_id in list(self._instances.keys()):
            instance = self._instances.pop(instance_id, None)
            if instance:
                instance.dispose()
        
        if self._agent_pool:
            self._agent_pool.destroy_all_instances()
        
        if self.mcp_manager:
            try:
                await self.mcp_manager.disconnect()
            except Exception:
                pass
        
        if self.context_manager:
            self.context_manager.clear()
        
        self._initialized = False
        self._active_instance_id = None
        self.agent = None
    
    async def reload_config(self, config_name: str = None) -> bool:
        """重新加载配置
        
        Args:
            config_name: 指定要重载的配置名称，为 None 时重载所有配置
                         支持: 'model', 'agent', 'skills', 'prompts', 'mcp', 'all'
        
        Returns:
            bool: 重载是否成功
        """
        if self._is_reloading:
            print("配置正在重载中，请稍后...")
            return False
        
        self._is_reloading = True
        
        try:
            config_loader = ConfigLoader("config")
            new_config = config_loader.load_all()
            
            if config_name and config_name != 'all':
                if config_name == 'agent':
                    if self.agent:
                        self.agent.update_config(new_config)
                    self.config.agent = new_config.agent
                elif config_name == 'model':
                    self.config.model = new_config.model
                    if self.agent:
                        self.agent.llm = self.agent._create_llm()
                    if self._role_manager:
                        self._role_manager.set_default_model_config(new_config.model)
                elif config_name == 'skills':
                    self.config.skills = new_config.skills
                    if self.skill_loader:
                        await self.skill_loader.load_skill_metadata()
                elif config_name == 'prompts':
                    self.config.prompts = new_config.prompts
                elif config_name == 'mcp':
                    self.config.mcp = new_config.mcp
                else:
                    print(f"未知的配置名称: {config_name}")
                    return False
            else:
                for instance in self._instances.values():
                    instance.agent.update_config(new_config)
                self.config = new_config
                if self.skill_loader:
                    await self.skill_loader.load_skill_metadata()
                if self._role_manager:
                    self._role_manager.set_default_model_config(new_config.model)
            
            print(f"配置重载成功: {config_name or 'all'}")
            return True
            
        except Exception as e:
            print(f"配置重载失败: {e}")
            return False
        finally:
            self._is_reloading = False
    
    async def reload_model_config(self) -> bool:
        """重载模型配置"""
        return await self.reload_config('model')
    
    async def reload_agent_config(self) -> bool:
        """重载Agent配置"""
        return await self.reload_config('agent')
    
    async def reload_skills_config(self) -> bool:
        """重载Skills配置"""
        return await self.reload_config('skills')
    
    async def reload_all_configs(self) -> bool:
        """重载所有配置"""
        return await self.reload_config('all')
    
    async def reload_roles(self) -> bool:
        """重载角色配置"""
        if not self._role_manager:
            return False
        try:
            self._role_manager.reload_roles()
            print("角色配置重载成功")
            return True
        except Exception as e:
            print(f"角色配置重载失败: {e}")
            return False


async def run_with_mcp(config, skill_loader, context_manager, config_loader) -> None:
    mcp_config = build_mcp_config(config)
    
    mcp_manager = MCPManager(mcp_config)
    await mcp_manager.connect()
    tools = mcp_manager.get_tools()
    register_mcp_tools(tools)
    print(f"MCP已连接，加载了 {len(tools)} 个工具")
    
    app_state = AppState()
    await app_state.initialize(
        config=config,
        skill_loader=skill_loader,
        context_manager=context_manager,
        mcp_manager=mcp_manager,
        max_instances=5,
        roles_dir="config/roles",
        skills_dir=config.skills.directory
    )
    
    console = Console(
        agent=app_state.agent,
        skill_loader=skill_loader,
        mcp_manager=mcp_manager,
        config=config,
        role_manager=app_state.role_manager,
        config_loader=config_loader,
        app_state=app_state
    )
    
    try:
        await console.run()
    finally:
        await app_state.cleanup()


async def run_without_mcp(config, skill_loader, context_manager, config_loader) -> None:
    app_state = AppState()
    await app_state.initialize(
        config=config,
        skill_loader=skill_loader,
        context_manager=context_manager,
        mcp_manager=None,
        max_instances=5,
        roles_dir="config/roles",
        skills_dir=config.skills.directory
    )
    
    console = Console(
        agent=app_state.agent,
        skill_loader=skill_loader,
        mcp_manager=None,
        config=config,
        role_manager=app_state.role_manager,
        config_loader=config_loader,
        app_state=app_state
    )
    
    try:
        await console.run()
    finally:
        await app_state.cleanup()


async def run_web_mode(port: int = 8000) -> None:
    import uvicorn
    from src.api.app import create_app
    from src.api.routes.configs import set_app_state as set_config_state
    from src.api.websocket import set_app_state as set_ws_state, init_command_dispatcher as init_ws_dispatcher
    from src.api.routes.commands import init_dispatcher as init_http_dispatcher
    from src.commands.context import CommandContext
    
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
    enabled_skills = config.skills.enabled_skills if config.skills else None
    max_loaded_skills = 3
    if config.skills and config.skills.skill_loading:
        max_loaded_skills = config.skills.skill_loading.max_loaded_skills
    
    skill_loader = SkillLoader(
        skills_dir=config.skills.directory,
        enabled_skills=enabled_skills,
        max_loaded_skills=max_loaded_skills
    )
    await skill_loader.load_skill_metadata()
    
    print("正在初始化上下文管理器...")
    context_manager = ContextManager(
        max_tokens=4000,
        keep_recent=4,
        auto_compress=True
    )
    
    app_state = AppState()
    
    mcp_manager = None
    if has_enabled_mcp_servers(config):
        print("正在连接MCP服务器...")
        mcp_config = build_mcp_config(config)
        
        try:
            mcp_manager = MCPManager(mcp_config)
            await mcp_manager.connect()
            tools = mcp_manager.get_tools()
            register_mcp_tools(tools)
            print(f"MCP已连接，加载了 {len(tools)} 个工具")
        except Exception as e:
            print(f"MCP连接失败: {e}")
            print("将以无MCP模式运行...")
            mcp_manager = None
    
    print("正在初始化Agent实例池...")
    await app_state.initialize(
        config=config,
        skill_loader=skill_loader,
        context_manager=context_manager,
        mcp_manager=mcp_manager,
        max_instances=5,
        roles_dir="config/roles",
        skills_dir=config.skills.directory
    )
    
    set_config_state(app_state)
    set_ws_state(app_state)
    
    command_context = CommandContext(
        agent=app_state.agent,
        skill_loader=skill_loader,
        mcp_manager=mcp_manager,
        role_manager=app_state.role_manager,
        config_loader=config_loader,
        config=config,
        agent_pool=app_state.agent_pool
    )
    init_ws_dispatcher(command_context)
    init_http_dispatcher(command_context)
    
    app = create_app()
    
    print()
    print(f"HTTP服务已启动: http://127.0.0.1:{port}")
    print(f"Agent实例数: {app_state.get_instance_count()}")
    print("按 Ctrl+C 停止服务")
    print()
    
    uvicorn_config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info"
    )
    server = uvicorn.Server(uvicorn_config)
    
    try:
        await server.serve()
    except KeyboardInterrupt:
        print("\n正在关闭服务...")
    finally:
        await app_state.cleanup()


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
    enabled_skills = config.skills.enabled_skills if config.skills else None
    max_loaded_skills = 3
    if config.skills and config.skills.skill_loading:
        max_loaded_skills = config.skills.skill_loading.max_loaded_skills
    
    skill_loader = SkillLoader(
        skills_dir=config.skills.directory,
        enabled_skills=enabled_skills,
        max_loaded_skills=max_loaded_skills
    )
    await skill_loader.load_skill_metadata()
    
    print("正在初始化上下文管理器...")
    context_manager = ContextManager(
        max_tokens=4000,
        keep_recent=4,
        auto_compress=True
    )
    
    if has_enabled_mcp_servers(config):
        print("正在连接MCP服务器...")
        try:
            await run_with_mcp(config, skill_loader, context_manager, config_loader)
        except Exception as e:
            print(f"MCP连接失败: {e}")
            print("将以无MCP模式运行...")
            await run_without_mcp(config, skill_loader, context_manager, config_loader)
    else:
        await run_without_mcp(config, skill_loader, context_manager, config_loader)


def main() -> None:
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n\n程序已退出")


if __name__ == "__main__":
    main()
