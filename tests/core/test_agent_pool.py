import pytest
import threading
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

from src.core.agent_pool import (
    AgentPool,
    AgentInstance,
    InstanceStatus,
    Task,
)


class TestInstanceStatus:
    def test_idle(self):
        assert InstanceStatus.IDLE.value == "idle"

    def test_busy(self):
        assert InstanceStatus.BUSY.value == "busy"

    def test_error(self):
        assert InstanceStatus.ERROR.value == "error"

    def test_disposed(self):
        assert InstanceStatus.DISPOSED.value == "disposed"

    def test_all_members(self):
        members = list(InstanceStatus)
        assert len(members) == 4


class TestAgentInstance:
    def _make_instance(self, status=InstanceStatus.IDLE):
        mock_agent = MagicMock()
        mock_cm = MagicMock()
        mock_sl = MagicMock()
        mock_tr = MagicMock()
        return AgentInstance(
            instance_id="test-id",
            agent=mock_agent,
            context_manager=mock_cm,
            skill_loader=mock_sl,
            tool_registry=mock_tr,
            status=status,
        )

    def test_default_status_is_idle(self):
        inst = self._make_instance()
        assert inst.status == InstanceStatus.IDLE

    def test_acquire_from_idle(self):
        inst = self._make_instance()
        assert inst.acquire() is True
        assert inst.status == InstanceStatus.BUSY
        assert inst.last_used_at is not None

    def test_acquire_from_busy_fails(self):
        inst = self._make_instance(InstanceStatus.BUSY)
        assert inst.acquire() is False

    def test_acquire_from_error_fails(self):
        inst = self._make_instance(InstanceStatus.ERROR)
        assert inst.acquire() is False

    def test_acquire_from_disposed_fails(self):
        inst = self._make_instance(InstanceStatus.DISPOSED)
        assert inst.acquire() is False

    def test_release_from_busy(self):
        inst = self._make_instance(InstanceStatus.BUSY)
        inst.release()
        assert inst.status == InstanceStatus.IDLE

    def test_release_from_idle_no_change(self):
        inst = self._make_instance(InstanceStatus.IDLE)
        inst.release()
        assert inst.status == InstanceStatus.IDLE

    def test_mark_error(self):
        inst = self._make_instance()
        inst.mark_error("something went wrong")
        assert inst.status == InstanceStatus.ERROR
        assert inst.error_message == "something went wrong"

    def test_dispose(self):
        inst = self._make_instance()
        inst.dispose()
        assert inst.status == InstanceStatus.DISPOSED
        inst.context_manager.clear.assert_called_once()

    def test_is_available_idle(self):
        inst = self._make_instance(InstanceStatus.IDLE)
        assert inst.is_available() is True

    def test_is_available_busy(self):
        inst = self._make_instance(InstanceStatus.BUSY)
        assert inst.is_available() is False

    def test_is_available_error(self):
        inst = self._make_instance(InstanceStatus.ERROR)
        assert inst.is_available() is False

    def test_is_available_disposed(self):
        inst = self._make_instance(InstanceStatus.DISPOSED)
        assert inst.is_available() is False

    def test_concurrent_acquire(self):
        inst = self._make_instance()
        results = []
        barrier = threading.Barrier(2)

        def try_acquire():
            barrier.wait()
            results.append(inst.acquire())

        t1 = threading.Thread(target=try_acquire)
        t2 = threading.Thread(target=try_acquire)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert results.count(True) == 1
        assert results.count(False) == 1

    def test_task_count_default(self):
        inst = self._make_instance()
        assert inst.task_count == 0

    def test_role_name_default(self):
        inst = self._make_instance()
        assert inst.role_name is None


class TestTask:
    def test_default_values(self):
        task = Task(task_id="t1", input_text="hello")
        assert task.task_id == "t1"
        assert task.input_text == "hello"
        assert task.role_name is None
        assert task.priority == 0
        assert task.result is None
        assert task.error is None

    def test_priority_comparison(self):
        high = Task(task_id="h", input_text="high", priority=10)
        low = Task(task_id="l", input_text="low", priority=1)
        assert high < low

    def test_same_priority(self):
        t1 = Task(task_id="t1", input_text="a", priority=5)
        t2 = Task(task_id="t2", input_text="b", priority=5)
        assert not (t1 < t2)


