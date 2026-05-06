from src.skills.registry import SkillRegistry
from src.skills.parser import SkillMetadata


def _make_metadata(name: str, description: str = "", triggers: list = None) -> SkillMetadata:
    return SkillMetadata(
        name=name,
        description=description,
        triggers=triggers or [],
    )


class TestRegisterNewSkill:
    def test_registers_metadata(self):
        registry = SkillRegistry()
        meta = _make_metadata("new-skill", "A new skill")
        registry.register_new_skill(meta)
        assert registry.has_skill("new-skill")
        assert registry.get_skill("new-skill").description == "A new skill"

    def test_registers_with_content(self):
        registry = SkillRegistry()
        meta = _make_metadata("new-skill-content", "With content")
        registry.register_new_skill(meta, content="Skill body")
        assert registry.get_content("new-skill-content") == "Skill body"

    def test_registers_without_content(self):
        registry = SkillRegistry()
        meta = _make_metadata("new-skill-no-content", "No content")
        registry.register_new_skill(meta)
        assert registry.has_skill("new-skill-no-content")
        assert registry.get_content("new-skill-no-content") is None


class TestUpdateSkillContent:
    def test_updates_content_and_timestamp(self):
        registry = SkillRegistry()
        meta = _make_metadata("updatable", "Can update")
        meta.updated_at = "2025-01-01T00:00:00"
        registry.register(meta, content="Old content")
        registry.update_skill_content("updatable", "New content")
        assert registry.get_content("updatable") == "New content"
        assert registry.get_skill("updatable").updated_at != "2025-01-01T00:00:00"
        assert registry.get_skill("updatable").updated_at != ""

    def test_nonexistent_skill_does_nothing(self):
        registry = SkillRegistry()
        registry.update_skill_content("ghost", "Some content")
        assert registry.get_content("ghost") is None
        assert not registry.has_skill("ghost")


class TestInvalidateContentCache:
    def test_removes_content_from_cache(self):
        registry = SkillRegistry(max_loaded_skills=5)
        meta = _make_metadata("cached-skill", "Cached")
        registry.register(meta, content="Cached content")
        assert registry.get_content("cached-skill") == "Cached content"
        registry.invalidate_content_cache("cached-skill")
        assert registry.get_content("cached-skill") is None

    def test_nonexistent_skill_does_nothing(self):
        registry = SkillRegistry()
        registry.invalidate_content_cache("ghost")

    def test_after_invalidation_get_content_returns_none(self):
        registry = SkillRegistry(max_loaded_skills=5)
        meta = _make_metadata("inv-skill", "To invalidate")
        registry.register(meta, content="Will be gone")
        assert registry.get_content("inv-skill") is not None
        registry.invalidate_content_cache("inv-skill")
        result = registry.get_content("inv-skill")
        assert result is None


class TestFindMatchingSkillNameMatch:
    def test_name_match_when_trigger_not_matched(self):
        registry = SkillRegistry()
        meta = _make_metadata("web-search", "Search the web", triggers=["look up"])
        registry.register(meta)
        assert registry.find_matching_skill("use web-search to find info") == "web-search"

    def test_trigger_match_takes_priority_over_name_match(self):
        registry = SkillRegistry()
        meta_a = _make_metadata("skill-a", "Skill A", triggers=["activate"])
        meta_b = _make_metadata("skill-b", "Skill B", triggers=[])
        registry.register(meta_a)
        registry.register(meta_b)
        assert registry.find_matching_skill("activate skill-b") == "skill-a"

    def test_name_match_is_case_insensitive(self):
        registry = SkillRegistry()
        meta = _make_metadata("CodeReview", "Review code", triggers=[])
        registry.register(meta)
        assert registry.find_matching_skill("run codereview now") == "CodeReview"

    def test_name_match_returns_none_when_no_match(self):
        registry = SkillRegistry()
        meta = _make_metadata("deploy", "Deploy app", triggers=["push to prod"])
        registry.register(meta)
        assert registry.find_matching_skill("check the logs") is None
