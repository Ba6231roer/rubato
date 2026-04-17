import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.tools.docs import (
    ToolDocsGenerator,
    ToolDoc,
    ToolParameter,
    ToolExample,
    BUILTIN_TOOLS_DOCS,
    generate_tool_docs_for_prompt,
)


class TestBuiltinToolsDocs:
    """BUILTIN_TOOLS_DOCS 内容验证测试"""

    def test_contains_spawn_agent(self):
        assert "spawn_agent" in BUILTIN_TOOLS_DOCS

    def test_contains_shell_tool(self):
        assert "shell_tool" in BUILTIN_TOOLS_DOCS

    def test_contains_file_tools(self):
        file_tool_names = [
            "file_read", "file_write", "file_replace",
            "file_list", "file_search", "file_exists",
            "file_mkdir", "file_delete"
        ]
        for name in file_tool_names:
            assert name in BUILTIN_TOOLS_DOCS, f"Missing tool doc: {name}"

    def test_all_docs_are_tool_doc_instances(self):
        for name, doc in BUILTIN_TOOLS_DOCS.items():
            assert isinstance(doc, ToolDoc), f"{name} is not a ToolDoc instance"

    def test_all_docs_have_name_matching_key(self):
        for key, doc in BUILTIN_TOOLS_DOCS.items():
            assert doc.name == key, f"Key '{key}' does not match doc.name '{doc.name}'"

    def test_all_docs_have_description(self):
        for name, doc in BUILTIN_TOOLS_DOCS.items():
            assert doc.description, f"Tool '{name}' has empty description"

    def test_all_docs_have_parameters(self):
        for name, doc in BUILTIN_TOOLS_DOCS.items():
            assert len(doc.parameters) > 0, f"Tool '{name}' has no parameters"

    def test_all_docs_category_is_builtin(self):
        for name, doc in BUILTIN_TOOLS_DOCS.items():
            assert doc.category == "builtin", f"Tool '{name}' category is not 'builtin'"

    def test_spawn_agent_doc_structure(self):
        doc = BUILTIN_TOOLS_DOCS["spawn_agent"]
        param_names = [p.name for p in doc.parameters]
        assert "agent_name" in param_names
        assert "task" in param_names
        assert len(doc.examples) > 0

    def test_shell_tool_doc_structure(self):
        doc = BUILTIN_TOOLS_DOCS["shell_tool"]
        param_names = [p.name for p in doc.parameters]
        assert "commands" in param_names


class TestToolDocsGenerator:
    """ToolDocsGenerator 生成工具说明文档测试"""

    def test_generate_docs_empty_returns_empty(self):
        gen = ToolDocsGenerator()
        result = gen.generate_docs()
        assert result == ""

    def test_generate_docs_with_builtin_tools(self):
        gen = ToolDocsGenerator()
        result = gen.generate_docs(builtin_tools=["spawn_agent", "shell_tool"])
        assert "可用工具说明" in result
        assert "系统内置工具" in result
        assert "spawn_agent" in result
        assert "shell_tool" in result

    def test_generate_docs_skips_unknown_builtin_tools(self):
        gen = ToolDocsGenerator()
        result = gen.generate_docs(builtin_tools=["nonexistent_tool"])
        assert "nonexistent_tool" not in result

    def test_generate_docs_with_mcp_tools(self):
        gen = ToolDocsGenerator()
        mcp_tools = [
            {
                "name": "browser_click",
                "description": "Click an element",
                "parameters": [
                    {"name": "selector", "type": "str", "description": "CSS selector", "required": True}
                ]
            }
        ]
        result = gen.generate_docs(mcp_tools=mcp_tools)
        assert "MCP工具" in result
        assert "browser_click" in result
        assert "selector" in result

    def test_generate_docs_with_skills(self):
        gen = ToolDocsGenerator()
        skills = [
            {
                "name": "web_search",
                "description": "Search the web",
                "triggers": ["search", "find"],
                "required_tools": ["browser"]
            }
        ]
        result = gen.generate_docs(skills=skills)
        assert "Skill" in result
        assert "web_search" in result
        assert "search" in result

    def test_generate_docs_all_sections(self):
        gen = ToolDocsGenerator()
        result = gen.generate_docs(
            builtin_tools=["spawn_agent"],
            mcp_tools=[{"name": "mcp_tool", "description": "A tool", "parameters": []}],
            skills=[{"name": "skill1", "description": "A skill"}]
        )
        assert "系统内置工具" in result
        assert "MCP工具" in result
        assert "Skill" in result

    def test_generate_docs_with_examples(self):
        gen = ToolDocsGenerator(include_examples=True)
        result = gen.generate_docs(builtin_tools=["spawn_agent"])
        assert "示例" in result

    def test_generate_docs_without_examples(self):
        gen = ToolDocsGenerator(include_examples=False)
        result = gen.generate_docs(builtin_tools=["spawn_agent"])
        assert "示例" not in result


class TestToolDocsFormat:
    """工具文档格式和注入位置测试"""

    def test_doc_starts_with_header(self):
        gen = ToolDocsGenerator()
        result = gen.generate_docs(builtin_tools=["spawn_agent"])
        assert result.startswith("\n\n# 可用工具说明\n\n")

    def test_builtin_section_has_header(self):
        gen = ToolDocsGenerator()
        result = gen.generate_docs(builtin_tools=["spawn_agent"])
        assert "## 系统内置工具" in result

    def test_mcp_section_has_header(self):
        gen = ToolDocsGenerator()
        result = gen.generate_docs(mcp_tools=[{"name": "t", "description": "d", "parameters": []}])
        assert "## MCP工具" in result

    def test_skill_section_has_header(self):
        gen = ToolDocsGenerator()
        result = gen.generate_docs(skills=[{"name": "s", "description": "d"}])
        assert "## Skill" in result

    def test_tool_name_as_h3(self):
        gen = ToolDocsGenerator()
        result = gen.generate_docs(builtin_tools=["spawn_agent"])
        assert "### spawn_agent" in result

    def test_parameters_section(self):
        gen = ToolDocsGenerator()
        result = gen.generate_docs(builtin_tools=["spawn_agent"])
        assert "**参数**：" in result

    def test_parameter_format_with_required(self):
        gen = ToolDocsGenerator()
        result = gen.generate_docs(builtin_tools=["shell_tool"])
        assert "`commands`" in result

    def test_parameter_format_with_optional(self):
        gen = ToolDocsGenerator()
        result = gen.generate_docs(builtin_tools=["file_read"])
        assert "可选" in result

    def test_parameter_default_value(self):
        gen = ToolDocsGenerator()
        result = gen.generate_docs(builtin_tools=["file_read"])
        assert "默认" in result


class TestGenerateToolDocsForPrompt:
    """generate_tool_docs_for_prompt 便捷函数测试"""

    def test_function_delegates_to_generator(self):
        result = generate_tool_docs_for_prompt(builtin_tools=["spawn_agent"])
        assert "spawn_agent" in result

    def test_function_with_include_examples_false(self):
        result = generate_tool_docs_for_prompt(
            builtin_tools=["spawn_agent"],
            include_examples=False
        )
        assert "示例" not in result
