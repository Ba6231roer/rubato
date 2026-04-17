from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from src.commands.context import CommandContext
from src.commands.models import CommandResult, ResultType
from src.commands.registry import CommandRegistry


@pytest.fixture(autouse=True)
def _reset_registry():
    CommandRegistry._instance = None
    yield
    CommandRegistry._instance = None


def _make_agent(**overrides):
    agent = MagicMock()
    agent.tools = []
    agent.clear_context = MagicMock()
    agent.get_current_system_prompt = MagicMock(return_value="system prompt")
    agent.get_system_prompt = MagicMock(return_value="system prompt")
    agent.reload_system_prompt = MagicMock()
    agent._rebuild_query_engine = MagicMock()
    agent._system_prompt_registry = MagicMock()
    agent._system_prompt_registry.add_skill = MagicMock()
    agent._system_prompt_registry.build = MagicMock(return_value="rebuilt prompt")
    agent._current_system_prompt = ""
    agent.context_manager = MagicMock()
    agent.context_manager.is_skill_loaded = MagicMock(return_value=False)
    agent.context_manager.mark_skill_loaded = MagicMock()
    agent._query_engine = MagicMock()
    agent._query_engine.get_messages = MagicMock(return_value=[])
    agent._query_engine.get_session_id = MagicMock(return_value="sid-1234-5678")
    agent._query_engine.get_session_metadata = MagicMock(return_value=None)
    agent._query_engine._session_storage = MagicMock()
    agent.load_session = MagicMock(return_value=True)
    agent.role_config = None
    for k, v in overrides.items():
        setattr(agent, k, v)
    return agent


def _make_role(name="default", description="Default role", **overrides):
    role = MagicMock()
    role.name = name
    role.description = description
    role.tools = MagicMock()
    role.tools.skills = None
    for k, v in overrides.items():
        setattr(role, k, v)
    return role


def _make_role_manager(**overrides):
    rm = MagicMock()
    rm.list_roles = MagicMock(return_value=["default", "developer"])
    rm.get_current_role = MagicMock(return_value=_make_role())
    rm.get_role = MagicMock(side_effect=lambda n: _make_role(name=n, description=f"{n} role"))
    rm.get_role_info = MagicMock(return_value={
        "name": "developer",
        "description": "Developer role",
        "model": {
            "inherit": True,
            "provider": "openai",
            "name": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 2000,
        },
        "execution": {
            "max_context_tokens": 8000,
            "timeout": 300,
            "recursion_limit": 25,
            "sub_agent_recursion_limit": 15,
        },
        "available_tools": [],
        "metadata": {},
    })
    rm.has_role = MagicMock(return_value=True)
    rm.switch_role = MagicMock(return_value=_make_role(name="developer", description="Developer role"))
    rm.reload_roles = MagicMock()
    rm.get_merged_model_config = MagicMock(return_value=None)
    for k, v in overrides.items():
        setattr(rm, k, v)
    return rm


def _make_skill_loader(**overrides):
    sl = MagicMock()
    sl.list_skills = MagicMock(return_value=[])
    sl.has_skill = MagicMock(return_value=True)
    sl.load_full_skill = AsyncMock(return_value="skill content")
    sl.load_skill_metadata = AsyncMock()
    sl.registry = MagicMock()
    sl.registry.get_skill = MagicMock(return_value=None)
    for k, v in overrides.items():
        setattr(sl, k, v)
    return sl


def _make_skill_metadata(name="test-skill", description="A test skill", version="1.0", triggers=None):
    meta = MagicMock()
    meta.name = name
    meta.description = description
    meta.version = version
    meta.triggers = triggers or ["test"]
    return meta


def _make_mcp_manager(**overrides):
    mm = MagicMock()
    mm.is_connected = True
    mm.check_browser_alive = AsyncMock(return_value=True)
    mm.close_browser = AsyncMock(return_value=True)
    mm.ensure_browser = AsyncMock(return_value=True)
    for k, v in overrides.items():
        setattr(mm, k, v)
    return mm


def _make_config(**overrides):
    cfg = MagicMock()
    cfg.model = MagicMock()
    cfg.model.model = MagicMock()
    cfg.model.model.provider = "openai"
    cfg.model.model.name = "gpt-4"
    cfg.model.model.temperature = 0.7
    cfg.model.model.max_tokens = 2000
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _make_config_loader(**overrides):
    cl = MagicMock()
    cl.load_all = MagicMock()
    for k, v in overrides.items():
        setattr(cl, k, v)
    return cl


def _make_tool(name="tool1", description="A tool"):
    t = MagicMock()
    t.name = name
    t.description = description
    return t


