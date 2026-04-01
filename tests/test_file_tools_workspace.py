import pytest
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.file_tools.workspace import WorkspaceManager
from src.config.models import ProjectConfig, WorkspaceConfig


class TestWorkspaceManager:
    """WorkspaceManager 测试类"""
    
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
    def workspace_manager(self, project_config):
        """创建 WorkspaceManager 实例"""
        return WorkspaceManager(project_config)
    
    def test_init_workspace_manager(self, workspace_manager, temp_project):
        """测试 WorkspaceManager 初始化"""
        assert workspace_manager is not None
        assert workspace_manager.get_main_workspace() == temp_project.resolve()
        assert len(workspace_manager.get_workspace_roots()) == 1
    
    def test_init_with_additional_workspaces(self, temp_project, tmp_path):
        """测试带额外 workspace 的初始化"""
        additional_workspace = tmp_path / "additional"
        additional_workspace.mkdir()
        
        workspace_config = WorkspaceConfig(
            main=temp_project,
            additional=[additional_workspace],
            excluded=[]
        )
        
        project_config = ProjectConfig(
            name="test_project",
            root=temp_project,
            workspace=workspace_config
        )
        
        manager = WorkspaceManager(project_config)
        
        roots = manager.get_workspace_roots()
        assert len(roots) == 2
        assert temp_project.resolve() in roots
        assert additional_workspace.resolve() in roots
    
    def test_resolve_absolute_path(self, workspace_manager, temp_project):
        """测试解析绝对路径"""
        absolute_path = temp_project / "src" / "main.py"
        resolved = workspace_manager.resolve_path(absolute_path)
        
        assert resolved.is_absolute()
        assert resolved == absolute_path.resolve()
    
    def test_resolve_relative_path(self, workspace_manager, temp_project):
        """测试解析相对路径"""
        relative_path = "src/main.py"
        resolved = workspace_manager.resolve_path(relative_path)
        
        expected = (temp_project / "src" / "main.py").resolve()
        assert resolved == expected
    
    def test_resolve_empty_path_raises_error(self, workspace_manager):
        """测试空路径抛出异常"""
        with pytest.raises(ValueError, match="path cannot be empty"):
            workspace_manager.resolve_path("")
        
        with pytest.raises(ValueError, match="path cannot be empty"):
            workspace_manager.resolve_path("   ")
    
    def test_is_within_workspace_absolute_path(self, workspace_manager, temp_project):
        """测试绝对路径在 workspace 内"""
        path = temp_project / "src" / "main.py"
        assert workspace_manager.is_within_workspace(path) is True
    
    def test_is_within_workspace_relative_path(self, workspace_manager):
        """测试相对路径在 workspace 内"""
        assert workspace_manager.is_within_workspace("src/main.py") is True
        assert workspace_manager.is_within_workspace("tests/test_example.py") is True
    
    def test_is_outside_workspace(self, workspace_manager, tmp_path):
        """测试路径在 workspace 外"""
        outside_path = tmp_path / "outside_project" / "file.txt"
        assert workspace_manager.is_within_workspace(outside_path) is False
    
    def test_is_within_workspace_empty_path(self, workspace_manager):
        """测试空路径返回 False"""
        assert workspace_manager.is_within_workspace("") is False
    
    def test_is_excluded_exact_match(self, workspace_manager, temp_project):
        """测试精确匹配排除模式"""
        env_path = temp_project / ".env"
        assert workspace_manager.is_excluded(env_path) is True
    
    def test_is_excluded_wildcard_pattern(self, workspace_manager, temp_project):
        """测试通配符排除模式"""
        log_file = temp_project / "debug.log"
        assert workspace_manager.is_excluded(log_file) is True
        
        another_log = temp_project / "src" / "error.log"
        assert workspace_manager.is_excluded(another_log) is True
    
    def test_is_excluded_double_star_pattern(self, workspace_manager, temp_project):
        """测试 ** 通配符排除模式"""
        node_module_file = temp_project / "node_modules" / "package" / "index.js"
        assert workspace_manager.is_excluded(node_module_file) is True
        
        nested_node_module = temp_project / "node_modules" / "deep" / "nested" / "file.js"
        assert workspace_manager.is_excluded(nested_node_module) is True
    
    def test_is_not_excluded(self, workspace_manager, temp_project):
        """测试未被排除的路径"""
        src_file = temp_project / "src" / "main.py"
        assert workspace_manager.is_excluded(src_file) is False
        
        test_file = temp_project / "tests" / "test_main.py"
        assert workspace_manager.is_excluded(test_file) is False
    
    def test_is_path_valid(self, workspace_manager, temp_project):
        """测试路径有效性检查"""
        valid_path = temp_project / "src" / "main.py"
        assert workspace_manager.is_path_valid(valid_path) is True
        
        excluded_path = temp_project / ".env"
        assert workspace_manager.is_path_valid(excluded_path) is False
        
        outside_path = temp_project.parent / "outside" / "file.txt"
        assert workspace_manager.is_path_valid(outside_path) is False
    
    def test_validate_path_success(self, workspace_manager, temp_project):
        """测试路径验证成功"""
        valid_path = temp_project / "src" / "main.py"
        resolved = workspace_manager.validate_path(valid_path)
        
        assert resolved == valid_path.resolve()
    
    def test_validate_path_outside_workspace(self, workspace_manager, tmp_path):
        """测试验证 workspace 外路径抛出异常"""
        outside_path = tmp_path / "outside" / "file.txt"
        
        with pytest.raises(ValueError, match="outside workspace boundaries"):
            workspace_manager.validate_path(outside_path)
    
    def test_validate_path_excluded(self, workspace_manager, temp_project):
        """测试验证排除路径抛出异常"""
        excluded_path = temp_project / ".env"
        
        with pytest.raises(PermissionError, match="excluded from workspace"):
            workspace_manager.validate_path(excluded_path)
    
    def test_get_main_workspace(self, workspace_manager, temp_project):
        """测试获取主 workspace"""
        main = workspace_manager.get_main_workspace()
        assert main == temp_project.resolve()
    
    def test_get_workspace_roots(self, workspace_manager, temp_project):
        """测试获取所有 workspace 根路径"""
        roots = workspace_manager.get_workspace_roots()
        assert len(roots) == 1
        assert roots[0] == temp_project.resolve()
    
    def test_get_relative_path(self, workspace_manager, temp_project):
        """测试获取相对路径"""
        absolute_path = temp_project / "src" / "main.py"
        relative = workspace_manager.get_relative_path(absolute_path)
        
        assert relative == Path("src") / "main.py"
    
    def test_get_relative_path_outside_workspace(self, workspace_manager, tmp_path):
        """测试获取 workspace 外路径的相对路径返回 None"""
        outside_path = tmp_path / "outside" / "file.txt"
        relative = workspace_manager.get_relative_path(outside_path)
        
        assert relative is None
    
    def test_find_workspace_for_path(self, workspace_manager, temp_project):
        """测试查找路径所属 workspace"""
        path = temp_project / "src" / "main.py"
        workspace = workspace_manager.find_workspace_for_path(path)
        
        assert workspace == temp_project.resolve()
    
    def test_find_workspace_for_path_outside(self, workspace_manager, tmp_path):
        """测试查找 workspace 外路径返回 None"""
        outside_path = tmp_path / "outside" / "file.txt"
        workspace = workspace_manager.find_workspace_for_path(outside_path)
        
        assert workspace is None
    
    def test_list_excluded_patterns(self, workspace_manager):
        """测试获取排除模式列表"""
        patterns = workspace_manager.list_excluded_patterns()
        
        assert ".env" in patterns
        assert "node_modules/**" in patterns
        assert "**/__pycache__/**" in patterns
        assert "*.log" in patterns
    
    def test_add_excluded_pattern(self, workspace_manager):
        """测试添加排除模式"""
        workspace_manager.add_excluded_pattern("*.tmp")
        
        patterns = workspace_manager.list_excluded_patterns()
        assert "*.tmp" in patterns
    
    def test_add_duplicate_excluded_pattern(self, workspace_manager):
        """测试添加重复排除模式"""
        initial_count = len(workspace_manager.list_excluded_patterns())
        workspace_manager.add_excluded_pattern(".env")
        
        patterns = workspace_manager.list_excluded_patterns()
        assert patterns.count(".env") == 1
        assert len(patterns) == initial_count
    
    def test_remove_excluded_pattern(self, workspace_manager):
        """测试移除排除模式"""
        result = workspace_manager.remove_excluded_pattern(".env")
        
        assert result is True
        patterns = workspace_manager.list_excluded_patterns()
        assert ".env" not in patterns
    
    def test_remove_nonexistent_excluded_pattern(self, workspace_manager):
        """测试移除不存在的排除模式"""
        result = workspace_manager.remove_excluded_pattern("nonexistent")
        assert result is False
    
    def test_multiple_workspaces(self, tmp_path):
        """测试多个 workspace 场景"""
        main_workspace = tmp_path / "main"
        main_workspace.mkdir()
        
        additional_workspace = tmp_path / "additional"
        additional_workspace.mkdir()
        
        workspace_config = WorkspaceConfig(
            main=main_workspace,
            additional=[additional_workspace],
            excluded=[]
        )
        
        project_config = ProjectConfig(
            name="multi_workspace_project",
            root=main_workspace,
            workspace=workspace_config
        )
        
        manager = WorkspaceManager(project_config)
        
        main_file = main_workspace / "file.txt"
        additional_file = additional_workspace / "file.txt"
        
        assert manager.is_within_workspace(main_file) is True
        assert manager.is_within_workspace(additional_file) is True
        
        outside_file = tmp_path / "outside" / "file.txt"
        assert manager.is_within_workspace(outside_file) is False
    
    def test_relative_workspace_path(self, tmp_path):
        """测试相对 workspace 路径"""
        project_root = tmp_path / "project"
        project_root.mkdir()
        
        workspace_config = WorkspaceConfig(
            main=Path("."),
            additional=[],
            excluded=[]
        )
        
        project_config = ProjectConfig(
            name="relative_project",
            root=project_root,
            workspace=workspace_config
        )
        
        manager = WorkspaceManager(project_config)
        
        assert manager.get_main_workspace() == project_root.resolve()
        
        file_path = project_root / "src" / "main.py"
        assert manager.is_within_workspace(file_path) is True


