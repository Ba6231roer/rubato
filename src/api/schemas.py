from pydantic import BaseModel
from typing import List, Optional


class ConfigInfo(BaseModel):
    name: str
    file: str
    description: str


class ConfigContent(BaseModel):
    name: str
    content: str


class ConfigUpdateRequest(BaseModel):
    content: str


class ConfigUpdateResponse(BaseModel):
    success: bool
    message: str


class StatusResponse(BaseModel):
    model: str
    mcp_enabled: bool
    mcp_connected: bool
    skills: List[str]
    browser_alive: Optional[bool] = None


class SkillInfo(BaseModel):
    name: str
    description: str
    version: str
    triggers: List[str]


class RoleInfo(BaseModel):
    name: str
    description: str
    is_current: bool


class ToolInfo(BaseModel):
    name: str
    description: str


class WSMessage(BaseModel):
    type: str
    content: str


class TestCaseTreeNode(BaseModel):
    name: str
    type: str
    path: str
    children: Optional[List['TestCaseTreeNode']] = None


TestCaseTreeNode.model_rebuild()


class TestCaseFileContent(BaseModel):
    path: str
    content: str


class TestCaseFileUpdateRequest(BaseModel):
    path: str
    content: str


class TestCaseFileUpdateResponse(BaseModel):
    success: bool
    message: str


class WorkspaceTreeNode(BaseModel):
    name: str
    type: str
    path: str
    file_type: Optional[str] = None
    children: Optional[List['WorkspaceTreeNode']] = None


WorkspaceTreeNode.model_rebuild()


class WorkspaceFileContent(BaseModel):
    path: str
    content: Optional[str] = None
    editable: bool = True
    file_type: str = "text"


class WorkspaceFileUpdateRequest(BaseModel):
    path: str
    content: str


class WorkspaceFileUpdateResponse(BaseModel):
    success: bool
    message: str


class WorkspaceConvertRequest(BaseModel):
    path: str


class WorkspaceConvertResponse(BaseModel):
    success: bool
    content: Optional[str] = None
    message: str = ""


class CommandRequest(BaseModel):
    command: str


class CommandInfo(BaseModel):
    name: str
    aliases: List[str]
    description: str
    usage: str


class CommandResponse(BaseModel):
    type: str
    message: str
    data: Optional[dict] = None
    actions: List[str] = []


class SessionInfo(BaseModel):
    session_id: str
    role: str = ""
    model: str = ""
    message_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    description: str = ""
    parent_session_id: Optional[str] = None


class SessionDetail(BaseModel):
    session_id: str
    role: str = ""
    model: str = ""
    message_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    description: str = ""
    parent_session_id: Optional[str] = None
    sub_sessions: List[dict] = []
    messages: List[dict] = []


class SessionLoadResponse(BaseModel):
    success: bool
    message: str
    session_id: str = ""
    messages: List[dict] = []
