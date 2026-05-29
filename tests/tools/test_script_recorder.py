import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.tools.script_recorder import (
    ScriptRecorder,
    RecordEntry,
    get_script_recorder,
    set_recording_context,
    save_active_recording,
    _generate_heading,
)
from src.tools import script_recorder as sr_module


@pytest.fixture(autouse=True)
def _reset_singleton():
    yield
    sr_module._recorder_instance = None


class TestScriptRecorderBasic:

    def test_start_and_record_single_command(self):
        recorder = ScriptRecorder(enable_llm_review=False)
        recorder.start_recording("test_system")
        recorder.record_command(
            "navigate",
            "Ran Playwright code:\nawait page.goto('http://example.com');",
        )
        script = recorder.stop_recording()
        assert "async (page) => {" in script
        assert "page.goto('http://example.com')" in script

    def test_record_command_extracts_code_snippet(self):
        recorder = ScriptRecorder(enable_llm_review=False)
        result = recorder._extract_code_snippet(
            "Ran Playwright code:\nawait page.click('button');"
        )
        assert result is not None
        assert "await page.click('button')" in result

    def test_record_command_no_code_snippet(self):
        recorder = ScriptRecorder(enable_llm_review=False)
        result = recorder._extract_code_snippet("some random output without code")
        assert result is None

    def test_stop_recording_without_start_returns_empty(self):
        recorder = ScriptRecorder(enable_llm_review=False)
        result = recorder.stop_recording()
        assert result == ""

    def test_auto_start_on_record_command(self):
        recorder = ScriptRecorder(enable_llm_review=False)
        with patch("src.tools.script_recorder.ScriptRecorder._extract_code_snippet", return_value="await page.click('btn');"):
            with patch(
                "src.tools.snapshot_interceptor.get_system_name",
                return_value="test_system",
            ):
                recorder.record_command("click", "Ran Playwright code:\nawait page.click('btn');")
        assert recorder._recording is True
        assert len(recorder._buffer) >= 1


class TestRuleDedup:

    def test_snapshot_commands_filtered(self):
        recorder = ScriptRecorder(enable_llm_review=False)
        recorder.start_recording("sys")
        recorder._buffer = [
            RecordEntry(index=1, command="snap1", code_snippet="await page.screenshot();",
                        success=True, timestamp=0, action="snapshot"),
            RecordEntry(index=2, command="click", code_snippet="await page.click('button');",
                        success=True, timestamp=1, action="click"),
            RecordEntry(index=3, command="snap2", code_snippet="await page.screenshot();",
                        success=True, timestamp=2, action="snapshot"),
        ]
        recorder._raw_buffer = list(recorder._buffer)
        recorder._recording = True
        script = recorder.stop_recording()
        assert "screenshot" not in script
        assert "page.click('button')" in script

    def test_consecutive_gotos_keep_last(self):
        recorder = ScriptRecorder(enable_llm_review=False)
        recorder.start_recording("sys")
        recorder._buffer = [
            RecordEntry(index=1, command="nav1", code_snippet="await page.goto('http://a.com');",
                        success=True, timestamp=0, action="goto"),
            RecordEntry(index=2, command="nav2", code_snippet="await page.goto('http://b.com');",
                        success=True, timestamp=1, action="goto"),
            RecordEntry(index=3, command="nav3", code_snippet="await page.goto('http://c.com');",
                        success=True, timestamp=2, action="goto"),
            RecordEntry(index=4, command="click", code_snippet="await page.click('button');",
                        success=True, timestamp=3, action="click"),
        ]
        recorder._raw_buffer = list(recorder._buffer)
        recorder._recording = True
        script = recorder.stop_recording()
        assert "http://a.com" not in script
        assert "http://b.com" not in script
        assert "http://c.com" in script
        assert "page.click('button')" in script

    def test_verify_steps_preserved(self):
        recorder = ScriptRecorder(enable_llm_review=False)
        recorder.start_recording("sys")
        recorder._buffer = [
            RecordEntry(index=1, command="click", code_snippet="await page.click('button');",
                        success=True, timestamp=0, action="click"),
            RecordEntry(index=2, command="verify", code_snippet="await page.isVisible('button');",
                        success=True, timestamp=1, action="verify"),
            RecordEntry(index=3, command="click2", code_snippet="await page.click('link');",
                        success=True, timestamp=2, action="click"),
        ]
        recorder._raw_buffer = list(recorder._buffer)
        recorder._recording = True
        script = recorder.stop_recording()
        assert "page.click('button')" in script
        assert "isVisible('button')" in script
        assert "page.click('link')" in script

    def test_non_consecutive_gotos_preserved(self):
        recorder = ScriptRecorder(enable_llm_review=False)
        recorder.start_recording("sys")
        recorder._buffer = [
            RecordEntry(index=1, command="nav1", code_snippet="await page.goto('http://a.com');",
                        success=True, timestamp=0, action="goto"),
            RecordEntry(index=2, command="click", code_snippet="await page.click('button');",
                        success=True, timestamp=1, action="click"),
            RecordEntry(index=3, command="nav2", code_snippet="await page.goto('http://b.com');",
                        success=True, timestamp=2, action="goto"),
        ]
        recorder._raw_buffer = list(recorder._buffer)
        recorder._recording = True
        script = recorder.stop_recording()
        assert "http://a.com" in script
        assert "http://b.com" in script
        assert "page.click('button')" in script


