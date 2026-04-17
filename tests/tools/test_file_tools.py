import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.tools.file_tools.provider import FileToolProvider
from src.tools.file_tools.workspace import WorkspaceManager
from src.tools.file_tools.permission import (
    PermissionChecker,
    PermissionResult,
    PermissionStatus,
)
from src.tools.file_tools.audit import (
    AuditLogger,
    AuditConfig,
    OperationType,
    OperationResult,
)
from src.config.models import (
    ProjectConfig,
    WorkspaceConfig,
    FileToolsConfig,
    PermissionMode,
)


def _make_project_config(tmp_path, excluded=None):
    project_root = tmp_path / "test_project"
    project_root.mkdir(exist_ok=True)
    (project_root / "src").mkdir(exist_ok=True)
    (project_root / "tests").mkdir(exist_ok=True)

    workspace_config = WorkspaceConfig(
        main=project_root,
        additional=[],
        excluded=excluded or [".env", "node_modules/**"]
    )
    return ProjectConfig(
        name="test_project",
        root=project_root,
        workspace=workspace_config
    )


def _make_file_tools_config(**overrides):
    defaults = {
        "enabled": True,
        "permission_mode": PermissionMode.ask,
        "custom_permissions": {},
        "default_permissions": PermissionMode.ask,
        "audit": True,
    }
    defaults.update(overrides)
    return FileToolsConfig(**defaults)


class TestFileToolProviderToolList:
    """FileToolProvider 文件操作工具列表测试"""

    def test_enabled_returns_tools(self, tmp_path):
        project_config = _make_project_config(tmp_path)
        file_tools_config = _make_file_tools_config(enabled=True)
        provider = FileToolProvider(project_config, file_tools_config)
        tools = provider.get_tools()
        assert len(tools) > 0
        tool_names = [t.name for t in tools]
        assert "file_read" in tool_names
        assert "file_write" in tool_names
        assert "file_replace" in tool_names
        assert "file_list" in tool_names
        assert "file_search" in tool_names
        assert "file_exists" in tool_names
        assert "file_delete" in tool_names
        assert "file_mkdir" in tool_names
        provider.close()

    def test_disabled_returns_empty(self, tmp_path):
        project_config = _make_project_config(tmp_path)
        file_tools_config = _make_file_tools_config(enabled=False)
        provider = FileToolProvider(project_config, file_tools_config)
        tools = provider.get_tools()
        assert tools == []
        provider.close()

    def test_is_available_enabled(self, tmp_path):
        project_config = _make_project_config(tmp_path)
        file_tools_config = _make_file_tools_config(enabled=True)
        provider = FileToolProvider(project_config, file_tools_config)
        assert provider.is_available() is True
        provider.close()

    def test_is_available_disabled(self, tmp_path):
        project_config = _make_project_config(tmp_path)
        file_tools_config = _make_file_tools_config(enabled=False)
        provider = FileToolProvider(project_config, file_tools_config)
        assert provider.is_available() is False
        provider.close()