class TestAgentPoolCreateInstance:
    @patch("src.core.agent_pool.SessionStorage")
    @patch("src.core.agent_pool.RubatoAgent")
    @patch("src.core.agent_pool.RoleManager")
    @patch("src.core.agent_pool.get_llm_logger")
    def test_create_instance_basic(self, mock_logger, MockRM, MockAgent, MockSS):
        mock_rm = MockRM.return_value
        mock_rm.load_roles.return_value = {}
        mock_rm.list_roles.return_value = []
        mock_rm.has_role.return_value = False

        mock_config = MagicMock()
        mock_config.project = MagicMock()
        mock_config.project.root = MagicMock()
        mock_config.model = MagicMock()
        mock_config.mcp = MagicMock()
        mock_config.mcp.model_dump.return_value = {}
        mock_config.skills = None
        mock_config.tools = None
        mock_config.file_tools = None

        pool = AgentPool(config=mock_config, max_instances=5)

        import asyncio
        asyncio.run(pool.initialize())

        mock_rm.has_role.return_value = False

        instance = asyncio.run(pool.create_instance(instance_id="inst-1"))

        assert instance.instance_id == "inst-1"
        assert instance.status == InstanceStatus.IDLE
        assert pool.get_instance_count() == 1

    @patch("src.core.agent_pool.SessionStorage")
    @patch("src.core.agent_pool.RubatoAgent")
    @patch("src.core.agent_pool.RoleManager")
    @patch("src.core.agent_pool.get_llm_logger")
    def test_create_instance_max_limit(self, mock_logger, MockRM, MockAgent, MockSS):
        mock_rm = MockRM.return_value
        mock_rm.load_roles.return_value = {}
        mock_rm.list_roles.return_value = []
        mock_rm.has_role.return_value = False

        mock_config = MagicMock()
        mock_config.project = MagicMock()
        mock_config.project.root = MagicMock()
        mock_config.model = MagicMock()
        mock_config.mcp = MagicMock()
        mock_config.mcp.model_dump.return_value = {}
        mock_config.skills = None
        mock_config.tools = None
        mock_config.file_tools = None

        pool = AgentPool(config=mock_config, max_instances=1)

        import asyncio
        asyncio.run(pool.initialize())

        asyncio.run(pool.create_instance(instance_id="inst-1"))

        with pytest.raises(RuntimeError, match="最大实例数"):
            asyncio.run(pool.create_instance(instance_id="inst-2"))

    @patch("src.core.agent_pool.SessionStorage")
    @patch("src.core.agent_pool.RubatoAgent")
    @patch("src.core.agent_pool.RoleManager")
    @patch("src.core.agent_pool.get_llm_logger")
    def test_get_instance(self, mock_logger, MockRM, MockAgent, MockSS):
        mock_rm = MockRM.return_value
        mock_rm.load_roles.return_value = {}
        mock_rm.list_roles.return_value = []
        mock_rm.has_role.return_value = False

        mock_config = MagicMock()
        mock_config.project = MagicMock()
        mock_config.project.root = MagicMock()
        mock_config.model = MagicMock()
        mock_config.mcp = MagicMock()
        mock_config.mcp.model_dump.return_value = {}
        mock_config.skills = None
        mock_config.tools = None
        mock_config.file_tools = None

        pool = AgentPool(config=mock_config, max_instances=5)

        import asyncio
        asyncio.run(pool.initialize())

        instance = asyncio.run(pool.create_instance(instance_id="inst-1"))
        found = pool.get_instance("inst-1")
        assert found is instance
        assert pool.get_instance("nonexistent") is None

    @patch("src.core.agent_pool.SessionStorage")
    @patch("src.core.agent_pool.RubatoAgent")
    @patch("src.core.agent_pool.RoleManager")
    @patch("src.core.agent_pool.get_llm_logger")
    def test_destroy_instance(self, mock_logger, MockRM, MockAgent, MockSS):
        mock_rm = MockRM.return_value
        mock_rm.load_roles.return_value = {}
        mock_rm.list_roles.return_value = []
        mock_rm.has_role.return_value = False

        mock_config = MagicMock()
        mock_config.project = MagicMock()
        mock_config.project.root = MagicMock()
        mock_config.model = MagicMock()
        mock_config.mcp = MagicMock()
        mock_config.mcp.model_dump.return_value = {}
        mock_config.skills = None
        mock_config.tools = None
        mock_config.file_tools = None

        pool = AgentPool(config=mock_config, max_instances=5)

        import asyncio
        asyncio.run(pool.initialize())

        asyncio.run(pool.create_instance(instance_id="inst-1"))
        assert pool.destroy_instance("inst-1") is True
        assert pool.get_instance_count() == 0
        assert pool.destroy_instance("inst-1") is False

    @patch("src.core.agent_pool.SessionStorage")
    @patch("src.core.agent_pool.RubatoAgent")
    @patch("src.core.agent_pool.RoleManager")
    @patch("src.core.agent_pool.get_llm_logger")
    def test_list_instances(self, mock_logger, MockRM, MockAgent, MockSS):
        mock_rm = MockRM.return_value
        mock_rm.load_roles.return_value = {}
        mock_rm.list_roles.return_value = []
        mock_rm.has_role.return_value = False

        mock_config = MagicMock()
        mock_config.project = MagicMock()
        mock_config.project.root = MagicMock()
        mock_config.model = MagicMock()
        mock_config.mcp = MagicMock()
        mock_config.mcp.model_dump.return_value = {}
        mock_config.skills = None
        mock_config.tools = None
        mock_config.file_tools = None

        pool = AgentPool(config=mock_config, max_instances=5)

        import asyncio
        asyncio.run(pool.initialize())

        asyncio.run(pool.create_instance(instance_id="inst-1"))
        asyncio.run(pool.create_instance(instance_id="inst-2"))

        instances = pool.list_instances()
        assert len(instances) == 2
        ids = [i["instance_id"] for i in instances]
        assert "inst-1" in ids
        assert "inst-2" in ids

    @patch("src.core.agent_pool.SessionStorage")
    @patch("src.core.agent_pool.RubatoAgent")
    @patch("src.core.agent_pool.RoleManager")
    @patch("src.core.agent_pool.get_llm_logger")
    def test_available_count(self, mock_logger, MockRM, MockAgent, MockSS):
        mock_rm = MockRM.return_value
        mock_rm.load_roles.return_value = {}
        mock_rm.list_roles.return_value = []
        mock_rm.has_role.return_value = False

        mock_config = MagicMock()
        mock_config.project = MagicMock()
        mock_config.project.root = MagicMock()
        mock_config.model = MagicMock()
        mock_config.mcp = MagicMock()
        mock_config.mcp.model_dump.return_value = {}
        mock_config.skills = None
        mock_config.tools = None
        mock_config.file_tools = None

        pool = AgentPool(config=mock_config, max_instances=5)

        import asyncio
        asyncio.run(pool.initialize())

        asyncio.run(pool.create_instance(instance_id="inst-1"))
        assert pool.get_available_count() == 1

        inst = pool.get_instance("inst-1")
        inst.acquire()
        assert pool.get_available_count() == 0
