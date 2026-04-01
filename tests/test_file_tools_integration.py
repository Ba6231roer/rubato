import pytest
import tempfile
import sys
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.models import (
    AppConfig,
    ProjectConfig,
    WorkspaceConfig,
    FileToolsConfig,
    PermissionMode,
    RoleConfig,
    RoleFileToolsConfig,
    WorkspaceRestrictionConfig,
    FullModelConfig,
    ModelConfig,
    PromptConfig,
    SkillsConfig,
    AgentConfig
)
from src.core.agent_pool import AgentPool
from src.mcp.tools import ToolRegistry
from src.tools.file_tools import FileToolProvider
from src.tools.file_tools.audit import OperationType, OperationResult


class TestFileToolsIntegration:
    def test_tool_registry_with_file_tools(self, tmp_path):
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        
        src_dir = project_root / "src"
        src_dir.mkdir()
        
        workspace_config = WorkspaceConfig(
            main=project_root,
            additional=[],
            excluded=[]
        )
        
        project_config = ProjectConfig(
            name="test_project",
            root=project_root,
            workspace=workspace_config
        )
        
        file_tools_config = FileToolsConfig(
            enabled=True,
            permission_mode=PermissionMode.ask,
            custom_permissions={},
            default_permissions=PermissionMode.ask,
            audit=True
        )
        
        provider = FileToolProvider(project_config, file_tools_config)
        
        registry = ToolRegistry()
        registry.register_provider(provider)
        
        tools = registry.get_all_tools()
        
        tool_names = [tool.name for tool in tools]
        
        assert len(tools) == 10
        assert "file_read" in tool_names
        assert "file_write" in tool_names
        assert "file_replace" in tool_names
        assert "file_list" in tool_names
        assert "file_search" in tool_names
        assert "file_exists" in tool_names
        assert "file_delete" in tool_names
        assert "file_copy" in tool_names
        assert "file_move" in tool_names
        assert "file_mkdir" in tool_names
    
    def test_tool_registry_without_file_tools(self, tmp_path):
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        
        workspace_config = WorkspaceConfig(
            main=project_root,
            additional=[],
            excluded=[]
        )
        
        project_config = ProjectConfig(
            name="test_project",
            root=project_root,
            workspace=workspace_config
        )
        
        file_tools_config = FileToolsConfig(
            enabled=False,
            permission_mode=PermissionMode.ask,
            custom_permissions={},
            default_permissions=PermissionMode.ask,
            audit=True
        )
        
        provider = FileToolProvider(project_config, file_tools_config)
        
        registry = ToolRegistry()
        registry.register_provider(provider)
        
        tools = registry.get_all_tools()
        
        assert len(tools) == 0
    
    def test_role_config_with_file_tools(self, tmp_path):
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        
        workspace_config = WorkspaceConfig(
            main=project_root,
            additional=[],
            excluded=["*.log", ".env"]
        )
        
        workspace_restriction = WorkspaceRestrictionConfig(
            allowed_subdirs=["src", "tests"],
            excluded_patterns=["*.log"],
            read_only_dirs=["config"]
        )
        
        role_file_tools = RoleFileToolsConfig(
            enabled=True,
            workspace=workspace_config,
            workspace_restriction=workspace_restriction,
            permissions={
                "default": PermissionMode.allow,
                "custom": {
                    "delete": PermissionMode.deny
                }
            },
            audit=True
        )
        
        role_config = RoleConfig(
            name="code-generator",
            description="Code generator role",
            system_prompt_file="prompts/code_generator.txt",
            file_tools=role_file_tools
        )
        
        assert role_config.file_tools is not None
        assert role_config.file_tools.enabled is True
        assert role_config.file_tools.workspace_restriction is not None
        assert "src" in role_config.file_tools.workspace_restriction.allowed_subdirs
        assert role_config.file_tools.permissions["default"] == PermissionMode.allow
    
    def test_role_config_without_file_tools(self):
        role_config = RoleConfig(
            name="browser-tester",
            description="Browser testing role",
            system_prompt_file="prompts/browser_tester.txt"
        )
        
        assert role_config.file_tools is None
    
    def test_file_tool_provider_with_role_config(self, tmp_path):
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        
        src_dir = project_root / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("print('hello')")
        
        workspace_config = WorkspaceConfig(
            main=project_root,
            additional=[],
            excluded=["*.log"]
        )
        
        workspace_restriction = WorkspaceRestrictionConfig(
            allowed_subdirs=["src"],
            excluded_patterns=[],
            read_only_dirs=[]
        )
        
        role_file_tools = RoleFileToolsConfig(
            enabled=True,
            workspace=workspace_config,
            workspace_restriction=workspace_restriction,
            permissions={
                "default": PermissionMode.allow,
                "custom": {}
            },
            audit=True
        )
        
        project_config = ProjectConfig(
            name="test_project",
            root=project_root,
            workspace=workspace_config
        )
        
        file_tools_config = FileToolsConfig(
            enabled=True,
            permission_mode=PermissionMode.allow,
            custom_permissions={},
            default_permissions=PermissionMode.allow,
            audit=True
        )
        
        provider = FileToolProvider(project_config, file_tools_config)
        
        tools = provider.get_tools()
        assert len(tools) == 10
        
        test_file = src_dir / "main.py"
        permission_result = provider.check_permission(
            str(test_file),
            OperationType.READ
        )
        assert permission_result.allowed is True
        
        provider.log_success(
            tool_name="read_file",
            path=str(test_file),
            operation=OperationType.READ
        )
        
        entries = provider.audit_logger.query_by_path(str(test_file))
        assert len(entries) > 0
        assert entries[0].result == OperationResult.SUCCESS
    
    def test_permission_control_with_role_config(self, tmp_path):
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        
        src_dir = project_root / "src"
        src_dir.mkdir()
        
        config_dir = project_root / "config"
        config_dir.mkdir()
        
        workspace_config = WorkspaceConfig(
            main=project_root,
            additional=[],
            excluded=[]
        )
        
        workspace_restriction = WorkspaceRestrictionConfig(
            allowed_subdirs=["src"],
            excluded_patterns=[],
            read_only_dirs=["config"]
        )
        
        role_file_tools = RoleFileToolsConfig(
            enabled=True,
            workspace=workspace_config,
            workspace_restriction=workspace_restriction,
            permissions={
                "default": PermissionMode.allow,
                "custom": {
                    "delete": PermissionMode.deny
                }
            },
            audit=True
        )
        
        project_config = ProjectConfig(
            name="test_project",
            root=project_root,
            workspace=workspace_config
        )
        
        file_tools_config = FileToolsConfig(
            enabled=True,
            permission_mode=PermissionMode.allow,
            custom_permissions={
                "delete": PermissionMode.deny
            },
            default_permissions=PermissionMode.allow,
            audit=True
        )
        
        provider = FileToolProvider(project_config, file_tools_config)
        
        src_file = src_dir / "test.py"
        src_file.write_text("print('test')")
        
        read_permission = provider.check_permission(
            str(src_file),
            OperationType.READ
        )
        assert read_permission.allowed is True
        
        write_permission = provider.check_permission(
            str(src_file),
            OperationType.WRITE
        )
        assert write_permission.allowed is True
        
        delete_permission = provider.check_permission(
            str(src_file),
            OperationType.DELETE
        )
        assert delete_permission.allowed is False
    
    def test_audit_logging_integration(self, tmp_path):
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        
        workspace_config = WorkspaceConfig(
            main=project_root,
            additional=[],
            excluded=[]
        )
        
        project_config = ProjectConfig(
            name="test_project",
            root=project_root,
            workspace=workspace_config
        )
        
        file_tools_config = FileToolsConfig(
            enabled=True,
            permission_mode=PermissionMode.ask,
            audit=True
        )
        
        provider = FileToolProvider(project_config, file_tools_config)
        
        test_file = project_root / "test.py"
        test_file.write_text("print('test')")
        
        provider.log_success(
            tool_name="read_file",
            path=str(test_file),
            operation=OperationType.READ,
            extra={"size": 100}
        )
        
        provider.log_denied(
            tool_name="delete_file",
            path=str(test_file),
            operation=OperationType.DELETE,
            reason="Delete permission denied"
        )
        
        provider.log_error(
            tool_name="write_file",
            path=str(test_file),
            operation=OperationType.WRITE,
            error="Disk full"
        )
        
        all_entries = provider.audit_logger.query_by_path(str(test_file))
        assert len(all_entries) == 3
        
        success_entries = provider.audit_logger.query(result=OperationResult.SUCCESS)
        assert len(success_entries) > 0
        
        denied_entries = provider.audit_logger.query(result=OperationResult.DENIED)
        assert len(denied_entries) > 0
        
        error_entries = provider.audit_logger.query(result=OperationResult.ERROR)
        assert len(error_entries) > 0
    
    def test_workspace_boundary_enforcement(self, tmp_path):
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        
        outside_root = tmp_path / "outside_project"
        outside_root.mkdir()
        
        workspace_config = WorkspaceConfig(
            main=project_root,
            additional=[],
            excluded=[]
        )
        
        project_config = ProjectConfig(
            name="test_project",
            root=project_root,
            workspace=workspace_config
        )
        
        file_tools_config = FileToolsConfig(
            enabled=True,
            permission_mode=PermissionMode.allow,
            audit=True
        )
        
        provider = FileToolProvider(project_config, file_tools_config)
        
        inside_file = project_root / "inside.txt"
        inside_file.write_text("inside")
        
        outside_file = outside_root / "outside.txt"
        outside_file.write_text("outside")
        
        inside_permission = provider.check_permission(
            str(inside_file),
            OperationType.READ
        )
        assert inside_permission.allowed is True
        
        outside_permission = provider.check_permission(
            str(outside_file),
            OperationType.READ
        )
        assert outside_permission.allowed is False
        assert "outside workspace" in outside_permission.reason.lower()
    
    def test_excluded_patterns_enforcement(self, tmp_path):
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        
        env_file = project_root / ".env"
        env_file.write_text("SECRET=123")
        
        log_file = project_root / "debug.log"
        log_file.write_text("log content")
        
        normal_file = project_root / "main.py"
        normal_file.write_text("print('hello')")
        
        workspace_config = WorkspaceConfig(
            main=project_root,
            additional=[],
            excluded=[".env", "*.log"]
        )
        
        project_config = ProjectConfig(
            name="test_project",
            root=project_root,
            workspace=workspace_config
        )
        
        file_tools_config = FileToolsConfig(
            enabled=True,
            permission_mode=PermissionMode.allow,
            audit=True
        )
        
        provider = FileToolProvider(project_config, file_tools_config)
        
        env_permission = provider.check_permission(
            str(env_file),
            OperationType.READ
        )
        assert env_permission.allowed is False
        assert "excluded" in env_permission.reason.lower()
        
        log_permission = provider.check_permission(
            str(log_file),
            OperationType.READ
        )
        assert log_permission.allowed is False
        
        normal_permission = provider.check_permission(
            str(normal_file),
            OperationType.READ
        )
        assert normal_permission.allowed is True


