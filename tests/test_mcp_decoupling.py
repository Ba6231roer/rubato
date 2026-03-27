"""MCP解耦集成测试

验证MCP禁用场景：
1. config/mcp_config.yaml 中 playwright.enabled: false
2. has_enabled_mcp_servers() 函数返回 False
3. build_mcp_config() 函数返回空字典
4. Agent 可以在没有 MCPManager 的情况下初始化
5. MCPToolProvider 在 MCP 禁用时返回空工具列表
"""

import pytest
from pathlib import Path
import sys
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.models import (
    AppConfig, MCPConfig, MCPServerConfig, ModelConfig,
    FullModelConfig, PromptConfig, SkillsConfig, AgentConfig
)
from src.main import build_mcp_config, has_enabled_mcp_servers
from src.tools.mcp_provider import MCPToolProvider
from src.mcp.client import MCPManager


class TestMCPConfigDisabled:
    """测试MCP配置禁用场景"""

    def test_config_file_has_playwright_disabled(self):
        """测试1: 验证配置文件中 playwright.enabled 为 false"""
        import yaml
        
        config_path = Path(__file__).parent.parent / "config" / "mcp_config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
        
        assert "mcp" in config_data
        assert "servers" in config_data["mcp"]
        assert "playwright" in config_data["mcp"]["servers"]
        assert config_data["mcp"]["servers"]["playwright"]["enabled"] == False

    def test_has_enabled_mcp_servers_returns_false(self):
        """测试2: has_enabled_mcp_servers() 返回 False"""
        server_config = MCPServerConfig(
            enabled=False,
            command="npx.cmd",
            args=["-y", "@playwright/mcp"]
        )
        
        mock_config = MagicMock()
        mock_config.mcp = MagicMock()
        mock_config.mcp.servers = {"playwright": server_config}
        
        result = has_enabled_mcp_servers(mock_config)
        
        assert result == False, "当所有MCP服务器都禁用时，应返回False"

    def test_build_mcp_config_returns_empty_dict(self):
        """测试3: build_mcp_config() 返回空字典"""
        server_config = MCPServerConfig(
            enabled=False,
            command="npx.cmd",
            args=["-y", "@playwright/mcp"]
        )
        
        mock_config = MagicMock()
        mock_config.mcp = MagicMock()
        mock_config.mcp.servers = {"playwright": server_config}
        
        result = build_mcp_config(mock_config)
        
        assert result == {}, "当所有MCP服务器都禁用时，应返回空字典"

    def test_build_mcp_config_with_no_mcp_config(self):
        """测试3.1: 当 mcp 配置为 None 时，build_mcp_config() 返回空字典"""
        mock_config = MagicMock()
        mock_config.mcp = None
        
        result = build_mcp_config(mock_config)
        
        assert result == {}

    def test_build_mcp_config_with_no_servers(self):
        """测试3.2: 当 servers 为空时，build_mcp_config() 返回空字典"""
        mock_config = MagicMock()
        mock_config.mcp = MagicMock()
        mock_config.mcp.servers = {}
        
        result = build_mcp_config(mock_config)
        
        assert result == {}


