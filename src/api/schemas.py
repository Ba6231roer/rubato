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


class ToolInfo(BaseModel):
    name: str
    description: str


class WSMessage(BaseModel):
    type: str
    content: str
