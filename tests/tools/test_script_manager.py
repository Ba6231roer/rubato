import os
import subprocess
import pytest
import yaml
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.tools.script_manager import ScriptManager


class TestCalculateScriptPath:
    def test_basic_path_calculation(self):
        mgr = ScriptManager("dummy_root")
        path = mgr._calculate_script_path(
            "资金驾驶舱",
            "测试案例.md",
            "资金看板场景/查询资金看板/正例-查询当日资金看板数据",
        )
        normalized = path.replace("\\", "/")
        assert "资金驾驶舱/测试案例/资金看板场景/查询资金看板/正例-查询当日资金看板数据.js" in normalized

    def test_single_level_heading(self):
        mgr = ScriptManager("dummy_root")
        path = mgr._calculate_script_path("系统A", "文件.md", "案例名")
        normalized = path.replace("\\", "/")
        assert "系统A/文件/案例名.js" in normalized

    def test_special_chars_sanitized(self):
        mgr = ScriptManager("dummy_root")
        path = mgr._calculate_script_path("系统", "文件.md", 'a<b>"c')
        assert "<" not in path
        assert ">" not in path
        assert '"' not in path
        normalized = path.replace("\\", "/")
        assert normalized.endswith("a_b_c.js")


class TestSanitizeName:
    def test_remove_invalid_chars(self):
        result = ScriptManager._sanitize_name('a<b>c')
        assert result == "a_b_c"

    def test_empty_returns_unnamed(self):
        result = ScriptManager._sanitize_name('')
        assert result == "unnamed"

    def test_strip_dots_and_underscores(self):
        result = ScriptManager._sanitize_name('..test..')
        assert result == "test"


class TestSaveAndFindScript:
    def test_save_creates_file(self, tmp_path):
        mgr = ScriptManager(str(tmp_path))
        path = mgr.save_script("系统A", "文件.md", "场景/案例1", "console.log('hello')")
        assert os.path.isfile(path)

    def test_save_updates_index(self, tmp_path):
        mgr = ScriptManager(str(tmp_path))
        mgr.save_script("系统A", "文件.md", "场景/案例1", "console.log('hello')")
        index_path = tmp_path / "webui_scripts" / "INDEX.yaml"
        assert index_path.is_file()
        with open(index_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        entries = data["scripts"]
        assert len(entries) == 1
        assert entries[0]["source"] == "文件.md"
        assert entries[0]["heading_path"] == "场景/案例1"

    def test_find_script_exists(self, tmp_path):
        mgr = ScriptManager(str(tmp_path))
        mgr.save_script("系统A", "文件.md", "场景/案例1", "console.log('hello')")
        found = mgr.find_script("系统A", "文件.md", "场景/案例1")
        assert found is not None
        assert os.path.isfile(found.path)

    def test_find_script_not_exists(self, tmp_path):
        mgr = ScriptManager(str(tmp_path))
        found = mgr.find_script("系统A", "文件.md", "场景/案例1")
        assert found is None

    def test_overwrite_existing_script(self, tmp_path):
        mgr = ScriptManager(str(tmp_path))
        mgr.save_script("系统A", "文件.md", "场景/案例1", "content_v1")
        mgr.save_script("系统A", "文件.md", "场景/案例1", "content_v2")
        found = mgr.find_script("系统A", "文件.md", "场景/案例1")
        with open(found.path, "r", encoding="utf-8") as f:
            assert f.read() == "content_v2"


class TestExecuteScript:
    def test_execute_parse_pass_result(self, tmp_path):
        mgr = ScriptManager(str(tmp_path))
        script_file = tmp_path / "test_script.js"
        script_file.write_text("async (page) => {}", encoding="utf-8")
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = 'Some output\nResult: {"status": "PASS", "message": "ok"}'
        mock_proc.stderr = ""
        with patch("subprocess.run", return_value=mock_proc):
            result = mgr.execute_script(str(script_file))
        assert result["status"] == "PASS"
        assert result["message"] == "ok"

    def test_execute_parse_fail_result(self, tmp_path):
        mgr = ScriptManager(str(tmp_path))
        script_file = tmp_path / "test_script.js"
        script_file.write_text("async (page) => {}", encoding="utf-8")
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = 'Result: {"status": "FAIL", "message": "error", "failedStep": 3}'
        mock_proc.stderr = ""
        with patch("subprocess.run", return_value=mock_proc):
            result = mgr.execute_script(str(script_file))
        assert result["status"] == "FAIL"
        assert result["failedStep"] == 3

    def test_execute_timeout(self, tmp_path):
        mgr = ScriptManager(str(tmp_path))
        script_file = tmp_path / "test_script.js"
        script_file.write_text("async (page) => {}", encoding="utf-8")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="test", timeout=120)):
            result = mgr.execute_script(str(script_file))
        assert result["status"] == "FAIL"
        assert "timed out" in result["message"].lower()


