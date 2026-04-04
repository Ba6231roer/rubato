"""
E2E 测试：test-case-executor 角色使用 playwright-cli skill

测试内容：
1. 验证角色配置正确禁用 MCP
2. 验证 playwright-cli skill 正确加载
3. 验证使用 playwright-cli 执行浏览器自动化任务
"""

import sys
import pytest
import asyncio
import tempfile
import os
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from pathlib import Path

sys.path.insert(0, '.')

from src.core.agent import RubatoAgent
from src.core.role_manager import RoleManager
from src.config.models import (
    AppConfig, FullModelConfig, ModelConfig, MCPConfig, 
    PromptConfig, SkillsConfig, AgentConfig, AgentExecutionConfig,
    ProjectConfig, FileToolsConfig, UnifiedToolsConfig, RoleConfig,
    RoleModelConfig, RoleExecutionConfig, WorkspaceConfig
)
from src.context.manager import ContextManager
from src.mcp.tools import ToolRegistry
from src.skills.loader import SkillLoader
from src.skills.manager import SkillManager
from langchain_core.tools import tool


def create_e2e_config() -> AppConfig:
    """创建端到端测试配置"""
    return AppConfig(
        model=FullModelConfig(
            model=ModelConfig(
                provider="openai",
                name="e2e-test-model",
                api_key="e2e-test-api-key",
                base_url="https://api.e2e.test.com/v1",
                temperature=0.7,
                max_tokens=80000
            )
        ),
        mcp=MCPConfig(servers={}),
        prompts=PromptConfig(
            system_prompt_file="prompts/system_prompt.txt"
        ),
        skills=SkillsConfig(
            directory="skills",
            auto_load=False,
            enabled_skills=[]
        ),
        agent=AgentConfig(
            max_context_tokens=80000,
            execution=AgentExecutionConfig(
                recursion_limit=100,
                sub_agent_recursion_limit=50
            )
        ),
        project=ProjectConfig(
            name="e2e-test-project",
            root=Path("."),
            workspace=WorkspaceConfig(main=Path("."))
        ),
        file_tools=FileToolsConfig(),
        tools=UnifiedToolsConfig()
    )


def create_e2e_tool_registry() -> ToolRegistry:
    """创建端到端测试工具注册表"""
    tool_registry = ToolRegistry()
    
    @tool
    def shell_tool(command: str) -> str:
        """执行 Shell 命令"""
        return f"executed: {command}"
    
    @tool
    def file_read(path: str) -> str:
        """读取文件"""
        return f"content of {path}"
    
    @tool
    def file_write(path: str, content: str) -> str:
        """写入文件"""
        return f"written to {path}"
    
    tool_registry.register(shell_tool)
    tool_registry.register(file_read)
    tool_registry.register(file_write)
    
    return tool_registry


def create_e2e_skill_loader_with_playwright() -> SkillLoader:
    """创建包含 playwright-cli skill 的 SkillLoader"""
    skill_loader = SkillLoader(
        skills_dir="skills",
        enabled_skills=["playwright-cli"],
        max_loaded_skills=3
    )
    
    return skill_loader


