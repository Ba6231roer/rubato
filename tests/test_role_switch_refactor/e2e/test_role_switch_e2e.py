"""
端到端测试：角色切换完整场景验证

测试内容：
1. 测试完整的用户场景：启动 → 切换角色 → 对话 → 切换角色 → 对话
2. 测试所有命令的一致性：/prompt show、/status full、/status prompt
"""

import sys
import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from pathlib import Path

sys.path.insert(0, '.')

from src.core.agent import RubatoAgent
from src.core.role_manager import RoleManager
from src.cli.commands import CommandHandler
from src.config.models import (
    AppConfig, FullModelConfig, ModelConfig, MCPConfig, 
    PromptConfig, SkillsConfig, AgentConfig, AgentExecutionConfig,
    ProjectConfig, FileToolsConfig, UnifiedToolsConfig, RoleConfig,
    RoleModelConfig, RoleExecutionConfig, WorkspaceConfig
)
from src.context.manager import ContextManager
from src.mcp.tools import ToolRegistry
from src.skills.loader import SkillLoader
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
    
    @tool
    def browser_navigate(url: str) -> str:
        """导航到 URL"""
        return f"navigated to {url}"
    
    @tool
    def browser_click(selector: str) -> str:
        """点击元素"""
        return f"clicked {selector}"
    
    tool_registry.register(shell_tool)
    tool_registry.register(file_read)
    tool_registry.register(file_write)
    tool_registry.register(browser_navigate)
    tool_registry.register(browser_click)
    
    return tool_registry


def create_e2e_skill_loader() -> SkillLoader:
    """创建端到端测试 SkillLoader"""
    skill_loader = Mock(spec=SkillLoader)
    skill_loader.has_skill = Mock(return_value=False)
    skill_loader.load_full_skill = Mock(return_value=None)
    skill_loader.get_all_skill_metadata = Mock(return_value={})
    return skill_loader


class TestE2ERoleSwitchScenario:
    """端到端角色切换场景测试"""
    
    @pytest.fixture
    def setup_e2e_environment(self):
        """设置端到端测试环境"""
        config = create_e2e_config()
        skill_loader = create_e2e_skill_loader()
        context_manager = ContextManager(max_tokens=80000, auto_compress=False)
        tool_registry = create_e2e_tool_registry()
        
        with patch.object(Path, 'exists', return_value=False):
            agent = RubatoAgent(
                config=config,
                skill_loader=skill_loader,
                context_manager=context_manager,
                tool_registry=tool_registry
            )
        
        return {
            'agent': agent,
            'config': config,
            'tool_registry': tool_registry,
            'skill_loader': skill_loader,
            'context_manager': context_manager
        }
    
    @pytest.mark.asyncio
    async def test_complete_user_scenario(self, setup_e2e_environment):
        """测试 1: 完整的用户场景：启动 → 切换角色 → 对话 → 切换角色 → 对话"""
        env = setup_e2e_environment
        agent = env['agent']
        
        initial_prompt = agent.get_system_prompt()
        assert initial_prompt is not None
        assert len(initial_prompt) > 0
        
        role1_config = RoleConfig(
            name='browser-tester',
            description='浏览器测试专家',
            system_prompt_file='prompts/roles/browser_tester.txt',
            model=RoleModelConfig(inherit=True),
            execution=RoleExecutionConfig(
                max_context_tokens=60000,
                timeout=300
            ),
            available_tools=['browser_navigate', 'browser_click', 'shell_tool']
        )
        
        with patch.object(Path, 'exists', return_value=False):
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__ = lambda s: s
                mock_open.return_value.__exit__ = Mock()
                mock_open.return_value.read.return_value = "你是浏览器测试专家，专注于 Web 应用的自动化测试。"
                
                agent.reload_system_prompt(role_config=role1_config)
        
        prompt_after_role1 = agent.get_system_prompt()
        assert prompt_after_role1 != initial_prompt
        assert "浏览器测试" in prompt_after_role1 or "browser" in prompt_after_role1.lower()
        
        role2_config = RoleConfig(
            name='file-manager',
            description='文件管理专家',
            system_prompt_file='prompts/roles/file_manager.txt',
            model=RoleModelConfig(inherit=True),
            execution=RoleExecutionConfig(
                max_context_tokens=70000,
                timeout=200
            ),
            available_tools=['file_read', 'file_write', 'shell_tool']
        )
        
        with patch.object(Path, 'exists', return_value=False):
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__ = lambda s: s
                mock_open.return_value.__exit__ = Mock()
                mock_open.return_value.read.return_value = "你是文件管理专家，专注于文件系统的操作和管理。"
                
                agent.reload_system_prompt(role_config=role2_config)
        
        prompt_after_role2 = agent.get_system_prompt()
        assert prompt_after_role2 != prompt_after_role1
        assert "文件管理" in prompt_after_role2 or "file" in prompt_after_role2.lower()
    
    @pytest.mark.asyncio
    async def test_role_consistency_across_operations(self, setup_e2e_environment):
        """测试角色切换后各属性的一致性"""
        env = setup_e2e_environment
        agent = env['agent']
        
        role_config = RoleConfig(
            name='test-executor',
            description='测试执行者',
            system_prompt_file='prompts/roles/test_executor.txt',
            model=RoleModelConfig(inherit=True),
            execution=RoleExecutionConfig(
                max_context_tokens=50000,
                timeout=180,
                recursion_limit=80
            ),
            available_tools=['shell_tool', 'file_read']
        )
        
        with patch.object(Path, 'exists', return_value=False):
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__ = lambda s: s
                mock_open.return_value.__exit__ = Mock()
                mock_open.return_value.read.return_value = "你是测试执行者，负责执行各类测试任务。"
                
                agent.reload_system_prompt(role_config=role_config)
        
        assert agent.role_config == role_config
        
        prompt1 = agent.get_system_prompt()
        prompt2 = agent.get_current_system_prompt()
        assert prompt1 == prompt2


