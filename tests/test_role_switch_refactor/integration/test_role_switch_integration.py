"""
集成测试：角色切换集成验证

测试内容：
1. 测试启动时默认角色加载
2. 测试角色切换后系统提示词正确
3. 测试角色切换后模型配置正确
4. 测试角色切换后工具列表正确
5. 测试多次角色切换
"""

import sys
import pytest
import asyncio
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
from langchain_core.tools import tool


def create_test_config() -> AppConfig:
    """创建测试配置"""
    return AppConfig(
        model=FullModelConfig(
            model=ModelConfig(
                provider="openai",
                name="default-model",
                api_key="test-api-key",
                base_url="https://api.test.com/v1",
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
            name="test-project",
            root=Path("."),
            workspace=WorkspaceConfig(main=Path("."))
        ),
        file_tools=FileToolsConfig(),
        tools=UnifiedToolsConfig()
    )


def create_test_tool_registry() -> ToolRegistry:
    """创建测试工具注册表"""
    tool_registry = ToolRegistry()
    
    @tool
    def shell_tool(command: str) -> str:
        """Shell工具"""
        return f"executed: {command}"
    
    @tool
    def file_read(path: str) -> str:
        """文件读取工具"""
        return f"content of {path}"
    
    @tool
    def file_write(path: str, content: str) -> str:
        """文件写入工具"""
        return f"written to {path}"
    
    tool_registry.register(shell_tool)
    tool_registry.register(file_read)
    tool_registry.register(file_write)
    
    return tool_registry


def create_test_skill_loader() -> SkillLoader:
    """创建测试 SkillLoader"""
    skill_loader = Mock(spec=SkillLoader)
    skill_loader.has_skill = Mock(return_value=False)
    skill_loader.load_full_skill = Mock(return_value=None)
    skill_loader.get_all_skill_metadata = Mock(return_value={})
    return skill_loader


class TestRoleSwitchIntegration:
    """角色切换集成测试"""
    
    @pytest.fixture
    def setup_agent(self):
        """设置测试 Agent"""
        config = create_test_config()
        skill_loader = create_test_skill_loader()
        context_manager = ContextManager(max_tokens=80000, auto_compress=False)
        tool_registry = create_test_tool_registry()
        
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
            'tool_registry': tool_registry
        }
    
    def test_default_role_on_startup(self, setup_agent):
        """测试 1: 启动时默认角色加载"""
        agent = setup_agent['agent']
        
        assert agent is not None
        assert agent.config is not None
        assert agent.llm is not None
        assert agent.tools is not None
        assert len(agent.tools) > 0
        
        system_prompt = agent.get_system_prompt()
        assert system_prompt is not None
        assert len(system_prompt) > 0
    
    def test_role_switch_system_prompt_update(self, setup_agent):
        """测试 2: 角色切换后系统提示词正确"""
        agent = setup_agent['agent']
        
        original_prompt = agent.get_system_prompt()
        
        new_role_config = RoleConfig(
            name='code-reviewer',
            description='代码审查专家',
            system_prompt_file='prompts/roles/code_reviewer.txt',
            model=RoleModelConfig(inherit=True),
            execution=RoleExecutionConfig(
                max_context_tokens=60000,
                timeout=300
            ),
            available_tools=['file_read', 'file_write']
        )
        
        with patch.object(Path, 'exists', return_value=False):
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__ = lambda s: s
                mock_open.return_value.__exit__ = Mock()
                mock_open.return_value.read.return_value = "你是代码审查专家，专注于代码质量和最佳实践。"
                
                agent.reload_system_prompt(role_config=new_role_config)
        
        new_prompt = agent.get_system_prompt()
        
        assert new_prompt != original_prompt
        assert "代码审查" in new_prompt or "code review" in new_prompt.lower()
    
    def test_role_switch_model_config_update(self, setup_agent):
        """测试 3: 角色切换后模型配置正确"""
        agent = setup_agent['agent']
        
        original_llm = agent.llm
        original_model_name = original_llm.model_name
        
        new_model_config = ModelConfig(
            provider="openai",
            name="specialized-model",
            api_key="special-api-key",
            base_url="https://special.api.com/v1",
            temperature=0.3,
            max_tokens=40000
        )
        
        new_llm = agent._create_llm(model_config=new_model_config)
        
        assert new_llm.model_name == "specialized-model"
        assert new_llm.model_name != original_model_name
    
    def test_role_switch_tools_update(self, setup_agent):
        """测试 4: 角色切换后工具列表正确"""
        agent = setup_agent['agent']
        tool_registry = setup_agent['tool_registry']
        
        original_tools = agent.tools.copy()
        original_tool_names = [t.name for t in original_tools]
        
        new_role_config = RoleConfig(
            name='limited-executor',
            description='受限执行者',
            system_prompt_file='prompts/roles/limited.txt',
            model=RoleModelConfig(inherit=True),
            execution=RoleExecutionConfig(),
            available_tools=['shell_tool']
        )
        
        with patch.object(Path, 'exists', return_value=False):
            agent_with_role = RubatoAgent(
                config=setup_agent['config'],
                skill_loader=create_test_skill_loader(),
                context_manager=ContextManager(max_tokens=80000, auto_compress=False),
                tool_registry=tool_registry,
                role_config=new_role_config
            )
        
        new_tool_names = [t.name for t in agent_with_role.tools if t.name != 'spawn_agent']
        
        assert 'shell_tool' in new_tool_names
        assert 'file_read' not in new_tool_names
        assert 'file_write' not in new_tool_names
    
    def test_multiple_role_switches(self, setup_agent):
        """测试 5: 多次角色切换"""
        agent = setup_agent['agent']
        
        prompts = []
        
        role_configs = [
            RoleConfig(
                name='role-1',
                description='角色1',
                system_prompt_file='prompts/roles/role1.txt',
                model=RoleModelConfig(inherit=True),
                execution=RoleExecutionConfig()
            ),
            RoleConfig(
                name='role-2',
                description='角色2',
                system_prompt_file='prompts/roles/role2.txt',
                model=RoleModelConfig(inherit=True),
                execution=RoleExecutionConfig()
            ),
            RoleConfig(
                name='role-3',
                description='角色3',
                system_prompt_file='prompts/roles/role3.txt',
                model=RoleModelConfig(inherit=True),
                execution=RoleExecutionConfig()
            )
        ]
        
        for i, role_config in enumerate(role_configs):
            with patch.object(Path, 'exists', return_value=False):
                with patch('builtins.open', create=True) as mock_open:
                    mock_open.return_value.__enter__ = lambda s: s
                    mock_open.return_value.__exit__ = Mock()
                    mock_open.return_value.read.return_value = f"这是角色{i+1}的系统提示词"
                    
                    agent.reload_system_prompt(role_config=role_config)
            
            current_prompt = agent.get_system_prompt()
            prompts.append(current_prompt)
            
            assert f"角色{i+1}" in current_prompt or f"这是角色{i+1}的系统提示词" in current_prompt
        
        for i in range(len(prompts) - 1):
            assert prompts[i] != prompts[i + 1]