def _make_message(content="hello", msg_type="HumanMessage"):
    msg = MagicMock()
    msg.content = content
    type(msg).__name__ = msg_type
    return msg


def _make_session_meta(session_id="sid-1234", role="default", message_count=5, updated_at="2025-01-01T00:00:00", description=""):
    meta = MagicMock()
    meta.session_id = session_id
    meta.role = role
    meta.message_count = message_count
    meta.updated_at = updated_at
    meta.created_at = "2025-01-01T00:00:00"
    meta.description = description
    return meta


# ===== HelpCommand =====

class TestHelpCommand:
    async def test_help_returns_info(self):
        from src.commands.impl.help import HelpCommand
        ctx = CommandContext()
        cmd = HelpCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.INFO
        assert "可用命令" in result.message

    async def test_help_includes_status_section(self):
        from src.commands.impl.help import HelpCommand
        ctx = CommandContext()
        cmd = HelpCommand()
        result = await cmd.execute("", ctx)
        assert "/status" in result.message

    async def test_help_includes_role_section(self):
        from src.commands.impl.help import HelpCommand
        ctx = CommandContext()
        cmd = HelpCommand()
        result = await cmd.execute("", ctx)
        assert "/role" in result.message

    async def test_help_name_and_aliases(self):
        from src.commands.impl.help import HelpCommand
        cmd = HelpCommand()
        assert cmd.name == "help"
        assert "?" in cmd.aliases
        assert "h" in cmd.aliases


# ===== QuitCommand =====

class TestQuitCommand:
    async def test_quit_returns_exit(self):
        from src.commands.impl.quit import QuitCommand
        ctx = CommandContext()
        cmd = QuitCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.EXIT
        assert "再见" in result.message

    async def test_quit_name_and_aliases(self):
        from src.commands.impl.quit import QuitCommand
        cmd = QuitCommand()
        assert cmd.name == "quit"
        assert "exit" in cmd.aliases


# ===== ConfigCommand =====

class TestConfigCommand:
    async def test_config_shows_model_info(self):
        from src.commands.impl.config import ConfigCommand
        ctx = CommandContext(config=_make_config())
        cmd = ConfigCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.INFO
        assert "openai/gpt-4" in result.message
        assert "0.7" in result.message

    async def test_config_no_config_returns_error(self):
        from src.commands.impl.config import ConfigCommand
        ctx = CommandContext()
        cmd = ConfigCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.ERROR
        assert "配置未加载" in result.message

    async def test_config_with_mcp_connected(self):
        from src.commands.impl.config import ConfigCommand
        mcp = _make_mcp_manager()
        mcp.is_connected = True
        ctx = CommandContext(config=_make_config(), mcp_manager=mcp)
        cmd = ConfigCommand()
        result = await cmd.execute("", ctx)
        assert "已连接" in result.message

    async def test_config_with_mcp_disconnected(self):
        from src.commands.impl.config import ConfigCommand
        mcp = _make_mcp_manager()
        mcp.is_connected = False
        ctx = CommandContext(config=_make_config(), mcp_manager=mcp)
        cmd = ConfigCommand()
        result = await cmd.execute("", ctx)
        assert "未连接" in result.message

    async def test_config_returns_data(self):
        from src.commands.impl.config import ConfigCommand
        ctx = CommandContext(config=_make_config())
        cmd = ConfigCommand()
        result = await cmd.execute("", ctx)
        assert result.data is not None
        assert result.data["model"]["provider"] == "openai"


# ===== RoleCommand =====