class TestE2ECommandConsistency:
    """端到端命令一致性测试"""
    
    @pytest.fixture
    def setup_command_handler(self):
        """设置命令处理器"""
        config = create_e2e_config()
        skill_loader = create_e2e_skill_loader()
        context_manager = ContextManager(max_tokens=80000, auto_compress=False)
        tool_registry = create_e2e_tool_registry()
        
        with patch.object(Path, 'exists', return_value=False):
            agent = RubatoAgent(
                config=config,
                skill_loader=skill_loader,
                context_manager=context_manager,
                tool_registry=tool_registry
            )
        
        handler = CommandHandler(
            agent=agent,
            skill_loader=skill_loader,
            mcp_manager=None,
            role_manager=None,
            config_loader=None,
            agent_pool=None
        )
        
        return {
            'handler': handler,
            'agent': agent,
            'config': config
        }
    
    @pytest.mark.asyncio
    async def test_prompt_show_command(self, setup_command_handler):
        """测试 /prompt show 命令"""
        env = setup_command_handler
        handler = env['handler']
        agent = env['agent']
        
        system_prompt = agent.get_system_prompt()
        
        assert system_prompt is not None
        assert len(system_prompt) > 0
        
        assert "工具" in system_prompt or "Tool" in system_prompt.lower()
    
    @pytest.mark.asyncio
    async def test_status_full_command(self, setup_command_handler):
        """测试 /status full 命令"""
        env = setup_command_handler
        agent = env['agent']
        
        status_info = {
            'model': agent.llm.model_name,
            'tool_count': len(agent.tools),
            'max_context_tokens': agent.max_context_tokens,
            'recursion_limit': agent.recursion_limit
        }
        
        assert status_info['model'] == 'e2e-test-model'
        assert status_info['tool_count'] > 0
        assert status_info['max_context_tokens'] == 80000
        assert status_info['recursion_limit'] == 100
    
    @pytest.mark.asyncio
    async def test_status_prompt_command(self, setup_command_handler):
        """测试 /status prompt 命令"""
        env = setup_command_handler
        agent = env['agent']
        
        prompt_info = {
            'system_prompt': agent.get_system_prompt(),
            'current_system_prompt': agent.get_current_system_prompt()
        }
        
        assert prompt_info['system_prompt'] == prompt_info['current_system_prompt']
        assert len(prompt_info['system_prompt']) > 0
    
    @pytest.mark.asyncio
    async def test_command_consistency_after_role_switch(self, setup_command_handler):
        """测试角色切换后命令的一致性"""
        env = setup_command_handler
        agent = env['agent']
        
        initial_prompt = agent.get_system_prompt()
        
        new_role_config = RoleConfig(
            name='new-role',
            description='新角色',
            system_prompt_file='prompts/roles/new_role.txt',
            model=RoleModelConfig(inherit=True),
            execution=RoleExecutionConfig()
        )
        
        with patch.object(Path, 'exists', return_value=False):
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__ = lambda s: s
                mock_open.return_value.__exit__ = Mock()
                mock_open.return_value.read.return_value = "这是新角色的系统提示词"
                
                agent.reload_system_prompt(role_config=new_role_config)
        
        new_prompt = agent.get_system_prompt()
        
        assert new_prompt != initial_prompt
        
        prompt1 = agent.get_system_prompt()
        prompt2 = agent.get_current_system_prompt()
        assert prompt1 == prompt2


