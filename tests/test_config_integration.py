import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.loader import ConfigLoader
from src.config.models import AppConfig

def test_config_loading():
    print("=" * 60)
    print("测试配置加载功能")
    print("=" * 60)
    
    try:
        loader = ConfigLoader(config_dir="config")
        config = loader.load_all()
        
        print("\n✓ 配置加载成功！\n")
        
        print("-" * 60)
        print("1. 项目配置
        print("-" * 60)
        if config.project:
            print(f"  项目名称: {config.project.name}")
            print(f"  项目根目录: {config.project.root}")
            print(f"  主工作区: {config.project.workspace.main}")
            print(f"  额外工作区: {config.project.workspace.additional}")
            print(f"  排除路径: {config.project.workspace.excluded}")
        else:
            print("  未加载项目配置")
        
        print("\n" + "-" * 60)
        print("2. 文件工具配置
        print("-" * 60)
        if config.file_tools:
            print(f"  启用状态: {config.file_tools.enabled}")
            print(f"  权限模式: {config.file_tools.permission_mode}")
            print(f"  默认权限: {config.file_tools.default_permissions}")
            print(f"  自定义权限: {config.file_tools.custom_permissions}")
            print(f"  审计日志: {config.file_tools.audit}")
        else:
            print("  未加载文件工具配置")
        
        print("\n" + "-" * 60)
        print("3. 其他配置:")
        print("-" * 60)
        print(f"  模型配置: {config.model.model.name} ({config.model.model.provider})")
        print(f"  MCP 配置: {'已加载' if config.mcp else '未加载'}")
        print(f"  提示词配置: {config.prompts.system_prompt_file}")
        print(f"  Skills 配置: {config.skills.directory}")
        print(f"  Agent 配置: max_context_tokens={config.agent.max_context_tokens}")
        
        print("\n" + "=" * 60)
        print("✓ 所有配置加载测试通过！")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n✗ 配置加载失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_env_var_replacement():
    print("\n" + "=" * 60)
    print("测试环境变量替换功能")
    print("=" * 60)
    
    try:
        loader = ConfigLoader(config_dir="config")
        
        test_cases = [
            ("${PROJECT_ROOT}", "项目根目录"),
            ("${HOME}", "用户主目录"),
            ("${CONFIG_DIR}", "配置目录"),
        ]
        
        for test_str, description in test_cases:
            result = loader._replace_env_vars(test_str)
            print(f"\n  {description}:")
            print(f"    输入: {test_str}")
            print(f"    输出: {result}")
        
        print("\n✓ 环境变量替换测试通过！")
        return True
        
    except Exception as e:
        print(f"\n✗ 环境变量替换测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success1 = test_config_loading()
    success2 = test_env_var_replacement()
    
    if success1 and success2:
        print("\n" + "=" * 60)
        print("✓✓✓ 所有测试通过！✓✓✓")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("✗✗✗ 部分测试失败！✗✗✗")
        print("=" * 60)
        sys.exit(1)
