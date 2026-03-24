from fastapi import APIRouter, HTTPException
from pathlib import Path
from typing import Dict, List
import yaml

from ..schemas import (
    ConfigInfo, ConfigContent, ConfigUpdateRequest, 
    ConfigUpdateResponse, StatusResponse, SkillInfo, ToolInfo
)

router = APIRouter()

CONFIG_DIR = Path("config")
SKILLS_DIR = Path("skills")

CONFIG_FILES = {
    "model": {
        "file": "model_config.yaml",
        "description": "模型配置 - API密钥、模型名称、参数设置"
    },
    "mcp": {
        "file": "mcp_config.yaml",
        "description": "MCP配置 - Playwright浏览器自动化设置"
    },
    "prompt": {
        "file": "prompt_config.yaml",
        "description": "提示词配置 - 系统提示词文件路径"
    },
    "skills": {
        "file": "skills_config.yaml",
        "description": "Skill配置 - Skill目录和加载设置"
    },
    "test": {
        "file": "test_config.yaml",
        "description": "测试配置 - 系统标识、应用标识、测试案例路径"
    }
}

_app_state = None


def set_app_state(state):
    global _app_state
    _app_state = state


def get_app_state():
    return _app_state


@router.get("/configs", response_model=List[ConfigInfo])
async def list_configs():
    configs = []
    for name, info in CONFIG_FILES.items():
        configs.append(ConfigInfo(
            name=name,
            file=info["file"],
            description=info["description"]
        ))
    return configs


@router.get("/configs/{config_name}", response_model=ConfigContent)
async def get_config(config_name: str):
    if config_name not in CONFIG_FILES:
        raise HTTPException(status_code=404, detail=f"配置 '{config_name}' 不存在")
    
    file_path = CONFIG_DIR / CONFIG_FILES[config_name]["file"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"配置文件不存在: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return ConfigContent(name=config_name, content=content)


@router.put("/configs/{config_name}", response_model=ConfigUpdateResponse)
async def update_config(config_name: str, request: ConfigUpdateRequest):
    if config_name not in CONFIG_FILES:
        raise HTTPException(status_code=404, detail=f"配置 '{config_name}' 不存在")
    
    try:
        yaml.safe_load(request.content)
    except yaml.YAMLError as e:
        return ConfigUpdateResponse(success=False, message=f"YAML格式错误: {str(e)}")
    
    file_path = CONFIG_DIR / CONFIG_FILES[config_name]["file"]
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(request.content)
        
        if _app_state and hasattr(_app_state, 'reload_config'):
            await _app_state.reload_config(config_name)
        
        return ConfigUpdateResponse(success=True, message="配置已保存")
    except Exception as e:
        return ConfigUpdateResponse(success=False, message=f"保存失败: {str(e)}")


@router.get("/status", response_model=StatusResponse)
async def get_status():
    state = get_app_state()
    
    model_name = "unknown"
    mcp_enabled = False
    mcp_connected = False
    skills: List[str] = []
    browser_alive = None
    
    if state:
        if hasattr(state, 'config') and state.config:
            if hasattr(state.config, 'model') and state.config.model:
                model_name = state.config.model.model.name if state.config.model.model else "unknown"
            if hasattr(state.config, 'mcp') and state.config.mcp:
                mcp_enabled = state.config.mcp.playwright.enabled if state.config.mcp.playwright else False
        
        if hasattr(state, 'mcp_manager') and state.mcp_manager:
            mcp_connected = True
            browser_alive = state.mcp_manager._browser_alive if hasattr(state.mcp_manager, '_browser_alive') else None
        
        if hasattr(state, 'skill_loader') and state.skill_loader:
            skills = [s.name for s in state.skill_loader.list_skills()]
    
    return StatusResponse(
        model=model_name,
        mcp_enabled=mcp_enabled,
        mcp_connected=mcp_connected,
        skills=skills,
        browser_alive=browser_alive
    )


@router.get("/skills", response_model=List[SkillInfo])
async def list_skills():
    state = get_app_state()
    skills = []
    
    if state and hasattr(state, 'skill_loader') and state.skill_loader:
        for metadata in state.skill_loader.list_skills():
            skills.append(SkillInfo(
                name=metadata.name,
                description=metadata.description,
                version=metadata.version,
                triggers=metadata.triggers
            ))
    
    return skills


@router.get("/tools", response_model=List[ToolInfo])
async def list_tools():
    from ...mcp.tools import get_all_tools
    
    tools = []
    for tool in get_all_tools():
        tools.append(ToolInfo(
            name=tool.name,
            description=tool.description
        ))
    
    return tools
