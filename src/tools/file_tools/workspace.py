import fnmatch
import logging
from pathlib import Path
from typing import List, Union, Optional

from src.config.models import ProjectConfig, WorkspaceConfig


class WorkspaceManager:
    """Workspace 路径管理器
    
    负责：
    1. 路径解析和规范化
    2. Workspace 边界检查
    3. 排除列表检查
    4. 符号链接处理
    5. 路径遍历攻击防护
    """
    
    def __init__(self, project_config: ProjectConfig):
        """初始化 Workspace 管理器
        
        Args:
            project_config: 项目配置，包含 Workspace 配置信息
        """
        self._project_config = project_config
        self._workspace_config = project_config.workspace
        self._workspace_paths = self._init_workspace_paths()
        self._excluded_patterns = self._workspace_config.excluded
        self._logger = logging.getLogger(__name__)
    
    def _init_workspace_paths(self) -> List[Path]:
        """初始化所有 workspace 路径（解析后的绝对路径）
        
        Returns:
            List[Path]: 解析后的 workspace 路径列表
        """
        paths = []
        
        main_path = self._resolve_workspace_path(self._workspace_config.main)
        paths.append(main_path)
        
        for additional_path in self._workspace_config.additional:
            resolved = self._resolve_workspace_path(additional_path)
            paths.append(resolved)
        
        return paths
    
    def _resolve_workspace_path(self, path: Path) -> Path:
        """解析 workspace 路径
        
        Args:
            path: workspace 路径
            
        Returns:
            Path: 解析后的绝对路径
        """
        if not path.is_absolute():
            path = self._project_config.root / path
        
        return path.resolve()
    
    def resolve_path(self, path: Union[str, Path]) -> Path:
        """解析路径，处理符号链接和相对路径
        
        Args:
            path: 待解析的路径（可以是相对路径或绝对路径）
            
        Returns:
            Path: 解析后的绝对路径
            
        Raises:
            ValueError: 如果路径为空
        """
        if isinstance(path, str):
            if not path or not path.strip():
                raise ValueError('path cannot be empty')
            p = Path(path)
        else:
            p = path
        
        if not p.is_absolute():
            p = self._project_config.root / p
        
        resolved = p.resolve()
        
        if resolved.is_symlink():
            resolved = resolved.resolve()
        
        return resolved
    
    def is_within_workspace(self, path: Union[str, Path]) -> bool:
        """检查路径是否在 Workspace 边界内
        
        Args:
            path: 待检查的路径
            
        Returns:
            bool: 如果路径在任一 workspace 内返回 True，否则返回 False
        """
        try:
            resolved = self.resolve_path(path)
        except ValueError:
            return False
        
        for workspace_root in self._workspace_paths:
            try:
                resolved.relative_to(workspace_root)
                return True
            except ValueError:
                continue
        
        return False
    
    def is_excluded(self, path: Union[str, Path]) -> bool:
        """检查路径是否在排除列表中
        
        使用 fnmatch 模式匹配，支持通配符如 **/*.env
        
        Args:
            path: 待检查的路径
            
        Returns:
            bool: 如果路径匹配任一排除模式返回 True，否则返回 False
        """
        if not self._excluded_patterns:
            return False
        
        try:
            resolved = self.resolve_path(path)
        except ValueError:
            return False
        
        path_str = str(resolved)
        
        for pattern in self._excluded_patterns:
            if self._match_pattern(path_str, pattern):
                return True
        
        return False
    
    def _match_pattern(self, path: str, pattern: str) -> bool:
        """匹配路径与排除模式
        
        支持 fnmatch 风格的模式匹配，包括：
        - * 匹配任意字符（除路径分隔符）
        - ** 匹配任意字符（包括路径分隔符）
        - ? 匹配单个字符
        - [seq] 匹配序列中的任意字符
        
        Args:
            path: 待匹配的路径
            pattern: 排除模式
            
        Returns:
            bool: 如果匹配返回 True，否则返回 False
        """
        if '**' in pattern:
            parts = pattern.split('**')
            if len(parts) == 2:
                prefix = parts[0].rstrip('/\\')
                suffix = parts[1].lstrip('/\\')
                
                if prefix and suffix:
                    if prefix in path and suffix in path:
                        prefix_idx = path.index(prefix)
                        suffix_idx = path.rindex(suffix)
                        return prefix_idx < suffix_idx
                elif prefix:
                    return prefix in path
                elif suffix:
                    return suffix in path
        
        path_obj = Path(path)
        
        if fnmatch.fnmatch(path, pattern):
            return True
        
        if fnmatch.fnmatch(path_obj.name, pattern):
            return True
        
        for parent in path_obj.parents:
            relative = path_obj.relative_to(parent)
            if fnmatch.fnmatch(str(relative), pattern):
                return True
        
        return False
    
    def is_path_valid(self, path: Union[str, Path]) -> bool:
        """检查路径是否有效（在 workspace 内且未被排除）
        
        Args:
            path: 待检查的路径
            
        Returns:
            bool: 如果路径有效返回 True，否则返回 False
        """
        if not self.is_within_workspace(path):
            return False
        
        if self.is_excluded(path):
            return False
        
        return True
    
    def validate_path(self, path: Union[str, Path]) -> Path:
        """验证路径并返回解析后的路径
        
        Args:
            path: 待验证的路径
            
        Returns:
            Path: 解析后的路径
            
        Raises:
            ValueError: 如果路径不在 workspace 内
            PermissionError: 如果路径被排除
        """
        resolved = self.resolve_path(path)
        
        if not self.is_within_workspace(resolved):
            raise ValueError(
                f"Path '{path}' is outside workspace boundaries. "
                f"Resolved path: '{resolved}'"
            )
        
        if self.is_excluded(resolved):
            raise PermissionError(
                f"Path '{path}' is excluded from workspace operations. "
                f"Resolved path: '{resolved}'"
            )
        
        return resolved
    
    def get_workspace_roots(self) -> List[Path]:
        """获取所有 workspace 根路径
        
        Returns:
            List[Path]: workspace 根路径列表
        """
        return self._workspace_paths.copy()
    
    def get_main_workspace(self) -> Path:
        """获取主 workspace 路径
        
        Returns:
            Path: 主 workspace 路径
        """
        return self._workspace_paths[0]
    
    def get_relative_path(self, path: Union[str, Path]) -> Optional[Path]:
        """获取路径相对于主 workspace 的相对路径
        
        Args:
            path: 目标路径
            
        Returns:
            Optional[Path]: 相对路径，如果不在 workspace 内返回 None
        """
        try:
            resolved = self.resolve_path(path)
            main_workspace = self.get_main_workspace()
            return resolved.relative_to(main_workspace)
        except (ValueError, Exception):
            return None
    
    def find_workspace_for_path(self, path: Union[str, Path]) -> Optional[Path]:
        """查找路径所属的 workspace
        
        Args:
            path: 目标路径
            
        Returns:
            Optional[Path]: 包含该路径的 workspace 根路径，如果不在任何 workspace 内返回 None
        """
        try:
            resolved = self.resolve_path(path)
        except ValueError:
            return None
        
        for workspace_root in self._workspace_paths:
            try:
                resolved.relative_to(workspace_root)
                return workspace_root
            except ValueError:
                continue
        
        return None
    
    def list_excluded_patterns(self) -> List[str]:
        """获取所有排除模式
        
        Returns:
            List[str]: 排除模式列表
        """
        return self._excluded_patterns.copy()
    
    def add_excluded_pattern(self, pattern: str) -> None:
        """添加排除模式
        
        Args:
            pattern: 排除模式
        """
        if pattern not in self._excluded_patterns:
            self._excluded_patterns.append(pattern)
            self._logger.info(f"Added excluded pattern: {pattern}")
    
    def remove_excluded_pattern(self, pattern: str) -> bool:
        """移除排除模式
        
        Args:
            pattern: 要移除的排除模式
            
        Returns:
            bool: 如果成功移除返回 True，如果模式不存在返回 False
        """
        if pattern in self._excluded_patterns:
            self._excluded_patterns.remove(pattern)
            self._logger.info(f"Removed excluded pattern: {pattern}")
            return True
        return False