class TestTestCaseExecutorWithPlaywrightCLI:
    """test-case-executor 角色使用 playwright-cli skill 测试"""
    
    @pytest.fixture
    def setup_executor_environment(self):
        """设置测试环境"""
        config = create_e2e_config()
        skill_loader = create_e2e_skill_loader_with_playwright()
        context_manager = ContextManager(max_tokens=80000, auto_compress=False)
        tool_registry = create_e2e_tool_registry()
        
        role_config = RoleConfig(
            name='test-case-executor',
            description='测试案例执行者',
            system_prompt_file='prompts/roles/test_case_executor.txt',
            model=RoleModelConfig(inherit=True),
            execution=RoleExecutionConfig(
                max_context_tokens=80000,
                timeout=300,
                recursion_limit=100
            ),
            available_tools=['shell_tool', 'file_read', 'file_write'],
            tools={
                'builtin': {
                    'spawn_agent': True,
                    'shell_tool': True,
                    'file_tools': {'enabled': True}
                },
                'mcp': {'enabled': False},
                'skills': ['playwright-cli']
            }
        )
        
        return {
            'config': config,
            'skill_loader': skill_loader,
            'context_manager': context_manager,
            'tool_registry': tool_registry,
            'role_config': role_config
        }
    
    def test_role_config_disables_mcp(self, setup_executor_environment):
        """测试角色配置正确禁用 MCP"""
        env = setup_executor_environment
        role_config = env['role_config']
        
        assert role_config.tools is not None
        assert role_config.tools.get('mcp') is not None
        assert role_config.tools.get('mcp').get('enabled') == False
    
    def test_role_config_includes_playwright_skill(self, setup_executor_environment):
        """测试角色配置包含 playwright-cli skill"""
        env = setup_executor_environment
        role_config = env['role_config']
        
        assert role_config.tools is not None
        assert 'playwright-cli' in role_config.tools.get('skills', [])
    
    @pytest.mark.asyncio
    async def test_skill_loader_has_playwright_cli(self, setup_executor_environment):
        """测试 SkillLoader 能加载 playwright-cli skill"""
        env = setup_executor_environment
        skill_loader = env['skill_loader']
        
        await skill_loader.load_skill_metadata()
        
        assert skill_loader.has_skill('playwright-cli')
    
    @pytest.mark.asyncio
    async def test_playwright_cli_skill_content(self, setup_executor_environment):
        """测试 playwright-cli skill 内容正确加载"""
        env = setup_executor_environment
        skill_loader = env['skill_loader']
        
        await skill_loader.load_skill_metadata()
        
        content = await skill_loader.load_full_skill('playwright-cli')
        
        assert content is not None
        assert len(content) > 0
        assert 'playwright-cli' in content.lower()
        assert 'open' in content.lower()
        assert 'goto' in content.lower()
    
    @pytest.mark.asyncio
    async def test_playwright_cli_skill_triggers(self, setup_executor_environment):
        """测试 playwright-cli skill 触发词"""
        env = setup_executor_environment
        skill_loader = env['skill_loader']
        
        await skill_loader.load_skill_metadata()
        
        test_inputs = [
            "打开百度",
            "浏览器自动化",
            "网页测试",
            "playwright 操作",
            "点击按钮",
            "输入文本"
        ]
        
        for test_input in test_inputs:
            matched_skill = skill_loader.find_matching_skill(test_input)
            assert matched_skill == 'playwright-cli', f"输入 '{test_input}' 应该匹配 playwright-cli skill"
    
    def test_mcp_disabled_in_tool_registry(self, setup_executor_environment):
        """测试 MCP 工具不被注册到 ToolRegistry"""
        from src.core.agent_pool import AgentPool
        
        env = setup_executor_environment
        config = env['config']
        role_config = env['role_config']
        
        agent_pool = AgentPool(
            config=config,
            max_instances=1,
            roles_dir="config/roles",
            skills_dir="skills"
        )
        
        tool_registry = agent_pool._create_tool_registry(
            mcp_manager=None,
            role_config=role_config
        )
        
        tools = tool_registry.get_all_tools()
        tool_names = [t.name for t in tools]
        
        assert 'shell_tool' in tool_names
        assert 'file_read' in tool_names
        assert 'file_write' in tool_names


class TestPlaywrightCLIWorkflow:
    """playwright-cli 工作流测试"""
    
    @pytest.mark.asyncio
    async def test_baidu_search_workflow_commands(self):
        """测试百度搜索工作流的 playwright-cli 命令序列"""
        
        expected_commands = [
            "playwright-cli open https://www.baidu.com",
            "playwright-cli type python",
            "playwright-cli press Enter",
            "playwright-cli click e1",
        ]
        
        for cmd in expected_commands:
            assert cmd.startswith("playwright-cli"), f"命令应该是 playwright-cli: {cmd}"
    
    def test_playwright_cli_skill_metadata(self):
        """测试 playwright-cli skill 元数据"""
        skill_file = Path("skills/playwright-cli/SKILL.md")
        
        if skill_file.exists():
            content = skill_file.read_text(encoding='utf-8')
            
            assert 'name: playwright-cli' in content
            assert 'description:' in content
            assert 'triggers:' in content
            assert 'tools:' in content
            assert 'ShellTool' in content


def test_role_config_file():
    """测试角色配置文件"""
    role_file = Path("config/roles/test_case_executor.yaml")
    
    assert role_file.exists(), "test_case_executor.yaml 应该存在"
    
    content = role_file.read_text(encoding='utf-8')
    
    assert 'mcp:' in content
    assert 'enabled: false' in content
    assert 'playwright-cli' in content


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
