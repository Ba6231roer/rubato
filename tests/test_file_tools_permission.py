import pytest
import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.file_tools.permission import (
    PermissionChecker,
    PermissionResult,
    PermissionStatus
)
from src.tools.file_tools.workspace import WorkspaceManager
from src.tools.file_tools.audit import OperationType
from src.config.models import (
    FileToolsConfig,
    PermissionMode,
    ProjectConfig,
    WorkspaceConfig
)


class TestPermissionResult:
    """PermissionResult 测试类"""
    
    def test_permission_result_allowed(self, tmp_path):
        """测试允许的结果"""
        result = PermissionResult(
            allowed=True,
            status=PermissionStatus.ALLOWED,
            path=tmp_path / "test.py",
            operation=OperationType.READ
        )
        
        assert result.allowed is True
        assert result.status == PermissionStatus.ALLOWED
        assert bool(result) is True
        assert result.requires_confirmation is False
    
    def test_permission_result_denied(self, tmp_path):
        """测试拒绝的结果"""
        result = PermissionResult(
            allowed=False,
            status=PermissionStatus.DENIED,
            path=tmp_path / "test.py",
            operation=OperationType.DELETE,
            reason="Operation denied"
        )
        
        assert result.allowed is False
        assert result.status == PermissionStatus.DENIED
        assert bool(result) is False
        assert result.reason == "Operation denied"
    
    def test_permission_result_ask(self, tmp_path):
        """测试需要确认的结果"""
        result = PermissionResult(
            allowed=True,
            status=PermissionStatus.ASK,
            path=tmp_path / "test.py",
            operation=OperationType.WRITE,
            requires_confirmation=True
        )
        
        assert result.allowed is True
        assert result.requires_confirmation is True
    
    def test_permission_result_to_dict(self, tmp_path):
        """测试转换为字典"""
        test_path = tmp_path / "test.py"
        result = PermissionResult(
            allowed=True,
            status=PermissionStatus.ALLOWED,
            path=test_path,
            operation=OperationType.READ,
            resolved_path=test_path.resolve()
        )
        
        d = result.to_dict()
        
        assert d["allowed"] is True
        assert d["status"] == PermissionStatus.ALLOWED
        assert d["path"] == str(test_path)
        assert d["operation"] == "read"
        assert d["resolved_path"] == str(test_path.resolve())