class TestAgentPoolFileToolsIntegration:
    @pytest.fixture
    def mock_config(self, tmp_path):
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        
        workspace_config = WorkspaceConfig(
            main=project_root,
            additional=[],
            excluded=[]
        )
        
        project_config = ProjectConfig(
            name="test_project",
            root=project_root,
            workspace=workspace_config
        )
        
        file_tools_config = FileToolsConfig(
            enabled=True,
            permission_mode=PermissionMode.ask,
            audit=True
        )
        
        model_config = ModelConfig(
            provider="openai",
            name="gpt-4",
            api_key="test-key"
        )
        
        full_model_config = FullModelConfig(
            model=model_config
        )
        
        prompt_config = PromptConfig(
            system_prompt_file="prompts/system_prompt.txt"
        )
        
        skills_config = SkillsConfig(
            directory="skills"
        )
        
        agent_config = AgentConfig()
        
        return AppConfig(
            model=full_model_config,
            project=project_config,
            file_tools=file_tools_config,
            prompts=prompt_config,
            skills=skills_config,
            agent=agent_config
        )
    
    def test_should_enable_file_tools_with_config(self, mock_config, tmp_path):
        pool = AgentPool(
            config=mock_config,
            max_instances=1,
            roles_dir=str(tmp_path / "roles"),
            skills_dir=str(tmp_path / "skills")
        )
        
        assert pool._should_enable_file_tools() is True
    
    def test_should_enable_file_tools_disabled(self, mock_config, tmp_path):
        mock_config.file_tools.enabled = False
        
        pool = AgentPool(
            config=mock_config,
            max_instances=1,
            roles_dir=str(tmp_path / "roles"),
            skills_dir=str(tmp_path / "skills")
        )
        
        assert pool._should_enable_file_tools() is False
    
    def test_should_enable_file_tools_with_role_config(self, mock_config, tmp_path):
        role_file_tools = RoleFileToolsConfig(
            enabled=True,
            permissions={
                "default": PermissionMode.allow,
                "custom": {}
            }
        )
        
        role_config = RoleConfig(
            name="test-role",
            description="Test role",
            system_prompt_file="prompts/test.txt",
            file_tools=role_file_tools
        )
        
        pool = AgentPool(
            config=mock_config,
            max_instances=1,
            roles_dir=str(tmp_path / "roles"),
            skills_dir=str(tmp_path / "skills")
        )
        
        assert pool._should_enable_file_tools(role_config) is True
    
    def test_should_enable_file_tools_role_disabled(self, mock_config, tmp_path):
        role_file_tools = RoleFileToolsConfig(
            enabled=False
        )
        
        role_config = RoleConfig(
            name="test-role",
            description="Test role",
            system_prompt_file="prompts/test.txt",
            file_tools=role_file_tools
        )
        
        pool = AgentPool(
            config=mock_config,
            max_instances=1,
            roles_dir=str(tmp_path / "roles"),
            skills_dir=str(tmp_path / "skills")
        )
        
        assert pool._should_enable_file_tools(role_config) is False
    
    def test_create_file_tool_provider(self, mock_config, tmp_path):
        pool = AgentPool(
            config=mock_config,
            max_instances=1,
            roles_dir=str(tmp_path / "roles"),
            skills_dir=str(tmp_path / "skills")
        )
        
        provider = pool._create_file_tool_provider()
        
        assert provider is not None
        assert isinstance(provider, FileToolProvider)
        assert provider.is_available()
    
    def test_create_file_tool_provider_with_role_config(self, mock_config, tmp_path):
        project_root = tmp_path / "role_project"
        project_root.mkdir()
        
        workspace_config = WorkspaceConfig(
            main=project_root,
            additional=[],
            excluded=[]
        )
        
        role_file_tools = RoleFileToolsConfig(
            enabled=True,
            workspace=workspace_config,
            permissions={
                "default": PermissionMode.allow,
                "custom": {}
            }
        )
        
        role_config = RoleConfig(
            name="test-role",
            description="Test role",
            system_prompt_file="prompts/test.txt",
            file_tools=role_file_tools
        )
        
        pool = AgentPool(
            config=mock_config,
            max_instances=1,
            roles_dir=str(tmp_path / "roles"),
            skills_dir=str(tmp_path / "skills")
        )
        
        provider = pool._create_file_tool_provider(role_config)
        
        assert provider is not None
        assert isinstance(provider, FileToolProvider)
    
    def test_create_tool_registry_includes_file_tools(self, mock_config, tmp_path):
        pool = AgentPool(
            config=mock_config,
            max_instances=1,
            roles_dir=str(tmp_path / "roles"),
            skills_dir=str(tmp_path / "skills")
        )
        
        registry = pool._create_tool_registry()
        
        tools = registry.get_all_tools()
        tool_names = [tool.name for tool in tools]
        
        assert "file_read" in tool_names
        assert "file_write" in tool_names
        assert "file_list" in tool_names
    
    def test_create_tool_registry_without_file_tools(self, mock_config, tmp_path):
        mock_config.file_tools.enabled = False
        
        pool = AgentPool(
            config=mock_config,
            max_instances=1,
            roles_dir=str(tmp_path / "roles"),
            skills_dir=str(tmp_path / "skills")
        )
        
        registry = pool._create_tool_registry()
        
        tools = registry.get_all_tools()
        tool_names = [tool.name for tool in tools]
        
        assert "read_file" not in tool_names
        assert "write_file" not in tool_names
    
    @pytest.mark.asyncio
    async def test_create_instance_with_file_tools(self, mock_config, tmp_path):
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        
        pool = AgentPool(
            config=mock_config,
            max_instances=1,
            roles_dir=str(roles_dir),
            skills_dir=str(skills_dir)
        )
        
        await pool.initialize()
        
        instance = await pool.create_instance()
        
        assert instance is not None
        assert instance.tool_registry is not None
        
        tools = instance.tool_registry.get_all_tools()
        tool_names = [tool.name for tool in tools]
        
        assert "file_read" in tool_names
        assert "file_write" in tool_names