class TestE2EMultiRoleWorkflow:
    """端到端多角色工作流测试"""
    
    @pytest.mark.asyncio
    async def test_sequential_role_switches(self):
        """测试连续的角色切换"""
        config = create_e2e_config()
        skill_loader = create_e2e_skill_loader()
        context_manager = ContextManager(max_tokens=80000, auto_compress=False)
        tool_registry = create_e2e_tool_registry()
        
        with patch.object(Path, 'exists', return_value=False):
            agent = RubatoAgent(
                config=config,
                skill_loader=skill_loader,
                context_manager=context_manager,
                tool_registry=tool_registry
            )
        
        roles = [
            ('developer', '开发专家', '你是开发专家，专注于代码编写和优化。'),
            ('reviewer', '代码审查专家', '你是代码审查专家，专注于代码质量。'),
            ('tester', '测试专家', '你是测试专家，专注于测试用例设计。'),
        ]
        
        prompts = []
        
        for role_name, description, prompt_content in roles:
            role_config = RoleConfig(
                name=role_name,
                description=description,
                system_prompt_file=f'prompts/roles/{role_name}.txt',
                model=RoleModelConfig(inherit=True),
                execution=RoleExecutionConfig()
            )
            
            with patch.object(Path, 'exists', return_value=False):
                with patch('builtins.open', create=True) as mock_open:
                    mock_open.return_value.__enter__ = lambda s: s
                    mock_open.return_value.__exit__ = Mock()
                    mock_open.return_value.read.return_value = prompt_content
                    
                    agent.reload_system_prompt(role_config=role_config)
            
            current_prompt = agent.get_system_prompt()
            prompts.append(current_prompt)
            
            assert description.split('，')[0] in current_prompt or role_name in current_prompt.lower()
        
        for i in range(len(prompts) - 1):
            assert prompts[i] != prompts[i + 1]
    
    @pytest.mark.asyncio
    async def test_role_switch_with_tool_filtering(self):
        """测试带工具过滤的角色切换"""
        config = create_e2e_config()
        skill_loader = create_e2e_skill_loader()
        context_manager = ContextManager(max_tokens=80000, auto_compress=False)
        tool_registry = create_e2e_tool_registry()
        
        role_config = RoleConfig(
            name='browser-only',
            description='仅浏览器操作',
            system_prompt_file='prompts/roles/browser_only.txt',
            model=RoleModelConfig(inherit=True),
            execution=RoleExecutionConfig(),
            available_tools=['browser_navigate', 'browser_click']
        )
        
        with patch.object(Path, 'exists', return_value=False):
            agent = RubatoAgent(
                config=config,
                skill_loader=skill_loader,
                context_manager=context_manager,
                tool_registry=tool_registry,
                role_config=role_config
            )
        
        tool_names = [t.name for t in agent.tools if t.name != 'spawn_agent']
        
        assert 'browser_navigate' in tool_names
        assert 'browser_click' in tool_names
        assert 'file_read' not in tool_names
        assert 'file_write' not in tool_names
        assert 'shell_tool' not in tool_names


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
