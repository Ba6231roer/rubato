import yaml
from pathlib import Path
from typing import Dict, List, Optional
from itertools import chain

from .models import RoleConfig
from .validators import ConfigValidationError, handle_pydantic_error, replace_env_vars


class RoleConfigLoader:
    """角色配置加载器"""

    def __init__(self, roles_dir: str = "config/roles"):
        self.roles_dir = Path(roles_dir)
        self._roles: Dict[str, RoleConfig] = {}
        self._loaded = False

    def load_all(self) -> Dict[str, RoleConfig]:
        """加载所有角色配置"""
        if self._loaded:
            return self._roles

        if not self.roles_dir.exists():
            self.roles_dir.mkdir(parents=True, exist_ok=True)
            self._loaded = True
            return self._roles

        role_files = chain(self.roles_dir.glob("*.yaml"), self.roles_dir.glob("*.yml"))
        for role_file in role_files:
            try:
                role_config = self._load_role_file(role_file)
                if role_config:
                    self._roles[role_config.name] = role_config
            except Exception as e:
                raise ConfigValidationError(f"加载角色配置文件 {role_file} 失败: {e}")

        self._loaded = True
        return self._roles

    def _load_role_file(self, file_path: Path) -> Optional[RoleConfig]:
        """加载单个角色配置文件"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        content = replace_env_vars(content)

        data = yaml.safe_load(content)
        if not data:
            return None

        try:
            return RoleConfig(**data)
        except Exception as e:
            if hasattr(e, 'errors'):
                raise handle_pydantic_error(e)
            raise

    def get_role(self, name: str) -> Optional[RoleConfig]:
        """获取指定角色配置"""
        if not self._loaded:
            self.load_all()
        return self._roles.get(name)

    def get_all_roles(self) -> Dict[str, RoleConfig]:
        """获取所有角色配置"""
        if not self._loaded:
            self.load_all()
        return self._roles

    def list_roles(self) -> List[str]:
        """列出所有角色名称"""
        if not self._loaded:
            self.load_all()
        return list(self._roles.keys())

    def reload(self) -> Dict[str, RoleConfig]:
        """重新加载所有角色配置"""
        self._loaded = False
        self._roles.clear()
        return self.load_all()

    def load_system_prompt(self, role_config: RoleConfig) -> str:
        """加载角色的系统提示词"""
        prompt_file = Path(role_config.system_prompt_file)

        if not prompt_file.is_absolute():
            prompt_file = Path.cwd() / prompt_file

        if not prompt_file.exists():
            raise ConfigValidationError(f"系统提示词文件不存在: {prompt_file}")

        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read()