class TestRoleManagerIntegration:
    """RoleManager 集成测试"""
    
    @pytest.fixture
    def setup_role_manager(self):
        """设置 RoleManager"""
        default_model = FullModelConfig(
            model=ModelConfig(
                provider="openai",
                name="default-model",
                api_key="test-api-key",
                base_url="https://api.test.com/v1",
                temperature=0.7,
                max_tokens=80000
            )
        )
        
        with patch('src.core.role_manager.RoleConfigLoader') as MockLoader:
            mock_loader = Mock()
            mock_loader.load_all.return_value = {
                '_default': RoleConfig(
                    name='_default',
                    description='默认角色',
                    system_prompt_file='prompts/roles/_default.txt',
                    model=RoleModelConfig(inherit=True),
                    execution=RoleExecutionConfig()
                ),
                'test-role': RoleConfig(
                    name='test-role',
                    description='测试角色',
                    system_prompt_file='prompts/roles/test_role.txt',
                    model=RoleModelConfig(
                        inherit=False,
                        provider="openai",
                        name="test-model",
                        temperature=0.5
                    ),
                    execution=RoleExecutionConfig(
                        max_context_tokens=60000
                    )
                )
            }
            mock_loader.get_role.side_effect = lambda name: mock_loader.load_all.return_value.get(name)
            mock_loader.list_roles.return_value = ['_default', 'test-role']
            MockLoader.return_value = mock_loader
            
            manager = RoleManager(
                roles_dir="config/roles",
                default_model_config=default_model
            )
        
        return manager
    
    def test_role_manager_initialization(self, setup_role_manager):
        """测试 RoleManager 初始化"""
        manager = setup_role_manager
        
        roles = manager.load_roles()
        
        assert roles is not None
        assert len(roles) >= 0
    
    def test_role_manager_get_current_role(self, setup_role_manager):
        """测试获取当前角色"""
        manager = setup_role_manager
        
        manager.load_roles()
        
        current_role = manager.get_current_role()
        
        assert current_role is not None
        assert current_role.name == '_default'
    
    def test_role_manager_switch_role(self, setup_role_manager):
        """测试切换角色"""
        manager = setup_role_manager
        
        manager.load_roles()
        
        new_role = manager.switch_role('test-role')
        
        assert new_role is not None
        assert new_role.name == 'test-role'
        
        current_role = manager.get_current_role()
        assert current_role.name == 'test-role'


class TestAgentPoolIntegration:
    """AgentPool 集成测试"""
    
    @pytest.mark.asyncio
    async def test_agent_pool_create_instance_with_role(self):
        """测试 AgentPool 创建带角色的实例"""
        from src.core.agent_pool import AgentPool
        
        config = create_test_config()
        
        with patch('src.core.agent_pool.AgentPool._create_skill_loader') as mock_skill_loader:
            mock_skill_loader.return_value = create_test_skill_loader()
            
            with patch('src.core.agent_pool.AgentPool._create_tool_registry') as mock_tool_registry:
                mock_tool_registry.return_value = create_test_tool_registry()
                
                pool = AgentPool(
                    config=config,
                    max_instances=5
                )
                
                await pool.initialize()
                
                instance = await pool.create_instance(
                    instance_id="test-instance",
                    role_name=None
                )
                
                assert instance is not None
                assert instance.agent is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
