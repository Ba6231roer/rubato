from pathlib import Path

from src.skills.parser import SkillParser, SkillMetadata


class TestSplitYamlHeader:
    def test_splits_yaml_header_and_body(self):
        content = """---
name: test-skill
description: A test skill
triggers:
  - "test"
---

# Body content

Some text here."""
        yaml_part, body = SkillParser._split_yaml_header(content)
        assert yaml_part is not None
        assert "name: test-skill" in yaml_part
        assert "# Body content" in body

    def test_no_yaml_header_returns_none(self):
        content = "# Just a markdown file\n\nNo YAML header here."
        yaml_part, body = SkillParser._split_yaml_header(content)
        assert yaml_part is None
        assert body == content

    def test_empty_string(self):
        yaml_part, body = SkillParser._split_yaml_header("")
        assert yaml_part is None
        assert body == ""

    def test_only_yaml_header_no_body(self):
        content = """---
name: minimal
---"""
        yaml_part, body = SkillParser._split_yaml_header(content)
        assert yaml_part is not None
        assert "name: minimal" in yaml_part
        assert body == ""


class TestParseContent:
    def test_parse_full_yaml_header(self):
        content = """---
name: my-skill
description: My skill description
version: "2.0"
author: tester
triggers:
  - "deploy"
  - "发布"
tools:
  - file_read
  - shell
paths:
  - "src/**/*.py"
---

# My Skill

Detailed instructions here."""
        metadata, body = SkillParser.parse_content(content)
        assert metadata.name == "my-skill"
        assert metadata.description == "My skill description"
        assert metadata.version == "2.0"
        assert metadata.author == "tester"
        assert metadata.triggers == ["deploy", "发布"]
        assert metadata.tools == ["file_read", "shell"]
        assert metadata.paths == ["src/**/*.py"]
        assert "# My Skill" in body
        assert "Detailed instructions here." in body
        assert "name: my-skill" not in body

    def test_parse_partial_yaml_header(self):
        content = """---
name: partial-skill
description: Only name and description
---

Body only."""
        metadata, body = SkillParser.parse_content(content)
        assert metadata.name == "partial-skill"
        assert metadata.description == "Only name and description"
        assert metadata.version == "1.0"
        assert metadata.triggers == []
        assert metadata.tools == []
        assert metadata.paths == []
        assert body == "Body only."

    def test_parse_no_yaml_header(self):
        content = "# No YAML\n\nJust plain markdown."
        metadata, body = SkillParser.parse_content(content)
        assert metadata.name == ""
        assert metadata.description == ""
        assert body == content

    def test_parse_empty_content(self):
        metadata, body = SkillParser.parse_content("")
        assert metadata.name == ""
        assert metadata.description == ""
        assert body == ""

    def test_body_excludes_yaml_header(self):
        content = """---
name: body-test
description: Test body extraction
---

# Heading

Paragraph text."""
        metadata, body = SkillParser.parse_content(content)
        assert "---" not in body
        assert "name: body-test" not in body
        assert "# Heading" in body
        assert "Paragraph text." in body


class TestParseFile:
    def test_parse_skill_file(self, tmp_path: Path):
        skill_file = tmp_path / "test-skill.md"
        skill_file.write_text("""---
name: file-skill
description: Parsed from file
triggers:
  - "file"
---

# File Skill

Content from file.""", encoding="utf-8")
        metadata, body = SkillParser.parse_file(skill_file)
        assert metadata.name == "file-skill"
        assert metadata.description == "Parsed from file"
        assert metadata.triggers == ["file"]
        assert metadata.file_path == str(skill_file)
        assert "# File Skill" in body

    def test_parse_empty_file(self, tmp_path: Path):
        skill_file = tmp_path / "empty.md"
        skill_file.write_text("", encoding="utf-8")
        metadata, body = SkillParser.parse_file(skill_file)
        assert metadata.name == ""
        assert metadata.description == ""
        assert body == ""

    def test_parse_file_no_yaml_header(self, tmp_path: Path):
        skill_file = tmp_path / "no-yaml.md"
        skill_file.write_text("# Just content\n\nNo YAML header.", encoding="utf-8")
        metadata, body = SkillParser.parse_file(skill_file)
        assert metadata.name == ""
        assert body == "# Just content\n\nNo YAML header."


class TestExtractYamlHeader:
    def test_extract_returns_dict(self):
        content = """---
name: extract-test
description: Extraction test
version: "3.0"
---

Body."""
        result = SkillParser.extract_yaml_header(content)
        assert result is not None
        assert result["name"] == "extract-test"
        assert result["description"] == "Extraction test"
        assert result["version"] == "3.0"

    def test_extract_no_header_returns_none(self):
        content = "# No header"
        result = SkillParser.extract_yaml_header(content)
        assert result is None

    def test_extract_empty_returns_none(self):
        result = SkillParser.extract_yaml_header("")
        assert result is None
