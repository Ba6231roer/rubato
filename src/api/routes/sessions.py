from fastapi import APIRouter, HTTPException
from typing import List
from dataclasses import asdict

from ..schemas import SessionInfo, SessionDetail, SessionLoadResponse
from ...context.session_storage import MessageSerializer

router = APIRouter()

_app_state = None


def set_app_state(state):
    global _app_state
    _app_state = state


def get_app_state():
    return _app_state


@router.get("/sessions", response_model=List[SessionInfo])
async def list_sessions():
    state = get_app_state()

    if not state or not hasattr(state, 'agent') or not state.agent:
        raise HTTPException(status_code=503, detail="Agent未初始化")

    session_storage = state.agent.get_session_storage()
    if not session_storage:
        return []

    sessions = session_storage.list_sessions()
    result = []
    for meta in sessions:
        result.append(SessionInfo(
            session_id=meta.session_id,
            role=meta.role,
            model=meta.model,
            message_count=meta.message_count,
            created_at=meta.created_at,
            updated_at=meta.updated_at,
            description=meta.description,
            parent_session_id=meta.parent_session_id,
        ))
    return result


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str):
    state = get_app_state()

    if not state or not hasattr(state, 'agent') or not state.agent:
        raise HTTPException(status_code=503, detail="Agent未初始化")

    session_storage = state.agent.get_session_storage()
    if not session_storage:
        raise HTTPException(status_code=503, detail="会话存储未初始化")

    metadata = session_storage.get_session_metadata(session_id)
    if not metadata:
        raise HTTPException(status_code=404, detail=f"会话 '{session_id}' 不存在")

    try:
        _, messages = session_storage.load_session_with_meta(session_id)
        serialized_messages = MessageSerializer.serialize_list(messages)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"会话 '{session_id}' 不存在")
    except Exception:
        serialized_messages = []

    sub_sessions = [asdict(ref) for ref in metadata.sub_sessions]

    return SessionDetail(
        session_id=metadata.session_id,
        role=metadata.role,
        model=metadata.model,
        message_count=metadata.message_count,
        created_at=metadata.created_at,
        updated_at=metadata.updated_at,
        description=metadata.description,
        parent_session_id=metadata.parent_session_id,
        sub_sessions=sub_sessions,
        messages=serialized_messages,
    )


@router.post("/sessions/{session_id}/load", response_model=SessionLoadResponse)
async def load_session(session_id: str):
    state = get_app_state()

    if not state or not hasattr(state, 'agent') or not state.agent:
        raise HTTPException(status_code=503, detail="Agent未初始化")

    session_storage = state.agent.get_session_storage()
    if not session_storage:
        return SessionLoadResponse(
            success=False,
            message="会话存储未初始化",
        )

    if not session_storage.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"会话 '{session_id}' 不存在")

    success = state.agent.load_session(session_id)
    if not success:
        return SessionLoadResponse(
            success=False,
            message="加载会话失败",
        )

    try:
        _, messages = session_storage.load_session_with_meta(session_id)
        serialized_messages = MessageSerializer.serialize_list(messages)
    except Exception:
        serialized_messages = []

    return SessionLoadResponse(
        success=True,
        message="会话已加载",
        session_id=session_id,
        messages=serialized_messages,
    )
