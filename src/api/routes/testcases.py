from fastapi import APIRouter, HTTPException
from pathlib import Path
from typing import List, Optional
import yaml

from ..schemas import (
    TestCaseTreeNode, TestCaseFileContent, 
    TestCaseFileUpdateRequest, TestCaseFileUpdateResponse
)

router = APIRouter()

CONFIG_DIR = Path("config")
DEFAULT_TEST_CASE_PATH = Path("test_case_path")
DEFAULT_KNOWLEDGE_PATH = Path("knowledge_path")


def get_test_case_path() -> Path:
    config_file = CONFIG_DIR / "test_config.yaml"
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
            path = config.get('test_case_path', '')
            if path:
                return Path(path)
    return DEFAULT_TEST_CASE_PATH


def get_knowledge_path() -> Path:
    config_file = CONFIG_DIR / "test_config.yaml"
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
            path = config.get('knowledge_path', '')
            if path:
                return Path(path)
    return DEFAULT_KNOWLEDGE_PATH


def build_tree(base_path: Path, current_path: Path) -> List[TestCaseTreeNode]:
    nodes = []
    try:
        items = sorted(current_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        for item in items:
            if item.is_dir():
                children = build_tree(base_path, item)
                if children:
                    relative_path = str(item.relative_to(base_path))
                    nodes.append(TestCaseTreeNode(
                        name=item.name,
                        type="folder",
                        path=relative_path,
                        children=children
                    ))
            elif item.suffix.lower() == '.md':
                relative_path = str(item.relative_to(base_path))
                nodes.append(TestCaseTreeNode(
                    name=item.name,
                    type="file",
                    path=relative_path
                ))
    except PermissionError:
        pass
    return nodes


@router.get("/testcases/tree", response_model=List[TestCaseTreeNode])
async def get_testcase_tree():
    test_case_path = get_test_case_path()
    if not test_case_path.exists():
        return []
    return build_tree(test_case_path, test_case_path)


@router.get("/testcases/file", response_model=TestCaseFileContent)
async def get_testcase_file(path: str):
    test_case_path = get_test_case_path()
    file_path = test_case_path / path
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {path}")
    
    if not str(file_path.resolve()).startswith(str(test_case_path.resolve())):
        raise HTTPException(status_code=403, detail="无权访问此路径")
    
    if file_path.suffix.lower() != '.md':
        raise HTTPException(status_code=400, detail="仅支持读取 .md 文件")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return TestCaseFileContent(path=path, content=content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")


@router.put("/testcases/file", response_model=TestCaseFileUpdateResponse)
async def update_testcase_file(request: TestCaseFileUpdateRequest):
    test_case_path = get_test_case_path()
    file_path = test_case_path / request.path
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {request.path}")
    
    if not str(file_path.resolve()).startswith(str(test_case_path.resolve())):
        raise HTTPException(status_code=403, detail="无权访问此路径")
    
    if file_path.suffix.lower() != '.md':
        raise HTTPException(status_code=400, detail="仅支持保存 .md 文件")
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(request.content)
        return TestCaseFileUpdateResponse(success=True, message="文件已保存")
    except Exception as e:
        return TestCaseFileUpdateResponse(success=False, message=f"保存失败: {str(e)}")


@router.get("/knowledge/tree", response_model=List[TestCaseTreeNode])
async def get_knowledge_tree():
    knowledge_path = get_knowledge_path()
    if not knowledge_path.exists():
        return []
    return build_tree(knowledge_path, knowledge_path)


@router.get("/knowledge/file", response_model=TestCaseFileContent)
async def get_knowledge_file(path: str):
    knowledge_path = get_knowledge_path()
    file_path = knowledge_path / path
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {path}")
    
    if not str(file_path.resolve()).startswith(str(knowledge_path.resolve())):
        raise HTTPException(status_code=403, detail="无权访问此路径")
    
    if file_path.suffix.lower() != '.md':
        raise HTTPException(status_code=400, detail="仅支持读取 .md 文件")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return TestCaseFileContent(path=path, content=content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")


@router.put("/knowledge/file", response_model=TestCaseFileUpdateResponse)
async def update_knowledge_file(request: TestCaseFileUpdateRequest):
    knowledge_path = get_knowledge_path()
    file_path = knowledge_path / request.path
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {request.path}")
    
    if not str(file_path.resolve()).startswith(str(knowledge_path.resolve())):
        raise HTTPException(status_code=403, detail="无权访问此路径")
    
    if file_path.suffix.lower() != '.md':
        raise HTTPException(status_code=400, detail="仅支持保存 .md 文件")
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(request.content)
        return TestCaseFileUpdateResponse(success=True, message="文件已保存")
    except Exception as e:
        return TestCaseFileUpdateResponse(success=False, message=f"保存失败: {str(e)}")
