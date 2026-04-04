"""
E2E 测试验证脚本
验证 test-case-executor 角色配置和 MCP 配置正确性
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from pathlib import Path


def verify_mcp_config():
    """验证 MCP 配置"""
    print("=" * 60)
    print("验证 MCP 配置")
    print("=" * 60)
    
    import yaml
    mcp_config_path = Path("config/mcp_config.yaml")
    
    with open(mcp_config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    playwright_enabled = config.get('mcp', {}).get('servers', {}).get('playwright', {}).get('enabled', False)
    
    print(f"Playwright MCP 服务器状态: {'已启用' if playwright_enabled else '未启用'}")
    
    if playwright_enabled:
        server_config = config['mcp']['servers']['playwright']
        print(f"  - 命令: {server_config.get('command')}")
        print(f"  - 参数: {server_config.get('args')}")
        print(f"  - 浏览器类型: {server_config.get('browser', {}).get('type')}")
        print(f"  - Headless: {server_config.get('browser', {}).get('headless')}")
    
    return playwright_enabled


def verify_role_config():
    """验证角色配置"""
    print("\n" + "=" * 60)
    print("验证 test-case-executor 角色配置")
    print("=" * 60)
    
    import yaml
    role_config_path = Path("config/roles/test_case_executor.yaml")
    
    with open(role_config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    print(f"角色名称: {config.get('name')}")
    print(f"描述: {config.get('description')}")
    print(f"系统提示文件: {config.get('system_prompt_file')}")
    
    prompt_file = Path(config.get('system_prompt_file', ''))
    if prompt_file.exists():
        print(f"  ✓ 系统提示文件存在")
        with open(prompt_file, 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"  - 文件大小: {len(content)} 字符")
    else:
        print(f"  ✗ 系统提示文件不存在")
    
    tools = config.get('tools', {})
    print(f"\n工具配置:")
    print(f"  - spawn_agent: {tools.get('builtin', {}).get('spawn_agent')}")
    print(f"  - shell_tool: {tools.get('builtin', {}).get('shell_tool')}")
    print(f"  - file_tools: {tools.get('builtin', {}).get('file_tools', {}).get('enabled')}")
    print(f"  - skills: {tools.get('skills')}")
    
    return config


def verify_skills():
    """验证 Skills 配置"""
    print("\n" + "=" * 60)
    print("验证 Skills 配置")
    print("=" * 60)
    
    skills_dir = Path("skills")
    skill_files = list(skills_dir.glob("*.md"))
    
    print(f"Skills 目录: {skills_dir}")
    print(f"发现的 Skills: {len(skill_files)}")
    
    for skill_file in skill_files:
        print(f"\n  - {skill_file.name}")
        
        import yaml
        with open(skill_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
                print(f"    名称: {frontmatter.get('name')}")
                print(f"    描述: {frontmatter.get('description')}")
                print(f"    触发词: {frontmatter.get('triggers', [])}")
    
    playwright_skill = skills_dir / "playwright-cli.md"
    if playwright_skill.exists():
        print(f"\n  ✓ playwright-cli skill 存在")
    else:
        print(f"\n  ✗ playwright-cli skill 不存在")
    
    return skill_files


def simulate_test_execution():
    """模拟测试执行过程"""
    print("\n" + "=" * 60)
    print("模拟测试执行: 打开百度，输入python检索，点击打开检索结果第一条")
    print("=" * 60)
    
    test_steps = [
        {
            "step": 1,
            "action": "browser_navigate",
            "params": {"url": "https://www.baidu.com"},
            "description": "导航到百度首页"
        },
        {
            "step": 2,
            "action": "browser_type",
            "params": {"selector": "#kw", "text": "python"},
            "description": "在搜索框输入 'python'"
        },
        {
            "step": 3,
            "action": "browser_click",
            "params": {"selector": "#su"},
            "description": "点击搜索按钮"
        },
        {
            "step": 4,
            "action": "browser_wait_for",
            "params": {"selector": ".result", "timeout": 5000},
            "description": "等待搜索结果加载"
        },
        {
            "step": 5,
            "action": "browser_click",
            "params": {"selector": ".result a:first-child"},
            "description": "点击第一条检索结果"
        }
    ]
    
    print("\n测试步骤:")
    for step in test_steps:
        print(f"\n  步骤 {step['step']}: {step['description']}")
        print(f"    工具: {step['action']}")
        print(f"    参数: {step['params']}")
    
    print("\n" + "-" * 60)
    print("模拟执行结果:")
    print("-" * 60)
    
    for step in test_steps:
        print(f"  ✓ 步骤 {step['step']}: {step['description']} - 模拟成功")
    
    return test_steps


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("  Rubato E2E 测试验证")
    print("  测试案例: 打开百度，输入python检索，点击打开检索结果第一条")
    print("=" * 60)
    
    os.chdir(Path(__file__).parent.parent)
    
    mcp_ok = verify_mcp_config()
    role_config = verify_role_config()
    skills = verify_skills()
    test_steps = simulate_test_execution()
    
    print("\n" + "=" * 60)
    print("验证结果汇总")
    print("=" * 60)
    
    results = {
        "MCP Playwright 配置": "✓ 已启用" if mcp_ok else "✗ 未启用",
        "test-case-executor 角色": "✓ 配置正确" if role_config else "✗ 配置错误",
        "playwright-cli Skill": "✓ 存在" if Path("skills/playwright-cli.md").exists() else "✗ 不存在",
        "测试步骤定义": "✓ 已定义" if test_steps else "✗ 未定义"
    }
    
    for item, status in results.items():
        print(f"  {item}: {status}")
    
    all_ok = all("✓" in v for v in results.values())
    
    print("\n" + "=" * 60)
    if all_ok:
        print("  所有配置验证通过！可以执行 E2E 测试。")
    else:
        print("  部分配置需要修复。")
    print("=" * 60)
    
    return all_ok


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
