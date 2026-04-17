from src.skills.registry import SkillRegistry
from src.skills.parser import SkillMetadata


def _make_metadata(name: str, description: str = "", triggers: list = None) -> SkillMetadata:
    return SkillMetadata(
        name=name,
        description=description,
        triggers=triggers or [],
    )


class TestRegisterAndGet:
    def test_register_and_get_skill(self):
        registry = SkillRegistry()
        meta = _make_metadata("skill-a", "Skill A description")
        registry.register(meta)
        result = registry.get_skill("skill-a")
        assert result is not None
        assert result.name == "skill-a"
        assert result.description == "Skill A description"

    def test_get_nonexistent_returns_none(self):
        registry = SkillRegistry()
        assert registry.get_skill("no-such-skill") is None

    def test_register_with_content(self):
        registry = SkillRegistry()
        meta = _make_metadata("skill-with-content", "Has content")
        registry.register(meta, content="Body text")
        assert registry.get_content("skill-with-content") == "Body text"

    def test_register_overwrites_existing(self):
        registry = SkillRegistry()
        meta1 = _make_metadata("skill-x", "Version 1")
        meta2 = _make_metadata("skill-x", "Version 2")
        registry.register(meta1)
        registry.register(meta2)
        result = registry.get_skill("skill-x")
        assert result.description == "Version 2"

    def test_has_skill(self):
        registry = SkillRegistry()
        meta = _make_metadata("exists")
        registry.register(meta)
        assert registry.has_skill("exists") is True
        assert registry.has_skill("not-exists") is False


class TestUnregister:
    def test_unregister_removes_skill(self):
        registry = SkillRegistry()
        meta = _make_metadata("to-remove", "Remove me")
        registry.register(meta)
        assert registry.has_skill("to-remove")
        registry.unregister("to-remove")
        assert not registry.has_skill("to-remove")

    def test_unregister_also_removes_content(self):
        registry = SkillRegistry()
        meta = _make_metadata("content-remove")
        registry.register(meta, content="Some content")
        assert registry.get_content("content-remove") == "Some content"
        registry.unregister("content-remove")
        assert registry.get_content("content-remove") is None

    def test_unregister_nonexistent_no_error(self):
        registry = SkillRegistry()
        registry.unregister("ghost")


class TestListSkills:
    def test_list_skills_empty(self):
        registry = SkillRegistry()
        assert registry.list_skills() == []

    def test_list_skills_returns_all(self):
        registry = SkillRegistry()
        registry.register(_make_metadata("a", "A"))
        registry.register(_make_metadata("b", "B"))
        registry.register(_make_metadata("c", "C"))
        names = {s.name for s in registry.list_skills()}
        assert names == {"a", "b", "c"}


class TestFindMatchingSkill:
    def test_match_by_trigger(self):
        registry = SkillRegistry()
        registry.register(_make_metadata("deploy", "Deploy", triggers=["deploy", "发布"]))
        result = registry.find_matching_skill("please deploy the app")
        assert result == "deploy"

    def test_match_by_trigger_chinese(self):
        registry = SkillRegistry()
        registry.register(_make_metadata("deploy", "Deploy", triggers=["deploy", "发布"]))
        result = registry.find_matching_skill("请发布应用")
        assert result == "deploy"

    def test_case_insensitive_match(self):
        registry = SkillRegistry()
        registry.register(_make_metadata("test", "Test", triggers=["Deploy"]))
        result = registry.find_matching_skill("DEPLOY now")
        assert result == "test"

    def test_no_match_returns_none(self):
        registry = SkillRegistry()
        registry.register(_make_metadata("test", "Test", triggers=["deploy"]))
        result = registry.find_matching_skill("nothing matches here")
        assert result is None


class TestGetSkillFile:
    def test_returns_file_path(self):
        registry = SkillRegistry()
        meta = _make_metadata("file-skill")
        meta.file_path = "/path/to/skill.md"
        registry.register(meta)
        assert registry.get_skill_file("file-skill") == "/path/to/skill.md"

    def test_returns_empty_for_nonexistent(self):
        registry = SkillRegistry()
        assert registry.get_skill_file("ghost") == ""


class TestLRUCache:
    def test_store_and_get_content(self):
        registry = SkillRegistry(max_loaded_skills=5)
        registry.store_content("skill-1", "Content 1")
        assert registry.get_content("skill-1") == "Content 1"

    def test_get_content_nonexistent_returns_none(self):
        registry = SkillRegistry()
        assert registry.get_content("no-content") is None

    def test_lru_eviction_oldest_first(self):
        registry = SkillRegistry(max_loaded_skills=2)
        registry.store_content("oldest", "Oldest content")
        registry.store_content("middle", "Middle content")
        assert registry.get_content("oldest") is not None
        assert registry.get_content("middle") is not None
        registry.store_content("newest", "Newest content")
        assert registry.get_content("oldest") is None
        assert registry.get_content("middle") is not None
        assert registry.get_content("newest") is not None

    def test_lru_access_updates_order(self):
        registry = SkillRegistry(max_loaded_skills=2)
        registry.store_content("a", "Content A")
        registry.store_content("b", "Content B")
        registry.get_content("a")
        registry.store_content("c", "Content C")
        assert registry.get_content("a") is not None
        assert registry.get_content("b") is None
        assert registry.get_content("c") is not None

    def test_store_content_overwrites_existing(self):
        registry = SkillRegistry(max_loaded_skills=5)
        registry.store_content("skill", "Old content")
        registry.store_content("skill", "New content")
        assert registry.get_content("skill") == "New content"

    def test_get_loaded_count(self):
        registry = SkillRegistry(max_loaded_skills=5)
        assert registry.get_loaded_count() == 0
        registry.store_content("a", "A")
        assert registry.get_loaded_count() == 1
        registry.store_content("b", "B")
        assert registry.get_loaded_count() == 2

    def test_set_max_loaded_skills_shrinks_cache(self):
        registry = SkillRegistry(max_loaded_skills=5)
        registry.store_content("a", "A")
        registry.store_content("b", "B")
        registry.store_content("c", "C")
        registry.set_max_loaded_skills(1)
        assert registry.get_loaded_count() == 1
        assert registry.get_content("a") is None
        assert registry.get_content("b") is None
        assert registry.get_content("c") is not None

    def test_register_with_content_respects_limit(self):
        registry = SkillRegistry(max_loaded_skills=2)
        meta1 = _make_metadata("s1")
        meta2 = _make_metadata("s2")
        meta3 = _make_metadata("s3")
        registry.register(meta1, content="C1")
        registry.register(meta2, content="C2")
        registry.register(meta3, content="C3")
        assert registry.get_content("s1") is None
        assert registry.get_content("s2") is not None
        assert registry.get_content("s3") is not None
