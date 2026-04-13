import pytest
from src.config.models import (
    ModelParameters,
    AgentExecutionConfig,
    FullModelConfig,
    ModelConfig,
)


class TestModelParameters:
    def test_default_values(self):
        params = ModelParameters()
        assert params.retry_max_count == 3
        assert params.retry_initial_delay == 10.0
        assert params.retry_max_delay == 60.0
        assert params.llm_timeout == 300.0

    def test_custom_values(self):
        params = ModelParameters(
            retry_max_count=5,
            retry_initial_delay=15.0,
            retry_max_delay=120.0,
            llm_timeout=600.0,
        )
        assert params.retry_max_count == 5
        assert params.retry_initial_delay == 15.0
        assert params.retry_max_delay == 120.0
        assert params.llm_timeout == 600.0

    def test_validation_positive(self):
        with pytest.raises(ValueError):
            ModelParameters(retry_max_count=0)
        with pytest.raises(ValueError):
            ModelParameters(retry_initial_delay=-1)
        with pytest.raises(ValueError):
            ModelParameters(retry_max_delay=0)
        with pytest.raises(ValueError):
            ModelParameters(llm_timeout=-1)

    def test_old_fields_removed(self):
        with pytest.raises(Exception):
            ModelParameters(retry_times=3)
        with pytest.raises(Exception):
            ModelParameters(retry_delay=1.0)
        with pytest.raises(Exception):
            ModelParameters(timeout=30.0)


class TestAgentExecutionConfig:
    def test_default_values(self):
        config = AgentExecutionConfig()
        assert config.recursion_limit == 100
        assert config.sub_agent_recursion_limit == 50
        assert config.llm_timeout == 300

    def test_custom_values(self):
        config = AgentExecutionConfig(
            recursion_limit=200,
            sub_agent_recursion_limit=100,
            llm_timeout=600,
        )
        assert config.recursion_limit == 200
        assert config.sub_agent_recursion_limit == 100
        assert config.llm_timeout == 600

    def test_validation_positive(self):
        with pytest.raises(ValueError):
            AgentExecutionConfig(llm_timeout=0)
        with pytest.raises(ValueError):
            AgentExecutionConfig(recursion_limit=-1)

    def test_old_field_removed(self):
        with pytest.raises(Exception):
            AgentExecutionConfig(default_timeout=300)


class TestFullModelConfig:
    def test_no_fallback_model(self):
        config = FullModelConfig(
            model=ModelConfig(
                provider="openai",
                name="gpt-4",
                api_key="test-key",
            )
        )
        assert not hasattr(config, 'fallback_model')

    def test_parameters_defaults(self):
        config = FullModelConfig(
            model=ModelConfig(
                provider="openai",
                name="gpt-4",
                api_key="test-key",
            )
        )
        assert config.parameters.retry_max_count == 3
        assert config.parameters.retry_initial_delay == 10.0
        assert config.parameters.retry_max_delay == 60.0
        assert config.parameters.llm_timeout == 300.0
