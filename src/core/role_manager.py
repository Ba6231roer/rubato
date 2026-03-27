from typing import Dict, List, Optional, Any
from pathlib import Path

from ..config.role_loader import RoleConfigLoader
from ..config.models import RoleConfig, ModelConfig, FullModelConfig
from ..config.validators import ConfigValidationError


class RoleManager:
    """角色管理器"""
    
    def __init__(
        self,
        roles_dir: str = "config/roles",
        default_model_config: Optional[FullModelConfig] = None
    ):
        self.loader = RoleConfigLoader(roles_dir)
        self._default_model_config = default_model_config
        self._current_role: Optional[RoleConfig] = None
        self._merged_model_configs: Dict[str, ModelConfig] = {}
    
    def load_roles(self) -> Dict[str, RoleConfig]:
        """加载所有角色配置"""
        roles = self.loader.load_all()
        for name, role in roles.items():
            self._merged_model_configs[name] = self._merge_model_config(role)
        return roles
    
    def _merge_model_config(self, role_config: RoleConfig) -> ModelConfig:
        """合并角色模型配置与默认配置"""
        if role_config.model.inherit and self._default_model_config:
            base_config = self._default_model_config.model
            
            merged = ModelConfig(
                provider=role_config.model.provider or base_config.provider,
                name=role_config.model.name or base_config.name,
                api_key=role_config.model.api_key or base_config.api_key,
                base_url=role_config.model.base_url or base_config.base_url,
                temperature=role_config.model.temperature 
                    if role_config.model.temperature is not None 
                    else base_config.temperature,
                max_tokens=role_config.model.max_tokens or base_config.max_tokens
            )
            return merged
        elif not role_config.model.inherit:
            if not role_config.model.provider or not role_config.model.name:
                raise ConfigValidationError(
                    f"角色 {role_config.name} 未继承默认模型配置，必须提供 provider 和 name"
                )
            merged = ModelConfig(
                provider=role_config.model.provider,
                name=role_config.model.name,
                api_key=role_config.model.api_key or "",
                base_url=role_config.model.base_url,
                temperature=role_config.model.temperature or 0.7,
                max_tokens=role_config.model.max_tokens or 2000
            )
            return merged
        else:
            raise ConfigValidationError(
                f"角色 {role_config.name} 需要模型配置，但未提供默认模型配置"
            )
    
    def get_role(self, name: str) -> Optional[RoleConfig]:
        """获取指定角色配置"""
        return self.loader.get_role(name)
    
    def get_merged_model_config(self, role_name: str) -> Optional[ModelConfig]:
        """获取角色的合并后模型配置"""
        if role_name not in self._merged_model_configs:
            role = self.get_role(role_name)
            if role:
                self._merged_model_configs[role_name] = self._merge_model_config(role)
        return self._merged_model_configs.get(role_name)
    
    def switch_role(self, name: str) -> RoleConfig:
        """切换当前角色"""
        role = self.loader.get_role(name)
        if not role:
            raise ConfigValidationError(f"角色 '{name}' 不存在")
        self._current_role = role
        return role
    
    def get_current_role(self) -> Optional[RoleConfig]:
        """获取当前角色"""
        return self._current_role
    
    def list_roles(self) -> List[str]:
        """列出所有角色名称"""
        return self.loader.list_roles()
    
    def get_all_roles(self) -> Dict[str, RoleConfig]:
        """获取所有角色配置"""
        return self.loader.get_all_roles()
    
    def get_role_info(self, name: str) -> Optional[Dict[str, Any]]:
        """获取角色详细信息"""
        role = self.get_role(name)
        if not role:
            return None
        
        merged_model = self.get_merged_model_config(name)
        
        return {
            "name": role.name,
            "description": role.description,
            "system_prompt_file": role.system_prompt_file,
            "model": {
                "inherit": role.model.inherit,
                "provider": merged_model.provider if merged_model else None,
                "name": merged_model.name if merged_model else None,
                "temperature": merged_model.temperature if merged_model else None,
                "max_tokens": merged_model.max_tokens if merged_model else None,
            },
            "execution": {
                "max_context_tokens": role.execution.max_context_tokens,
                "timeout": role.execution.timeout,
                "recursion_limit": role.execution.recursion_limit,
                "sub_agent_recursion_limit": role.execution.sub_agent_recursion_limit,
            },
            "available_tools": role.available_tools,
            "metadata": role.metadata
        }
    
    def load_system_prompt(self, role_name: Optional[str] = None) -> str:
        """加载角色的系统提示词"""
        role = self.get_role(role_name) if role_name else self._current_role
        if not role:
            raise ConfigValidationError("未指定角色，无法加载系统提示词")
        return self.loader.load_system_prompt(role)
    
    def reload_roles(self) -> Dict[str, RoleConfig]:
        """重新加载所有角色配置"""
        self._merged_model_configs.clear()
        return self.loader.reload()
    
    def set_default_model_config(self, config: FullModelConfig) -> None:
        """设置默认模型配置"""
        self._default_model_config = config
        self._merged_model_configs.clear()
        for name, role in self.get_all_roles().items():
            self._merged_model_configs[name] = self._merge_model_config(role)
    
    def has_role(self, name: str) -> bool:
        """检查角色是否存在"""
        return name in self.loader.list_roles()
    
    def get_available_tools(self, role_name: Optional[str] = None) -> List[str]:
        """获取角色的可用工具列表"""
        role = self.get_role(role_name) if role_name else self._current_role
        if not role:
            return []
        return role.available_tools
