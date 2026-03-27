from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_core.tools import BaseTool
from typing import Optional, List, Dict, Any
import asyncio

from .errors import MCPConnectionError


class MCPManager:
    """MCP管理器，使用langchain-mcp-adapters
    
    关键：使用持久 session 来确保 MCP 连接在整个 Agent 执行期间保持活跃，
    浏览器会话才能持续共享。
    
    注意：langchain-mcp-adapters 0.1.0+ 版本不再支持直接使用 async with，
    需要通过 client.session() 来管理持久连接。
    
    浏览器持久化：
    - 移除 --isolated 参数后，浏览器 profile 保存在磁盘
    - 程序退出时不关闭浏览器，下次任务继续复用
    - 只有用户手动关闭浏览器时才关闭
    
    支持多服务器配置：
    - config 格式: {server_name: {command, args, connection, ...}, ...}
    - 会连接所有配置的服务器并聚合工具
    """
    
    def __init__(self, config: dict):
        self.config = config
        self._client: Optional[MultiServerMCPClient] = None
        self._tools: List[BaseTool] = []
        self._connected = False
        self._sessions: Dict[str, Any] = {}
        self._session_cms: Dict[str, Any] = {}
        self._browser_alive = False
    
    async def __aenter__(self) -> "MCPManager":
        """进入上下文管理器，建立并保持 MCP 连接"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """退出上下文管理器，断开 MCP 连接但不关闭浏览器"""
        await self.disconnect(close_browser=False)
    
    async def connect(self) -> None:
        """连接到所有配置的MCP服务器（带重试机制）"""
        if not self.config:
            raise MCPConnectionError("MCP配置为空")
        
        connections = {}
        server_configs = {}
        
        for server_name, server_config in self.config.items():
            if not isinstance(server_config, dict):
                continue
            
            command = server_config.get("command")
            if not command:
                continue
            
            args = server_config.get("args", [])
            connection_cfg = server_config.get("connection", {})
            
            connections[server_name] = {
                "command": command,
                "args": args,
                "transport": "stdio",
            }
            server_configs[server_name] = connection_cfg
        
        if not connections:
            raise MCPConnectionError("没有有效的MCP服务器配置")
        
        self._client = MultiServerMCPClient(connections)
        
        for server_name, connection_cfg in server_configs.items():
            retry_times = connection_cfg.get("retry_times", 3)
            retry_delay = connection_cfg.get("retry_delay", 5)
            timeout = connection_cfg.get("timeout", 30)
            
            last_error = None
            for attempt in range(retry_times):
                try:
                    session_cm = self._client.session(server_name)
                    session = await session_cm.__aenter__()
                    await session.initialize()
                    
                    self._session_cms[server_name] = session_cm
                    self._sessions[server_name] = session
                    
                    server_tools = await asyncio.wait_for(
                        load_mcp_tools(session),
                        timeout=timeout
                    )
                    self._tools.extend(server_tools)
                    
                    if server_name == "playwright":
                        self._browser_alive = True
                    
                    break
                except asyncio.TimeoutError:
                    last_error = f"MCP连接超时（{timeout}秒）"
                    await self._cleanup_server_session(server_name)
                except Exception as e:
                    last_error = f"MCP连接失败：{str(e)}"
                    await self._cleanup_server_session(server_name)
                
                if attempt < retry_times - 1:
                    await asyncio.sleep(retry_delay)
            
            if last_error and server_name not in self._sessions:
                print(f"警告: 服务器 {server_name} 连接失败: {last_error}")
        
        if self._sessions:
            self._connected = True
        else:
            raise MCPConnectionError("无法连接任何MCP服务器")
    
    async def _cleanup_server_session(self, server_name: str):
        """清理指定服务器的 session 资源"""
        if server_name in self._session_cms:
            try:
                await self._session_cms[server_name].__aexit__(None, None, None)
            except:
                pass
        self._session_cms.pop(server_name, None)
        self._sessions.pop(server_name, None)
    
    def get_tools(self) -> List[BaseTool]:
        """获取所有MCP工具"""
        if not self._connected:
            raise MCPConnectionError("MCP未连接，请先调用connect()")
        return self._tools
    
    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected
    
    @property
    def browser_alive(self) -> bool:
        """检查浏览器是否存活"""
        return self._browser_alive
    
    async def check_browser_alive(self) -> bool:
        """检查浏览器是否存活
        
        通过调用 browser_snapshot 来检测浏览器是否还在运行。
        如果调用成功，说明浏览器存活；如果失败，说明浏览器已被关闭。
        """
        session = self._sessions.get("playwright")
        if not session:
            self._browser_alive = False
            return False
        
        try:
            await session.call_tool("browser_snapshot", {})
            self._browser_alive = True
            return True
        except Exception:
            self._browser_alive = False
            return False
    
    async def ensure_browser(self) -> bool:
        """确保浏览器可用
        
        如果浏览器已关闭，则重新初始化 MCP 连接。
        返回 True 表示浏览器可用，False 表示无法恢复。
        """
        if await self.check_browser_alive():
            return True
        
        print("\n[系统] 检测到浏览器已关闭，正在重新初始化...")
        
        await self._cleanup_server_session("playwright")
        self._tools = []
        self._connected = False
        
        playwright_config = self.config.get("playwright")
        if not playwright_config:
            return False
        
        try:
            connection_cfg = playwright_config.get("connection", {})
            retry_times = connection_cfg.get("retry_times", 3)
            retry_delay = connection_cfg.get("retry_delay", 5)
            timeout = connection_cfg.get("timeout", 30)
            
            for attempt in range(retry_times):
                try:
                    session_cm = self._client.session("playwright")
                    session = await session_cm.__aenter__()
                    await session.initialize()
                    
                    self._session_cms["playwright"] = session_cm
                    self._sessions["playwright"] = session
                    
                    server_tools = await asyncio.wait_for(
                        load_mcp_tools(session),
                        timeout=timeout
                    )
                    self._tools.extend(server_tools)
                    self._browser_alive = True
                    self._connected = bool(self._sessions)
                    return True
                except Exception:
                    await self._cleanup_server_session("playwright")
                    if attempt < retry_times - 1:
                        await asyncio.sleep(retry_delay)
            
            return False
        except Exception as e:
            print(f"\n[系统] 浏览器重新初始化失败: {e}")
            return False
    
    async def close_browser(self) -> bool:
        """显式关闭浏览器
        
        返回 True 表示关闭成功，False 表示关闭失败。
        """
        session = self._sessions.get("playwright")
        if not session:
            return False
        
        try:
            await session.call_tool("browser_close", {})
            self._browser_alive = False
            return True
        except Exception as e:
            print(f"\n[系统] 关闭浏览器失败: {e}")
            return False
    
    async def disconnect(self, close_browser: bool = False) -> None:
        """断开所有MCP连接
        
        Args:
            close_browser: 是否关闭浏览器（默认不关闭）
        """
        if close_browser:
            await self.close_browser()
        
        for server_name in list(self._sessions.keys()):
            await self._cleanup_server_session(server_name)
        
        self._client = None
        self._tools = []
        self._connected = False