class TestRoleCommand:
    async def test_role_list(self):
        from src.commands.impl.role import RoleCommand
        rm = _make_role_manager()
        ctx = CommandContext(role_manager=rm)
        cmd = RoleCommand()
        result = await cmd.execute("list", ctx)
        assert result.type == ResultType.INFO
        assert "可用角色" in result.message

    async def test_role_list_empty(self):
        from src.commands.impl.role import RoleCommand
        rm = _make_role_manager()
        rm.list_roles = MagicMock(return_value=[])
        ctx = CommandContext(role_manager=rm)
        cmd = RoleCommand()
        result = await cmd.execute("list", ctx)
        assert "没有可用的角色" in result.message

    async def test_role_show(self):
        from src.commands.impl.role import RoleCommand
        rm = _make_role_manager()
        ctx = CommandContext(role_manager=rm)
        cmd = RoleCommand()
        result = await cmd.execute("show developer", ctx)
        assert result.type == ResultType.INFO
        assert "developer" in result.message

    async def test_role_show_missing_name(self):
        from src.commands.impl.role import RoleCommand
        rm = _make_role_manager()
        ctx = CommandContext(role_manager=rm)
        cmd = RoleCommand()
        result = await cmd.execute("show", ctx)
        assert result.type == ResultType.ERROR
        assert "请指定角色名称" in result.message

    async def test_role_show_not_found(self):
        from src.commands.impl.role import RoleCommand
        rm = _make_role_manager()
        rm.get_role_info = MagicMock(return_value=None)
        ctx = CommandContext(role_manager=rm)
        cmd = RoleCommand()
        result = await cmd.execute("show nonexistent", ctx)
        assert result.type == ResultType.ERROR
        assert "未找到角色" in result.message

    async def test_role_switch(self):
        from src.commands.impl.role import RoleCommand
        rm = _make_role_manager()
        agent = _make_agent()
        agent.load_role_skills = AsyncMock()
        agent_pool = MagicMock()
        agent_pool._create_tool_registry = MagicMock(return_value=MagicMock())
        ctx = CommandContext(role_manager=rm, agent=agent, agent_pool=agent_pool)
        cmd = RoleCommand()
        result = await cmd.execute("developer", ctx)
        assert result.type == ResultType.SUCCESS
        assert "developer" in result.message

    async def test_role_switch_nonexistent(self):
        from src.commands.impl.role import RoleCommand
        rm = _make_role_manager()
        rm.has_role = MagicMock(return_value=False)
        ctx = CommandContext(role_manager=rm, agent=_make_agent())
        cmd = RoleCommand()
        result = await cmd.execute("nonexistent", ctx)
        assert result.type == ResultType.ERROR
        assert "不存在" in result.message

    async def test_role_no_args_shows_usage(self):
        from src.commands.impl.role import RoleCommand
        rm = _make_role_manager()
        ctx = CommandContext(role_manager=rm)
        cmd = RoleCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.INFO
        assert "/role" in result.message

    async def test_role_no_role_manager(self):
        from src.commands.impl.role import RoleCommand
        ctx = CommandContext()
        cmd = RoleCommand()
        result = await cmd.execute("list", ctx)
        assert result.type == ResultType.ERROR
        assert "角色管理未启用" in result.message


# ===== SkillCommand =====

class TestSkillCommand:
    async def test_skill_list(self):
        from src.commands.impl.skill import SkillCommand
        meta = _make_skill_metadata("deploy", "Deploy skill")
        sl = _make_skill_loader()
        sl.list_skills = MagicMock(return_value=[meta])
        ctx = CommandContext(skill_loader=sl)
        cmd = SkillCommand()
        result = await cmd.execute("list", ctx)
        assert result.type == ResultType.INFO
        assert "可用Skills" in result.message
        assert "deploy" in result.message

    async def test_skill_list_empty(self):
        from src.commands.impl.skill import SkillCommand
        sl = _make_skill_loader()
        sl.list_skills = MagicMock(return_value=[])
        ctx = CommandContext(skill_loader=sl)
        cmd = SkillCommand()
        result = await cmd.execute("list", ctx)
        assert "没有可用的Skills" in result.message

    async def test_skill_show(self):
        from src.commands.impl.skill import SkillCommand
        meta = _make_skill_metadata("deploy", "Deploy skill", version="2.0", triggers=["deploy", "发布"])
        sl = _make_skill_loader()
        sl.registry.get_skill = MagicMock(return_value=meta)
        ctx = CommandContext(skill_loader=sl)
        cmd = SkillCommand()
        result = await cmd.execute("show deploy", ctx)
        assert result.type == ResultType.INFO
        assert "deploy" in result.message
        assert "2.0" in result.message

    async def test_skill_show_missing_name(self):
        from src.commands.impl.skill import SkillCommand
        sl = _make_skill_loader()
        ctx = CommandContext(skill_loader=sl)
        cmd = SkillCommand()
        result = await cmd.execute("show", ctx)
        assert result.type == ResultType.ERROR
        assert "请指定Skill名称" in result.message

    async def test_skill_show_not_found(self):
        from src.commands.impl.skill import SkillCommand
        sl = _make_skill_loader()
        sl.registry.get_skill = MagicMock(return_value=None)
        ctx = CommandContext(skill_loader=sl)
        cmd = SkillCommand()
        result = await cmd.execute("show nonexistent", ctx)
        assert result.type == ResultType.ERROR
        assert "未找到Skill" in result.message

    async def test_skill_load(self):
        from src.commands.impl.skill import SkillCommand
        sl = _make_skill_loader()
        agent = _make_agent()
        ctx = CommandContext(skill_loader=sl, agent=agent)
        cmd = SkillCommand()
        result = await cmd.execute("load deploy", ctx)
        assert result.type == ResultType.INFO
        assert "已加载Skill" in result.message

    async def test_skill_load_missing_name(self):
        from src.commands.impl.skill import SkillCommand
        sl = _make_skill_loader()
        ctx = CommandContext(skill_loader=sl)
        cmd = SkillCommand()
        result = await cmd.execute("load", ctx)
        assert result.type == ResultType.ERROR
        assert "请指定Skill名称" in result.message

    async def test_skill_load_already_loaded(self):
        from src.commands.impl.skill import SkillCommand
        sl = _make_skill_loader()
        agent = _make_agent()
        agent.context_manager.is_skill_loaded = MagicMock(return_value=True)
        ctx = CommandContext(skill_loader=sl, agent=agent)
        cmd = SkillCommand()
        result = await cmd.execute("load deploy", ctx)
        assert "已加载过" in result.message

    async def test_skill_load_not_found(self):
        from src.commands.impl.skill import SkillCommand
        sl = _make_skill_loader()
        sl.has_skill = MagicMock(return_value=False)
        agent = _make_agent()
        ctx = CommandContext(skill_loader=sl, agent=agent)
        cmd = SkillCommand()
        result = await cmd.execute("load ghost", ctx)
        assert "未找到Skill" in result.message

    async def test_skill_no_skill_loader(self):
        from src.commands.impl.skill import SkillCommand
        ctx = CommandContext()
        cmd = SkillCommand()
        result = await cmd.execute("list", ctx)
        assert result.type == ResultType.ERROR
        assert "Skill加载器未初始化" in result.message

    async def test_skill_no_args_shows_usage(self):
        from src.commands.impl.skill import SkillCommand
        sl = _make_skill_loader()
        ctx = CommandContext(skill_loader=sl)
        cmd = SkillCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.INFO
        assert "/skill" in result.message


