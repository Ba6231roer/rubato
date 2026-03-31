from dataclasses import dataclass, field
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.agent import RubatoAgent
    from ..core.role_manager import RoleManager
    from ..skills.loader import SkillLoader
    from ..mcp.client import MCPManager
    from ..config.loader import ConfigLoader
    from ..config.models import AppConfig


@dataclass
class CommandContext:
    agent: Optional['RubatoAgent'] = None
    skill_loader: Optional['SkillLoader'] = None
    mcp_manager: Optional['MCPManager'] = None
    role_manager: Optional['RoleManager'] = None
    config_loader: Optional['ConfigLoader'] = None
    config: Optional['AppConfig'] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_agent(self) -> 'RubatoAgent':
        if not self.agent:
            raise ValueError("Agent not available in context")
        return self.agent
    
    def get_skill_loader(self) -> 'SkillLoader':
        if not self.skill_loader:
            raise ValueError("SkillLoader not available in context")
        return self.skill_loader
    
    def get_mcp_manager(self) -> 'MCPManager':
        if not self.mcp_manager:
            raise ValueError("MCPManager not available in context")
        return self.mcp_manager
    
    def get_role_manager(self) -> 'RoleManager':
        if not self.role_manager:
            raise ValueError("RoleManager not available in context")
        return self.role_manager
    
    def get_config_loader(self) -> 'ConfigLoader':
        if not self.config_loader:
            raise ValueError("ConfigLoader not available in context")
        return self.config_loader
    
    def get_config(self) -> 'AppConfig':
        if not self.config:
            raise ValueError("AppConfig not available in context")
        return self.config