class TestWorkspaceManagerPathValidation:
    """WorkspaceManager 路径验证测试"""

    def test_resolve_absolute_path(self, tmp_path):
        project_config = _make_project_config(tmp_path)
        wm = WorkspaceManager(project_config)
        resolved = wm.resolve_path(tmp_path / "test_project" / "src")
        assert resolved.is_absolute()

    def test_resolve_relative_path(self, tmp_path):
        project_config = _make_project_config(tmp_path)
        wm = WorkspaceManager(project_config)
        resolved = wm.resolve_path("src")
        assert resolved.is_absolute()

    def test_resolve_empty_path_raises(self, tmp_path):
        project_config = _make_project_config(tmp_path)
        wm = WorkspaceManager(project_config)
        with pytest.raises(ValueError, match="empty"):
            wm.resolve_path("")

    def test_is_within_workspace_inside(self, tmp_path):
        project_config = _make_project_config(tmp_path)
        wm = WorkspaceManager(project_config)
        assert wm.is_within_workspace(tmp_path / "test_project" / "src") is True

    def test_is_within_workspace_outside(self, tmp_path):
        project_config = _make_project_config(tmp_path)
        wm = WorkspaceManager(project_config)
        assert wm.is_within_workspace(tmp_path / "other_project") is False

    def test_is_excluded_pattern(self, tmp_path):
        project_config = _make_project_config(tmp_path, excluded=[".env"])
        wm = WorkspaceManager(project_config)
        env_file = tmp_path / "test_project" / ".env"
        env_file.write_text("KEY=val")
        assert wm.is_excluded(env_file) is True

    def test_is_not_excluded_normal_file(self, tmp_path):
        project_config = _make_project_config(tmp_path, excluded=[".env"])
        wm = WorkspaceManager(project_config)
        normal_file = tmp_path / "test_project" / "src" / "main.py"
        normal_file.write_text("print('hello')")
        assert wm.is_excluded(normal_file) is False

    def test_validate_path_inside_workspace(self, tmp_path):
        project_config = _make_project_config(tmp_path)
        wm = WorkspaceManager(project_config)
        resolved = wm.validate_path("src")
        assert resolved.is_absolute()

    def test_validate_path_outside_raises_value_error(self, tmp_path):
        project_config = _make_project_config(tmp_path)
        wm = WorkspaceManager(project_config)
        with pytest.raises(ValueError, match="outside workspace"):
            wm.validate_path(tmp_path / "other_project" / "file.txt")

    def test_validate_path_excluded_raises_permission_error(self, tmp_path):
        project_config = _make_project_config(tmp_path, excluded=[".env"])
        wm = WorkspaceManager(project_config)
        env_file = tmp_path / "test_project" / ".env"
        env_file.write_text("KEY=val")
        with pytest.raises(PermissionError, match="excluded"):
            wm.validate_path(env_file)

    def test_get_workspace_roots(self, tmp_path):
        project_config = _make_project_config(tmp_path)
        wm = WorkspaceManager(project_config)
        roots = wm.get_workspace_roots()
        assert len(roots) >= 1
        assert roots[0].exists()

    def test_get_main_workspace(self, tmp_path):
        project_config = _make_project_config(tmp_path)
        wm = WorkspaceManager(project_config)
        main = wm.get_main_workspace()
        assert main.exists()

    def test_add_and_remove_excluded_pattern(self, tmp_path):
        project_config = _make_project_config(tmp_path)
        wm = WorkspaceManager(project_config)
        wm.add_excluded_pattern("*.log")
        assert "*.log" in wm.list_excluded_patterns()
        assert wm.remove_excluded_pattern("*.log") is True
        assert "*.log" not in wm.list_excluded_patterns()
        assert wm.remove_excluded_pattern("nonexistent") is False


class TestPermissionCheckerModes:
    """PermissionChecker 权限检查模式测试"""

    def _make_checker(self, tmp_path, **config_overrides):
        project_config = _make_project_config(tmp_path)
        wm = WorkspaceManager(project_config)
        config = _make_file_tools_config(**config_overrides)
        return PermissionChecker(config, wm)

    def test_read_is_allowed_by_default(self, tmp_path):
        checker = self._make_checker(tmp_path)
        result = checker.check("src/main.py", OperationType.READ)
        assert result.allowed is True
        assert result.status == PermissionStatus.ALLOWED

    def test_write_is_ask_by_default(self, tmp_path):
        checker = self._make_checker(tmp_path)
        result = checker.check("src/main.py", OperationType.WRITE)
        assert result.status == PermissionStatus.ASK
        assert result.requires_confirmation is True

    def test_delete_is_deny_by_default(self, tmp_path):
        checker = self._make_checker(tmp_path)
        result = checker.check("src/main.py", OperationType.DELETE)
        assert result.allowed is False
        assert result.status == PermissionStatus.DENIED

    def test_list_is_allowed_by_default(self, tmp_path):
        checker = self._make_checker(tmp_path)
        result = checker.check("src", OperationType.LIST)
        assert result.allowed is True
        assert result.status == PermissionStatus.ALLOWED

    def test_custom_permissions_override_default(self, tmp_path):
        custom = {"delete": PermissionMode.allow}
        checker = self._make_checker(tmp_path, custom_permissions=custom)
        result = checker.check("src/main.py", OperationType.DELETE)
        assert result.allowed is True

    def test_path_outside_workspace_denied(self, tmp_path):
        checker = self._make_checker(tmp_path)
        result = checker.check("/some/outside/path", OperationType.READ)
        assert result.allowed is False
        assert result.status == PermissionStatus.DENIED

    def test_empty_path_denied(self, tmp_path):
        checker = self._make_checker(tmp_path)
        result = checker.check("", OperationType.READ)
        assert result.allowed is False
        assert result.status == PermissionStatus.DENIED

    def test_is_operation_allowed(self, tmp_path):
        checker = self._make_checker(tmp_path)
        assert checker.is_operation_allowed(OperationType.READ) is True
        assert checker.is_operation_allowed(OperationType.DELETE) is False

    def test_is_write_operation(self, tmp_path):
        checker = self._make_checker(tmp_path)
        assert checker.is_write_operation(OperationType.WRITE) is True
        assert checker.is_write_operation(OperationType.READ) is False

    def test_is_dangerous_operation(self, tmp_path):
        checker = self._make_checker(tmp_path)
        assert checker.is_dangerous_operation(OperationType.DELETE) is True
        assert checker.is_dangerous_operation(OperationType.READ) is False

    def test_set_permission_mode(self, tmp_path):
        checker = self._make_checker(tmp_path)
        checker.set_permission_mode(OperationType.DELETE, PermissionMode.allow)
        assert checker.get_permission_mode(OperationType.DELETE) == PermissionMode.allow

    def test_get_all_permissions(self, tmp_path):
        checker = self._make_checker(tmp_path)
        perms = checker.get_all_permissions()
        assert isinstance(perms, dict)
        assert "read" in perms
        assert "delete" in perms

    def test_check_path_access(self, tmp_path):
        checker = self._make_checker(tmp_path)
        result = checker.check_path_access("src/main.py")
        assert isinstance(result, PermissionResult)

    def test_validate_for_operation_success(self, tmp_path):
        checker = self._make_checker(tmp_path)
        resolved = checker.validate_for_operation("src/main.py", OperationType.READ)
        assert resolved.is_absolute()

    def test_validate_for_operation_denied_raises(self, tmp_path):
        checker = self._make_checker(tmp_path)
        with pytest.raises(PermissionError):
            checker.validate_for_operation("src/main.py", OperationType.DELETE)

    def test_validate_for_operation_outside_raises_value_error(self, tmp_path):
        checker = self._make_checker(tmp_path)
        with pytest.raises(ValueError):
            checker.validate_for_operation("/outside/path", OperationType.READ)

    def test_permission_result_bool(self, tmp_path):
        checker = self._make_checker(tmp_path)
        allowed = checker.check("src/main.py", OperationType.READ)
        assert bool(allowed) is True
        denied = checker.check("src/main.py", OperationType.DELETE)
        assert bool(denied) is False

    def test_permission_result_to_dict(self, tmp_path):
        checker = self._make_checker(tmp_path)
        result = checker.check("src/main.py", OperationType.READ)
        d = result.to_dict()
        assert "allowed" in d
        assert "status" in d
        assert "path" in d
        assert "operation" in d


