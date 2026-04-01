import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import os
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.file_tools.audit import (
    AuditEntry,
    AuditLogger,
    AuditConfig,
    OperationType,
    OperationResult
)


class TestOperationType:
    """操作类型枚举测试"""
    
    def test_operation_types(self):
        assert OperationType.READ == "read"
        assert OperationType.WRITE == "write"
        assert OperationType.DELETE == "delete"
        assert OperationType.LIST == "list"
        assert OperationType.SEARCH == "search"
    
    def test_operation_type_values(self):
        values = [op.value for op in OperationType]
        assert "read" in values
        assert "write" in values
        assert "delete" in values


class TestOperationResult:
    """操作结果枚举测试"""
    
    def test_result_types(self):
        assert OperationResult.SUCCESS == "success"
        assert OperationResult.DENIED == "denied"
        assert OperationResult.ERROR == "error"


class TestAuditEntry:
    """审计日志条目测试"""
    
    def test_create_entry(self):
        entry = AuditEntry(
            timestamp=datetime.now(),
            tool_name="file_read",
            path="/test/path.txt",
            operation=OperationType.READ,
            result=OperationResult.SUCCESS
        )
        
        assert entry.tool_name == "file_read"
        assert entry.path == "/test/path.txt"
        assert entry.operation == OperationType.READ
        assert entry.result == OperationResult.SUCCESS
        assert entry.error_message is None
        assert entry.user_info is None
    
    def test_create_entry_with_error(self):
        entry = AuditEntry(
            timestamp=datetime.now(),
            tool_name="file_write",
            path="/test/path.txt",
            operation=OperationType.WRITE,
            result=OperationResult.ERROR,
            error_message="Permission denied"
        )
        
        assert entry.result == OperationResult.ERROR
        assert entry.error_message == "Permission denied"
    
    def test_create_entry_with_user_info(self):
        user_info = {"user_id": "123", "role": "admin"}
        entry = AuditEntry(
            timestamp=datetime.now(),
            tool_name="file_read",
            path="/test/path.txt",
            operation=OperationType.READ,
            result=OperationResult.SUCCESS,
            user_info=user_info
        )
        
        assert entry.user_info == user_info
    
    def test_validate_empty_tool_name(self):
        with pytest.raises(ValueError):
            AuditEntry(
                timestamp=datetime.now(),
                tool_name="",
                path="/test/path.txt",
                operation=OperationType.READ,
                result=OperationResult.SUCCESS
            )
    
    def test_validate_empty_path(self):
        with pytest.raises(ValueError):
            AuditEntry(
                timestamp=datetime.now(),
                tool_name="file_read",
                path="",
                operation=OperationType.READ,
                result=OperationResult.SUCCESS
            )
    
    def test_to_dict(self):
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        entry = AuditEntry(
            timestamp=timestamp,
            tool_name="file_read",
            path="/test/path.txt",
            operation=OperationType.READ,
            result=OperationResult.SUCCESS
        )
        
        data = entry.to_dict()
        
        assert data["timestamp"] == "2024-01-01T12:00:00"
        assert data["tool_name"] == "file_read"
        assert data["path"] == "/test/path.txt"
        assert data["operation"] == "read"
        assert data["result"] == "success"
    
    def test_to_json(self):
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        entry = AuditEntry(
            timestamp=timestamp,
            tool_name="file_read",
            path="/test/path.txt",
            operation=OperationType.READ,
            result=OperationResult.SUCCESS
        )
        
        json_str = entry.to_json()
        
        assert '"tool_name": "file_read"' in json_str
        assert '"path": "/test/path.txt"' in json_str
    
    def test_from_dict(self):
        data = {
            "timestamp": "2024-01-01T12:00:00",
            "tool_name": "file_read",
            "path": "/test/path.txt",
            "operation": "read",
            "result": "success"
        }
        
        entry = AuditEntry.from_dict(data)
        
        assert entry.timestamp == datetime(2024, 1, 1, 12, 0, 0)
        assert entry.tool_name == "file_read"
        assert entry.operation == OperationType.READ
        assert entry.result == OperationResult.SUCCESS
    
    def test_from_json(self):
        json_str = '{"timestamp": "2024-01-01T12:00:00", "tool_name": "file_read", "path": "/test/path.txt", "operation": "read", "result": "success"}'
        
        entry = AuditEntry.from_json(json_str)
        
        assert entry.tool_name == "file_read"
        assert entry.operation == OperationType.READ
    
    def test_serialization_roundtrip(self):
        original = AuditEntry(
            timestamp=datetime.now(),
            tool_name="file_read",
            path="/test/path.txt",
            operation=OperationType.READ,
            result=OperationResult.SUCCESS,
            user_info={"user": "test"}
        )
        
        json_str = original.to_json()
        restored = AuditEntry.from_json(json_str)
        
        assert restored.tool_name == original.tool_name
        assert restored.path == original.path
        assert restored.operation == original.operation
        assert restored.result == original.result
        assert restored.user_info == original.user_info


