"""测试角色配置系统"""

import sys
sys.path.insert(0, '.')

from src.config.models import RoleConfig, RoleModelConfig, RoleExecutionConfig, FullModelConfig, ModelConfig
from src.config.role_loader import RoleConfigLoader
from src.core.role_manager import RoleManager

def test_role_models():
    print("=" * 50)
    print("测试 1: 角色配置模型")
    print("=" * 50)
    
    role = RoleConfig(
        name='test-case-executor',
        description='测试案例执行者',
        system_prompt_file='prompts/roles/test_case_executor.txt',
        model=RoleModelConfig(inherit=True),
        execution=RoleExecutionConfig(max_context_tokens=80000, timeout=300),
        available_tools=['shell_tool', 'spawn_agent']
    )
    
    print(f"✓ RoleConfig 创建成功")
    print(f"  - 名称: {role.name}")
    print(f"  - 描述: {role.description}")
    print(f"  - 模型继承: {role.model.inherit}")
    print(f"  - 可用工具: {role.available_tools}")
    print()

def test_role_loader():
    print("=" * 50)
    print("测试 2: 角色配置加载器")
    print("=" * 50)
    
    loader = RoleConfigLoader(roles_dir="config/roles")
    roles = loader.load_all()
    
    print(f"✓ 加载了 {len(roles)} 个角色")
    for name, role in roles.items():
        print(f"  - {name}: {role.description}")
    
    role = loader.get_role('test-case-executor')
    if role:
        print(f"✓ 获取角色 'test-case-executor' 成功")
        print(f"  - 可用工具: {role.available_tools}")
    
    role_names = loader.list_roles()
    print(f"✓ 角色列表: {role_names}")
    print()

def test_role_manager():
    print("=" * 50)
    print("测试 3: 角色管理器")
    print("=" * 50)
    
    default_model = FullModelConfig(
        model=ModelConfig(
            provider="openai",
            name="deepseek-chat",
            api_key="test-key",
            base_url="https://api.deepseek.com/v1",
            temperature=0.7,
            max_tokens=80000
        )
    )
    
    manager = RoleManager(
        roles_dir="config/roles",
        default_model_config=default_model
    )
    
    roles = manager.load_roles()
    print(f"✓ 加载了 {len(roles)} 个角色")
    
    role_info = manager.get_role_info('test-case-executor')
    if role_info:
        print(f"✓ 获取角色信息成功:")
        print(f"  - 名称: {role_info['name']}")
        print(f"  - 描述: {role_info['description']}")
        print(f"  - 模型: {role_info['model']['provider']}/{role_info['model']['name']}")
        print(f"  - 最大上下文: {role_info['execution']['max_context_tokens']}")
    
    current = manager.switch_role('test-case-executor')
    print(f"✓ 切换到角色: {current.name}")
    
    current_role = manager.get_current_role()
    if current_role:
        print(f"✓ 当前角色: {current_role.name}")
    
    merged_config = manager.get_merged_model_config('test-case-executor')
    if merged_config:
        print(f"✓ 合并后的模型配置:")
        print(f"  - Provider: {merged_config.provider}")
        print(f"  - Model: {merged_config.name}")
        print(f"  - Temperature: {merged_config.temperature}")
    
    tools = manager.get_available_tools()
    print(f"✓ 可用工具: {tools}")
    print()

def test_system_prompt_loading():
    print("=" * 50)
    print("测试 4: 系统提示词加载")
    print("=" * 50)
    
    loader = RoleConfigLoader(roles_dir="config/roles")
    loader.load_all()
    
    role = loader.get_role('test-case-executor')
    if role:
        prompt = loader.load_system_prompt(role)
        print(f"✓ 系统提示词加载成功")
        print(f"  - 长度: {len(prompt)} 字符")
        print(f"  - 前100字符: {prompt[:100]}...")
    print()

def test_validation():
    print("=" * 50)
    print("测试 5: 验证功能")
    print("=" * 50)
    
    try:
        invalid_role = RoleConfig(
            name='',
            description='测试',
            system_prompt_file='test.txt'
        )
    except Exception as e:
        print(f"✓ 空名称验证成功: {str(e)[:50]}...")
    
    try:
        invalid_role = RoleConfig(
            name='invalid name!',
            description='测试',
            system_prompt_file='test.txt'
        )
    except Exception as e:
        print(f"✓ 无效名称验证成功: {str(e)[:50]}...")
    
    try:
        invalid_temp = RoleModelConfig(temperature=2.0)
    except Exception as e:
        print(f"✓ 温度范围验证成功: {str(e)[:50]}...")
    
    print()

if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("角色配置系统测试")
    print("=" * 50 + "\n")
    
    try:
        test_role_models()
        test_role_loader()
        test_role_manager()
        test_system_prompt_loading()
        test_validation()
        
        print("=" * 50)
        print("所有测试通过! ✓")
        print("=" * 50)
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