class TestAuditLogger:
    """AuditLogger 审计日志记录测试"""

    def test_log_success(self, tmp_path):
        log_file = tmp_path / "audit.log"
        config = AuditConfig(enabled=True, log_file=str(log_file))
        logger = AuditLogger(config)

        logger.log_success(
            tool_name="file_read",
            path="/test/path.txt",
            operation=OperationType.READ
        )
        logger.close()

        content = log_file.read_text(encoding="utf-8")
        assert "file_read" in content
        assert "success" in content

    def test_log_denied(self, tmp_path):
        log_file = tmp_path / "audit.log"
        config = AuditConfig(enabled=True, log_file=str(log_file))
        logger = AuditLogger(config)

        logger.log_denied(
            tool_name="file_delete",
            path="/test/secret.txt",
            operation=OperationType.DELETE,
            reason="Permission denied"
        )
        logger.close()

        content = log_file.read_text(encoding="utf-8")
        assert "denied" in content
        assert "Permission denied" in content

    def test_log_error(self, tmp_path):
        log_file = tmp_path / "audit.log"
        config = AuditConfig(enabled=True, log_file=str(log_file))
        logger = AuditLogger(config)

        logger.log_error(
            tool_name="file_write",
            path="/test/output.txt",
            operation=OperationType.WRITE,
            error="Disk full"
        )
        logger.close()

        content = log_file.read_text(encoding="utf-8")
        assert "error" in content
        assert "Disk full" in content

    def test_disabled_logger_no_output(self, tmp_path):
        log_file = tmp_path / "audit.log"
        config = AuditConfig(enabled=False, log_file=str(log_file))
        logger = AuditLogger(config)

        logger.log_success(
            tool_name="file_read",
            path="/test/path.txt",
            operation=OperationType.READ
        )
        logger.close()

        assert not log_file.exists() or log_file.read_text(encoding="utf-8").strip() == ""

    def test_query_returns_entries(self, tmp_path):
        log_file = tmp_path / "audit.log"
        config = AuditConfig(enabled=True, log_file=str(log_file))
        logger = AuditLogger(config)

        logger.log_success(
            tool_name="file_read",
            path="/test/path.txt",
            operation=OperationType.READ
        )
        logger.log_denied(
            tool_name="file_delete",
            path="/test/secret.txt",
            operation=OperationType.DELETE,
            reason="No permission"
        )
        logger.close()

        logger2 = AuditLogger(config)
        entries = logger2.query()
        assert len(entries) == 2
        logger2.close()

    def test_query_by_path(self, tmp_path):
        log_file = tmp_path / "audit.log"
        config = AuditConfig(enabled=True, log_file=str(log_file))
        logger = AuditLogger(config)

        logger.log_success(
            tool_name="file_read",
            path="/test/path.txt",
            operation=OperationType.READ
        )
        logger.log_success(
            tool_name="file_read",
            path="/other/path.txt",
            operation=OperationType.READ
        )
        logger.close()

        logger2 = AuditLogger(config)
        entries = logger2.query_by_path("/test/path.txt")
        assert len(entries) == 1
        logger2.close()

    def test_query_by_operation(self, tmp_path):
        log_file = tmp_path / "audit.log"
        config = AuditConfig(enabled=True, log_file=str(log_file))
        logger = AuditLogger(config)

        logger.log_success(
            tool_name="file_read",
            path="/test/path.txt",
            operation=OperationType.READ
        )
        logger.log_success(
            tool_name="file_write",
            path="/test/path.txt",
            operation=OperationType.WRITE
        )
        logger.close()

        logger2 = AuditLogger(config)
        entries = logger2.query_by_operation(OperationType.READ)
        assert len(entries) == 1
        logger2.close()

    def test_query_denied(self, tmp_path):
        log_file = tmp_path / "audit.log"
        config = AuditConfig(enabled=True, log_file=str(log_file))
        logger = AuditLogger(config)

        logger.log_success(
            tool_name="file_read",
            path="/test/path.txt",
            operation=OperationType.READ
        )
        logger.log_denied(
            tool_name="file_delete",
            path="/test/secret.txt",
            operation=OperationType.DELETE,
            reason="No permission"
        )
        logger.close()

        logger2 = AuditLogger(config)
        entries = logger2.query_denied()
        assert len(entries) == 1
        assert entries[0].result == OperationResult.DENIED
        logger2.close()

    def test_get_statistics(self, tmp_path):
        log_file = tmp_path / "audit.log"
        config = AuditConfig(enabled=True, log_file=str(log_file))
        logger = AuditLogger(config)

        logger.log_success(
            tool_name="file_read",
            path="/test/path.txt",
            operation=OperationType.READ
        )
        logger.log_denied(
            tool_name="file_delete",
            path="/test/secret.txt",
            operation=OperationType.DELETE,
            reason="No permission"
        )
        logger.close()

        logger2 = AuditLogger(config)
        stats = logger2.get_statistics()
        assert stats["total_count"] == 2
        assert "read" in stats["by_operation"]
        assert "success" in stats["by_result"]
        logger2.close()

    def test_clear(self, tmp_path):
        log_file = tmp_path / "audit.log"
        config = AuditConfig(enabled=True, log_file=str(log_file))
        logger = AuditLogger(config)

        logger.log_success(
            tool_name="file_read",
            path="/test/path.txt",
            operation=OperationType.READ
        )
        logger.close()

        logger2 = AuditLogger(config)
        logger2.clear()
        logger2.close()

        logger3 = AuditLogger(config)
        entries = logger3.query()
        assert len(entries) == 0
        logger3.close()

    def test_query_nonexistent_file(self, tmp_path):
        log_file = tmp_path / "nonexistent.log"
        config = AuditConfig(enabled=True, log_file=str(log_file))
        logger = AuditLogger(config)
        entries = logger.query()
        assert entries == []
        logger.close()


