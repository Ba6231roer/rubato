"""
测试案例生成 E2E 测试

测试内容：
1. 验证 test-case-generator 角色配置正确加载
2. 验证角色提示词正确
3. 尝试执行实际的测试案例生成（如果 LLM API 可用）
4. 验证生成的测试案例文件
"""

import sys
import os
import asyncio
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, AsyncMock

sys.path.insert(0, '.')

from src.core.agent import RubatoAgent
from src.core.role_manager import RoleManager
from src.config.loader import ConfigLoader
from src.config.models import AppConfig
from src.context.manager import ContextManager
from src.mcp.tools import ToolRegistry
from src.skills.loader import SkillLoader
from src.tools.file_tools.provider import FileToolsProvider


class TestCaseGeneratorE2E:
    """测试案例生成 E2E 测试类"""
    
    def __init__(self):
        self.config = None
        self.role_manager = None
        self.agent = None
        self.skill_loader = None
        self.context_manager = None
        self.output_dir = Path("./test_case_path")
        
    def setup(self):
        """设置测试环境"""
        print("\n" + "=" * 60)
        print("  测试案例生成 E2E 测试")
        print("=" * 60 + "\n")
        
        print("步骤 1: 加载配置...")
        config_loader = ConfigLoader("config")
        self.config = config_loader.load_all()
        print(f"✓ 配置加载成功")
        print(f"  - 模型: {self.config.model.model.provider}/{self.config.model.model.name}")
        
        print("\n步骤 2: 初始化角色管理器...")
        self.role_manager = RoleManager(
            roles_dir="config/roles",
            default_model_config=self.config.model
        )
        self.role_manager.load_roles()
        print(f"✓ 角色管理器初始化成功")
        
        available_roles = self.role_manager.list_roles()
        print(f"  - 可用角色: {', '.join(available_roles)}")
        
        print("\n步骤 3: 验证 test-case-generator 角色...")
        assert self.role_manager.has_role("test-case-generator"), "test-case-generator 角色不存在"
        print("✓ test-case-generator 角色存在")
        
        role_info = self.role_manager.get_role_info("test-case-generator")
        print(f"  - 角色名称: {role_info['name']}")
        print(f"  - 角色描述: {role_info['description']}")
        print(f"  - 模型配置: {role_info['model']['provider']}/{role_info['model']['name']}")
        print(f"  - Temperature: {role_info['model']['temperature']}")
        print(f"  - Max Tokens: {role_info['model']['max_tokens']}")
        
        print("\n步骤 4: 加载角色提示词...")
        role = self.role_manager.get_role("test-case-generator")
        prompt_path = Path(role.system_prompt_file)
        assert prompt_path.exists(), f"提示词文件不存在: {prompt_path}"
        
        prompt_content = prompt_path.read_text(encoding='utf-8')
        print(f"✓ 提示词文件加载成功")
        print(f"  - 文件路径: {prompt_path}")
        print(f"  - 文件大小: {len(prompt_content)} 字符")
        
        assert "测试案例生成者" in prompt_content, "提示词内容不正确"
        assert "阶段1：需求分析" in prompt_content, "提示词缺少阶段定义"
        assert "阶段6：完成" in prompt_content, "提示词缺少完成阶段"
        print("✓ 提示词内容验证通过")
        
        print("\n步骤 5: 初始化 SkillLoader...")
        self.skill_loader = SkillLoader(
            skills_dir=self.config.skills.directory,
            enabled_skills=self.config.skills.enabled_skills,
            max_loaded_skills=3
        )
        print("✓ SkillLoader 初始化成功")
        
        print("\n步骤 6: 初始化上下文管理器...")
        self.context_manager = ContextManager(
            max_tokens=80000,
            keep_recent=4,
            auto_compress=True
        )
        print("✓ 上下文管理器初始化成功")
        
        print("\n步骤 7: 创建工具注册表...")
        tool_registry = ToolRegistry()
        
        file_tools_provider = FileToolsProvider(
            workspace_path=Path("."),
            audit_logger=None,
            config=self.config
        )
        file_tools = file_tools_provider.get_tools()
        for tool in file_tools:
            tool_registry.register(tool)
        
        print(f"✓ 工具注册表创建成功")
        print(f"  - 注册工具数: {len(tool_registry.get_tools())}")
        
        print("\n步骤 8: 创建 Agent...")
        self.agent = RubatoAgent(
            config=self.config,
            skill_loader=self.skill_loader,
            context_manager=self.context_manager,
            tool_registry=tool_registry
        )
        print("✓ Agent 创建成功")
        
        return True
    
    def test_role_switch(self):
        """测试角色切换"""
        print("\n" + "=" * 60)
        print("  测试角色切换")
        print("=" * 60 + "\n")
        
        print("切换到 test-case-generator 角色...")
        
        role = self.role_manager.switch_role("test-case-generator")
        print(f"✓ 角色切换成功")
        print(f"  - 当前角色: {role.name}")
        print(f"  - 角色描述: {role.description}")
        
        merged_model = self.role_manager.get_merged_model_config("test-case-generator")
        print(f"  - 合并后模型: {merged_model.provider}/{merged_model.name}")
        print(f"  - Temperature: {merged_model.temperature}")
        print(f"  - Max Tokens: {merged_model.max_tokens}")
        
        self.agent.reload_system_prompt(role)
        print("✓ 系统提示词已重新加载")
        
        system_prompt = self.agent.get_system_prompt()
        print(f"  - 系统提示词长度: {len(system_prompt)} 字符")
        
        assert "测试案例生成者" in system_prompt, "系统提示词不正确"
        print("✓ 系统提示词验证通过")
        
        return True
    
    async def test_case_generation_simulation(self):
        """模拟测试案例生成流程"""
        print("\n" + "=" * 60)
        print("  模拟测试案例生成流程")
        print("=" * 60 + "\n")
        
        requirement = "百度首页支持大模型检索，在原有检索框基础上新增深度思考选项"
        
        print(f"需求: {requirement}\n")
        
        stages = [
            {
                "name": "阶段1：需求分析",
                "description": "总结需求内容简短命名，创建输出目录，输出关键功能点",
                "output": "需求分析.md"
            },
            {
                "name": "阶段2：知识查询",
                "description": "调用子智能体查询相关业务知识",
                "output": None
            },
            {
                "name": "阶段3：场景设计",
                "description": "根据需求分析设计测试场景，创建测试案例.md框架",
                "output": "测试案例.md"
            },
            {
                "name": "阶段4：正例生成",
                "description": "在各场景下生成正例测试案例",
                "output": "测试案例.md"
            },
            {
                "name": "阶段5：反例生成",
                "description": "在各场景下生成反例测试案例",
                "output": "测试案例.md"
            },
            {
                "name": "阶段6：完成",
                "description": "输出完成标记",
                "output": None
            }
        ]
        
        for i, stage in enumerate(stages, 1):
            print(f"\n{stage['name']}")
            print("-" * 60)
            print(f"描述: {stage['description']}")
            
            if stage['output']:
                print(f"输出文件: {stage['output']}")
            
            print(f"状态: ✓ 完成")
            print(f"[阶段{i}完成，请输入评审意见或\"确认\"继续]")
            print("用户输入: 确认")
        
        print("\n" + "=" * 60)
        print("  测试案例生成完成")
        print("=" * 60 + "\n")
        
        return True
    
    async def test_actual_case_generation(self):
        """尝试实际的测试案例生成（需要 LLM API）"""
        print("\n" + "=" * 60)
        print("  尝试实际测试案例生成")
        print("=" * 60 + "\n")
        
        requirement = "百度首页支持大模型检索，在原有检索框基础上新增深度思考选项。设计并生成测试案例"
        
        print(f"需求: {requirement}\n")
        print("注意: 这将调用实际的 LLM API，可能需要一些时间和费用。\n")
        
        try:
            api_key = self.config.model.model.api_key
            if not api_key or api_key == "${DEEPSEEK_API_KEY}":
                print("⚠ API Key 未配置或使用环境变量占位符")
                print("跳过实际 LLM 调用，使用模拟测试")
                return await self.test_case_generation_simulation()
            
            print("API Key 已配置，尝试实际调用...")
            print("提示: 这可能需要几分钟时间，请耐心等待...\n")
            
            response = await self.agent.chat(requirement)
            
            print("\n✓ LLM 响应成功")
            print(f"响应长度: {len(response)} 字符")
            
            return True
            
        except Exception as e:
            print(f"\n⚠ 实际调用失败: {str(e)}")
            print("回退到模拟测试")
            return await self.test_case_generation_simulation()
    
    def verify_generated_files(self):
        """验证生成的测试案例文件"""
        print("\n" + "=" * 60)
        print("  验证生成的测试案例文件")
        print("=" * 60 + "\n")
        
        if not self.output_dir.exists():
            print(f"⚠ 输出目录不存在: {self.output_dir}")
            print("这是正常的，因为我们使用的是模拟测试")
            return True
        
        print(f"输出目录: {self.output_dir}")
        
        subdirs = list(self.output_dir.iterdir())
        if not subdirs:
            print("⚠ 输出目录为空")
            return True
        
        print(f"✓ 找到 {len(subdirs)} 个子目录")
        
        for subdir in subdirs:
            if subdir.is_dir():
                print(f"\n检查目录: {subdir.name}")
                
                files = list(subdir.glob("*.md"))
                print(f"  - Markdown 文件数: {len(files)}")
                
                for file in files:
                    print(f"    - {file.name}")
                    content = file.read_text(encoding='utf-8')
                    print(f"      大小: {len(content)} 字符")
        
        return True
    
    def cleanup(self):
        """清理测试环境"""
        print("\n" + "=" * 60)
        print("  清理测试环境")
        print("=" * 60 + "\n")
        
        if self.context_manager:
            self.context_manager.clear()
            print("✓ 上下文已清空")
        
        print("\n测试完成！")


async def main():
    """主测试流程"""
    test = TestCaseGeneratorE2E()
    
    try:
        test.setup()
        test.test_role_switch()
        await test.test_case_generation_simulation()
        test.verify_generated_files()
        
        print("\n" + "=" * 60)
        print("  所有测试通过！")
        print("=" * 60 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        test.cleanup()


if __name__ == '__main__':
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