class TestCheckDuplicate:
    def test_duplicate_detected(self, tmp_path):
        mgr = ScriptManager(str(tmp_path))
        script_a = (
            "await page.getByRole('button', {name: 'Login'}).click();\n"
            "await page.getByText('Submit').click();"
        )
        mgr.save_script("系统A", "文件.md", "场景/案例1", script_a)
        script_b = (
            "await page.getByRole('button', {name: 'Login'}).click();\n"
            "await page.getByText('Submit').click();"
        )
        result = mgr.check_duplicate("系统A", script_b)
        assert result is not None

    def test_no_duplicate_different_locators(self, tmp_path):
        mgr = ScriptManager(str(tmp_path))
        script_a = "await page.getByRole('button', {name: 'Login'}).click();"
        mgr.save_script("系统A", "文件.md", "场景/案例1", script_a)
        script_b = "await page.getByRole('link', {name: 'Home'}).click();"
        result = mgr.check_duplicate("系统A", script_b)
        assert result is None

    def test_no_duplicate_different_step_count(self, tmp_path):
        mgr = ScriptManager(str(tmp_path))
        many_steps = "\n".join(
            f"await page.getByRole('button', {{name: 'Btn{i}'}}).click();"
            for i in range(10)
        )
        mgr.save_script("系统A", "文件.md", "场景/案例1", many_steps)
        few_steps = "await page.getByRole('button', {name: 'Btn0'}).click();"
        result = mgr.check_duplicate("系统A", few_steps)
        assert result is None


class TestParsePlaywrightOutput:
    def test_parse_result_json(self):
        output = 'Some log\nResult: {"status": "PASS", "message": "ok"}'
        result = ScriptManager._parse_playwright_output(output)
        assert result is not None
        assert result["status"] == "PASS"
        assert result["message"] == "ok"

    def test_parse_no_result(self):
        output = "Just some log output without result"
        result = ScriptManager._parse_playwright_output(output)
        assert result is None

    def test_parse_invalid_json(self):
        output = "Result: {invalid}"
        result = ScriptManager._parse_playwright_output(output)
        assert result is None


class TestExtractLocators:
    def test_extract_getByRole(self):
        content = "await page.getByRole('button', {name: 'Login'}).click();"
        locators = ScriptManager._extract_locators(content)
        assert "getByRole('button', {name: 'Login'})" in locators

    def test_extract_multiple_locator_types(self):
        content = (
            "page.getByRole('button', {name: 'Login'}).click();\n"
            "page.getByText('Hello').click();"
        )
        locators = ScriptManager._extract_locators(content)
        assert "getByRole('button', {name: 'Login'})" in locators
        assert "getByText('Hello')" in locators


class TestCountSteps:
    def test_count_click_and_fill(self):
        content = "await page.click('.btn');\nawait page.fill('#input', 'text');"
        assert ScriptManager._count_steps(content) == 2

    def test_count_zero(self):
        assert ScriptManager._count_steps("just some plain text") == 0


class TestSaveCaseText:
    def test_save_case_text_creates_file(self, tmp_path):
        mgr = ScriptManager(str(tmp_path))
        path = mgr.save_case_text("系统A", "案例标题", "这是案例内容")
        assert os.path.isfile(path)
        normalized = path.replace("\\", "/")
        assert "workspace/test_cases" in normalized

    def test_save_case_text_content_format(self, tmp_path):
        mgr = ScriptManager(str(tmp_path))
        path = mgr.save_case_text("系统A", "案例标题", "这是案例内容")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert content.startswith("# 案例标题")