# ===== ToolCommand =====

class TestToolCommand:
    async def test_tool_list(self):
        from src.commands.impl.tool import ToolCommand
        agent = _make_agent()
        agent.tools = [_make_tool("shell", "Run shell commands"), _make_tool("file_read", "Read files")]
        ctx = CommandContext(agent=agent)
        cmd = ToolCommand()
        result = await cmd.execute("list", ctx)
        assert result.type == ResultType.INFO
        assert "可用工具" in result.message
        assert "shell" in result.message

    async def test_tool_list_empty(self):
        from src.commands.impl.tool import ToolCommand
        agent = _make_agent()
        agent.tools = []
        ctx = CommandContext(agent=agent)
        cmd = ToolCommand()
        result = await cmd.execute("list", ctx)
        assert "没有可用的工具" in result.message

    async def test_tool_list_no_agent(self):
        from src.commands.impl.tool import ToolCommand
        ctx = CommandContext()
        cmd = ToolCommand()
        result = await cmd.execute("list", ctx)
        assert "没有可用的工具" in result.message

    async def test_tool_no_args_shows_usage(self):
        from src.commands.impl.tool import ToolCommand
        ctx = CommandContext()
        cmd = ToolCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.INFO
        assert "/tool" in result.message

    async def test_tool_list_long_description_truncated(self):
        from src.commands.impl.tool import ToolCommand
        agent = _make_agent()
        agent.tools = [_make_tool("longtool", "A" * 60)]
        ctx = CommandContext(agent=agent)
        cmd = ToolCommand()
        result = await cmd.execute("list", ctx)
        assert "..." in result.message


# ===== StatusCommand =====

