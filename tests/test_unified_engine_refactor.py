"""
Rubato 统一引擎重构自检测试

验证项目从双引擎（LangGraph React + QueryEngine）架构
重构为单一 QueryEngine-only 架构的完整性。
"""

import sys
import os
import re
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

results = []


def record(test_name: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    results.append((test_name, passed, detail))
    suffix = f" — {detail}" if detail else ""
    print(f"  [{status}] {test_name}{suffix}")


def test_import_verification():
    print("\n=== Test 1: Import Verification ===")
    imports = [
        ("src.core.agent.RubatoAgent", "from src.core.agent import RubatoAgent"),
        ("src.core.sub_agents.SubAgentManager", "from src.core.sub_agents import SubAgentManager"),
        ("src.core.sub_agents.create_spawn_agent_tool", "from src.core.sub_agents import create_spawn_agent_tool"),
        ("src.core.sub_agent_types.SubAgentExecutionConfig", "from src.core.sub_agent_types import SubAgentExecutionConfig"),
        ("src.core.sub_agent_types.SubAgentSpawnOptions", "from src.core.sub_agent_types import SubAgentSpawnOptions"),
        ("src.core.query_engine.QueryEngine", "from src.core.query_engine import QueryEngine"),
        ("src.core.query_engine.QueryEngineConfig", "from src.core.query_engine import QueryEngineConfig"),
        ("src.context.manager.ContextManager", "from src.context.manager import ContextManager"),
        ("src.config.models.RoleExecutionConfig", "from src.config.models import RoleExecutionConfig"),
    ]
    for name, stmt in imports:
        try:
            exec(stmt)
            record(name, True)
        except Exception as e:
            record(name, False, str(e))


def test_context_manager_simplification():
    print("\n=== Test 2: ContextManager Simplification ===")
    from src.context.manager import ContextManager

    removed_methods = [
        "add_user_message", "add_ai_message", "add_ai_message_full",
        "add_tool_message", "get_messages", "set_messages",
        "get_history", "get_token_count", "compress_now",
    ]
    kept_methods = [
        "clear", "mark_skill_loaded", "is_skill_loaded",
        "get_loaded_skills", "get_context", "add_context", "update_context",
    ]

    for m in removed_methods:
        has = hasattr(ContextManager, m)
        record(f"ContextManager should NOT have '{m}'", not has,
               f"still present!" if has else "")

    for m in kept_methods:
        has = hasattr(ContextManager, m)
        record(f"ContextManager SHOULD have '{m}'", has,
               f"missing!" if not has else "")

    try:
        cm = ContextManager()
        record("ContextManager() no-arg constructor", True)
    except Exception as e:
        record("ContextManager() no-arg constructor", False, str(e))


def test_role_execution_config_cleanup():
    print("\n=== Test 3: RoleExecutionConfig Cleanup ===")
    from src.config.models import RoleExecutionConfig

    has_field = "use_query_engine" in RoleExecutionConfig.model_fields
    record("RoleExecutionConfig should NOT have 'use_query_engine' field",
           not has_field, "field still exists!" if has_field else "")

    try:
        rec = RoleExecutionConfig()
        has_attr = hasattr(rec, "use_query_engine")
        record("RoleExecutionConfig instance should NOT have 'use_query_engine' attr",
               not has_attr, "attr still exists!" if has_attr else "")
    except Exception as e:
        record("RoleExecutionConfig() instantiation", False, str(e))


def test_sub_agent_execution_config_cleanup():
    print("\n=== Test 4: SubAgentExecutionConfig Cleanup ===")
    from src.core.sub_agent_types import SubAgentExecutionConfig, SubAgentSpawnOptions

    has_exec = "use_query_engine" in SubAgentExecutionConfig.model_fields
    record("SubAgentExecutionConfig should NOT have 'use_query_engine' field",
           not has_exec, "field still exists!" if has_exec else "")

    has_spawn = "use_query_engine" in SubAgentSpawnOptions.model_fields
    record("SubAgentSpawnOptions should NOT have 'use_query_engine' field",
           not has_spawn, "field still exists!" if has_spawn else "")


def test_no_langgraph_references():
    print("\n=== Test 5: No LangGraph References in Core ===")
    core_dir = os.path.join(os.path.dirname(__file__), "..", "src", "core")

    agent_path = os.path.normpath(os.path.join(core_dir, "agent.py"))
    sub_agents_path = os.path.normpath(os.path.join(core_dir, "sub_agents.py"))

    def file_contains(filepath, pattern):
        if not os.path.exists(filepath):
            return False, "file not found"
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        matches = re.findall(pattern, content)
        return len(matches) == 0, f"{len(matches)} match(es) found"

    ok, detail = file_contains(agent_path, r"from\s+langgraph|import\s+langgraph")
    record("agent.py should NOT import from langgraph", ok, detail)

    ok, detail = file_contains(sub_agents_path, r"create_react_agent")
    record("sub_agents.py should NOT import create_react_agent", ok, detail)


def test_no_use_query_engine_references():
    print("\n=== Test 6: No use_query_engine References in Source ===")
    src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
    match_count = 0
    match_files = []

    for root, dirs, files in os.walk(src_dir):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(root, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    if "use_query_engine" in line:
                        match_count += 1
                        rel = os.path.relpath(fpath, src_dir)
                        match_files.append(f"{rel}:{i}: {line.strip()}")

    record("No 'use_query_engine' references in src/",
           match_count == 0,
           f"{match_count} match(es): {match_files[:3]}" if match_count else "")


def test_query_engine_api():
    print("\n=== Test 7: QueryEngine API Verification ===")
    from src.core.query_engine import QueryEngine

    required_methods = [
        "get_messages", "set_messages", "clear_messages",
        "submit_message", "interrupt", "is_running",
        "get_session_id", "get_usage",
    ]

    for m in required_methods:
        has = hasattr(QueryEngine, m)
        record(f"QueryEngine SHOULD have '{m}()'", has,
               "missing!" if not has else "")


def test_rubato_agent_attributes():
    print("\n=== Test 8: RubatoAgent Attribute Verification ===")
    from src.core.agent import RubatoAgent
    import inspect

    init_source = inspect.getsource(RubatoAgent.__init__)

    should_have_instance = [
        ("_query_engine", "instance attribute"),
        ("max_turns", "instance attribute"),
    ]
    should_have_method = [
        ("_rebuild_query_engine", "method"),
    ]
    should_not_have = [
        ("agent", "attribute (LangGraph agent)"),
        ("use_query_engine", "attribute"),
        ("_create_agent", "method"),
        ("sync_query_engine_messages", "method"),
        ("reset_query_engine", "method"),
    ]

    for name, desc in should_have_instance:
        pattern = rf"self\.{name}\s*[:=]"
        found = bool(re.search(pattern, init_source))
        record(f"RubatoAgent SHOULD have '{name}' ({desc})", found,
               "not found in __init__!" if not found else "")

    for name, desc in should_have_method:
        has = hasattr(RubatoAgent, name)
        record(f"RubatoAgent SHOULD have '{name}' ({desc})", has,
               "missing!" if not has else "")

    for name, desc in should_not_have:
        has = hasattr(RubatoAgent, name)
        record(f"RubatoAgent should NOT have '{name}' ({desc})",
               not has, "still present!" if has else "")


def main():
    print("=" * 60)
    print("Rubato Unified Engine Refactor — Self-Test")
    print("=" * 60)

    test_import_verification()
    test_context_manager_simplification()
    test_role_execution_config_cleanup()
    test_sub_agent_execution_config_cleanup()
    test_no_langgraph_references()
    test_no_use_query_engine_references()
    test_query_engine_api()
    test_rubato_agent_attributes()

    total = len(results)
    passed = sum(1 for _, p, _ in results if p)
    failed = total - passed

    print("\n" + "=" * 60)
    print(f"Summary: {passed}/{total} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        print("\nFailed tests:")
        for name, p, detail in results:
            if not p:
                suffix = f" — {detail}" if detail else ""
                print(f"  X {name}{suffix}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
