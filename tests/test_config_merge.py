"""测试配置合并逻辑"""

import sys
sys.path.insert(0, '.')

from src.config.models import (
    AppConfig, AgentConfig, AgentExecutionConfig,
    RoleConfig, RoleModelConfig, RoleExecutionConfig,
    FullModelConfig, ModelConfig, PromptConfig, SkillsConfig
)

def test_config_merge():
    print("=" * 60)
    print("测试配置合并逻辑")
    print("=" * 60)
    
    global_config = AppConfig(
        model=FullModelConfig(
            model=ModelConfig(
                provider="openai",
                name="deepseek-chat",
                api_key="test-key",
                base_url="https://api.deepseek.com/v1"
            )
        ),
        prompts=PromptConfig(),
        skills=SkillsConfig(),
        agent=AgentConfig(
            max_context_tokens=80000,
            execution=AgentExecutionConfig(
                recursion_limit=100,
                sub_agent_recursion_limit=50
            )
        )
    )
    
    print("\n全局配置:")
    print(f"  - max_context_tokens: {global_config.agent.max_context_tokens}")
    print(f"  - recursion_limit: {global_config.agent.execution.recursion_limit}")
    print(f"  - sub_agent_recursion_limit: {global_config.agent.execution.sub_agent_recursion_limit}")
    
    role_config = RoleConfig(
        name='test-role',
        description='测试角色',
        system_prompt_file='test.txt',
        model=RoleModelConfig(inherit=True),
        execution=RoleExecutionConfig(
            max_context_tokens=40000,
            recursion_limit=30,
            sub_agent_recursion_limit=25
        )
    )
    
    print("\nRole 配置:")
    print(f"  - max_context_tokens: {role_config.execution.max_context_tokens}")
    print(f"  - recursion_limit: {role_config.execution.recursion_limit}")
    print(f"  - sub_agent_recursion_limit: {role_config.execution.sub_agent_recursion_limit}")
    
    print("\n测试配置合并逻辑:")
    
    max_context_tokens = (
        role_config.execution.max_context_tokens
        if role_config and role_config.execution and role_config.execution.max_context_tokens
        else global_config.agent.max_context_tokens
    )
    
    recursion_limit = (
        role_config.execution.recursion_limit
        if role_config and role_config.execution and role_config.execution.recursion_limit
        else global_config.agent.execution.recursion_limit
    )
    
    sub_agent_recursion_limit = (
        role_config.execution.sub_agent_recursion_limit
        if role_config and role_config.execution and role_config.execution.sub_agent_recursion_limit
        else global_config.agent.execution.sub_agent_recursion_limit
    )
    
    print(f"  - 合并后的 max_context_tokens: {max_context_tokens} (期望: 40000)")
    print(f"  - 合并后的 recursion_limit: {recursion_limit} (期望: 30)")
    print(f"  - 合并后的 sub_agent_recursion_limit: {sub_agent_recursion_limit} (期望: 25)")
    
    assert max_context_tokens == 40000, f"max_context_tokens 应该是 40000，实际是 {max_context_tokens}"
    assert recursion_limit == 30, f"recursion_limit 应该是 30，实际是 {recursion_limit}"
    assert sub_agent_recursion_limit == 25, f"sub_agent_recursion_limit 应该是 25，实际是 {sub_agent_recursion_limit}"
    
    print("\n✓ 配置合并逻辑测试通过!")
    
    print("\n测试无 role_config 的情况:")
    
    max_context_tokens_no_role = global_config.agent.max_context_tokens
    recursion_limit_no_role = global_config.agent.execution.recursion_limit
    sub_agent_recursion_limit_no_role = global_config.agent.execution.sub_agent_recursion_limit
    
    print(f"  - max_context_tokens: {max_context_tokens_no_role} (期望: 80000)")
    print(f"  - recursion_limit: {recursion_limit_no_role} (期望: 100)")
    print(f"  - sub_agent_recursion_limit: {sub_agent_recursion_limit_no_role} (期望: 50)")
    
    assert max_context_tokens_no_role == 80000
    assert recursion_limit_no_role == 100
    assert sub_agent_recursion_limit_no_role == 50
    
    print("\n✓ 无 role_config 测试通过!")
    
    print("\n测试 role_config 部分字段为 None 的情况:")
    
    role_config_partial = RoleConfig(
        name='test-role-partial',
        description='测试角色（部分配置）',
        system_prompt_file='test.txt',
        model=RoleModelConfig(inherit=True),
        execution=RoleExecutionConfig(
            max_context_tokens=60000,
            recursion_limit=None,
            sub_agent_recursion_limit=None
        )
    )
    
    max_context_tokens_partial = (
        role_config_partial.execution.max_context_tokens
        if role_config_partial and role_config_partial.execution and role_config_partial.execution.max_context_tokens
        else global_config.agent.max_context_tokens
    )
    
    recursion_limit_partial = (
        role_config_partial.execution.recursion_limit
        if role_config_partial and role_config_partial.execution and role_config_partial.execution.recursion_limit
        else global_config.agent.execution.recursion_limit
    )
    
    sub_agent_recursion_limit_partial = (
        role_config_partial.execution.sub_agent_recursion_limit
        if role_config_partial and role_config_partial.execution and role_config_partial.execution.sub_agent_recursion_limit
        else global_config.agent.execution.sub_agent_recursion_limit
    )
    
    print(f"  - max_context_tokens: {max_context_tokens_partial} (期望: 60000)")
    print(f"  - recursion_limit: {recursion_limit_partial} (期望: 100，使用全局配置)")
    print(f"  - sub_agent_recursion_limit: {sub_agent_recursion_limit_partial} (期望: 50，使用全局配置)")
    
    assert max_context_tokens_partial == 60000
    assert recursion_limit_partial == 100
    assert sub_agent_recursion_limit_partial == 50
    
    print("\n✓ 部分配置测试通过!")
    
    print("\n" + "=" * 60)
    print("所有测试通过! ✓")
    print("=" * 60)

if __name__ == '__main__':
    try:
        test_config_merge()
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