class TestPermissionChecker:
    """PermissionChecker 测试类"""
    
    @pytest.fixture
    def temp_project(self, tmp_path):
        """创建临时项目结构"""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        
        src_dir = project_root / "src"
        src_dir.mkdir()
        
        tests_dir = project_root / "tests"
        tests_dir.mkdir()
        
        env_file = project_root / ".env"
        env_file.write_text("SECRET_KEY=secret")
        
        return project_root
    
    @pytest.fixture
    def workspace_config(self, temp_project):
        """创建 workspace 配置"""
        return WorkspaceConfig(
            main=temp_project,
            additional=[],
            excluded=[".env", "*.log", "node_modules/**"]
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
    def workspace_manager(self, project_config):
        """创建 WorkspaceManager 实例"""
        return WorkspaceManager(project_config)
    
    @pytest.fixture
    def file_tools_config(self):
        """创建 FileToolsConfig 实例"""
        return FileToolsConfig(
            enabled=True,
            permission_mode=PermissionMode.ask,
            custom_permissions={},
            default_permissions=PermissionMode.ask
        )
    
    @pytest.fixture
    def permission_checker(self, file_tools_config, workspace_manager):
        """创建 PermissionChecker 实例"""
        return PermissionChecker(file_tools_config, workspace_manager)
    
    def test_init_permission_checker(self, permission_checker):
        """测试 PermissionChecker 初始化"""
        assert permission_checker is not None
        assert permission_checker.workspace_manager is not None
        assert permission_checker.config is not None
    
    def test_default_permissions(self, permission_checker):
        """测试默认权限配置"""
        permissions = permission_checker.get_all_permissions()
        
        assert permissions["read"] == PermissionMode.allow
        assert permissions["list"] == PermissionMode.allow
        assert permissions["exists"] == PermissionMode.allow
        assert permissions["search"] == PermissionMode.allow
        assert permissions["write"] == PermissionMode.ask
        assert permissions["replace"] == PermissionMode.ask
        assert permissions["delete"] == PermissionMode.deny
    
    def test_custom_permissions(self, workspace_manager, temp_project):
        """测试自定义权限配置"""
        config = FileToolsConfig(
            enabled=True,
            permission_mode=PermissionMode.ask,
            custom_permissions={
                "delete": PermissionMode.ask,
                "write": PermissionMode.deny
            }
        )
        
        checker = PermissionChecker(config, workspace_manager)
        permissions = checker.get_all_permissions()
        
        assert permissions["delete"] == PermissionMode.ask
        assert permissions["write"] == PermissionMode.deny
    
    def test_check_read_operation_allowed(self, permission_checker, temp_project):
        """测试读操作权限检查"""
        test_file = temp_project / "src" / "main.py"
        result = permission_checker.check(test_file, OperationType.READ)
        
        assert result.allowed is True
        assert result.status == PermissionStatus.ALLOWED
        assert result.requires_confirmation is False
    
    def test_check_write_operation_requires_confirmation(self, permission_checker, temp_project):
        """测试写操作需要确认"""
        test_file = temp_project / "src" / "main.py"
        result = permission_checker.check(test_file, OperationType.WRITE)
        
        assert result.allowed is True
        assert result.status == PermissionStatus.ASK
        assert result.requires_confirmation is True
    
    def test_check_delete_operation_denied(self, permission_checker, temp_project):
        """测试删除操作被拒绝"""
        test_file = temp_project / "src" / "main.py"
        result = permission_checker.check(test_file, OperationType.DELETE)
        
        assert result.allowed is False
        assert result.status == PermissionStatus.DENIED
        assert "denied" in result.reason.lower()
    
    def test_check_path_outside_workspace(self, permission_checker, tmp_path):
        """测试 workspace 外路径被拒绝"""
        outside_path = tmp_path / "outside" / "file.txt"
        result = permission_checker.check(outside_path, OperationType.READ)
        
        assert result.allowed is False
        assert result.status == PermissionStatus.DENIED
        assert "outside workspace" in result.reason.lower()
    
    def test_check_excluded_path(self, permission_checker, temp_project):
        """测试排除路径被拒绝"""
        env_path = temp_project / ".env"
        result = permission_checker.check(env_path, OperationType.READ)
        
        assert result.allowed is False
        assert result.status == PermissionStatus.DENIED
        assert "excluded" in result.reason.lower()
    
    def test_check_empty_path(self, permission_checker):
        """测试空路径被拒绝"""
        result = permission_checker.check("", OperationType.READ)
        
        assert result.allowed is False
        assert result.status == PermissionStatus.DENIED
    
    def test_is_operation_allowed(self, permission_checker):
        """测试操作类型是否允许"""
        assert permission_checker.is_operation_allowed(OperationType.READ) is True
        assert permission_checker.is_operation_allowed(OperationType.WRITE) is True
        assert permission_checker.is_operation_allowed(OperationType.DELETE) is False
    
    def test_is_write_operation(self, permission_checker):
        """测试写操作判断"""
        assert permission_checker.is_write_operation(OperationType.WRITE) is True
        assert permission_checker.is_write_operation(OperationType.DELETE) is True
        assert permission_checker.is_write_operation(OperationType.READ) is False
        assert permission_checker.is_write_operation(OperationType.LIST) is False
    
    def test_is_dangerous_operation(self, permission_checker):
        """测试危险操作判断"""
        assert permission_checker.is_dangerous_operation(OperationType.DELETE) is True
        assert permission_checker.is_dangerous_operation(OperationType.MOVE) is True
        assert permission_checker.is_dangerous_operation(OperationType.READ) is False
        assert permission_checker.is_dangerous_operation(OperationType.WRITE) is False
    
    def test_get_permission_mode(self, permission_checker):
        """测试获取权限模式"""
        assert permission_checker.get_permission_mode(OperationType.READ) == PermissionMode.allow
        assert permission_checker.get_permission_mode(OperationType.WRITE) == PermissionMode.ask
        assert permission_checker.get_permission_mode(OperationType.DELETE) == PermissionMode.deny
    
    def test_set_permission_mode(self, permission_checker):
        """测试动态设置权限模式"""
        permission_checker.set_permission_mode(OperationType.DELETE, PermissionMode.ask)
        
        assert permission_checker.get_permission_mode(OperationType.DELETE) == PermissionMode.ask
        
        result = permission_checker.check("test.py", OperationType.DELETE)
        assert result.status == PermissionStatus.ASK
    
    def test_check_path_access(self, permission_checker, temp_project):
        """测试路径访问权限检查"""
        test_file = temp_project / "src" / "main.py"
        result = permission_checker.check_path_access(test_file)
        
        assert result.allowed is True
        assert result.operation == OperationType.READ
    
    def test_validate_for_operation_success(self, permission_checker, temp_project):
        """测试验证操作路径成功"""
        test_file = temp_project / "src" / "main.py"
        resolved = permission_checker.validate_for_operation(test_file, OperationType.READ)
        
        assert resolved == test_file.resolve()
    
    def test_validate_for_operation_outside_workspace(self, permission_checker, tmp_path):
        """测试验证 workspace 外路径抛出异常"""
        outside_path = tmp_path / "outside" / "file.txt"
        
        with pytest.raises(ValueError, match="outside workspace"):
            permission_checker.validate_for_operation(outside_path, OperationType.READ)
    
    def test_validate_for_operation_excluded(self, permission_checker, temp_project):
        """测试验证排除路径抛出异常"""
        env_path = temp_project / ".env"
        
        with pytest.raises(PermissionError, match="excluded"):
            permission_checker.validate_for_operation(env_path, OperationType.READ)
    
    def test_validate_for_operation_denied(self, permission_checker, temp_project):
        """测试验证拒绝操作抛出异常"""
        test_file = temp_project / "src" / "main.py"
        
        with pytest.raises(PermissionError, match="denied"):
            permission_checker.validate_for_operation(test_file, OperationType.DELETE)
    
    def test_relative_path_resolution(self, permission_checker, temp_project):
        """测试相对路径解析"""
        result = permission_checker.check("src/main.py", OperationType.READ)
        
        assert result.allowed is True
        assert result.resolved_path == (temp_project / "src" / "main.py").resolve()
    
    def test_wildcard_excluded_path(self, permission_checker, temp_project):
        """测试通配符排除路径"""
        log_file = temp_project / "debug.log"
        result = permission_checker.check(log_file, OperationType.READ)
        
        assert result.allowed is False
        assert "excluded" in result.reason.lower()


class TestPermissionCheckerIntegration:
    """PermissionChecker 集成测试"""
    
    @pytest.fixture
    def multi_workspace_setup(self, tmp_path):
        """创建多 workspace 设置"""
        main_workspace = tmp_path / "main"
        main_workspace.mkdir()
        (main_workspace / "src").mkdir()
        
        additional_workspace = tmp_path / "additional"
        additional_workspace.mkdir()
        (additional_workspace / "lib").mkdir()
        
        workspace_config = WorkspaceConfig(
            main=main_workspace,
            additional=[additional_workspace],
            excluded=["*.tmp", "**/secrets/**"]
        )
        
        project_config = ProjectConfig(
            name="multi_project",
            root=main_workspace,
            workspace=workspace_config
        )
        
        workspace_manager = WorkspaceManager(project_config)
        
        file_tools_config = FileToolsConfig(
            enabled=True,
            permission_mode=PermissionMode.ask,
            custom_permissions={}
        )
        
        permission_checker = PermissionChecker(file_tools_config, workspace_manager)
        
        return {
            "main_workspace": main_workspace,
            "additional_workspace": additional_workspace,
            "workspace_manager": workspace_manager,
            "permission_checker": permission_checker
        }
    
    def test_main_workspace_access(self, multi_workspace_setup):
        """测试主 workspace 访问"""
        checker = multi_workspace_setup["permission_checker"]
        main = multi_workspace_setup["main_workspace"]
        
        result = checker.check(main / "src" / "main.py", OperationType.READ)
        
        assert result.allowed is True
    
    def test_additional_workspace_access(self, multi_workspace_setup):
        """测试额外 workspace 访问"""
        checker = multi_workspace_setup["permission_checker"]
        additional = multi_workspace_setup["additional_workspace"]
        
        result = checker.check(additional / "lib" / "helper.py", OperationType.READ)
        
        assert result.allowed is True
    
    def test_outside_all_workspaces_denied(self, multi_workspace_setup, tmp_path):
        """测试所有 workspace 外路径被拒绝"""
        checker = multi_workspace_setup["permission_checker"]
        outside = tmp_path / "outside" / "file.txt"
        
        result = checker.check(outside, OperationType.READ)
        
        assert result.allowed is False
        assert "outside workspace" in result.reason.lower()
    
    def test_excluded_pattern_in_any_workspace(self, multi_workspace_setup):
        """测试排除模式在任何 workspace 中生效"""
        checker = multi_workspace_setup["permission_checker"]
        main = multi_workspace_setup["main_workspace"]
        
        tmp_file = main / "temp.tmp"
        result = checker.check(tmp_file, OperationType.READ)
        
        assert result.allowed is False
        assert "excluded" in result.reason.lower()
    
    def test_double_star_exclusion(self, multi_workspace_setup):
        """测试 ** 通配符排除"""
        checker = multi_workspace_setup["permission_checker"]
        main = multi_workspace_setup["main_workspace"]
        
        secrets_dir = main / "config" / "secrets"
        secrets_dir.mkdir(parents=True)
        secret_file = secrets_dir / "key.txt"
        
        result = checker.check(secret_file, OperationType.READ)
        
        assert result.allowed is False


class TestPermissionCheckerEdgeCases:
    """PermissionChecker 边界情况测试"""
    
    @pytest.fixture
    def setup(self, tmp_path):
        """创建测试环境"""
        project_root = tmp_path / "project"
        project_root.mkdir()
        
        workspace_config = WorkspaceConfig(
            main=project_root,
            additional=[],
            excluded=[]
        )
        
        project_config = ProjectConfig(
            name="edge_project",
            root=project_root,
            workspace=workspace_config
        )
        
        workspace_manager = WorkspaceManager(project_config)
        
        file_tools_config = FileToolsConfig(
            enabled=True,
            permission_mode=PermissionMode.ask,
            custom_permissions={}
        )
        
        return PermissionChecker(file_tools_config, workspace_manager)
    
    def test_path_with_parent_references(self, setup, tmp_path):
        """测试包含父目录引用的路径"""
        project = tmp_path / "project"
        (project / "src").mkdir()
        
        result = setup.check(project / "src" / ".." / "src" / "main.py", OperationType.READ)
        
        assert result.allowed is True
    
    def test_unicode_path(self, setup, tmp_path):
        """测试 Unicode 路径"""
        project = tmp_path / "project"
        unicode_file = project / "文件" / "测试.py"
        unicode_file.parent.mkdir(parents=True, exist_ok=True)
        
        result = setup.check(unicode_file, OperationType.READ)
        
        assert result.allowed is True
    
    def test_all_operation_types(self, setup, tmp_path):
        """测试所有操作类型"""
        project = tmp_path / "project"
        test_file = project / "test.py"
        
        operations = [
            (OperationType.READ, True, PermissionStatus.ALLOWED),
            (OperationType.LIST, True, PermissionStatus.ALLOWED),
            (OperationType.EXISTS, True, PermissionStatus.ALLOWED),
            (OperationType.SEARCH, True, PermissionStatus.ALLOWED),
            (OperationType.WRITE, True, PermissionStatus.ASK),
            (OperationType.REPLACE, True, PermissionStatus.ASK),
            (OperationType.DELETE, False, PermissionStatus.DENIED),
            (OperationType.COPY, True, PermissionStatus.ASK),
            (OperationType.MOVE, True, PermissionStatus.ASK),
            (OperationType.MKDIR, True, PermissionStatus.ASK),
        ]
        
        for op, expected_allowed, expected_status in operations:
            result = setup.check(test_file, op)
            assert result.allowed == expected_allowed, f"Failed for {op.value}"
            assert result.status == expected_status, f"Failed status for {op.value}"
    
    def test_permission_result_with_none_resolved_path(self, tmp_path):
        """测试 resolved_path 为 None 的情况"""
        result = PermissionResult(
            allowed=False,
            status=PermissionStatus.DENIED,
            path=tmp_path / "nonexistent",
            operation=OperationType.READ,
            reason="Invalid path"
        )
        
        d = result.to_dict()
        assert d["resolved_path"] is None


class TestPermissionModes:
    """权限模式测试"""
    
    @pytest.fixture
    def create_checker_with_mode(self, tmp_path):
        """创建指定权限模式的检查器"""
        def _create(mode: PermissionMode, custom_perms=None):
            project_root = tmp_path / "project"
            project_root.mkdir()
            
            workspace_config = WorkspaceConfig(
                main=project_root,
                additional=[],
                excluded=[]
            )
            
            project_config = ProjectConfig(
                name="mode_project",
                root=project_root,
                workspace=workspace_config
            )
            
            workspace_manager = WorkspaceManager(project_config)
            
            file_tools_config = FileToolsConfig(
                enabled=True,
                permission_mode=mode,
                default_permissions=mode,
                custom_permissions=custom_perms or {}
            )
            
            return PermissionChecker(file_tools_config, workspace_manager), project_root
        
        return _create
    
    def test_allow_mode(self, create_checker_with_mode):
        """测试 allow 模式"""
        checker, project = create_checker_with_mode(
            PermissionMode.allow,
            custom_perms={"write": PermissionMode.allow}
        )
        
        result = checker.check(project / "test.py", OperationType.WRITE)
        
        assert result.allowed is True
        assert result.status == PermissionStatus.ALLOWED
    
    def test_deny_mode(self, create_checker_with_mode):
        """测试 deny 模式"""
        checker, project = create_checker_with_mode(
            PermissionMode.deny,
            custom_perms={"write": PermissionMode.deny}
        )
        
        result = checker.check(project / "test.py", OperationType.WRITE)
        
        assert result.allowed is False
        assert result.status == PermissionStatus.DENIED
    
    def test_ask_mode(self, create_checker_with_mode):
        """测试 ask 模式"""
        checker, project = create_checker_with_mode(PermissionMode.ask)
        
        result = checker.check(project / "test.py", OperationType.WRITE)
        
        assert result.allowed is True
        assert result.status == PermissionStatus.ASK
        assert result.requires_confirmation is True
