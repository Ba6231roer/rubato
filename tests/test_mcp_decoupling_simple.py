"""简单的MCP解耦测试脚本

直接运行测试，不依赖pytest
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock
import asyncio

sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 60)
print("MCP解耦集成测试")
print("=" * 60)
print()

test_results = []

def run_test(test_name, test_func):
    """运行单个测试"""
    try:
        test_func()
        test_results.append((test_name, "✓ 通过", None))
        print(f"✓ {test_name}")
        return True
    except AssertionError as e:
        test_results.append((test_name, "✗ 失败", str(e)))
        print(f"✗ {test_name}")
        print(f"  错误: {e}")
        return False
    except Exception as e:
        test_results.append((test_name, "✗ 错误", str(e)))
        print(f"✗ {test_name}")
        print(f"  异常: {type(e).__name__}: {e}")
        return False


print("-" * 60)
print("测试1: 验证配置文件中 playwright.enabled 为 false")
print("-" * 60)

def test_config_file():
    import yaml
    
    config_path = Path(__file__).parent.parent / "config" / "mcp_config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)
    
    assert "mcp" in config_data, "配置文件应包含 'mcp' 键"
    assert "servers" in config_data["mcp"], "配置应包含 'servers' 键"
    assert "playwright" in config_data["mcp"]["servers"], "配置应包含 'playwright' 服务器"
    assert config_data["mcp"]["servers"]["playwright"]["enabled"] == False, "playwright.enabled 应为 False"

run_test("配置文件验证", test_config_file)

print()
print("-" * 60)
print("测试2: has_enabled_mcp_servers() 返回 False")
print("-" * 60)

def test_has_enabled_mcp_servers():
    from src.config.models import MCPServerConfig
    from src.main import has_enabled_mcp_servers
    
    server_config = MCPServerConfig(
        enabled=False,
        command="npx.cmd",
        args=["-y", "@playwright/mcp"]
    )
    
    mock_config = MagicMock()
    mock_config.mcp = MagicMock()
    mock_config.mcp.servers = {"playwright": server_config}
    
    result = has_enabled_mcp_servers(mock_config)
    assert result == False, f"当所有MCP服务器都禁用时，应返回False，实际返回: {result}"

run_test("has_enabled_mcp_servers() 返回 False", test_has_enabled_mcp_servers)

print()
print("-" * 60)
print("测试3: build_mcp_config() 返回空字典")
print("-" * 60)

def test_build_mcp_config():
    from src.config.models import MCPServerConfig
    from src.main import build_mcp_config
    
    server_config = MCPServerConfig(
        enabled=False,
        command="npx.cmd",
        args=["-y", "@playwright/mcp"]
    )
    
    mock_config = MagicMock()
    mock_config.mcp = MagicMock()
    mock_config.mcp.servers = {"playwright": server_config}
    
    result = build_mcp_config(mock_config)
    assert result == {}, f"当所有MCP服务器都禁用时，应返回空字典，实际返回: {result}"

run_test("build_mcp_config() 返回空字典", test_build_mcp_config)

def test_build_mcp_config_none():
    from src.main import build_mcp_config
    
    mock_config = MagicMock()
    mock_config.mcp = None
    
    result = build_mcp_config(mock_config)
    assert result == {}, f"当mcp为None时，应返回空字典，实际返回: {result}"

run_test("build_mcp_config() 当mcp为None时返回空字典", test_build_mcp_config_none)

print()
print("-" * 60)
print("测试4: Agent 可以在没有 MCPManager 的情况下初始化")
print("-" * 60)

def test_app_state_init():
    from src.main import AppState
    
    app_state = AppState()
    
    assert app_state.mcp_manager is None, "AppState初始化时mcp_manager应为None"
    assert app_state.config is None, "AppState初始化时config应为None"
    assert app_state.agent is None, "AppState初始化时agent应为None"

run_test("AppState 初始化（无MCPManager）", test_app_state_init)

def test_tool_registry():
    from src.mcp.tools import ToolRegistry
    from src.tools.provider import LocalToolProvider, ShellToolProvider
    
    registry = ToolRegistry()
    
    local_provider = LocalToolProvider()
    registry.register_provider(local_provider)
    
    shell_provider = ShellToolProvider()
    registry.register_provider(shell_provider)
    
    tools = registry.get_all_tools()
    
    assert len(tools) >= 1, f"即使没有MCP，也应该有本地工具，实际: {len(tools)}"
    
    tool_names = [t.name for t in tools]
    assert len(tools) > 0, f"应该有工具，实际工具: {tool_names}"

run_test("ToolRegistry 无MCPManager时正常工作", test_tool_registry)

print()
print("-" * 60)
print("测试5: MCPToolProvider 在 MCP 禁用时返回空工具列表")
print("-" * 60)

def test_mcp_tool_provider_empty_config():
    from src.tools.mcp_provider import MCPToolProvider
    
    provider = MCPToolProvider(mcp_config={})
    
    tools = provider.get_tools()
    assert tools == [], f"当配置为空时，应返回空工具列表，实际返回: {tools}"
    assert provider.is_available() == False, "当配置为空时，is_available应返回False"

run_test("MCPToolProvider 空配置返回空工具列表", test_mcp_tool_provider_empty_config)

def test_mcp_tool_provider_no_manager():
    from src.tools.mcp_provider import MCPToolProvider
    
    mcp_config = {
        "playwright": {
            "command": "npx.cmd",
            "args": ["-y", "@playwright/mcp"],
            "enabled": False
        }
    }
    
    provider = MCPToolProvider(mcp_config=mcp_config, mcp_manager=None)
    
    tools = provider.get_tools()
    assert tools == [], f"当没有MCPManager时，应返回空工具列表，实际返回: {tools}"
    assert provider.is_available() == False, "当没有MCPManager时，is_available应返回False"

run_test("MCPToolProvider 无MCPManager返回空工具列表", test_mcp_tool_provider_no_manager)

def test_mcp_tool_provider_server_names():
    from src.tools.mcp_provider import MCPToolProvider
    
    provider = MCPToolProvider(mcp_config={})
    
    server_names = provider.get_server_names()
    assert server_names == [], f"当配置为空时，应返回空列表，实际返回: {server_names}"

run_test("MCPToolProvider.get_server_names() 返回空列表", test_mcp_tool_provider_server_names)

def test_mcp_tool_provider_is_server_enabled():
    from src.tools.mcp_provider import MCPToolProvider
    
    mcp_config = {
        "playwright": {
            "command": "npx.cmd",
            "args": ["-y", "@playwright/mcp"],
            "enabled": False
        }
    }
    
    provider = MCPToolProvider(mcp_config=mcp_config)
    
    result = provider.is_server_enabled("playwright")
    assert result == False, f"当服务器禁用时，应返回False，实际返回: {result}"

run_test("MCPToolProvider.is_server_enabled() 返回False", test_mcp_tool_provider_is_server_enabled)

print()
print("-" * 60)
print("测试6: MCPManager 在空配置时的行为")
print("-" * 60)

def test_mcp_manager_empty_config():
    from src.mcp.client import MCPManager
    
    manager = MCPManager(config={})
    
    assert manager.is_connected == False, "MCPManager初始化时is_connected应为False"

run_test("MCPManager 空配置初始化", test_mcp_manager_empty_config)

async def test_mcp_manager_connect_empty():
    from src.mcp.client import MCPManager
    from src.mcp.errors import MCPConnectionError
    
    manager = MCPManager(config={})
    
    try:
        await manager.connect()
        assert False, "应该抛出MCPConnectionError"
    except MCPConnectionError as e:
        assert "MCP配置为空" in str(e), f"错误消息应包含'MCP配置为空'，实际: {e}"

async def run_async_test():
    print("运行异步测试: MCPManager.connect() 空配置抛出错误")
    try:
        await test_mcp_manager_connect_empty()
        test_results.append(("MCPManager.connect() 空配置抛出错误", "✓ 通过", None))
        print("✓ MCPManager.connect() 空配置抛出错误")
    except AssertionError as e:
        test_results.append(("MCPManager.connect() 空配置抛出错误", "✗ 失败", str(e)))
        print(f"✗ MCPManager.connect() 空配置抛出错误")
        print(f"  错误: {e}")
    except Exception as e:
        test_results.append(("MCPManager.connect() 空配置抛出错误", "✗ 错误", str(e)))
        print(f"✗ MCPManager.connect() 空配置抛出错误")
        print(f"  异常: {type(e).__name__}: {e}")

asyncio.run(run_async_test())

print()
print("-" * 60)
print("测试7: 完整配置集成测试")
print("-" * 60)

def test_full_config_integration():
    from src.config.models import (
        AppConfig, MCPConfig, MCPServerConfig, ModelConfig,
        FullModelConfig, PromptConfig, SkillsConfig, AgentConfig
    )
    from src.main import has_enabled_mcp_servers, build_mcp_config
    
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
    
    assert config.mcp is not None, "配置应包含mcp"
    assert config.mcp.servers["playwright"].enabled == False, "playwright应为禁用状态"
    
    result = has_enabled_mcp_servers(config)
    assert result == False, f"has_enabled_mcp_servers应返回False，实际: {result}"
    
    mcp_dict = build_mcp_config(config)
    assert mcp_dict == {}, f"build_mcp_config应返回空字典，实际: {mcp_dict}"

run_test("完整配置集成测试", test_full_config_integration)

print()
print("=" * 60)
print("测试结果汇总")
print("=" * 60)

passed = sum(1 for _, status, _ in test_results if status == "✓ 通过")
failed = sum(1 for _, status, _ in test_results if status == "✗ 失败")
errors = sum(1 for _, status, _ in test_results if status == "✗ 错误")

print(f"总计: {len(test_results)} 个测试")
print(f"✓ 通过: {passed}")
print(f"✗ 失败: {failed}")
print(f"✗ 错误: {errors}")

if failed > 0 or errors > 0:
    print()
    print("失败的测试:")
    for name, status, error in test_results:
        if status != "✓ 通过":
            print(f"  - {name}: {error}")

print()
if failed == 0 and errors == 0:
    print("🎉 所有测试通过！MCP解耦功能正常工作。")
    sys.exit(0)
else:
    print("⚠️ 部分测试失败，请检查上述错误。")
    sys.exit(1)