class TestStatusCommand:
    async def test_status_overview(self):
        from src.commands.impl.status import StatusCommand
        rm = _make_role_manager()
        agent = _make_agent()
        agent.tools = [_make_tool()]
        ctx = CommandContext(role_manager=rm, agent=agent)
        cmd = StatusCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.INFO
        assert "当前状态概览" in result.message
        assert "default" in result.message

    async def test_status_tools(self):
        from src.commands.impl.status import StatusCommand
        agent = _make_agent()
        agent.tools = [_make_tool("t1", "Tool 1"), _make_tool("t2", "Tool 2")]
        ctx = CommandContext(agent=agent)
        cmd = StatusCommand()
        result = await cmd.execute("tools", ctx)
        assert result.type == ResultType.INFO
        assert "t1" in result.message
        assert "t2" in result.message

    async def test_status_tools_empty(self):
        from src.commands.impl.status import StatusCommand
        agent = _make_agent()
        agent.tools = []
        ctx = CommandContext(agent=agent)
        cmd = StatusCommand()
        result = await cmd.execute("tools", ctx)
        assert "没有可用的工具" in result.message

    async def test_status_prompt(self):
        from src.commands.impl.status import StatusCommand
        agent = _make_agent()
        ctx = CommandContext(agent=agent)
        cmd = StatusCommand()
        result = await cmd.execute("prompt", ctx)
        assert result.type == ResultType.INFO
        assert "系统提示词" in result.message

    async def test_status_full(self):
        from src.commands.impl.status import StatusCommand
        rm = _make_role_manager()
        agent = _make_agent()
        agent.tools = [_make_tool()]
        ctx = CommandContext(role_manager=rm, agent=agent)
        cmd = StatusCommand()
        result = await cmd.execute("full", ctx)
        assert result.type == ResultType.INFO
        assert "当前状态概览" in result.message

    async def test_status_no_role_manager(self):
        from src.commands.impl.status import StatusCommand
        agent = _make_agent()
        ctx = CommandContext(agent=agent)
        cmd = StatusCommand()
        result = await cmd.execute("", ctx)
        assert "未设置" in result.message

    async def test_status_no_agent(self):
        from src.commands.impl.status import StatusCommand
        ctx = CommandContext()
        cmd = StatusCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.INFO
        assert "可用工具数量: 0" in result.message


# ===== ClearCommand =====

class TestClearCommand:
    async def test_clear_success(self):
        from src.commands.impl.clear import ClearCommand
        agent = _make_agent()
        ctx = CommandContext(agent=agent)
        cmd = ClearCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.SUCCESS
        assert "对话历史已清空" in result.message
        agent.clear_context.assert_called_once()

    async def test_clear_no_agent(self):
        from src.commands.impl.clear import ClearCommand
        ctx = CommandContext()
        cmd = ClearCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.ERROR
        assert "Agent未初始化" in result.message


# ===== NewCommand =====

class TestNewCommand:
    async def test_new_clears_and_reloads(self):
        from src.commands.impl.new import NewCommand
        rm = _make_role_manager()
        agent = _make_agent()
        ctx = CommandContext(agent=agent, role_manager=rm)
        cmd = NewCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.SUCCESS
        assert "新对话已开始" in result.message
        agent.clear_context.assert_called_once()
        agent.reload_system_prompt.assert_called_once()

    async def test_new_no_agent(self):
        from src.commands.impl.new import NewCommand
        ctx = CommandContext()
        cmd = NewCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.ERROR
        assert "Agent未初始化" in result.message

    async def test_new_without_role_manager(self):
        from src.commands.impl.new import NewCommand
        agent = _make_agent()
        ctx = CommandContext(agent=agent)
        cmd = NewCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.SUCCESS
        agent.clear_context.assert_called_once()

    async def test_new_error_handling(self):
        from src.commands.impl.new import NewCommand
        agent = _make_agent()
        agent.clear_context = MagicMock(side_effect=RuntimeError("boom"))
        ctx = CommandContext(agent=agent)
        cmd = NewCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.ERROR
        assert "boom" in result.message


# ===== ReloadCommand =====

class TestReloadCommand:
    async def test_reload_all(self):
        from src.commands.impl.reload import ReloadCommand
        rm = _make_role_manager()
        cl = _make_config_loader()
        sl = _make_skill_loader()
        agent = _make_agent()
        ctx = CommandContext(role_manager=rm, config_loader=cl, skill_loader=sl, agent=agent)
        cmd = ReloadCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.SUCCESS
        assert "角色配置" in result.message
        assert "模型配置" in result.message
        assert "Skill配置" in result.message
        rm.reload_roles.assert_called_once()
        cl.load_all.assert_called_once()

    async def test_reload_no_managers(self):
        from src.commands.impl.reload import ReloadCommand
        ctx = CommandContext()
        cmd = ReloadCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.INFO
        assert "没有可重新加载的配置" in result.message

    async def test_reload_partial(self):
        from src.commands.impl.reload import ReloadCommand
        rm = _make_role_manager()
        agent = _make_agent()
        ctx = CommandContext(role_manager=rm, agent=agent)
        cmd = ReloadCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.SUCCESS
        assert "角色配置" in result.message

    async def test_reload_error(self):
        from src.commands.impl.reload import ReloadCommand
        rm = _make_role_manager()
        rm.reload_roles = MagicMock(side_effect=RuntimeError("fail"))
        ctx = CommandContext(role_manager=rm)
        cmd = ReloadCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.ERROR
        assert "fail" in result.message