class TestScriptAssembly:

    def test_assembled_script_has_meta_header(self):
        recorder = ScriptRecorder(enable_llm_review=False)
        recorder.start_recording("test_system")
        recorder.record_command(
            "click",
            "Ran Playwright code:\nawait page.click('button');",
        )
        script = recorder.stop_recording()
        assert script.startswith("async (page) => {")
        assert "// == META ==" in script

    def test_assembled_script_has_pass_return(self):
        recorder = ScriptRecorder(enable_llm_review=False)
        recorder.start_recording("test_system")
        recorder.record_command(
            "click",
            "Ran Playwright code:\nawait page.click('button');",
        )
        script = recorder.stop_recording()
        assert "status: 'PASS'" in script

    def test_assembled_script_includes_system_name(self):
        recorder = ScriptRecorder(enable_llm_review=False)
        recorder.start_recording("my_cool_system")
        recorder.record_command(
            "click",
            "Ran Playwright code:\nawait page.click('button');",
        )
        script = recorder.stop_recording()
        assert "my_cool_system" in script


class TestLLMReview:

    def test_llm_review_removes_entry(self):
        recorder = ScriptRecorder(enable_llm_review=True)
        recorder.start_recording("sys")
        recorder._buffer = [
            RecordEntry(index=1, command="cmd1", code_snippet="await page.click('a');",
                        success=True, timestamp=0, action="click"),
            RecordEntry(index=2, command="cmd2", code_snippet="await page.click('b');",
                        success=True, timestamp=1, action="click"),
        ]
        recorder._raw_buffer = list(recorder._buffer)
        recorder._recording = True

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='[{"index": 2, "decision": "remove"}]'))
        ]
        mock_client.chat.completions.create.return_value = mock_response

        with patch('src.tools.script_recorder._create_llm_client_from_config', return_value=(mock_client, {"model": "gpt-4", "temperature": 0.3, "max_tokens": 8000})):
            script = recorder.stop_recording()

        assert "page.click('a')" in script
        assert "page.click('b')" not in script

    def test_llm_review_failure_fallback(self):
        recorder = ScriptRecorder(enable_llm_review=True)
        recorder.start_recording("sys")
        recorder._buffer = [
            RecordEntry(index=1, command="cmd1", code_snippet="await page.click('a');",
                        success=True, timestamp=0, action="click"),
        ]
        recorder._raw_buffer = list(recorder._buffer)
        recorder._recording = True

        with patch('src.tools.script_recorder._create_llm_client_from_config', side_effect=Exception("config error")):
            script = recorder.stop_recording()

        assert "page.click('a')" in script


class TestGenerateHeading:

    def test_generate_heading_from_description(self):
        result = _generate_heading("test case name")
        assert result == "test case name"

    def test_generate_heading_empty_returns_timestamp(self):
        result = _generate_heading("")
        assert result.startswith("case_")

    def test_generate_heading_special_chars(self):
        result = _generate_heading("a<b>c|d")
        assert result == "a_b_c_d"


class TestSetRecordingContext:

    def test_set_recording_context(self):
        sr_module._recorder_instance = None
        set_recording_context("sys_name", "file.md", "h1/h2")
        recorder = get_script_recorder()
        assert recorder._case_system == "sys_name"
        assert recorder._case_source == "file.md"
        assert recorder._case_heading == "h1/h2"
        sr_module._recorder_instance = None


class TestSaveActiveRecording:

    def test_save_active_recording_no_recording_returns_none(self):
        sr_module._recorder_instance = None
        result = save_active_recording("some/path")
        assert result is None

    def test_save_active_recording_saves_script(self, tmp_path):
        recorder = ScriptRecorder(enable_llm_review=False)
        recorder.start_recording("test_system")
        recorder.record_command(
            "click",
            "Ran Playwright code:\nawait page.click('button');",
        )
        sr_module._recorder_instance = recorder

        with patch("src.tools.script_manager.ScriptManager") as MockManager:
            mock_mgr = MagicMock()
            mock_mgr.check_duplicate.return_value = None
            mock_mgr.save_script.return_value = str(tmp_path / "webui_scripts" / "test_system" / "case.js")
            MockManager.return_value = mock_mgr

            result = save_active_recording(str(tmp_path))
            assert result is not None
            mock_mgr.save_script.assert_called_once()
            assert sr_module._recorder_instance is None