class TestWorkspaceManagerSymlinks:
    """WorkspaceManager 符号链接测试"""
    
    @pytest.fixture
    def temp_project_with_symlink(self, tmp_path):
        """创建带符号链接的临时项目"""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        
        real_dir = tmp_path / "real_directory"
        real_dir.mkdir()
        (real_dir / "file.txt").write_text("content")
        
        symlink_path = project_root / "symlink_to_real"
        try:
            symlink_path.symlink_to(real_dir)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported on this system")
        
        workspace_config = WorkspaceConfig(
            main=project_root,
            additional=[],
            excluded=[]
        )
        
        project_config = ProjectConfig(
            name="symlink_project",
            root=project_root,
            workspace=workspace_config
        )
        
        return {
            "project_root": project_root,
            "real_dir": real_dir,
            "symlink_path": symlink_path,
            "project_config": project_config
        }
    
    def test_resolve_symlink(self, temp_project_with_symlink):
        """测试解析符号链接"""
        if not temp_project_with_symlink:
            pytest.skip("Symlink test skipped")
        
        manager = WorkspaceManager(temp_project_with_symlink["project_config"])
        symlink_file = temp_project_with_symlink["symlink_path"] / "file.txt"
        
        resolved = manager.resolve_path(symlink_file)
        assert resolved.exists()
    
    def test_symlink_within_workspace(self, temp_project_with_symlink):
        """测试符号链接在 workspace 内"""
        if not temp_project_with_symlink:
            pytest.skip("Symlink test skipped")
        
        manager = WorkspaceManager(temp_project_with_symlink["project_config"])
        symlink_file = temp_project_with_symlink["symlink_path"] / "file.txt"
        
        assert manager.is_within_workspace(symlink_file) is True