class TestFileToolsEndToEnd:
    @pytest.fixture
    def setup_project(self, tmp_path):
        project_root = tmp_path / "e2e_project"
        project_root.mkdir()
        
        src_dir = project_root / "src"
        src_dir.mkdir()
        
        tests_dir = project_root / "tests"
        tests_dir.mkdir()
        
        config_dir = project_root / "config"
        config_dir.mkdir()
        
        (src_dir / "main.py").write_text("print('hello')")
        (src_dir / "utils.py").write_text("def helper(): pass")
        (tests_dir / "test_main.py").write_text("def test_main(): pass")
        
        env_file = project_root / ".env"
        env_file.write_text("SECRET=123")
        
        return project_root
    
    def test_full_workflow(self, setup_project):
        project_root = setup_project
        
        workspace_config = WorkspaceConfig(
            main=project_root,
            additional=[],
            excluded=[".env", "*.log"]
        )
        
        project_config = ProjectConfig(
            name="e2e_project",
            root=project_root,
            workspace=workspace_config
        )
        
        file_tools_config = FileToolsConfig(
            enabled=True,
            permission_mode=PermissionMode.allow,
            custom_permissions={
                "delete": PermissionMode.deny
            },
            default_permissions=PermissionMode.allow,
            audit=True
        )
        
        provider = FileToolProvider(project_config, file_tools_config)
        
        registry = ToolRegistry()
        registry.register_provider(provider)
        
        tools = registry.get_all_tools()
        tools_dict = {tool.name: tool for tool in tools}
        
        assert len(tools) == 10
        
        main_py = project_root / "src" / "main.py"
        read_permission = provider.check_permission(str(main_py), OperationType.READ)
        assert read_permission.allowed is True
        
        write_permission = provider.check_permission(str(main_py), OperationType.WRITE)
        assert write_permission.allowed is True
        
        delete_permission = provider.check_permission(str(main_py), OperationType.DELETE)
        assert delete_permission.allowed is False
        
        env_file = project_root / ".env"
        env_permission = provider.check_permission(str(env_file), OperationType.READ)
        assert env_permission.allowed is False
        
        provider.log_success(
            tool_name="read_file",
            path=str(main_py),
            operation=OperationType.READ
        )
        
        provider.log_denied(
            tool_name="delete_file",
            path=str(main_py),
            operation=OperationType.DELETE,
            reason="Delete permission denied by policy"
        )
        
        entries = provider.audit_logger.query_by_path(str(main_py))
        assert len(entries) == 2
        
        success_entries = [e for e in entries if e.result == OperationResult.SUCCESS]
        denied_entries = [e for e in entries if e.result == OperationResult.DENIED]
        
        assert len(success_entries) == 1
        assert len(denied_entries) == 1
        
        provider.close()