# ===== PromptCommand =====

class TestPromptCommand:
    async def test_prompt_show(self):
        from src.commands.impl.prompt import PromptCommand
        agent = _make_agent()
        agent.get_system_prompt = MagicMock(return_value="Hello, I am an AI assistant.")
        ctx = CommandContext(agent=agent)
        cmd = PromptCommand()
        result = await cmd.execute("show", ctx)
        assert result.type == ResultType.INFO
        assert "系统提示词" in result.message
        assert "Hello" in result.message

    async def test_prompt_show_truncated(self):
        from src.commands.impl.prompt import PromptCommand
        agent = _make_agent()
        agent.get_system_prompt = MagicMock(return_value="A" * 600)
        ctx = CommandContext(agent=agent)
        cmd = PromptCommand()
        result = await cmd.execute("show", ctx)
        assert "..." in result.message
        assert result.data["truncated"] is True

    async def test_prompt_show_no_agent(self):
        from src.commands.impl.prompt import PromptCommand
        ctx = CommandContext()
        cmd = PromptCommand()
        result = await cmd.execute("show", ctx)
        assert result.type == ResultType.ERROR
        assert "Agent未初始化" in result.message

    async def test_prompt_no_args_shows_usage(self):
        from src.commands.impl.prompt import PromptCommand
        ctx = CommandContext()
        cmd = PromptCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.INFO
        assert "/prompt" in result.message


# ===== HistoryCommand =====

class TestHistoryCommand:
    async def test_history_with_messages(self):
        from src.commands.impl.history import HistoryCommand
        agent = _make_agent()
        msgs = [_make_message("hello", "HumanMessage"), _make_message("hi there", "AIMessage")]
        agent._query_engine.get_messages = MagicMock(return_value=msgs)
        ctx = CommandContext(agent=agent)
        cmd = HistoryCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.INFO
        assert "对话历史" in result.message
        assert "hello" in result.message

    async def test_history_empty(self):
        from src.commands.impl.history import HistoryCommand
        agent = _make_agent()
        agent._query_engine.get_messages = MagicMock(return_value=[])
        ctx = CommandContext(agent=agent)
        cmd = HistoryCommand()
        result = await cmd.execute("", ctx)
        assert "对话历史为空" in result.message

    async def test_history_no_agent(self):
        from src.commands.impl.history import HistoryCommand
        ctx = CommandContext()
        cmd = HistoryCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.ERROR
        assert "Agent未初始化" in result.message

    async def test_history_long_content_truncated(self):
        from src.commands.impl.history import HistoryCommand
        agent = _make_agent()
        msgs = [_make_message("A" * 150, "HumanMessage")]
        agent._query_engine.get_messages = MagicMock(return_value=msgs)
        ctx = CommandContext(agent=agent)
        cmd = HistoryCommand()
        result = await cmd.execute("", ctx)
        assert "..." in result.message


# ===== SessionCommand =====

