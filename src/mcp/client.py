from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_core.tools import BaseTool
from typing import Optional, List
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
    """
    
    def __init__(self, config: dict):
        self.config = config
        self._client: Optional[MultiServerMCPClient] = None
        self._tools: List[BaseTool] = []
        self._connected = False
        self._session_cm = None
        self._session = None
        self._browser_alive = False
    
    async def __aenter__(self) -> "MCPManager":
        """进入上下文管理器，建立并保持 MCP 连接"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """退出上下文管理器，断开 MCP 连接但不关闭浏览器"""
        await self.disconnect(close_browser=False)
    
    async def connect(self) -> None:
        """连接到MCP服务器（带重试机制）"""
        playwright_config = self.config.get("playwright", {})
        connection_config = playwright_config.get("connection", {})
        
        retry_times = connection_config.get("retry_times", 3)
        retry_delay = connection_config.get("retry_delay", 5)
        timeout = connection_config.get("timeout", 30)
        
        connection = {
            "command": playwright_config.get("command", "npx"),
            "args": playwright_config.get("args", ["-y", "@playwright/mcp"]),
            "transport": "stdio",
        }
        
        last_error = None
        for attempt in range(retry_times):
            try:
                self._client = MultiServerMCPClient({
                    "playwright": connection
                })
                
                self._session_cm = self._client.session("playwright")
                self._session = await self._session_cm.__aenter__()
                await self._session.initialize()
                
                self._tools = await asyncio.wait_for(
                    load_mcp_tools(self._session),
                    timeout=timeout
                )
                self._connected = True
                self._browser_alive = True
                return
            except asyncio.TimeoutError:
                last_error = f"MCP连接超时（{timeout}秒）"
                await self._cleanup_session()
            except Exception as e:
                last_error = f"MCP连接失败：{str(e)}"
                await self._cleanup_session()
            
            if attempt < retry_times - 1:
                await asyncio.sleep(retry_delay)
        
        raise MCPConnectionError(f"无法连接MCP服务器，已重试{retry_times}次。最后错误：{last_error}")
    
    async def _cleanup_session(self):
        """清理 session 资源"""
        if self._session_cm:
            try:
                await self._session_cm.__aexit__(None, None, None)
            except:
                pass
        self._session_cm = None
        self._session = None
    
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
        if not self._session:
            self._browser_alive = False
            return False
        
        try:
            await self._session.call_tool("browser_snapshot", {})
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
        
        await self._cleanup_session()
        self._client = None
        self._tools = []
        self._connected = False
        
        try:
            await self.connect()
            return True
        except Exception as e:
            print(f"\n[系统] 浏览器重新初始化失败: {e}")
            return False
    
    async def close_browser(self) -> bool:
        """显式关闭浏览器
        
        返回 True 表示关闭成功，False 表示关闭失败。
        """
        if not self._session:
            return False
        
        try:
            await self._session.call_tool("browser_close", {})
            self._browser_alive = False
            return True
        except Exception as e:
            print(f"\n[系统] 关闭浏览器失败: {e}")
            return False
    
    async def disconnect(self, close_browser: bool = False) -> None:
        """断开MCP连接
        
        Args:
            close_browser: 是否关闭浏览器（默认不关闭）
        """
        if close_browser and self._session:
            await self.close_browser()
        
        await self._cleanup_session()
        self._client = None
        self._tools = []
        self._connected = False
