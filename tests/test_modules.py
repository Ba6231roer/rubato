import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.models import ModelConfig, MCPConnectionConfig
from src.config.validators import validate_api_key, ConfigValidationError
from src.skills.parser import SkillParser
from src.skills.registry import SkillRegistry
from src.context.compressor import ContextCompressor
from src.context.manager import ContextManager


class TestModelConfig:
    """模型配置测试"""
    
    def test_valid_config(self):
        config = ModelConfig(
            provider="openai",
            name="gpt-4",
            api_key="test-key"
        )
        assert config.provider == "openai"
        assert config.name == "gpt-4"
        assert config.temperature == 0.7
    
    def test_invalid_temperature(self):
        with pytest.raises(ValueError):
            ModelConfig(
                provider="openai",
                name="gpt-4",
                api_key="test-key",
                temperature=1.5
            )
    
    def test_invalid_provider(self):
        with pytest.raises(ValueError):
            ModelConfig(
                provider="invalid",
                name="gpt-4",
                api_key="test-key"
            )


class TestMCPConnectionConfig:
    """MCP连接配置测试"""
    
    def test_valid_config(self):
        config = MCPConnectionConfig(
            retry_times=3,
            retry_delay=5,
            timeout=30
        )
        assert config.retry_times == 3
    
    def test_invalid_retry_times(self):
        with pytest.raises(ValueError):
            MCPConnectionConfig(retry_times=0)


class TestSkillParser:
    """Skill解析器测试"""
    
    def test_parse_yaml_header(self):
        content = """---
name: test-skill
description: Test skill
version: 1.0
---

# Content here
"""
        metadata, body = SkillParser.parse_content(content)
        assert metadata.name == "test-skill"
        assert metadata.description == "Test skill"
        assert "# Content here" in body
    
    def test_parse_no_header(self):
        content = "Just content without header"
        metadata, body = SkillParser.parse_content(content)
        assert metadata.name == ""
        assert body == content


class TestSkillRegistry:
    """Skill注册表测试"""
    
    def test_register_and_get(self):
        registry = SkillRegistry()
        from src.skills.parser import SkillMetadata
        
        metadata = SkillMetadata(
            name="test",
            description="Test skill",
            file_path="/test.md"
        )
        registry.register(metadata)
        
        assert registry.has_skill("test")
        assert registry.get_skill("test") == metadata
    
    def test_find_matching_skill(self):
        registry = SkillRegistry()
        from src.skills.parser import SkillMetadata
        
        metadata = SkillMetadata(
            name="test-skill",
            description="Test",
            triggers=["测试", "test"]
        )
        registry.register(metadata)
        
        assert registry.find_matching_skill("这是一个测试") == "test-skill"
        assert registry.find_matching_skill("no match") is None


class TestContextCompressor:
    """上下文压缩器测试"""
    
    def test_count_tokens(self):
        compressor = ContextCompressor()
        from langchain_core.messages import HumanMessage
        
        messages = [HumanMessage(content="Hello world")]
        count = compressor.count_tokens(messages)
        assert count > 0
    
    def test_needs_compression(self):
        compressor = ContextCompressor(max_tokens=10)
        from langchain_core.messages import HumanMessage
        
        short_messages = [HumanMessage(content="Hi")]
        assert not compressor.needs_compression(short_messages)
        
        long_messages = [HumanMessage(content="This is a very long message that should exceed the token limit")]
        assert compressor.needs_compression(long_messages)


class TestContextManager:
    """上下文管理器测试"""
    
    def test_add_messages(self):
        manager = ContextManager()
        manager.add_user_message("Hello")
        manager.add_ai_message("Hi there")
        
        messages = manager.get_messages()
        assert len(messages) == 2
    
    def test_clear(self):
        manager = ContextManager()
        manager.add_user_message("Hello")
        manager.clear()
        
        assert len(manager.get_messages()) == 0
    
    def test_loaded_skills(self):
        manager = ContextManager()
        manager.mark_skill_loaded("test-skill")
        
        assert manager.is_skill_loaded("test-skill")
        assert not manager.is_skill_loaded("other-skill")