class TestSessionCommand:
    async def test_session_list(self):
        from src.commands.impl.session import SessionCommand
        agent = _make_agent()
        storage = agent._query_engine._session_storage
        storage.list_sessions = MagicMock(return_value=[
            _make_session_meta("sid-1", "default", 5, "2025-01-01T00:00:00", "test session")
        ])
        ctx = CommandContext(agent=agent)
        cmd = SessionCommand()
        result = await cmd.execute("list", ctx)
        assert result.type == ResultType.INFO
        assert "会话列表" in result.message

    async def test_session_list_empty(self):
        from src.commands.impl.session import SessionCommand
        agent = _make_agent()
        storage = agent._query_engine._session_storage
        storage.list_sessions = MagicMock(return_value=[])
        ctx = CommandContext(agent=agent)
        cmd = SessionCommand()
        result = await cmd.execute("list", ctx)
        assert "没有已保存的会话" in result.message

    async def test_session_load(self):
        from src.commands.impl.session import SessionCommand
        agent = _make_agent()
        ctx = CommandContext(agent=agent)
        cmd = SessionCommand()
        result = await cmd.execute("load sid-1234", ctx)
        assert result.type == ResultType.SUCCESS
        assert "已加载" in result.message

    async def test_session_load_missing_id(self):
        from src.commands.impl.session import SessionCommand
        agent = _make_agent()
        ctx = CommandContext(agent=agent)
        cmd = SessionCommand()
        result = await cmd.execute("load", ctx)
        assert result.type == ResultType.ERROR
        assert "请指定要加载的会话ID" in result.message

    async def test_session_load_failure(self):
        from src.commands.impl.session import SessionCommand
        agent = _make_agent()
        agent.load_session = MagicMock(return_value=False)
        ctx = CommandContext(agent=agent)
        cmd = SessionCommand()
        result = await cmd.execute("load bad-id", ctx)
        assert result.type == ResultType.ERROR
        assert "加载会话失败" in result.message

    async def test_session_save(self):
        from src.commands.impl.session import SessionCommand
        agent = _make_agent()
        storage = agent._query_engine._session_storage
        ctx = CommandContext(agent=agent)
        cmd = SessionCommand()
        result = await cmd.execute("save my description", ctx)
        assert result.type == ResultType.SUCCESS
        assert "会话已保存" in result.message
        assert "my description" in result.message

    async def test_session_save_no_storage(self):
        from src.commands.impl.session import SessionCommand
        agent = _make_agent()
        agent._query_engine._session_storage = None
        ctx = CommandContext(agent=agent)
        cmd = SessionCommand()
        result = await cmd.execute("save", ctx)
        assert result.type == ResultType.ERROR
        assert "会话存储未初始化" in result.message

    async def test_session_current(self):
        from src.commands.impl.session import SessionCommand
        agent = _make_agent()
        agent._query_engine.get_session_metadata = MagicMock(return_value=_make_session_meta())
        ctx = CommandContext(agent=agent)
        cmd = SessionCommand()
        result = await cmd.execute("current", ctx)
        assert result.type == ResultType.INFO
        assert "当前会话信息" in result.message

    async def test_session_current_no_metadata(self):
        from src.commands.impl.session import SessionCommand
        agent = _make_agent()
        agent._query_engine.get_session_metadata = MagicMock(return_value=None)
        ctx = CommandContext(agent=agent)
        cmd = SessionCommand()
        result = await cmd.execute("current", ctx)
        assert result.type == ResultType.INFO
        assert "当前会话信息" in result.message

    async def test_session_delete(self):
        from src.commands.impl.session import SessionCommand
        agent = _make_agent()
        storage = agent._query_engine._session_storage
        storage.delete_session = MagicMock(return_value=True)
        agent._query_engine.get_session_id = MagicMock(return_value="current-sid")
        ctx = CommandContext(agent=agent)
        cmd = SessionCommand()
        result = await cmd.execute("delete other-sid", ctx)
        assert result.type == ResultType.SUCCESS
        assert "已删除" in result.message

    async def test_session_delete_current_session(self):
        from src.commands.impl.session import SessionCommand
        agent = _make_agent()
        agent._query_engine.get_session_id = MagicMock(return_value="same-sid")
        ctx = CommandContext(agent=agent)
        cmd = SessionCommand()
        result = await cmd.execute("delete same-sid", ctx)
        assert result.type == ResultType.ERROR
        assert "不能删除当前正在使用的会话" in result.message

    async def test_session_delete_missing_id(self):
        from src.commands.impl.session import SessionCommand
        agent = _make_agent()
        ctx = CommandContext(agent=agent)
        cmd = SessionCommand()
        result = await cmd.execute("delete", ctx)
        assert result.type == ResultType.ERROR
        assert "请指定要删除的会话ID" in result.message

    async def test_session_delete_failure(self):
        from src.commands.impl.session import SessionCommand
        agent = _make_agent()
        storage = agent._query_engine._session_storage
        storage.delete_session = MagicMock(return_value=False)
        agent._query_engine.get_session_id = MagicMock(return_value="current-sid")
        ctx = CommandContext(agent=agent)
        cmd = SessionCommand()
        result = await cmd.execute("delete other-sid", ctx)
        assert result.type == ResultType.ERROR
        assert "删除会话失败" in result.message

    async def test_session_no_subcommand(self):
        from src.commands.impl.session import SessionCommand
        agent = _make_agent()
        ctx = CommandContext(agent=agent)
        cmd = SessionCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.ERROR
        assert "请指定子命令" in result.message

    async def test_session_unknown_subcommand(self):
        from src.commands.impl.session import SessionCommand
        agent = _make_agent()
        ctx = CommandContext(agent=agent)
        cmd = SessionCommand()
        result = await cmd.execute("unknown", ctx)
        assert result.type == ResultType.ERROR
        assert "未知子命令" in result.message

    async def test_session_no_agent(self):
        from src.commands.impl.session import SessionCommand
        ctx = CommandContext()
        cmd = SessionCommand()
        result = await cmd.execute("list", ctx)
        assert result.type == ResultType.ERROR
        assert "Agent未初始化" in result.message

    async def test_session_format_datetime(self):
        from src.commands.impl.session import SessionCommand
        assert SessionCommand._format_datetime("2025-01-15T10:30:00") == "2025-01-15 10:30"
        assert SessionCommand._format_datetime("") == "-"
        assert SessionCommand._format_datetime("invalid") == "invalid"


