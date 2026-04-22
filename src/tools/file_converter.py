from pathlib import Path
from typing import Optional

TEXT_BASED_EXTENSIONS = {
    '.md', '.txt', '.py', '.js', '.html', '.css', '.json',
    '.yaml', '.yml', '.xml', '.csv', '.log', '.cfg',
    '.ini', '.conf', '.sh', '.bat', '.ps1',
}

CONVERTIBLE_EXTENSIONS = {
    '.doc', '.docx', '.ppt', '.pptx', '.xlsx', '.xls', '.pdf',
}

ALL_SUPPORTED_EXTENSIONS = TEXT_BASED_EXTENSIONS | CONVERTIBLE_EXTENSIONS


def is_text_based(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in TEXT_BASED_EXTENSIONS


def is_convertible(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in CONVERTIBLE_EXTENSIONS


def is_supported(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in ALL_SUPPORTED_EXTENSIONS


def get_file_type(file_path: str) -> str:
    suffix = Path(file_path).suffix.lower()
    if suffix in TEXT_BASED_EXTENSIONS:
        return "text"
    elif suffix in {'.doc', '.docx'}:
        return "document"
    elif suffix in {'.ppt', '.pptx'}:
        return "presentation"
    elif suffix in {'.xlsx', '.xls'}:
        return "spreadsheet"
    elif suffix == '.pdf':
        return "pdf"
    return "unknown"


def convert_to_text(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    suffix = path.suffix.lower()

    if suffix in TEXT_BASED_EXTENSIONS:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()

    if suffix in CONVERTIBLE_EXTENSIONS:
        try:
            from markitdown import MarkItDown
            md = MarkItDown()
            result = md.convert(str(path))
            return result.text_content if result.text_content else ""
        except ImportError:
            raise RuntimeError("markitdown库未安装，请运行: pip install 'markitdown[docx,pdf,pptx,xlsx]'")
        except Exception as e:
            raise RuntimeError(f"文件转换失败: {str(e)}")

    raise ValueError(f"不支持的文件格式: {suffix}")
