from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path
import yaml


@dataclass
class ToolParameter:
    name: str
    type: str
    description: str = ""
    required: bool = True
    default: Optional[Any] = None


@dataclass
class ToolExample:
    description: str = ""
    code: str = ""


@dataclass
class ToolDoc:
    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)
    examples: List[ToolExample] = field(default_factory=list)
    category: str = "builtin"


BUILTIN_TOOLS_DOCS: Dict[str, ToolDoc] = {
    "spawn_agent": ToolDoc(
        name="spawn_agent",
        description="创建子智能体执行特定任务。子智能体将继承当前角色的所有工具权限和配置。",
        parameters=[
            ToolParameter("agent_name", "str", "子智能体名称", required=True),
            ToolParameter("task", "str", "要执行的任务描述", required=True),
            ToolParameter("system_prompt", "str", "自定义系统提示词", required=False),
        ],
        examples=[
            ToolExample(
                description="创建搜索子智能体",
                code='spawn_agent(agent_name="search", task="搜索包含\'error\'的日志文件")'
            )
        ],
        category="builtin"
    ),
    "shell_tool": ToolDoc(
        name="shell_tool",
        description="执行Shell命令。",
        parameters=[
            ToolParameter("commands", "str", "要执行的shell命令字符串，例如 'git status' 或 'dir'", required=True),
        ],
        examples=[
            ToolExample(
                description="查看git状态",
                code='shell_tool(commands="git status")'
            )
        ],
        category="builtin"
    ),
    "file_read": ToolDoc(
        name="file_read",
        description="读取文件内容。",
        parameters=[
            ToolParameter("path", "str", "文件路径", required=True),
            ToolParameter("encoding", "str", "编码，默认utf-8", required=False, default="utf-8"),
            ToolParameter("start_line", "int", "起始行号", required=False),
            ToolParameter("end_line", "int", "结束行号", required=False),
        ],
        examples=[
            ToolExample(
                description="读取文件前50行",
                code='file_read(path="src/main.py", start_line=1, end_line=50)'
            )
        ],
        category="builtin"
    ),
    "file_write": ToolDoc(
        name="file_write",
        description="写入文件内容。",
        parameters=[
            ToolParameter("path", "str", "文件路径", required=True),
            ToolParameter("content", "str", "文件内容", required=True),
            ToolParameter("mode", "str", "写入模式，默认overwrite", required=False, default="overwrite"),
        ],
        examples=[
            ToolExample(
                description="写入测试结果",
                code='file_write(path="output/result.md", content="# 测试结果\\n...")'
            )
        ],
        category="builtin"
    ),
    "file_replace": ToolDoc(
        name="file_replace",
        description="替换文件中的内容。",
        parameters=[
            ToolParameter("path", "str", "文件路径", required=True),
            ToolParameter("old_str", "str", "要替换的内容", required=True),
            ToolParameter("new_str", "str", "替换后的内容", required=True),
        ],
        examples=[
            ToolExample(
                description="替换配置项",
                code='file_replace(path="config.yaml", old_str="enabled: false", new_str="enabled: true")'
            )
        ],
        category="builtin"
    ),
    "file_list": ToolDoc(
        name="file_list",
        description="列出目录内容。",
        parameters=[
            ToolParameter("path", "str", "目录路径", required=True),
            ToolParameter("pattern", "str", "文件模式匹配", required=False),
            ToolParameter("recursive", "bool", "是否递归，默认false", required=False, default=False),
        ],
        examples=[
            ToolExample(
                description="递归列出Python文件",
                code='file_list(path="src", pattern="*.py", recursive=true)'
            )
        ],
        category="builtin"
    ),
    "file_search": ToolDoc(
        name="file_search",
        description="搜索文件内容。",
        parameters=[
            ToolParameter("path", "str", "搜索路径", required=True),
            ToolParameter("pattern", "str", "搜索模式", required=True),
            ToolParameter("file_pattern", "str", "文件模式", required=False),
        ],
        examples=[
            ToolExample(
                description="搜索测试函数",
                code='file_search(path="src", pattern="def.*test", file_pattern="*.py")'
            )
        ],
        category="builtin"
    ),
    "file_exists": ToolDoc(
        name="file_exists",
        description="检查文件是否存在。",
        parameters=[
            ToolParameter("path", "str", "文件路径", required=True),
        ],
        examples=[
            ToolExample(
                description="检查配置文件",
                code='file_exists(path="config.yaml")'
            )
        ],
        category="builtin"
    ),
    "file_mkdir": ToolDoc(
        name="file_mkdir",
        description="创建目录。",
        parameters=[
            ToolParameter("path", "str", "目录路径", required=True),
        ],
        examples=[
            ToolExample(
                description="创建输出目录",
                code='file_mkdir(path="output/results")'
            )
        ],
        category="builtin"
    ),
    "file_delete": ToolDoc(
        name="file_delete",
        description="删除文件。",
        parameters=[
            ToolParameter("path", "str", "文件路径", required=True),
        ],
        examples=[
            ToolExample(
                description="删除临时文件",
                code='file_delete(path="temp/cache.tmp")'
            )
        ],
        category="builtin"
    ),
}


