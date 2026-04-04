"""测试 SkillManager 功能"""
import asyncio
import tempfile
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.skills import SkillManager, ConditionalSkill, SkillMetadata


def test_conditional_skill_matches():
    """测试 ConditionalSkill 路径匹配"""
    skill = SkillMetadata(
        name="test-skill",
        description="Test skill",
        paths=["requirements/**/*.md", "docs/**/*.md"]
    )
    
    conditional = ConditionalSkill(
        skill=skill,
        path_patterns=skill.paths
    )
    
    cwd = os.getcwd()
    
    assert conditional.matches("requirements/test.md", cwd) == True
    assert conditional.matches("requirements/subdir/test.md", cwd) == True
    assert conditional.matches("docs/guide.md", cwd) == True
    assert conditional.matches("src/main.py", cwd) == False
    assert conditional.matches("README.md", cwd) == False
    
    print("[PASS] ConditionalSkill 路径匹配测试通过")


async def test_skill_manager_load():
    """测试 SkillManager 加载功能"""
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        skills_dir.mkdir()
        
        skill_content = """---
name: test-skill
description: Test skill for manager
triggers:
  - "测试"
tools:
  - file_read
paths:
  - "requirements/**/*.md"
---

# Test Skill Content

This is a test skill.
"""
        
        skill_file = skills_dir / "test-skill.md"
        skill_file.write_text(skill_content, encoding='utf-8')
        
        unconditional_skill_content = """---
name: unconditional-skill
description: Unconditional skill
triggers:
  - "无条件"
tools:
  - file_read
---

# Unconditional Skill

This skill has no path conditions.
"""
        
        unconditional_file = skills_dir / "unconditional-skill.md"
        unconditional_file.write_text(unconditional_skill_content, encoding='utf-8')
        
        manager = SkillManager(
            skills_dir=str(skills_dir),
            cwd=tmpdir
        )
        
        skills = await manager.load_skills()
        
        assert len(skills) == 1
        assert skills[0].name == "unconditional-skill"
        
        assert manager.get_conditional_skills_count() == 1
        
        print("[PASS] SkillManager 加载测试通过")
        
        return manager, tmpdir


async def test_skill_manager_activate():
    """测试 SkillManager 条件激活功能"""
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        skills_dir.mkdir()
        
        skill_content = """---
name: conditional-skill
description: Conditional skill
triggers:
  - "条件"
paths:
  - "requirements/**/*.md"
  - "docs/**/*.md"
---

# Conditional Skill

This skill activates for specific paths.
"""
        
        skill_file = skills_dir / "conditional-skill.md"
        skill_file.write_text(skill_content, encoding='utf-8')
        
        manager = SkillManager(
            skills_dir=str(skills_dir),
            cwd=tmpdir
        )
        
        await manager.load_skills()
        
        assert manager.get_conditional_skills_count() == 1
        assert manager.get_dynamic_skills_count() == 0
        
        req_dir = Path(tmpdir) / "requirements"
        req_dir.mkdir()
        test_file = req_dir / "test.md"
        test_file.write_text("# Test", encoding='utf-8')
        
        activated = manager.activate_for_paths([str(test_file)])
        
        assert len(activated) == 1
        assert activated[0] == "conditional-skill"
        assert manager.get_conditional_skills_count() == 0
        assert manager.get_dynamic_skills_count() == 1
        
        print("[PASS] SkillManager 条件激活测试通过")


async def test_skill_manager_discover():
    """测试 SkillManager 动态发现功能"""
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        skills_dir.mkdir()
        
        manager = SkillManager(
            skills_dir=str(skills_dir),
            cwd=tmpdir
        )
        
        nested_dir = Path(tmpdir) / "project" / ".skills"
        nested_dir.mkdir(parents=True)
        
        nested_skill_content = """---
name: nested-skill
description: Nested skill
triggers:
  - "嵌套"
---

# Nested Skill

This is a nested skill.
"""
        
        nested_skill_file = nested_dir / "nested-skill.md"
        nested_skill_file.write_text(nested_skill_content, encoding='utf-8')
        
        project_file = Path(tmpdir) / "project" / "README.md"
        project_file.parent.mkdir(parents=True, exist_ok=True)
        project_file.write_text("# Project", encoding='utf-8')
        
        discovered = manager.discover_for_paths([str(project_file)])
        
        assert len(discovered) == 1
        assert discovered[0] == "nested-skill"
        assert manager.get_dynamic_skills_count() == 1
        
        print("[PASS] SkillManager 动态发现测试通过")


async def main():
    """运行所有测试"""
    print("=" * 50)
    print("开始测试 SkillManager")
    print("=" * 50)
    
    test_conditional_skill_matches()
    
    await test_skill_manager_load()
    
    await test_skill_manager_activate()
    
    await test_skill_manager_discover()
    
    print("=" * 50)
    print("所有测试通过！")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
