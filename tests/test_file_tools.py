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


class TestFileTools:
    """文件工具测试类"""
    
    @pytest.fixture
    def temp_project(self, tmp_path):
        """创建临时项目结构"""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        
        src_dir = project_root / "src"
        src_dir.mkdir()
        
        tests_dir = project_root / "tests"
        tests_dir.mkdir()
        
        test_file = src_dir / "test.py"
        test_file.write_text("print('hello')\nprint('world')\n")
        
        env_file = project_root / ".env"
        env_file.write_text("SECRET_KEY=secret")
        
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
            permission_mode=PermissionMode.allow,
            custom_permissions={"delete": PermissionMode.allow},
            default_permissions=PermissionMode.allow,
            audit=True
        )
    
    @pytest.fixture
    def provider(self, project_config, file_tools_config):
        """创建 FileToolProvider 实例"""
        return FileToolProvider(project_config, file_tools_config)
    
    def test_provider_initializes_tools(self, provider):
        """测试提供者初始化工具"""
        tools = provider.get_tools()
        
        assert len(tools) == 10
        
        tool_names = [tool.name for tool in tools]
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
    
    def test_file_read_tool(self, provider, temp_project):
        """测试 file_read 工具"""
        tools = provider.get_tools()
        file_read = next(tool for tool in tools if tool.name == "file_read")
        
        test_file = temp_project / "src" / "test.py"
        result = file_read.invoke({"path": str(test_file)})
        
        assert "print('hello')" in result
        assert "print('world')" in result
    
    def test_file_read_with_line_range(self, provider, temp_project):
        """测试 file_read 工具的行范围功能"""
        tools = provider.get_tools()
        file_read = next(tool for tool in tools if tool.name == "file_read")
        
        test_file = temp_project / "src" / "test.py"
        result = file_read.invoke({
            "path": str(test_file),
            "start_line": 1,
            "end_line": 1
        })
        
        assert "print('hello')" in result
        assert "print('world')" not in result
    
    def test_file_read_nonexistent_file(self, provider, temp_project):
        """测试读取不存在的文件"""
        tools = provider.get_tools()
        file_read = next(tool for tool in tools if tool.name == "file_read")
        
        result = file_read.invoke({"path": "nonexistent.py"})
        
        assert "Error:" in result
        assert "does not exist" in result
    
    def test_file_read_excluded_file(self, provider, temp_project):
        """测试读取被排除的文件"""
        tools = provider.get_tools()
        file_read = next(tool for tool in tools if tool.name == "file_read")
        
        env_file = temp_project / ".env"
        result = file_read.invoke({"path": str(env_file)})
        
        assert "Error:" in result
        assert "Permission denied" in result
    
    def test_file_write_tool(self, provider, temp_project):
        """测试 file_write 工具"""
        tools = provider.get_tools()
        file_write = next(tool for tool in tools if tool.name == "file_write")
        
        new_file = temp_project / "src" / "new_file.py"
        result = file_write.invoke({
            "path": str(new_file),
            "content": "print('new file')"
        })
        
        assert "Success" in result
        assert new_file.exists()
        assert new_file.read_text() == "print('new file')"
    
    def test_file_write_append_mode(self, provider, temp_project):
        """测试 file_write 工具的追加模式"""
        tools = provider.get_tools()
        file_write = next(tool for tool in tools if tool.name == "file_write")
        
        test_file = temp_project / "src" / "test.py"
        original_content = test_file.read_text()
        
        result = file_write.invoke({
            "path": str(test_file),
            "content": "\nprint('appended')",
            "mode": "append"
        })
        
        assert "Success" in result
        assert original_content in test_file.read_text()
        assert "print('appended')" in test_file.read_text()
    
    def test_file_replace_tool(self, provider, temp_project):
        """测试 file_replace 工具"""
        tools = provider.get_tools()
        file_replace = next(tool for tool in tools if tool.name == "file_replace")
        
        test_file = temp_project / "src" / "test.py"
        result = file_replace.invoke({
            "path": str(test_file),
            "old_str": "hello",
            "new_str": "goodbye"
        })
        
        assert "Success" in result
        assert "goodbye" in test_file.read_text()
        assert "hello" not in test_file.read_text()
    
    def test_file_replace_not_found(self, provider, temp_project):
        """测试替换不存在的字符串"""
        tools = provider.get_tools()
        file_replace = next(tool for tool in tools if tool.name == "file_replace")
        
        test_file = temp_project / "src" / "test.py"
        result = file_replace.invoke({
            "path": str(test_file),
            "old_str": "nonexistent",
            "new_str": "replacement"
        })
        
        assert "Error:" in result
        assert "not found" in result
    
    def test_file_list_tool(self, provider, temp_project):
        """测试 file_list 工具"""
        tools = provider.get_tools()
        file_list = next(tool for tool in tools if tool.name == "file_list")
        
        result = file_list.invoke({"path": str(temp_project)})
        
        assert "src/" in result
        assert "tests/" in result
    
    def test_file_list_with_pattern(self, provider, temp_project):
        """测试 file_list 工具的模式匹配"""
        tools = provider.get_tools()
        file_list = next(tool for tool in tools if tool.name == "file_list")
        
        result = file_list.invoke({
            "path": str(temp_project / "src"),
            "pattern": "*.py"
        })
        
        assert "test.py" in result
    
    def test_file_list_recursive(self, provider, temp_project):
        """测试 file_list 工具的递归列表"""
        tools = provider.get_tools()
        file_list = next(tool for tool in tools if tool.name == "file_list")
        
        result = file_list.invoke({
            "path": str(temp_project),
            "recursive": True
        })
        
        assert "src/test.py" in result or "test.py" in result
    
    def test_file_search_tool(self, provider, temp_project):
        """测试 file_search 工具"""
        tools = provider.get_tools()
        file_search = next(tool for tool in tools if tool.name == "file_search")
        
        result = file_search.invoke({
            "path": str(temp_project),
            "pattern": "print"
        })
        
        assert "print" in result
        assert "matches" in result
    
    def test_file_search_with_file_pattern(self, provider, temp_project):
        """测试 file_search 工具的文件模式"""
        tools = provider.get_tools()
        file_search = next(tool for tool in tools if tool.name == "file_search")
        
        result = file_search.invoke({
            "path": str(temp_project),
            "pattern": "print",
            "file_pattern": "*.py"
        })
        
        assert "print" in result
    
    def test_file_exists_tool(self, provider, temp_project):
        """测试 file_exists 工具"""
        tools = provider.get_tools()
        file_exists = next(tool for tool in tools if tool.name == "file_exists")
        
        test_file = temp_project / "src" / "test.py"
        result = file_exists.invoke({"path": str(test_file)})
        
        assert result == "true"
    
    def test_file_exists_nonexistent(self, provider, temp_project):
        """测试检查不存在的文件"""
        tools = provider.get_tools()
        file_exists = next(tool for tool in tools if tool.name == "file_exists")
        
        result = file_exists.invoke({"path": "nonexistent.py"})
        
        assert result == "false"
    
    def test_file_mkdir_tool(self, provider, temp_project):
        """测试 file_mkdir 工具"""
        tools = provider.get_tools()
        file_mkdir = next(tool for tool in tools if tool.name == "file_mkdir")
        
        new_dir = temp_project / "new_directory"
        result = file_mkdir.invoke({"path": str(new_dir)})
        
        assert "Success" in result
        assert new_dir.exists()
        assert new_dir.is_dir()
    
    def test_file_copy_tool(self, provider, temp_project):
        """测试 file_copy 工具"""
        tools = provider.get_tools()
        file_copy = next(tool for tool in tools if tool.name == "file_copy")
        
        src_file = temp_project / "src" / "test.py"
        dst_file = temp_project / "src" / "test_copy.py"
        
        result = file_copy.invoke({
            "src": str(src_file),
            "dst": str(dst_file)
        })
        
        assert "Success" in result
        assert dst_file.exists()
        assert dst_file.read_text() == src_file.read_text()
    
    def test_file_move_tool(self, provider, temp_project):
        """测试 file_move 工具"""
        tools = provider.get_tools()
        file_move = next(tool for tool in tools if tool.name == "file_move")
        
        src_file = temp_project / "src" / "test.py"
        dst_file = temp_project / "src" / "test_moved.py"
        original_content = src_file.read_text()
        
        result = file_move.invoke({
            "src": str(src_file),
            "dst": str(dst_file)
        })
        
        assert "Success" in result
        assert dst_file.exists()
        assert dst_file.read_text() == original_content
        assert not src_file.exists()
    
    def test_file_delete_tool(self, provider, temp_project):
        """测试 file_delete 工具"""
        tools = provider.get_tools()
        file_delete = next(tool for tool in tools if tool.name == "file_delete")
        
        test_file = temp_project / "src" / "test.py"
        assert test_file.exists()
        
        result = file_delete.invoke({"path": str(test_file)})
        
        assert "Success" in result
        assert not test_file.exists()
    
    def test_file_delete_nonexistent(self, provider, temp_project):
        """测试删除不存在的文件"""
        tools = provider.get_tools()
        file_delete = next(tool for tool in tools if tool.name == "file_delete")
        
        result = file_delete.invoke({"path": "nonexistent.py"})
        
        assert "Error:" in result
        assert "does not exist" in result
    
    def test_permission_denied_for_dangerous_operations(self, temp_project):
        """测试危险操作的权限拒绝"""
        workspace_config = WorkspaceConfig(
            main=temp_project,
            additional=[],
            excluded=[".env"]
        )
        project_config = ProjectConfig(
            name="test_project",
            root=temp_project,
            workspace=workspace_config
        )
        file_tools_config = FileToolsConfig(
            enabled=True,
            permission_mode=PermissionMode.deny,
            custom_permissions={"delete": PermissionMode.deny},
            default_permissions=PermissionMode.deny,
            audit=True
        )
        
        provider = FileToolProvider(project_config, file_tools_config)
        tools = provider.get_tools()
        file_delete = next(tool for tool in tools if tool.name == "file_delete")
        
        test_file = temp_project / "src" / "test.py"
        result = file_delete.invoke({"path": str(test_file)})
        
        assert "Error:" in result
        assert "Permission denied" in result
    
    def test_audit_log_for_tool_operations(self, provider, temp_project):
        """测试工具操作的审计日志"""
        tools = provider.get_tools()
        file_read = next(tool for tool in tools if tool.name == "file_read")
        
        test_file = temp_project / "src" / "test.py"
        file_read.invoke({"path": str(test_file)})
        
        entries = provider._audit_logger.query_by_path(str(test_file))
        
        assert len(entries) > 0
        assert entries[0].tool_name == "file_read"
        assert entries[0].operation == OperationType.READ
        assert entries[0].result == OperationResult.SUCCESS