class ToolDocsGenerator:
    """工具说明文档生成器"""
    
    def __init__(self, include_examples: bool = True):
        self.include_examples = include_examples
    
    def generate_docs(
        self,
        builtin_tools: Optional[List[str]] = None,
        mcp_tools: Optional[List[Dict[str, Any]]] = None,
        skills: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        sections = []
        
        if builtin_tools:
            sections.append(self._generate_builtin_docs(builtin_tools))
        
        if mcp_tools:
            sections.append(self._generate_mcp_docs(mcp_tools))
        
        if skills:
            sections.append(self._generate_skill_docs(skills))
        
        if sections:
            return "\n\n# 可用工具说明\n\n" + "\n\n".join(sections)
        return ""
    
    def _generate_builtin_docs(self, tools: List[str]) -> str:
        lines = ["## 系统内置工具\n"]
        
        for tool_name in tools:
            if tool_name in BUILTIN_TOOLS_DOCS:
                doc = BUILTIN_TOOLS_DOCS[tool_name]
                lines.append(self._format_tool_doc(doc))
        
        return "\n".join(lines)
    
    def _generate_mcp_docs(self, tools: List[Dict[str, Any]]) -> str:
        lines = ["## MCP工具\n"]
        
        for tool in tools:
            name = tool.get("name", "unknown")
            description = tool.get("description", "")
            parameters = tool.get("parameters", [])
            
            doc = ToolDoc(
                name=name,
                description=description,
                parameters=[
                    ToolParameter(
                        name=p.get("name", ""),
                        type=p.get("type", "any"),
                        description=p.get("description", ""),
                        required=p.get("required", True)
                    )
                    for p in parameters
                ],
                examples=[],
                category="mcp"
            )
            lines.append(self._format_tool_doc(doc))
        
        return "\n".join(lines)
    
    def _generate_skill_docs(self, skills: List[Dict[str, Any]]) -> str:
        lines = ["## Skill\n"]
        
        for skill in skills:
            name = skill.get("name", "unknown")
            description = skill.get("description", "")
            triggers = skill.get("triggers", [])
            required_tools = skill.get("required_tools", [])
            
            lines.append(f"### {name}")
            lines.append(f"{description}")
            
            if triggers:
                lines.append(f"\n**触发词**：{', '.join(triggers)}")
            
            if required_tools:
                lines.append(f"\n**所需工具**：{', '.join(required_tools)}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_tool_doc(self, doc: ToolDoc) -> str:
        lines = [f"### {doc.name}"]
        lines.append(f"{doc.description}")
        
        if doc.parameters:
            lines.append("\n**参数**：")
            for param in doc.parameters:
                required_mark = "" if param.required else ", 可选"
                default_info = f", 默认{param.default}" if param.default is not None else ""
                lines.append(f"- `{param.name}` ({param.type}{required_mark}{default_info}): {param.description}")
        
        if self.include_examples and doc.examples:
            lines.append("\n**示例**：")
            for example in doc.examples:
                if example.description:
                    lines.append(f"```")
                    lines.append(example.code)
                    lines.append(f"```")
        
        lines.append("")
        return "\n".join(lines)


def load_skill_metadata(skill_path: Path) -> Optional[Dict[str, Any]]:
    """加载Skill元数据（yaml头）"""
    try:
        content = skill_path.read_text(encoding='utf-8')
        
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                yaml_content = parts[1].strip()
                metadata = yaml.safe_load(yaml_content)
                
                return {
                    "name": metadata.get('name', skill_path.stem),
                    "description": metadata.get('description', ''),
                    "triggers": metadata.get('triggers', []),
                    "required_tools": metadata.get('required_tools', []),
                    "path": str(skill_path)
                }
    except Exception:
        pass
    
    return None


def generate_tool_docs_for_prompt(
    builtin_tools: Optional[List[str]] = None,
    mcp_tools: Optional[List[Dict[str, Any]]] = None,
    skills: Optional[List[Dict[str, Any]]] = None,
    include_examples: bool = True
) -> str:
    """生成用于系统提示词的工具说明文档"""
    generator = ToolDocsGenerator(include_examples=include_examples)
    return generator.generate_docs(builtin_tools, mcp_tools, skills)
