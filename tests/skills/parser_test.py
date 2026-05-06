from src.skills.parser import SkillParser, SkillMetadata


class TestSkillMetadataDefaults:
    def test_new_fields_default_values(self):
        metadata = SkillMetadata(name="test", description="test desc")
        assert metadata.category == ""
        assert metadata.created_by == "human"
        assert metadata.updated_at == ""

    def test_new_fields_custom_values(self):
        metadata = SkillMetadata(
            name="test",
            description="test desc",
            category="coding",
            created_by="agent",
            updated_at="2026-04-30",
        )
        assert metadata.category == "coding"
        assert metadata.created_by == "agent"
        assert metadata.updated_at == "2026-04-30"


class TestParseContentNewFields:
    def test_parse_with_new_fields(self):
        content = """---
name: my-skill
description: A skill with new fields
category: coding
created_by: agent
updated_at: "2026-04-30"
---

# Body content"""
        metadata, body = SkillParser.parse_content(content)
        assert metadata.name == "my-skill"
        assert metadata.description == "A skill with new fields"
        assert metadata.category == "coding"
        assert metadata.created_by == "agent"
        assert metadata.updated_at == "2026-04-30"
        assert "# Body content" in body

    def test_parse_without_new_fields_returns_defaults(self):
        content = """---
name: old-skill
description: A skill without new fields
---

# Body content"""
        metadata, body = SkillParser.parse_content(content)
        assert metadata.name == "old-skill"
        assert metadata.description == "A skill without new fields"
        assert metadata.category == ""
        assert metadata.created_by == "human"
        assert metadata.updated_at == ""

    def test_parse_partial_new_fields(self):
        content = """---
name: partial-skill
description: Partial new fields
category: analysis
---

# Body content"""
        metadata, body = SkillParser.parse_content(content)
        assert metadata.category == "analysis"
        assert metadata.created_by == "human"
        assert metadata.updated_at == ""


class TestBuildSkillContent:
    def test_roundtrip_full_metadata(self):
        original_content = """---
name: roundtrip-skill
description: Roundtrip test
version: "2.0"
author: tester
triggers:
- deploy
- 发布
tools:
- file_read
category: coding
created_by: agent
updated_at: "2026-04-30"
---

# Roundtrip Body

Some instructions here."""
        metadata, body = SkillParser.parse_content(original_content)
        rebuilt = SkillParser.build_skill_content(metadata, body)
        metadata2, body2 = SkillParser.parse_content(rebuilt)
        assert metadata2.name == metadata.name
        assert metadata2.description == metadata.description
        assert metadata2.version == metadata.version
        assert metadata2.author == metadata.author
        assert metadata2.triggers == metadata.triggers
        assert metadata2.tools == metadata.tools
        assert metadata2.category == metadata.category
        assert metadata2.created_by == metadata.created_by
        assert metadata2.updated_at == metadata.updated_at
        assert body2 == body

    def test_minimal_metadata_only_name_and_description(self):
        metadata = SkillMetadata(name="minimal", description="Minimal skill")
        body = "# Minimal Body"
        result = SkillParser.build_skill_content(metadata, body)
        assert result.startswith("---\n")
        assert "name: minimal" in result
        assert "description: Minimal skill" in result
        assert "version" not in result
        assert "author" not in result
        assert "category" not in result
        assert "created_by" not in result
        assert "updated_at" not in result
        assert "# Minimal Body" in result

    def test_build_and_parse_roundtrip_minimal(self):
        metadata = SkillMetadata(name="min", description="Min desc")
        body = "Just body text."
        content = SkillParser.build_skill_content(metadata, body)
        parsed_meta, parsed_body = SkillParser.parse_content(content)
        assert parsed_meta.name == "min"
        assert parsed_meta.description == "Min desc"
        assert parsed_meta.version == "1.0"
        assert parsed_meta.category == ""
        assert parsed_meta.created_by == "human"
        assert parsed_meta.updated_at == ""
        assert parsed_body == body

    def test_build_with_non_default_created_by(self):
        metadata = SkillMetadata(
            name="agent-skill",
            description="Agent created",
            created_by="agent",
        )
        body = "Body"
        content = SkillParser.build_skill_content(metadata, body)
        assert "created_by: agent" in content

    def test_build_with_category(self):
        metadata = SkillMetadata(
            name="cat-skill",
            description="Categorized",
            category="analysis",
        )
        body = "Body"
        content = SkillParser.build_skill_content(metadata, body)
        assert "category: analysis" in content

    def test_build_with_updated_at(self):
        metadata = SkillMetadata(
            name="dated-skill",
            description="Dated",
            updated_at="2026-04-30",
        )
        body = "Body"
        content = SkillParser.build_skill_content(metadata, body)
        assert "updated_at: '2026-04-30'" in content or 'updated_at: "2026-04-30"' in content or "updated_at: 2026-04-30" in content