class TestWorkspaceManagerEdgeCases:
    """WorkspaceManager 边界情况测试"""
    
    def test_path_with_parent_references(self, tmp_path):
        """测试包含父目录引用的路径"""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        
        workspace_config = WorkspaceConfig(
            main=project_root,
            additional=[],
            excluded=[]
        )
        
        project_config = ProjectConfig(
            name="edge_case_project",
            root=project_root,
            workspace=workspace_config
        )
        
        manager = WorkspaceManager(project_config)
        
        path_with_parent = project_root / "src" / ".." / "src" / "main.py"
        resolved = manager.resolve_path(path_with_parent)
        
        assert manager.is_within_workspace(resolved) is True
    
    def test_path_traversal_attempt(self, tmp_path):
        """测试路径遍历攻击防护"""
        project_root = tmp_path / "project"
        project_root.mkdir()
        
        workspace_config = WorkspaceConfig(
            main=project_root,
            additional=[],
            excluded=[]
        )
        
        project_config = ProjectConfig(
            name="security_project",
            root=project_root,
            workspace=workspace_config
        )
        
        manager = WorkspaceManager(project_config)
        
        traversal_path = project_root / ".." / "outside" / "file.txt"
        
        assert manager.is_within_workspace(traversal_path) is False
    
    def test_case_sensitivity(self, tmp_path):
        """测试路径大小写敏感性"""
        project_root = tmp_path / "Project"
        project_root.mkdir()
        
        workspace_config = WorkspaceConfig(
            main=project_root,
            additional=[],
            excluded=[]
        )
        
        project_config = ProjectConfig(
            name="case_project",
            root=project_root,
            workspace=workspace_config
        )
        
        manager = WorkspaceManager(project_config)
        
        lower_path = tmp_path / "project" / "file.txt"
        upper_path = tmp_path / "Project" / "file.txt"
        
        assert manager.is_within_workspace(upper_path) is True
    
    def test_unicode_path(self, tmp_path):
        """测试 Unicode 路径"""
        project_root = tmp_path / "项目"
        project_root.mkdir()
        
        workspace_config = WorkspaceConfig(
            main=project_root,
            additional=[],
            excluded=[]
        )
        
        project_config = ProjectConfig(
            name="unicode_project",
            root=project_root,
            workspace=workspace_config
        )
        
        manager = WorkspaceManager(project_config)
        
        unicode_file = project_root / "文件.txt"
        assert manager.is_within_workspace(unicode_file) is True
    
    def test_empty_excluded_list(self, tmp_path):
        """测试空排除列表"""
        project_root = tmp_path / "project"
        project_root.mkdir()
        
        workspace_config = WorkspaceConfig(
            main=project_root,
            additional=[],
            excluded=[]
        )
        
        project_config = ProjectConfig(
            name="no_exclusions_project",
            root=project_root,
            workspace=workspace_config
        )
        
        manager = WorkspaceManager(project_config)
        
        any_file = project_root / "any_file.txt"
        assert manager.is_excluded(any_file) is False
