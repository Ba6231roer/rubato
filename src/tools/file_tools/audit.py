import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, field_validator


class OperationType(str, Enum):
    """文件操作类型枚举"""
    READ = "read"
    WRITE = "write"
    REPLACE = "replace"
    DELETE = "delete"
    LIST = "list"
    SEARCH = "search"
    COPY = "copy"
    MOVE = "move"
    MKDIR = "mkdir"
    EXISTS = "exists"


class OperationResult(str, Enum):
    """操作结果枚举"""
    SUCCESS = "success"
    DENIED = "denied"
    ERROR = "error"


class AuditEntry(BaseModel):
    """审计日志条目数据模型
    
    记录文件工具的每次调用，包括操作类型、目标路径、结果等信息。
    """
    timestamp: datetime
    tool_name: str
    path: str
    operation: OperationType
    result: OperationResult
    error_message: Optional[str] = None
    user_info: Optional[Dict[str, Any]] = None
    extra: Optional[Dict[str, Any]] = None
    
    @field_validator('tool_name', 'path')
    @classmethod
    def validate_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('field cannot be empty')
        return v
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "tool_name": self.tool_name,
            "path": self.path,
            "operation": self.operation.value,
            "result": self.result.value,
            "error_message": self.error_message,
            "user_info": self.user_info,
            "extra": self.extra
        }
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuditEntry':
        """从字典创建实例"""
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if isinstance(data.get('operation'), str):
            data['operation'] = OperationType(data['operation'])
        if isinstance(data.get('result'), str):
            data['result'] = OperationResult(data['result'])
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'AuditEntry':
        """从 JSON 字符串创建实例"""
        return cls.from_dict(json.loads(json_str))


class AuditConfig(BaseModel):
    """审计日志配置"""
    enabled: bool = True
    log_file: str = "logs/file_tools_audit.log"
    include_content: bool = False
    max_file_size_mb: int = 100
    
    @field_validator('max_file_size_mb')
    @classmethod
    def validate_max_file_size(cls, v):
        if v <= 0:
            raise ValueError('max_file_size_mb must be positive')
        return v


