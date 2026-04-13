import asyncio
import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.core.llm_wrapper import LLMCaller
from src.config.models import (
    ModelConfig, FullModelConfig, RoleConfig, RoleModelConfig
)
from src.core.role_manager import RoleManager


def _make_async_stream(chunks):
    class FakeStream:
        def __init__(self, items):
            self._iter = iter(items)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration:
                raise StopAsyncIteration

    return FakeStream(chunks)


class TestMergeModelConfigAuthField:

    def _create_role_manager(self, default_model_config=None):
        role_configs = {
            "role-a": RoleConfig(
                name="role-a",
                description="角色A",
                system_prompt_file="a.txt",
                model=RoleModelConfig(inherit=True),
            ),
            "role-b": RoleConfig(
                name="role-b",
                description="角色B",
                system_prompt_file="b.txt",
                model=RoleModelConfig(inherit=True),
            ),
            "role-c": RoleConfig(
                name="role-c",
                description="角色C",
                system_prompt_file="c.txt",
                model=RoleModelConfig(
                    inherit=False,
                    provider="openai",
                    name="custom-model",
                    api_key="custom-key",
                    auth="custom-auth",
                    base_url="https://custom.api.com/v1"
                ),
            ),
        }
        manager = RoleManager.__new__(RoleManager)
        manager._role_configs = role_configs
        manager._default_model_config = default_model_config
        return manager

    def test_inherit_true_merges_auth_from_default(self):
        default = FullModelConfig(
            model=ModelConfig(
                provider="openai",
                name="glm-4.7",
                api_key="default-key",
                base_url="https://api.z.ai/v4",
                auth="default-auth-token",
            )
        )
        manager = self._create_role_manager(default)
        merged = manager._merge_model_config(manager._role_configs["role-a"])
        assert merged.auth == "default-auth-token"

    def test_inherit_true_role_auth_overrides_default(self):
        default = FullModelConfig(
            model=ModelConfig(
                provider="openai",
                name="glm-4.7",
                api_key="default-key",
                base_url="https://api.z.ai/v4",
                auth="default-auth-token",
            )
        )
        role_b_override = RoleConfig(
            name="role-b-override",
            description="角色B覆盖",
            system_prompt_file="b.txt",
            model=RoleModelConfig(inherit=True, auth="override-auth"),
        )
        manager = self._create_role_manager(default)
        merged = manager._merge_model_config(role_b_override)
        assert merged.auth == "override-auth"

    def test_inherit_false_includes_auth(self):
        default = FullModelConfig(
            model=ModelConfig(
                provider="openai",
                name="glm-4.7",
                api_key="default-key",
                base_url="https://api.z.ai/v4",
                auth="default-auth-token",
            )
        )
        manager = self._create_role_manager(default)
        merged = manager._merge_model_config(manager._role_configs["role-c"])
        assert merged.auth == "custom-auth"

    def test_inherit_false_no_auth_defaults_empty(self):
        role_no_auth = RoleConfig(
            name="role-no-auth",
            description="无auth角色",
            system_prompt_file="noauth.txt",
            model=RoleModelConfig(
                inherit=False,
                provider="openai",
                name="some-model",
                api_key="some-key",
            ),
        )
        manager = self._create_role_manager()
        merged = manager._merge_model_config(role_no_auth)
        assert merged.auth == ""


class TestStreamCallEmptyResponseRetry:

    def _create_llm_caller(self):
        return LLMCaller(
            api_key="test-key",
            model="test-model",
            base_url="https://api.test.com/v1",
            timeout=5.0,
            retry_max_count=2,
            retry_initial_delay=0.01,
            retry_max_delay=0.05,
        )

    @pytest.mark.asyncio
    async def test_empty_stream_triggers_retry_events(self):
        caller = self._create_llm_caller()

        call_num = 0

        async def mock_create(**kwargs):
            nonlocal call_num
            call_num += 1

            chunks = []

            if call_num > 1:
                delta = MagicMock()
                delta.content = "hello"
                delta.tool_calls = None
                chunk = MagicMock()
                chunk.choices = [MagicMock()]
                chunk.choices[0].delta = delta
                chunk.choices[0].finish_reason = "stop"
                chunks.append(chunk)

            return _make_async_stream(chunks)

        caller.client.chat.completions.create = mock_create

        messages = [HumanMessage(content="test")]
        events = []
        async for event in caller.stream_call(messages, use_tools=False):
            events.append(event)

        retry_events = [e for e in events if e["type"] == "retry"]
        assert len(retry_events) == 1
        assert retry_events[0]["attempt"] == 1

        text_events = [e for e in events if e["type"] == "text_delta"]
        assert len(text_events) == 1
        assert text_events[0]["text"] == "hello"

        complete_events = [e for e in events if e["type"] == "complete"]
        assert len(complete_events) == 1

    @pytest.mark.asyncio
    async def test_empty_stream_exhausted_retries_yields_error(self):
        caller = self._create_llm_caller()

        caller.client.chat.completions.create = AsyncMock(
            return_value=_make_async_stream([])
        )

        messages = [HumanMessage(content="test")]
        events = []
        async for event in caller.stream_call(messages, use_tools=False):
            events.append(event)

        retry_events = [e for e in events if e["type"] == "retry"]
        assert len(retry_events) == 2

        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "空响应" in error_events[0]["message"]
        assert "已重试2次" in error_events[0]["message"]

    @pytest.mark.asyncio
    async def test_retry_delay_exponential_backoff(self):
        caller = LLMCaller(
            api_key="test-key",
            model="test-model",
            base_url="https://api.test.com/v1",
            timeout=5.0,
            retry_max_count=3,
            retry_initial_delay=0.01,
            retry_max_delay=0.03,
        )

        caller.client.chat.completions.create = AsyncMock(
            return_value=_make_async_stream([])
        )

        messages = [HumanMessage(content="test")]
        events = []
        async for event in caller.stream_call(messages, use_tools=False):
            events.append(event)

        retry_events = [e for e in events if e["type"] == "retry"]
        assert len(retry_events) == 3
        assert retry_events[0]["delay"] == 0.01
        assert retry_events[1]["delay"] == 0.02
        assert retry_events[2]["delay"] == 0.03


class TestRoleSwitchQueryEngineRebuild:

    def test_create_llm_includes_auth_header(self):
        from src.core.agent import RubatoAgent

        config = MagicMock()
        config.model.model = ModelConfig(
            provider="openai",
            name="test-model",
            api_key="test-key",
            base_url="https://api.test.com/v1",
            auth="test-auth-token",
        )
        config.model.parameters = MagicMock()
        config.model.parameters.retry_max_count = 3
        config.model.parameters.retry_initial_delay = 1.0
        config.model.parameters.retry_max_delay = 30.0
        config.model.parameters.llm_timeout = 60.0
        config.prompts = MagicMock()
        config.skills = MagicMock()
        config.agent = MagicMock()

        agent = RubatoAgent.__new__(RubatoAgent)
        agent.config = config
        agent.llm = agent._create_llm(config.model.model)

        assert agent.llm.client._client.headers.get("Authorization") == "test-auth-token"

    def test_create_llm_without_auth_no_header(self):
        from src.core.agent import RubatoAgent

        config_no_auth = ModelConfig(
            provider="openai",
            name="test-model",
            api_key="test-key",
            base_url="https://api.test.com/v1",
        )

        agent = RubatoAgent.__new__(RubatoAgent)
        agent.config = MagicMock()
        llm = agent._create_llm(config_no_auth)

        assert llm.client._client.headers.get("Authorization") is None
