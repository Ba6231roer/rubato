import pytest
import tempfile
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.file_tools.provider import FileToolProvider
from src.tools.file_tools.audit import OperationType, OperationResult
from src.config.models import (
    ProjectConfig,
    WorkspaceConfig,
    FileToolsConfig,
    PermissionMode
)


class TestFileToolProvider:
    """FileToolProvider 测试类"""
    
    @pytest.fixture
    def temp_project(self, tmp_path):
        """创建临时项目结构"""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        
        src_dir = project_root / "src"
        src_dir.mkdir()
        
        tests_dir = project_root / "tests"
        tests_dir.mkdir()
        
        config_dir = project_root / "config"
        config_dir.mkdir()
        
        env_file = project_root / ".env"
        env_file.write_text("SECRET_KEY=secret")
        
        node_modules = project_root / "node_modules"
        node_modules.mkdir()
        
        return project_root
    
    @pytest.fixture
    def workspace_config(self, temp_project):
        """创建 workspace 配置"""
        return WorkspaceConfig(
            main=temp_project,
            additional=[],
            excluded=[".env", "node_modules/**", "**/__pycache__/**", "*.log"]
        )
    
    @pytest.fixture
    def project_config(self, temp_project, workspace_config):
        """创建项目配置"""
        return ProjectConfig(
            name="test_project",
            root=temp_project,
            workspace=workspace_config
        )
    
    @pytest.fixture
    def file_tools_config(self):
        """创建文件工具配置"""
        return FileToolsConfig(
            enabled=True,
            permission_mode=PermissionMode.ask,
            custom_permissions={},
            default_permissions=PermissionMode.ask,
            audit=True
        )
    
    @pytest.fixture
    def disabled_file_tools_config(self):
        """创建禁用的文件工具配置"""
        return FileToolsConfig(
            enabled=False,
            permission_mode=PermissionMode.ask,
            custom_permissions={},
            default_permissions=PermissionMode.ask,
            audit=True
        )
    
    @pytest.fixture
    def provider(self, project_config, file_tools_config):
        """创建 FileToolProvider 实例"""
        return FileToolProvider(project_config, file_tools_config)
    
    def test_init(self, project_config, file_tools_config):
        """测试初始化"""
        provider = FileToolProvider(project_config, file_tools_config)
        
        assert provider._project_config == project_config
        assert provider._file_tools_config == file_tools_config
        assert provider._workspace_manager is not None
        assert provider._permission_checker is not None
        assert provider._audit_logger is not None
        assert len(provider._tools) == 10
    
    def test_init_with_disabled_tools(self, project_config, disabled_file_tools_config):
        """测试禁用工具时的初始化"""
        provider = FileToolProvider(project_config, disabled_file_tools_config)
        
        assert provider._file_tools_config.enabled is False
        assert provider._tools == []
    
    def test_is_available_enabled(self, provider):
        """测试工具可用性检查（启用状态）"""
        assert provider.is_available() is True
    
    def test_is_available_disabled(self, project_config, disabled_file_tools_config):
        """测试工具可用性检查（禁用状态）"""
        provider = FileToolProvider(project_config, disabled_file_tools_config)
        assert provider.is_available() is False
    
    def test_is_available_nonexistent_workspace(self, tmp_path, file_tools_config):
        """测试 workspace 不存在时的可用性检查"""
        nonexistent_path = tmp_path / "nonexistent"
        workspace_config = WorkspaceConfig(
            main=nonexistent_path,
            additional=[],
            excluded=[]
        )
        project_config = ProjectConfig(
            name="test_project",
            root=tmp_path,
            workspace=workspace_config
        )
        
        provider = FileToolProvider(project_config, file_tools_config)
        assert provider.is_available() is False
    
    def test_get_tools_when_available(self, provider):
        """测试获取工具列表（可用状态）"""
        tools = provider.get_tools()
        
        assert isinstance(tools, list)
        assert len(tools) == 10
    
    def test_get_tools_when_disabled(self, project_config, disabled_file_tools_config):
        """测试获取工具列表（禁用状态）"""
        provider = FileToolProvider(project_config, disabled_file_tools_config)
        tools = provider.get_tools()
        
        assert isinstance(tools, list)
        assert len(tools) == 0
    
    def test_check_permission(self, provider, temp_project):
        """测试权限检查"""
        test_file = temp_project / "src" / "test.py"
        test_file.write_text("print('hello')")
        
        result = provider.check_permission(
            str(test_file),
            OperationType.READ
        )
        
        assert result.allowed is True
        assert result.operation == OperationType.READ
    
    def test_check_permission_excluded_path(self, provider, temp_project):
        """测试排除路径的权限检查"""
        env_file = temp_project / ".env"
        
        result = provider.check_permission(
            str(env_file),
            OperationType.READ
        )
        
        assert result.allowed is False
        assert "excluded" in result.reason.lower()
    
    def test_check_permission_outside_workspace(self, provider, tmp_path):
        """测试 workspace 外路径的权限检查"""
        outside_file = tmp_path / "outside.txt"
        outside_file.write_text("outside")
        
        result = provider.check_permission(
            str(outside_file),
            OperationType.READ
        )
        
        assert result.allowed is False
        assert "outside workspace" in result.reason.lower()
    
    def test_log_audit(self, provider, temp_project):
        """测试审计日志记录"""
        test_file = temp_project / "src" / "test.py"
        test_file.write_text("print('hello')")
        
        provider.log_audit(
            tool_name="test_tool",
            path=str(test_file),
            operation=OperationType.READ,
            result=OperationResult.SUCCESS
        )
        
        entries = provider._audit_logger.query_by_path(str(test_file))
        assert len(entries) > 0
        assert entries[0].tool_name == "test_tool"
        assert entries[0].operation == OperationType.READ
        assert entries[0].result == OperationResult.SUCCESS
    
    def test_log_success(self, provider, temp_project):
        """测试成功操作日志记录"""
        test_file = temp_project / "src" / "test.py"
        test_file.write_text("print('hello')")
        
        provider.log_success(
            tool_name="test_tool",
            path=str(test_file),
            operation=OperationType.READ
        )
        
        entries = provider._audit_logger.query_by_path(str(test_file))
        assert len(entries) > 0
        assert entries[0].result == OperationResult.SUCCESS
    
    def test_log_denied(self, provider, temp_project):
        """测试拒绝操作日志记录"""
        test_file = temp_project / "src" / "test.py"
        test_file.write_text("print('hello')")
        
        provider.log_denied(
            tool_name="test_tool",
            path=str(test_file),
            operation=OperationType.DELETE,
            reason="Operation denied by policy"
        )
        
        entries = provider._audit_logger.query_by_path(str(test_file))
        assert len(entries) > 0
        assert entries[0].result == OperationResult.DENIED
        assert "denied by policy" in entries[0].error_message
    
    def test_log_error(self, provider, temp_project):
        """测试错误操作日志记录"""
        test_file = temp_project / "src" / "test.py"
        test_file.write_text("print('hello')")
        
        provider.log_error(
            tool_name="test_tool",
            path=str(test_file),
            operation=OperationType.READ,
            error="File not found"
        )
        
        entries = provider._audit_logger.query_by_path(str(test_file))
        assert len(entries) > 0
        assert entries[0].result == OperationResult.ERROR
        assert "File not found" in entries[0].error_message
    
    def test_resolve_path(self, provider, temp_project):
        """测试路径解析"""
        relative_path = "src/test.py"
        resolved = provider.resolve_path(relative_path)
        
        assert resolved.is_absolute()
        assert resolved == temp_project / "src" / "test.py"
    
    def test_resolve_path_absolute(self, provider, temp_project):
        """测试绝对路径解析"""
        absolute_path = temp_project / "src" / "test.py"
        resolved = provider.resolve_path(absolute_path)
        
        assert resolved.is_absolute()
        assert resolved == absolute_path
    
    def test_validate_path(self, provider, temp_project):
        """测试路径验证"""
        test_file = temp_project / "src" / "test.py"
        test_file.write_text("print('hello')")
        
        validated = provider.validate_path(str(test_file))
        
        assert validated.is_absolute()
        assert validated == test_file.resolve()
    
    def test_validate_path_outside_workspace(self, provider, tmp_path):
        """测试验证 workspace 外路径"""
        outside_file = tmp_path / "outside.txt"
        outside_file.write_text("outside")
        
        with pytest.raises(ValueError, match="outside workspace"):
            provider.validate_path(str(outside_file))
    
    def test_validate_path_excluded(self, provider, temp_project):
        """测试验证排除路径"""
        env_file = temp_project / ".env"
        
        with pytest.raises(PermissionError, match="excluded"):
            provider.validate_path(str(env_file))
    
    def test_is_within_workspace(self, provider, temp_project):
        """测试检查路径是否在 workspace 内"""
        inside_file = temp_project / "src" / "test.py"
        assert provider.is_within_workspace(str(inside_file)) is True
    
    def test_is_within_workspace_outside(self, provider, tmp_path):
        """测试检查 workspace 外路径"""
        outside_file = tmp_path / "outside.txt"
        assert provider.is_within_workspace(str(outside_file)) is False
    
    def test_is_excluded(self, provider, temp_project):
        """测试检查路径是否被排除"""
        env_file = temp_project / ".env"
        assert provider.is_excluded(str(env_file)) is True
        
        src_file = temp_project / "src" / "test.py"
        assert provider.is_excluded(str(src_file)) is False
    
    def test_workspace_manager_property(self, provider):
        """测试 workspace_manager 属性"""
        manager = provider.workspace_manager
        assert manager is not None
        assert manager == provider._workspace_manager
    
    def test_permission_checker_property(self, provider):
        """测试 permission_checker 属性"""
        checker = provider.permission_checker
        assert checker is not None
        assert checker == provider._permission_checker
    
    def test_audit_logger_property(self, provider):
        """测试 audit_logger 属性"""
        logger = provider.audit_logger
        assert logger is not None
        assert logger == provider._audit_logger
    
    def test_config_property(self, provider, file_tools_config):
        """测试 config 属性"""
        config = provider.config
        assert config is not None
        assert config == file_tools_config
    
    def test_close(self, provider):
        """测试关闭资源"""
        provider.close()
        
        assert provider._audit_logger._file_handler is None
    
    def test_integration_permission_and_audit(self, provider, temp_project):
        """集成测试：权限检查和审计日志"""
        test_file = temp_project / "src" / "test.py"
        test_file.write_text("print('hello')")
        
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
        
        entries = provider._audit_logger.query_by_path(str(test_file))
        assert len(entries) > 0
        assert entries[0].result == OperationResult.SUCCESS
    
    def test_integration_denied_operation(self, provider, temp_project):
        """集成测试：拒绝操作"""
        env_file = temp_project / ".env"
        
        permission_result = provider.check_permission(
            str(env_file),
            OperationType.READ
        )
        
        assert permission_result.allowed is False
        
        provider.log_denied(
            tool_name="read_file",
            path=str(env_file),
            operation=OperationType.READ,
            reason=permission_result.reason
        )
        
        entries = provider._audit_logger.query_by_path(str(env_file))
        assert len(entries) > 0
        assert entries[0].result == OperationResult.DENIED
