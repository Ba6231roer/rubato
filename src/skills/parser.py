import yaml
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel


class SkillMetadata(BaseModel):
    """Skill元数据"""
    name: str
    description: str
    version: str = "1.0"
    author: str = ""
    triggers: List[str] = []
    tools: List[str] = []
    paths: List[str] = []
    file_path: str = ""


class SkillParser:
    """Skill解析器，解析md格式的Skill文件"""

    @staticmethod
    def _split_yaml_header(content: str) -> tuple[Optional[str], str]:
        """分离YAML头和正文，返回(yaml_content, body)；无YAML头时yaml_content为None"""
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                return parts[1].strip(), parts[2].strip()
        return None, content

    @staticmethod
    def parse_file(file_path: Path) -> tuple[SkillMetadata, str]:
        """解析Skill文件，返回元数据和内容"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        metadata, body = SkillParser.parse_content(content)
        metadata.file_path = str(file_path)

        return metadata, body

    @staticmethod
    def parse_content(content: str) -> tuple[SkillMetadata, str]:
        """解析Skill内容"""
        yaml_content, body = SkillParser._split_yaml_header(content)

        if yaml_content is not None:
            metadata_dict = yaml.safe_load(yaml_content)
            metadata = SkillMetadata(
                name=metadata_dict.get('name', ''),
                description=metadata_dict.get('description', ''),
                version=str(metadata_dict.get('version', '1.0')),
                author=metadata_dict.get('author', ''),
                triggers=metadata_dict.get('triggers', []),
                tools=metadata_dict.get('tools', []),
                paths=metadata_dict.get('paths', []),
            )
            return metadata, body

        return SkillMetadata(name='', description=''), content

    @staticmethod
    def extract_yaml_header(content: str) -> Optional[dict]:
        """提取YAML头"""
        yaml_content, _ = SkillParser._split_yaml_header(content)
        if yaml_content is not None:
            return yaml.safe_load(yaml_content)
        return None
