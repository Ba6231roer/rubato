import pytest
from src.skills.parser import SkillMetadata
from src.skills.registry import SkillRegistry


class TestSkillNameTrigger:
    def test_name_in_user_input_triggers_skill(self):
        registry = SkillRegistry()
        metadata = SkillMetadata(name="click-confirm-button", description="Click the confirm button on approval page")
        registry.register(metadata)
        result = registry.find_matching_skill("请使用 click-confirm-button 来点击确认按钮")
        assert result == "click-confirm-button"

    def test_name_in_test_case_document(self):
        registry = SkillRegistry()
        metadata = SkillMetadata(name="fill-approval-form", description="Fill the approval form")
        registry.register(metadata)
        case_content = """# 测试案例：业务审批

## 测试步骤
1. 打开审批页面
2. 填写审批表单

## 参考skill
- fill-approval-form
"""
        result = registry.find_matching_skill(case_content)
        assert result == "fill-approval-form"

    def test_trigger_takes_priority_over_name(self):
        registry = SkillRegistry()
        meta1 = SkillMetadata(name="skill-a", description="A", triggers=["特殊触发词"])
        meta2 = SkillMetadata(name="特殊触发词", description="B")
        registry.register(meta1)
        registry.register(meta2)
        result = registry.find_matching_skill("请使用特殊触发词操作")
        assert result == "skill-a"

    def test_no_match_returns_none(self):
        registry = SkillRegistry()
        metadata = SkillMetadata(name="some-skill", description="Some skill")
        registry.register(metadata)
        result = registry.find_matching_skill("这段文字不包含任何skill引用")
        assert result is None

    def test_multiple_names_match_first_registered(self):
        registry = SkillRegistry()
        meta1 = SkillMetadata(name="skill-alpha", description="Alpha")
        meta2 = SkillMetadata(name="skill-beta", description="Beta")
        registry.register(meta1)
        registry.register(meta2)
        result = registry.find_matching_skill("使用 skill-alpha 和 skill-beta")
        assert result == "skill-alpha"
