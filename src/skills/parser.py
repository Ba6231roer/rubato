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
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                yaml_content = parts[1].strip()
                body = parts[2].strip()
                
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
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                return yaml.safe_load(parts[1].strip())
        return None
