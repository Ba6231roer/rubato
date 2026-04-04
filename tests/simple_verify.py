"""
简单的测试案例生成验证脚本
"""

import sys
from pathlib import Path

sys.path.insert(0, '.')

def verify_role_config():
    """验证角色配置"""
    print("\n" + "=" * 60)
    print("  验证 test-case-generator 角色配置")
    print("=" * 60 + "\n")
    
    from src.core.role_manager import RoleManager
    from src.config.loader import ConfigLoader
    
    print("步骤 1: 加载配置...")
    config_loader = ConfigLoader("config")
    config = config_loader.load_all()
    print(f"[OK] 配置加载成功")
    print(f"  - 模型: {config.model.model.provider}/{config.model.model.name}")
    
    print("\n步骤 2: 初始化角色管理器...")
    role_manager = RoleManager(
        roles_dir="config/roles",
        default_model_config=config.model
    )
    role_manager.load_roles()
    print(f"[OK] 角色管理器初始化成功")
    
    print("\n步骤 3: 验证 test-case-generator 角色...")
    available_roles = role_manager.list_roles()
    print(f"  - 可用角色: {', '.join(available_roles)}")
    
    assert role_manager.has_role("test-case-generator"), "test-case-generator 角色不存在"
    print("[OK] test-case-generator 角色存在")
    
    print("\n步骤 4: 获取角色详细信息...")
    role_info = role_manager.get_role_info("test-case-generator")
    print(f"  - 角色名称: {role_info['name']}")
    print(f"  - 角色描述: {role_info['description']}")
    print(f"  - 模型配置: {role_info['model']['provider']}/{role_info['model']['name']}")
    print(f"  - Temperature: {role_info['model']['temperature']}")
    print(f"  - Max Tokens: {role_info['model']['max_tokens']}")
    print(f"  - 继承默认配置: {'是' if role_info['model']['inherit'] else '否'}")
    
    print("\n步骤 5: 验证角色提示词文件...")
    role = role_manager.get_role("test-case-generator")
    prompt_path = Path(role.system_prompt_file)
    
    if not prompt_path.exists():
        print(f"[ERROR] 提示词文件不存在: {prompt_path}")
        return False
    
    print(f"[OK] 提示词文件存在: {prompt_path}")
    
    prompt_content = prompt_path.read_text(encoding='utf-8')
    print(f"  - 文件大小: {len(prompt_content)} 字符")
    
    print("\n步骤 6: 验证提示词内容...")
    required_sections = [
        "测试案例生成者",
        "阶段1：需求分析",
        "阶段2：知识查询",
        "阶段3：场景设计",
        "阶段4：正例生成",
        "阶段5：反例生成",
        "阶段6：完成"
    ]
    
    all_found = True
    for section in required_sections:
        if section in prompt_content:
            print(f"  [OK] 包含: {section}")
        else:
            print(f"  [ERROR] 缺少: {section}")
            all_found = False
    
    if all_found:
        print("\n[OK] 提示词内容验证通过")
    else:
        print("\n[ERROR] 提示词内容验证失败")
        return False
    
    print("\n步骤 7: 验证工作流程定义...")
    workflow_keywords = [
        "每个阶段结束后必须输出阶段标记",
        "等待用户输入",
        "确认",
        "评审意见"
    ]
    
    workflow_found = True
    for keyword in workflow_keywords:
        if keyword in prompt_content:
            print(f"  [OK] 包含: {keyword}")
        else:
            print(f"  [ERROR] 缺少: {keyword}")
            workflow_found = False
    
    if workflow_found:
        print("\n[OK] 工作流程定义验证通过")
    else:
        print("\n[ERROR] 工作流程定义验证失败")
        return False
    
    print("\n步骤 8: 验证输出目录配置...")
    if "./test_case_path/" in prompt_content or "test_case_path" in prompt_content:
        print("  [OK] 输出目录配置正确")
    else:
        print("  [ERROR] 输出目录配置缺失")
        return False
    
    print("\n步骤 9: 验证测试案例格式定义...")
    format_keywords = [
        "前置条件",
        "测试步骤",
        "预期结果",
        "正例",
        "反例"
    ]
    
    format_found = True
    for keyword in format_keywords:
        if keyword in prompt_content:
            print(f"  [OK] 包含: {keyword}")
        else:
            print(f"  [ERROR] 缺少: {keyword}")
            format_found = False
    
    if format_found:
        print("\n[OK] 测试案例格式定义验证通过")
    else:
        print("\n[ERROR] 测试案例格式定义验证失败")
        return False
    
    print("\n" + "=" * 60)
    print("  所有验证通过！")
    print("=" * 60 + "\n")
    
    return True


def simulate_workflow():
    """模拟测试案例生成工作流程"""
    print("\n" + "=" * 60)
    print("  模拟测试案例生成工作流程")
    print("=" * 60 + "\n")
    
    requirement = "百度首页支持大模型检索，在原有检索框基础上新增深度思考选项"
    
    print(f"需求: {requirement}\n")
    
    stages = [
        {
            "name": "阶段1：需求分析",
            "description": "总结需求内容简短命名，创建输出目录，输出关键功能点",
            "output": "需求分析.md",
            "actions": [
                "总结需求内容简短命名: 百度大模型检索",
                "创建输出目录: ./test_case_path/百度大模型检索/",
                "输出关键功能点到 需求分析.md",
                "输出关键功能点列表"
            ]
        },
        {
            "name": "阶段2：知识查询",
            "description": "调用子智能体查询相关业务知识",
            "output": None,
            "actions": [
                "调用子智能体查询相关业务知识",
                "输出查询结果（如有）"
            ]
        },
        {
            "name": "阶段3：场景设计",
            "description": "根据需求分析设计测试场景，创建测试案例.md框架",
            "output": "测试案例.md",
            "actions": [
                "根据需求分析设计测试场景",
                "创建 测试案例.md，输出场景框架（仅一二三级标题）",
                "输出场景列表"
            ]
        },
        {
            "name": "阶段4：正例生成",
            "description": "在各场景下生成正例测试案例",
            "output": "测试案例.md",
            "actions": [
                "在 测试案例.md 的各场景下生成正例测试案例",
                "输出案例概览"
            ]
        },
        {
            "name": "阶段5：反例生成",
            "description": "在各场景下生成反例测试案例",
            "output": "测试案例.md",
            "actions": [
                "在 测试案例.md 的各场景下生成反例测试案例",
                "输出案例概览"
            ]
        },
        {
            "name": "阶段6：完成",
            "description": "输出完成标记",
            "output": None,
            "actions": [
                "输出完成标记"
            ]
        }
    ]
    
    for i, stage in enumerate(stages, 1):
        print(f"\n{stage['name']}")
        print("-" * 60)
        print(f"描述: {stage['description']}")
        
        if stage['output']:
            print(f"输出文件: {stage['output']}")
        
        print("\n执行动作:")
        for action in stage['actions']:
            print(f"  - {action}")
        
        print(f"\n状态: [OK] 完成")
        print(f"\n[阶段{i}完成，请输入评审意见或\"确认\"继续]")
        print("用户输入: 确认")
    
    print("\n" + "=" * 60)
    print("  测试案例生成完成")
    print("=" * 60)
    print("\n[测试案例生成完成，所有文件已保存到 ./test_case_path/百度大模型检索]")
    print()
    
    return True


def main():
    """主函数"""
    try:
        success = verify_role_config()
        
        if success:
            simulate_workflow()
            return 0
        else:
            return 1
            
    except Exception as e:
        print(f"\n[ERROR] 验证失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
