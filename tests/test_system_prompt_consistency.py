"""测试系统提示词属性一致性"""

import sys
sys.path.insert(0, '.')

from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

from src.core.agent import RubatoAgent
from src.config.models import (
    AppConfig, FullModelConfig, ModelConfig, MCPConfig, 
    PromptConfig, SkillsConfig, AgentConfig, AgentExecutionConfig,
    ProjectConfig, FileToolsConfig, UnifiedToolsConfig, RoleConfig,
    WorkspaceConfig
)
from src.context.manager import ContextManager
from src.mcp.tools import ToolRegistry
from src.skills.loader import SkillLoader


def create_mock_config() -> AppConfig:
    """创建模拟的配置对象"""
    return AppConfig(
        model=FullModelConfig(
            model=ModelConfig(
                provider="openai",
                name="test-model",
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


def create_mock_skill_loader() -> SkillLoader:
    """创建模拟的 SkillLoader"""
    skill_loader = Mock(spec=SkillLoader)
    skill_loader.has_skill = Mock(return_value=False)
    skill_loader.load_full_skill = Mock(return_value=None)
    return skill_loader


def create_mock_tool_registry() -> ToolRegistry:
    """创建模拟的 ToolRegistry"""
    tool_registry = ToolRegistry()
    return tool_registry


def create_mock_context_manager() -> ContextManager:
    """创建模拟的 ContextManager"""
    return ContextManager(max_tokens=80000, auto_compress=False)


def test_get_system_prompt_consistency():
    """测试 1: get_system_prompt() 和 get_current_system_prompt() 返回值一致性"""
    print("=" * 50)
    print("测试 1: get_system_prompt() 和 get_current_system_prompt() 返回值一致性")
    print("=" * 50)
    
    config = create_mock_config()
    skill_loader = create_mock_skill_loader()
    context_manager = create_mock_context_manager()
    tool_registry = create_mock_tool_registry()
    
    with patch.object(Path, 'exists', return_value=False):
        agent = RubatoAgent(
            config=config,
            skill_loader=skill_loader,
            context_manager=context_manager,
            tool_registry=tool_registry
        )
    
    prompt1 = agent.get_system_prompt()
    prompt2 = agent.get_current_system_prompt()
    
    print(f"[OK] get_system_prompt() 返回值长度: {len(prompt1)} 字符")
    print(f"[OK] get_current_system_prompt() 返回值长度: {len(prompt2)} 字符")
    print(f"[OK] 两个方法返回值是否相同: {prompt1 == prompt2}")
    
    assert prompt1 == prompt2, "get_system_prompt() 和 get_current_system_prompt() 应该返回相同的值"
    print("[OK] 测试通过：两个方法返回值一致\n")


def test_reload_system_prompt():
    """测试 2: 角色切换后系统提示词更新"""
    print("=" * 50)
    print("测试 2: 角色切换后系统提示词更新")
    print("=" * 50)
    
    config = create_mock_config()
    skill_loader = create_mock_skill_loader()
    context_manager = create_mock_context_manager()
    tool_registry = create_mock_tool_registry()
    
    with patch.object(Path, 'exists', return_value=False):
        agent = RubatoAgent(
            config=config,
            skill_loader=skill_loader,
            context_manager=context_manager,
            tool_registry=tool_registry
        )
    
    original_prompt = agent.get_system_prompt()
    print(f"[OK] 原始系统提示词长度: {len(original_prompt)} 字符")
    
    new_role_config = RoleConfig(
        name='test-role',
        description='测试角色',
        system_prompt_file='prompts/test_role.txt'
    )
    
    with patch.object(Path, 'exists', return_value=False):
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = Mock()
            mock_open.return_value.read.return_value = "这是测试角色的系统提示词"
            
            agent.reload_system_prompt(role_config=new_role_config)
    
    new_prompt1 = agent.get_system_prompt()
    new_prompt2 = agent.get_current_system_prompt()
    
    print(f"[OK] 切换角色后 get_system_prompt() 长度: {len(new_prompt1)} 字符")
    print(f"[OK] 切换角色后 get_current_system_prompt() 长度: {len(new_prompt2)} 字符")
    print(f"[OK] 两个方法返回值是否相同: {new_prompt1 == new_prompt2}")
    print(f"[OK] 系统提示词是否已更新: {new_prompt1 != original_prompt}")
    
    assert new_prompt1 == new_prompt2, "切换角色后，两个方法应该返回相同的新提示词"
    assert new_prompt1 != original_prompt, "切换角色后，系统提示词应该更新"
    print("[OK] 测试通过：角色切换后系统提示词正确更新\n")


def test_update_role_skills():
    """测试 3: update_role_skills() 方法"""
    print("=" * 50)
    print("测试 3: update_role_skills() 方法")
    print("=" * 50)
    
    config = create_mock_config()
    skill_loader = create_mock_skill_loader()
    context_manager = create_mock_context_manager()
    tool_registry = create_mock_tool_registry()
    
    with patch.object(Path, 'exists', return_value=False):
        agent = RubatoAgent(
            config=config,
            skill_loader=skill_loader,
            context_manager=context_manager,
            tool_registry=tool_registry
        )
    
    original_prompt = agent.get_system_prompt()
    print(f"[OK] 原始系统提示词长度: {len(original_prompt)} 字符")
    
    agent.update_role_skills(skills=["test_skill_1", "test_skill_2"])
    
    updated_prompt1 = agent.get_system_prompt()
    updated_prompt2 = agent.get_current_system_prompt()
    
    print(f"[OK] 更新 skills 后 get_system_prompt() 长度: {len(updated_prompt1)} 字符")
    print(f"[OK] 更新 skills 后 get_current_system_prompt() 长度: {len(updated_prompt2)} 字符")
    print(f"[OK] 两个方法返回值是否相同: {updated_prompt1 == updated_prompt2}")
    
    assert updated_prompt1 == updated_prompt2, "更新 skills 后，两个方法应该返回相同的提示词"
    print("[OK] 测试通过：update_role_skills() 方法正确工作\n")


def test_initialization_consistency():
    """测试 4: 初始化时属性一致性"""
    print("=" * 50)
    print("测试 4: 初始化时属性一致性")
    print("=" * 50)
    
    config = create_mock_config()
    skill_loader = create_mock_skill_loader()
    context_manager = create_mock_context_manager()
    tool_registry = create_mock_tool_registry()
    
    with patch.object(Path, 'exists', return_value=False):
        agent = RubatoAgent(
            config=config,
            skill_loader=skill_loader,
            context_manager=context_manager,
            tool_registry=tool_registry
        )
    
    system_prompt_attr = agent.system_prompt
    current_system_prompt_attr = agent._current_system_prompt
    
    print(f"[OK] system_prompt 属性长度: {len(system_prompt_attr)} 字符")
    print(f"[OK] _current_system_prompt 属性长度: {len(current_system_prompt_attr)} 字符")
    print(f"[OK] 两个属性值是否相同: {system_prompt_attr == current_system_prompt_attr}")
    
    assert system_prompt_attr == current_system_prompt_attr, "初始化时，system_prompt 和 _current_system_prompt 应该相同"
    print("[OK] 测试通过：初始化时属性一致\n")


def test_multiple_operations():
    """测试 5: 多次操作后的一致性"""
    print("=" * 50)
    print("测试 5: 多次操作后的一致性")
    print("=" * 50)
    
    config = create_mock_config()
    skill_loader = create_mock_skill_loader()
    context_manager = create_mock_context_manager()
    tool_registry = create_mock_tool_registry()
    
    with patch.object(Path, 'exists', return_value=False):
        agent = RubatoAgent(
            config=config,
            skill_loader=skill_loader,
            context_manager=context_manager,
            tool_registry=tool_registry
        )
    
    print("[OK] 执行多次操作测试...")
    
    for i in range(3):
        agent.update_role_skills(skills=[f"skill_{i}"])
        
        prompt1 = agent.get_system_prompt()
        prompt2 = agent.get_current_system_prompt()
        attr1 = agent.system_prompt
        attr2 = agent._current_system_prompt
        
        print(f"  第 {i+1} 次更新后:")
        print(f"    - get_system_prompt() == get_current_system_prompt(): {prompt1 == prompt2}")
        print(f"    - system_prompt == _current_system_prompt: {attr1 == attr2}")
        print(f"    - 所有值一致: {prompt1 == prompt2 == attr1 == attr2}")
        
        assert prompt1 == prompt2 == attr1 == attr2, f"第 {i+1} 次更新后，所有值应该保持一致"
    
    print("[OK] 测试通过：多次操作后属性保持一致\n")


if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("系统提示词属性一致性测试")
    print("=" * 50 + "\n")
    
    try:
        test_get_system_prompt_consistency()
        test_reload_system_prompt()
        test_update_role_skills()
        test_initialization_consistency()
        test_multiple_operations()
        
        print("=" * 50)
        print("所有测试通过! [OK]")
        print("=" * 50)
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