class TestAuditConfig:
    """审计配置测试"""
    
    def test_default_config(self):
        config = AuditConfig()
        
        assert config.enabled is True
        assert config.log_file == "logs/file_tools_audit.log"
        assert config.include_content is False
        assert config.max_file_size_mb == 100
    
    def test_custom_config(self):
        config = AuditConfig(
            enabled=False,
            log_file="custom/audit.log",
            include_content=True,
            max_file_size_mb=50
        )
        
        assert config.enabled is False
        assert config.log_file == "custom/audit.log"
        assert config.include_content is True
        assert config.max_file_size_mb == 50
    
    def test_validate_max_file_size(self):
        with pytest.raises(ValueError):
            AuditConfig(max_file_size_mb=0)
        
        with pytest.raises(ValueError):
            AuditConfig(max_file_size_mb=-1)


class TestAuditLogger:
    """审计日志记录器测试"""
    
    @pytest.fixture
    def temp_log_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            temp_path = f.name
        yield temp_path
        import gc
        gc.collect()
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except PermissionError:
                pass
    
    @pytest.fixture
    def audit_logger(self, temp_log_file):
        config = AuditConfig(
            enabled=True,
            log_file=temp_log_file
        )
        logger = AuditLogger(config)
        yield logger
        logger.close()
    
    def test_log_success(self, audit_logger, temp_log_file):
        audit_logger.log_success(
            tool_name="file_read",
            path="/test/path.txt",
            operation=OperationType.READ
        )
        
        with open(temp_log_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert '"tool_name": "file_read"' in content
        assert '"result": "success"' in content
    
    def test_log_denied(self, audit_logger, temp_log_file):
        audit_logger.log_denied(
            tool_name="file_write",
            path="/test/path.txt",
            operation=OperationType.WRITE,
            reason="Permission denied"
        )
        
        with open(temp_log_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert '"result": "denied"' in content
        assert '"error_message": "Permission denied"' in content
    
    def test_log_error(self, audit_logger, temp_log_file):
        audit_logger.log_error(
            tool_name="file_read",
            path="/test/path.txt",
            operation=OperationType.READ,
            error="File not found"
        )
        
        with open(temp_log_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert '"result": "error"' in content
        assert '"error_message": "File not found"' in content
    
    def test_log_disabled(self, temp_log_file):
        config = AuditConfig(
            enabled=False,
            log_file=temp_log_file
        )
        logger = AuditLogger(config)
        
        try:
            logger.log_success(
                tool_name="file_read",
                path="/test/path.txt",
                operation=OperationType.READ
            )
            
            with open(temp_log_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            assert content == ""
        finally:
            logger.close()
    
    def test_query_all(self, audit_logger):
        audit_logger.log_success("file_read", "/test/1.txt", OperationType.READ)
        audit_logger.log_success("file_write", "/test/2.txt", OperationType.WRITE)
        audit_logger.log_denied("file_delete", "/test/3.txt", OperationType.DELETE, "Not allowed")
        
        entries = audit_logger.query(limit=10)
        
        assert len(entries) == 3
    
    def test_query_by_path(self, audit_logger):
        audit_logger.log_success("file_read", "/test/1.txt", OperationType.READ)
        audit_logger.log_success("file_read", "/test/2.txt", OperationType.READ)
        audit_logger.log_success("file_read", "/other/3.txt", OperationType.READ)
        
        entries = audit_logger.query_by_path("/test")
        
        assert len(entries) == 2
        for entry in entries:
            assert "/test" in entry.path
    
    def test_query_by_operation(self, audit_logger):
        audit_logger.log_success("file_read", "/test/1.txt", OperationType.READ)
        audit_logger.log_success("file_write", "/test/2.txt", OperationType.WRITE)
        audit_logger.log_success("file_read", "/test/3.txt", OperationType.READ)
        
        entries = audit_logger.query_by_operation(OperationType.READ)
        
        assert len(entries) == 2
        for entry in entries:
            assert entry.operation == OperationType.READ
    
    def test_query_by_time_range(self, audit_logger):
        now = datetime.now()
        past = now - timedelta(hours=1)
        future = now + timedelta(hours=1)
        
        audit_logger.log_success("file_read", "/test/1.txt", OperationType.READ)
        
        entries = audit_logger.query_by_time_range(past, future)
        
        assert len(entries) == 1
    
    def test_query_denied(self, audit_logger):
        audit_logger.log_success("file_read", "/test/1.txt", OperationType.READ)
        audit_logger.log_denied("file_write", "/test/2.txt", OperationType.WRITE, "Denied")
        audit_logger.log_denied("file_delete", "/test/3.txt", OperationType.DELETE, "Denied")
        
        entries = audit_logger.query_denied()
        
        assert len(entries) == 2
        for entry in entries:
            assert entry.result == OperationResult.DENIED
    
    def test_query_errors(self, audit_logger):
        audit_logger.log_success("file_read", "/test/1.txt", OperationType.READ)
        audit_logger.log_error("file_write", "/test/2.txt", OperationType.WRITE, "Error")
        
        entries = audit_logger.query_errors()
        
        assert len(entries) == 1
        assert entries[0].result == OperationResult.ERROR
    
    def test_get_statistics(self, audit_logger):
        audit_logger.log_success("file_read", "/test/1.txt", OperationType.READ)
        audit_logger.log_success("file_write", "/test/2.txt", OperationType.WRITE)
        audit_logger.log_denied("file_delete", "/test/3.txt", OperationType.DELETE, "Denied")
        
        stats = audit_logger.get_statistics()
        
        assert stats["total_count"] == 3
        assert stats["by_operation"]["read"] == 1
        assert stats["by_operation"]["write"] == 1
        assert stats["by_operation"]["delete"] == 1
        assert stats["by_result"]["success"] == 2
        assert stats["by_result"]["denied"] == 1
    
    def test_get_statistics_empty(self, temp_log_file):
        config = AuditConfig(log_file=temp_log_file)
        logger = AuditLogger(config)
        
        try:
            stats = logger.get_statistics()
            
            assert stats["total_count"] == 0
            assert stats["by_operation"] == {}
            assert stats["by_result"] == {}
        finally:
            logger.close()
    
    def test_clear(self, audit_logger, temp_log_file):
        audit_logger.log_success("file_read", "/test/1.txt", OperationType.READ)
        
        audit_logger.clear()
        
        with open(temp_log_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert content == ""
    
    def test_query_with_limit(self, audit_logger):
        for i in range(10):
            audit_logger.log_success("file_read", f"/test/{i}.txt", OperationType.READ)
        
        entries = audit_logger.query(limit=5)
        
        assert len(entries) == 5
    
    def test_query_by_tool_name(self, audit_logger):
        audit_logger.log_success("file_read", "/test/1.txt", OperationType.READ)
        audit_logger.log_success("file_write", "/test/2.txt", OperationType.WRITE)
        
        entries = audit_logger.query(tool_name="file_read")
        
        assert len(entries) == 1
        assert entries[0].tool_name == "file_read"
    
    def test_log_with_extra_info(self, audit_logger, temp_log_file):
        extra = {"file_size": 1024, "encoding": "utf-8"}
        audit_logger.log_success(
            tool_name="file_read",
            path="/test/path.txt",
            operation=OperationType.READ,
            extra=extra
        )
        
        with open(temp_log_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert '"file_size": 1024' in content
        assert '"encoding": "utf-8"' in content