class TestFileToolProviderDelegation:
    """FileToolProvider 委托方法测试"""

    def test_check_permission(self, tmp_path):
        project_config = _make_project_config(tmp_path)
        file_tools_config = _make_file_tools_config()
        provider = FileToolProvider(project_config, file_tools_config)

        result = provider.check_permission("src/main.py", OperationType.READ)
        assert isinstance(result, PermissionResult)
        provider.close()

    def test_resolve_path(self, tmp_path):
        project_config = _make_project_config(tmp_path)
        file_tools_config = _make_file_tools_config()
        provider = FileToolProvider(project_config, file_tools_config)

        resolved = provider.resolve_path("src/main.py")
        assert resolved.is_absolute()
        provider.close()

    def test_is_within_workspace(self, tmp_path):
        project_config = _make_project_config(tmp_path)
        file_tools_config = _make_file_tools_config()
        provider = FileToolProvider(project_config, file_tools_config)

        assert provider.is_within_workspace("src/main.py") is True
        provider.close()

    def test_properties(self, tmp_path):
        project_config = _make_project_config(tmp_path)
        file_tools_config = _make_file_tools_config()
        provider = FileToolProvider(project_config, file_tools_config)

        assert isinstance(provider.workspace_manager, WorkspaceManager)
        assert isinstance(provider.permission_checker, PermissionChecker)
        assert isinstance(provider.audit_logger, AuditLogger)
        assert isinstance(provider.config, FileToolsConfig)
        provider.close()

    def test_log_audit(self, tmp_path):
        project_config = _make_project_config(tmp_path)
        file_tools_config = _make_file_tools_config()
        provider = FileToolProvider(project_config, file_tools_config)

        provider.log_success("file_read", "src/main.py", OperationType.READ)
        provider.log_denied("file_delete", "src/main.py", OperationType.DELETE, "denied")
        provider.log_error("file_write", "src/main.py", OperationType.WRITE, "error")
        provider.close()