class TestMCPToolProviderDisabled:
    """测试 MCPToolProvider 在 MCP 禁用时的行为"""

    def test_mcp_tool_provider_with_empty_config(self):
        """测试5.1: MCPToolProvider 在配置为空时返回空工具列表"""
        provider = MCPToolProvider(mcp_config={})
        
        tools = provider.get_tools()
        
        assert tools == [], "当配置为空时，应返回空工具列表"
        assert provider.is_available() == False

    def test_mcp_tool_provider_without_mcp_manager(self):
        """测试5.2: MCPToolProvider 在没有 MCPManager 时返回空工具列表"""
        mcp_config = {
            "playwright": {
                "command": "npx.cmd",
                "args": ["-y", "@playwright/mcp"],
                "enabled": False
            }
        }
        
        provider = MCPToolProvider(mcp_config=mcp_config, mcp_manager=None)
        
        tools = provider.get_tools()
        
        assert tools == [], "当没有MCPManager时，应返回空工具列表"
        assert provider.is_available() == False

    def test_mcp_tool_provider_is_available_false(self):
        """测试5.3: MCPToolProvider.is_available() 在 MCP 禁用时返回 False"""
        provider = MCPToolProvider(mcp_config={}, mcp_manager=None)
        
        assert provider.is_available() == False

    def test_mcp_tool_provider_get_server_names_empty(self):
        """测试5.4: MCPToolProvider.get_server_names() 在配置为空时返回空列表"""
        provider = MCPToolProvider(mcp_config={})
        
        server_names = provider.get_server_names()
        
        assert server_names == []

    def test_mcp_tool_provider_is_server_enabled_false(self):
        """测试5.5: MCPToolProvider.is_server_enabled() 在服务器禁用时返回 False"""
        mcp_config = {
            "playwright": {
                "command": "npx.cmd",
                "args": ["-y", "@playwright/mcp"],
                "enabled": False
            }
        }
        
        provider = MCPToolProvider(mcp_config=mcp_config)
        
        assert provider.is_server_enabled("playwright") == False

    @pytest.mark.asyncio
    async def test_mcp_tool_provider_async_get_tools_empty(self):
        """测试5.6: async_get_tools() 在 MCP 禁用时返回空列表"""
        provider = MCPToolProvider(mcp_config={}, mcp_manager=None)
        
        tools = await provider.async_get_tools()
        
        assert tools == []


class TestAgentInitializationWithoutMCP:
    """测试 Agent 在没有 MCPManager 的情况下初始化"""

    def test_app_state_initialization_without_mcp(self):
        """测试4.1: AppState 可以在没有 MCPManager 的情况下初始化"""
        from src.main import AppState
        
        app_state = AppState()
        
        assert app_state.mcp_manager is None
        assert app_state.config is None
        assert app_state.agent is None

    def test_tool_registry_without_mcp_manager(self):
        """测试4.2: ToolRegistry 在没有 MCPManager 时正常工作"""
        from src.mcp.tools import ToolRegistry
        from src.tools.provider import LocalToolProvider, ShellToolProvider
        
        registry = ToolRegistry()
        
        local_provider = LocalToolProvider()
        registry.register_provider(local_provider)
        
        shell_provider = ShellToolProvider()
        registry.register_provider(shell_provider)
        
        tools = registry.get_all_tools()
        
        assert len(tools) >= 1, "即使没有MCP，也应该有本地工具"


class TestMCPConfigIntegration:
    """MCP配置集成测试"""

    def test_full_config_with_disabled_mcp(self):
        """测试完整的配置加载流程（MCP禁用）"""
        model_config = ModelConfig(
            provider="openai",
            name="gpt-4",
            api_key="test-key"
        )
        
        full_model_config = FullModelConfig(model=model_config)
        
        server_config = MCPServerConfig(
            enabled=False,
            command="npx.cmd",
            args=["-y", "@playwright/mcp"]
        )
        
        mcp_config = MCPConfig(servers={"playwright": server_config})
        
        prompt_config = PromptConfig(
            system_prompt="test.md",
            skill_prompt="skill.md"
        )
        
        skills_config = SkillsConfig(
            directory="skills",
            auto_load=True
        )
        
        agent_config = AgentConfig()
        
        config = AppConfig(
            model=full_model_config,
            mcp=mcp_config,
            prompts=prompt_config,
            skills=skills_config,
            agent=agent_config
        )
        
        assert config.mcp is not None
        assert config.mcp.servers["playwright"].enabled == False
        
        result = has_enabled_mcp_servers(config)
        assert result == False
        
        mcp_dict = build_mcp_config(config)
        assert mcp_dict == {}


class TestMCPManagerEmptyConfig:
    """测试 MCPManager 在空配置时的行为"""

    def test_mcp_manager_with_empty_config(self):
        """测试 MCPManager 在配置为空时的行为"""
        manager = MCPManager(config={})
        
        assert manager.is_connected == False

    @pytest.mark.asyncio
    async def test_mcp_manager_connect_with_empty_config(self):
        """测试 MCPManager.connect() 在配置为空时抛出错误"""
        from src.mcp.errors import MCPConnectionError
        
        manager = MCPManager(config={})
        
        with pytest.raises(MCPConnectionError) as exc_info:
            await manager.connect()
        
        assert "MCP配置为空" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