class AuditLogger:
    """审计日志记录器
    
    负责记录和查询文件工具的审计日志。
    支持 JSON 格式的日志写入和按条件查询。
    """
    
    def __init__(self, config: AuditConfig):
        """初始化审计日志记录器
        
        Args:
            config: 审计日志配置
        """
        self._config = config
        self._log_file = Path(config.log_file)
        self._file_handler: Optional[logging.FileHandler] = None
        self._setup_logger()
    
    def _setup_logger(self) -> None:
        """设置日志记录器"""
        self._log_file.parent.mkdir(parents=True, exist_ok=True)
        
        logger_name = f"file_tools_audit_{id(self)}"
        self._logger = logging.getLogger(logger_name)
        self._logger.setLevel(logging.INFO)
        self._logger.handlers = []
        
        self._file_handler = logging.FileHandler(
            self._log_file,
            encoding="utf-8"
        )
        self._file_handler.setLevel(logging.INFO)
        self._file_handler.setFormatter(logging.Formatter("%(message)s"))
        self._logger.addHandler(self._file_handler)
    
    def close(self) -> None:
        """关闭日志记录器，释放文件句柄"""
        if self._file_handler:
            self._file_handler.close()
            self._logger.removeHandler(self._file_handler)
            self._file_handler = None
    
    def log(
        self,
        tool_name: str,
        path: str,
        operation: OperationType,
        result: OperationResult,
        error_message: Optional[str] = None,
        user_info: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录审计日志
        
        Args:
            tool_name: 工具名称
            path: 目标路径
            operation: 操作类型
            result: 操作结果
            error_message: 错误信息（可选）
            user_info: 用户信息（可选）
            extra: 额外信息（可选）
        """
        if not self._config.enabled:
            return
        
        entry = AuditEntry(
            timestamp=datetime.now(),
            tool_name=tool_name,
            path=path,
            operation=operation,
            result=result,
            error_message=error_message,
            user_info=user_info,
            extra=extra
        )
        
        self._logger.info(entry.to_json())
    
    def log_success(
        self,
        tool_name: str,
        path: str,
        operation: OperationType,
        user_info: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录成功操作
        
        Args:
            tool_name: 工具名称
            path: 目标路径
            operation: 操作类型
            user_info: 用户信息（可选）
            extra: 额外信息（可选）
        """
        self.log(
            tool_name=tool_name,
            path=path,
            operation=operation,
            result=OperationResult.SUCCESS,
            user_info=user_info,
            extra=extra
        )
    
    def log_denied(
        self,
        tool_name: str,
        path: str,
        operation: OperationType,
        reason: str,
        user_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录拒绝操作
        
        Args:
            tool_name: 工具名称
            path: 目标路径
            operation: 操作类型
            reason: 拒绝原因
            user_info: 用户信息（可选）
        """
        self.log(
            tool_name=tool_name,
            path=path,
            operation=operation,
            result=OperationResult.DENIED,
            error_message=reason,
            user_info=user_info
        )
    
    def log_error(
        self,
        tool_name: str,
        path: str,
        operation: OperationType,
        error: str,
        user_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录错误操作
        
        Args:
            tool_name: 工具名称
            path: 目标路径
            operation: 操作类型
            error: 错误信息
            user_info: 用户信息（可选）
        """
        self.log(
            tool_name=tool_name,
            path=path,
            operation=operation,
            result=OperationResult.ERROR,
            error_message=error,
            user_info=user_info
        )
    
    def query(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        path: Optional[str] = None,
        operation: Optional[OperationType] = None,
        result: Optional[OperationResult] = None,
        tool_name: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditEntry]:
        """查询审计日志
        
        Args:
            start_time: 开始时间（可选）
            end_time: 结束时间（可选）
            path: 目标路径（可选，支持部分匹配）
            operation: 操作类型（可选）
            result: 操作结果（可选）
            tool_name: 工具名称（可选）
            limit: 返回结果数量限制
            
        Returns:
            List[AuditEntry]: 匹配的审计日志条目列表
        """
        if not self._log_file.exists():
            return []
        
        entries: List[AuditEntry] = []
        
        with open(self._log_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    entry = AuditEntry.from_json(line)
                    
                    if not self._match_entry(
                        entry, start_time, end_time, path, operation, result, tool_name
                    ):
                        continue
                    
                    entries.append(entry)
                    
                    if len(entries) >= limit:
                        break
                except (json.JSONDecodeError, ValueError):
                    continue
        
        return entries
    
    def _match_entry(
        self,
        entry: AuditEntry,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        path: Optional[str],
        operation: Optional[OperationType],
        result: Optional[OperationResult],
        tool_name: Optional[str]
    ) -> bool:
        """检查条目是否匹配查询条件"""
        if start_time and entry.timestamp < start_time:
            return False
        
        if end_time and entry.timestamp > end_time:
            return False
        
        if path and path not in entry.path:
            return False
        
        if operation and entry.operation != operation:
            return False
        
        if result and entry.result != result:
            return False
        
        if tool_name and entry.tool_name != tool_name:
            return False
        
        return True
    
    def query_by_path(self, path: str, limit: int = 100) -> List[AuditEntry]:
        """按路径查询审计日志
        
        Args:
            path: 目标路径（支持部分匹配）
            limit: 返回结果数量限制
            
        Returns:
            List[AuditEntry]: 匹配的审计日志条目列表
        """
        return self.query(path=path, limit=limit)
    
    def query_by_operation(
        self,
        operation: OperationType,
        limit: int = 100
    ) -> List[AuditEntry]:
        """按操作类型查询审计日志
        
        Args:
            operation: 操作类型
            limit: 返回结果数量限制
            
        Returns:
            List[AuditEntry]: 匹配的审计日志条目列表
        """
        return self.query(operation=operation, limit=limit)
    
    def query_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        limit: int = 100
    ) -> List[AuditEntry]:
        """按时间范围查询审计日志
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回结果数量限制
            
        Returns:
            List[AuditEntry]: 匹配的审计日志条目列表
        """
        return self.query(start_time=start_time, end_time=end_time, limit=limit)
    
    def query_denied(self, limit: int = 100) -> List[AuditEntry]:
        """查询被拒绝的操作
        
        Args:
            limit: 返回结果数量限制
            
        Returns:
            List[AuditEntry]: 匹配的审计日志条目列表
        """
        return self.query(result=OperationResult.DENIED, limit=limit)
    
    def query_errors(self, limit: int = 100) -> List[AuditEntry]:
        """查询错误的操作
        
        Args:
            limit: 返回结果数量限制
            
        Returns:
            List[AuditEntry]: 匹配的审计日志条目列表
        """
        return self.query(result=OperationResult.ERROR, limit=limit)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取审计日志统计信息
        
        Returns:
            Dict[str, Any]: 统计信息，包括各操作类型的次数和结果分布
        """
        if not self._log_file.exists():
            return {
                "total_count": 0,
                "by_operation": {},
                "by_result": {}
            }
        
        total_count = 0
        by_operation: Dict[str, int] = {}
        by_result: Dict[str, int] = {}
        
        with open(self._log_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    entry = AuditEntry.from_json(line)
                    total_count += 1
                    
                    op = entry.operation.value
                    by_operation[op] = by_operation.get(op, 0) + 1
                    
                    res = entry.result.value
                    by_result[res] = by_result.get(res, 0) + 1
                except (json.JSONDecodeError, ValueError):
                    continue
        
        return {
            "total_count": total_count,
            "by_operation": by_operation,
            "by_result": by_result
        }
    
    def clear(self) -> None:
        """清空审计日志文件"""
        if self._log_file.exists():
            self._log_file.write_text('', encoding='utf-8')
