from fastapi import APIRouter, HTTPException
from pathlib import Path
from typing import List, Optional
import os

from ..schemas import (
    WorkspaceTreeNode, WorkspaceFileContent,
    WorkspaceFileUpdateRequest, WorkspaceFileUpdateResponse,
    WorkspaceConvertRequest, WorkspaceConvertResponse
)

router = APIRouter()

TEXT_BASED_EXTENSIONS = {
    '.md', '.txt', '.py', '.js', '.html', '.css', '.json',
    '.yaml', '.yml', '.xml', '.csv', '.log', '.cfg',
    '.ini', '.conf', '.sh', '.bat', '.ps1'
}

ALL_SUPPORTED_EXTENSIONS = TEXT_BASED_EXTENSIONS | {
    '.doc', '.docx', '.ppt', '.pptx', '.xlsx', '.xls', '.pdf'
}

FILE_TYPE_MAP = {}
for ext in TEXT_BASED_EXTENSIONS:
    FILE_TYPE_MAP[ext] = "text"
for ext in ('.doc', '.docx'):
    FILE_TYPE_MAP[ext] = "document"
for ext in ('.ppt', '.pptx'):
    FILE_TYPE_MAP[ext] = "presentation"
for ext in ('.xlsx', '.xls'):
    FILE_TYPE_MAP[ext] = "spreadsheet"
FILE_TYPE_MAP['.pdf'] = "pdf"


def get_workspace_path() -> Path:
    return Path("workspace")


def build_tree(base_path: Path, current_path: Path) -> List[WorkspaceTreeNode]:
    nodes = []
    try:
        items = sorted(current_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        for item in items:
            if item.is_dir():
                children = build_tree(base_path, item)
                if children:
                    relative_path = str(item.relative_to(base_path))
                    nodes.append(WorkspaceTreeNode(
                        name=item.name,
                        type="folder",
                        path=relative_path,
                        file_type=None,
                        children=children
                    ))
            elif item.suffix.lower() in ALL_SUPPORTED_EXTENSIONS:
                relative_path = str(item.relative_to(base_path))
                file_type = FILE_TYPE_MAP.get(item.suffix.lower(), "text")
                nodes.append(WorkspaceTreeNode(
                    name=item.name,
                    type="file",
                    path=relative_path,
                    file_type=file_type
                ))
    except PermissionError:
        pass
    return nodes


@router.get("/workspace/tree", response_model=List[WorkspaceTreeNode])
async def get_workspace_tree():
    workspace_path = get_workspace_path()
    if not workspace_path.exists():
        return []
    return build_tree(workspace_path, workspace_path)


@router.get("/workspace/file", response_model=WorkspaceFileContent)
async def get_workspace_file(path: str):
    workspace_path = get_workspace_path()
    file_path = workspace_path / path

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {path}")

    resolved_file = file_path.resolve()
    resolved_workspace = workspace_path.resolve()
    if not str(resolved_file).startswith(str(resolved_workspace)):
        raise HTTPException(status_code=403, detail="无权访问此路径")

    if file_path.suffix.lower() not in ALL_SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {file_path.suffix}")

    file_type = FILE_TYPE_MAP.get(file_path.suffix.lower(), "text")

    if file_path.suffix.lower() in TEXT_BASED_EXTENSIONS:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return WorkspaceFileContent(path=path, content=content, editable=True, file_type=file_type)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")
    else:
        stat = file_path.stat()
        return WorkspaceFileContent(
            path=path,
            content=None,
            editable=False,
            file_type=file_type
        )


@router.put("/workspace/file", response_model=WorkspaceFileUpdateResponse)
async def update_workspace_file(request: WorkspaceFileUpdateRequest):
    workspace_path = get_workspace_path()
    file_path = workspace_path / request.path

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {request.path}")

    resolved_file = file_path.resolve()
    resolved_workspace = workspace_path.resolve()
    if not str(resolved_file).startswith(str(resolved_workspace)):
        raise HTTPException(status_code=403, detail="无权访问此路径")

    if file_path.suffix.lower() not in TEXT_BASED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持保存文本格式文件")

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(request.content)
        return WorkspaceFileUpdateResponse(success=True, message="文件已保存")
    except Exception as e:
        return WorkspaceFileUpdateResponse(success=False, message=f"保存失败: {str(e)}")


@router.post("/workspace/convert", response_model=WorkspaceConvertResponse)
async def convert_workspace_file(request: WorkspaceConvertRequest):
    workspace_path = get_workspace_path()
    file_path = workspace_path / request.path

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {request.path}")

    resolved_file = file_path.resolve()
    resolved_workspace = workspace_path.resolve()
    if not str(resolved_file).startswith(str(resolved_workspace)):
        raise HTTPException(status_code=403, detail="无权访问此路径")

    try:
        from ...tools.file_converter import convert_to_text, is_text_based
        if is_text_based(str(file_path)):
            content = convert_to_text(str(file_path))
        else:
            content = convert_to_text(str(file_path))
        return WorkspaceConvertResponse(success=True, content=content, message="转换成功")
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        return WorkspaceConvertResponse(success=False, content=None, message=f"转换失败: {str(e)}")