# ===== BrowserCommand =====

class TestBrowserCommand:
    async def test_browser_status_connected(self):
        from src.commands.impl.browser import BrowserCommand
        mcp = _make_mcp_manager()
        ctx = CommandContext(mcp_manager=mcp)
        cmd = BrowserCommand()
        result = await cmd.execute("status", ctx)
        assert result.type == ResultType.INFO
        assert "运行中" in result.message

    async def test_browser_status_disconnected(self):
        from src.commands.impl.browser import BrowserCommand
        mcp = _make_mcp_manager()
        mcp.is_connected = False
        ctx = CommandContext(mcp_manager=mcp)
        cmd = BrowserCommand()
        result = await cmd.execute("status", ctx)
        assert result.type == ResultType.INFO
        assert "MCP未连接" in result.message

    async def test_browser_close(self):
        from src.commands.impl.browser import BrowserCommand
        mcp = _make_mcp_manager()
        ctx = CommandContext(mcp_manager=mcp)
        cmd = BrowserCommand()
        result = await cmd.execute("close", ctx)
        assert result.type == ResultType.SUCCESS
        assert "浏览器已关闭" in result.message

    async def test_browser_close_disconnected(self):
        from src.commands.impl.browser import BrowserCommand
        mcp = _make_mcp_manager()
        mcp.is_connected = False
        ctx = CommandContext(mcp_manager=mcp)
        cmd = BrowserCommand()
        result = await cmd.execute("close", ctx)
        assert result.type == ResultType.ERROR
        assert "MCP未连接" in result.message

    async def test_browser_close_failure(self):
        from src.commands.impl.browser import BrowserCommand
        mcp = _make_mcp_manager()
        mcp.close_browser = AsyncMock(return_value=False)
        ctx = CommandContext(mcp_manager=mcp)
        cmd = BrowserCommand()
        result = await cmd.execute("close", ctx)
        assert result.type == ResultType.ERROR
        assert "关闭浏览器失败" in result.message

    async def test_browser_reopen(self):
        from src.commands.impl.browser import BrowserCommand
        mcp = _make_mcp_manager()
        ctx = CommandContext(mcp_manager=mcp)
        cmd = BrowserCommand()
        result = await cmd.execute("reopen", ctx)
        assert result.type == ResultType.SUCCESS
        assert "浏览器已重新打开" in result.message

    async def test_browser_reopen_failure(self):
        from src.commands.impl.browser import BrowserCommand
        mcp = _make_mcp_manager()
        mcp.ensure_browser = AsyncMock(return_value=False)
        ctx = CommandContext(mcp_manager=mcp)
        cmd = BrowserCommand()
        result = await cmd.execute("reopen", ctx)
        assert result.type == ResultType.ERROR
        assert "重新打开浏览器失败" in result.message

    async def test_browser_no_mcp_manager(self):
        from src.commands.impl.browser import BrowserCommand
        ctx = CommandContext()
        cmd = BrowserCommand()
        result = await cmd.execute("status", ctx)
        assert result.type == ResultType.ERROR
        assert "MCP未启用" in result.message

    async def test_browser_no_args_shows_usage(self):
        from src.commands.impl.browser import BrowserCommand
        mcp = _make_mcp_manager()
        ctx = CommandContext(mcp_manager=mcp)
        cmd = BrowserCommand()
        result = await cmd.execute("", ctx)
        assert result.type == ResultType.INFO
        assert "/browser" in result.message


# ===== BaseCommand get_help =====

class TestBaseCommandGetHelp:
    def test_get_help_basic(self):
        from src.commands.impl.quit import QuitCommand
        cmd = QuitCommand()
        help_text = cmd.get_help()
        assert "/quit" in help_text
        assert "退出程序" in help_text

    def test_get_help_with_aliases(self):
        from src.commands.impl.help import HelpCommand
        cmd = HelpCommand()
        help_text = cmd.get_help()
        assert "/help" in help_text
        assert "/?" in help_text
        assert "/h" in help_text

    def test_get_help_with_usage(self):
        from src.commands.impl.role import RoleCommand
        cmd = RoleCommand()
        help_text = cmd.get_help()
        assert "用法" in help_text

    def test_validate_args_default(self):
        from src.commands.impl.quit import QuitCommand
        cmd = QuitCommand()
        assert cmd.validate_args("") is None
