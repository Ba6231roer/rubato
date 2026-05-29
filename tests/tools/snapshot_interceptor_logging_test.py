import logging
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.tools.snapshot_interceptor import (
    extract_snapshot_info,
    parse_aria_tree,
    process_snapshot_stdout,
    set_system_name,
)


class TestExtractSnapshotInfoLogging:
    def test_missing_page_url_logs_warning(self, caplog):
        stdout = "### Snapshot\n[Snapshot](.playwright-cli/test.yml)\n### Page\n- Page Title: Test\n"
        with caplog.at_level(logging.WARNING, logger="src.tools.snapshot_interceptor"):
            result = extract_snapshot_info(stdout)
        assert result is None
        assert "missing 'Page URL:'" in caplog.text

    def test_missing_snapshot_link_logs_warning(self, caplog):
        stdout = "### Page\n- Page URL: https://example.com\n- Page Title: Test\n### Snapshot\n"
        with caplog.at_level(logging.WARNING, logger="src.tools.snapshot_interceptor"):
            result = extract_snapshot_info(stdout)
        assert result is None
        assert "Snapshot stdout missing" in caplog.text
        assert "[Snapshot]" in caplog.text

    def test_valid_stdout_returns_info(self, caplog):
        stdout = (
            "### Page\n"
            "- Page URL: https://example.com/\n"
            "- Page Title: Example\n"
            "### Snapshot\n"
            "[Snapshot](.playwright-cli/page.yml)\n"
        )
        with caplog.at_level(logging.WARNING, logger="src.tools.snapshot_interceptor"):
            result = extract_snapshot_info(stdout)
        assert result is not None
        assert result[0] == "https://example.com/"
        assert result[2] == ".playwright-cli/page.yml"
        assert "missing" not in caplog.text


class TestProcessSnapshotStdoutLogging:
    def test_snapshot_file_not_found_logs_project_root(self, caplog, tmp_path):
        set_system_name("test_system")
        stdout = (
            "### Page\n"
            "- Page URL: https://example.com/\n"
            "- Page Title: Test\n"
            "### Snapshot\n"
            "[Snapshot](.playwright-cli/nonexistent.yml)\n"
        )
        with caplog.at_level(logging.WARNING, logger="src.tools.snapshot_interceptor"):
            count, cache_file = process_snapshot_stdout(stdout, str(tmp_path))
        assert count == 0
        assert cache_file is None
        assert "Snapshot file not found" in caplog.text
        assert str(tmp_path) in caplog.text

    def test_successful_cache_writes_file(self, caplog, tmp_path):
        set_system_name("test_system")
        snapshot_dir = tmp_path / ".playwright-cli"
        snapshot_dir.mkdir()
        snapshot_file = snapshot_dir / "page.yml"
        snapshot_file.write_text(
            '- button "Submit" [ref=e1]\n'
            '- textbox "Username" [ref=e2]\n',
            encoding="utf-8",
        )
        stdout = (
            "### Page\n"
            "- Page URL: https://example.com/login\n"
            "- Page Title: Login\n"
            "### Snapshot\n"
            f"[Snapshot](.playwright-cli/page.yml)\n"
        )
        with caplog.at_level(logging.INFO, logger="src.tools.snapshot_interceptor"):
            count, cache_file = process_snapshot_stdout(stdout, str(tmp_path))
        assert count == 2
        assert cache_file is not None
        assert os.path.exists(cache_file)
        assert "Snapshot info extracted" in caplog.text


class TestParseAriaTreeLogging:
    def test_empty_elements_logs_warning(self, caplog, tmp_path):
        yml_file = tmp_path / "empty.yml"
        yml_file.write_text(
            "- heading 'Welcome'\n- paragraph 'Hello'\n",
            encoding="utf-8",
        )
        with caplog.at_level(logging.WARNING, logger="src.tools.snapshot_interceptor"):
            elements = parse_aria_tree(str(yml_file))
        assert elements == []
        assert "No interactive elements parsed" in caplog.text

    def test_valid_yml_returns_elements(self, caplog, tmp_path):
        yml_file = tmp_path / "page.yml"
        yml_file.write_text(
            '- button "Submit" [ref=e1]\n'
            '- link "Home" [ref=e2]\n',
            encoding="utf-8",
        )
        with caplog.at_level(logging.WARNING, logger="src.tools.snapshot_interceptor"):
            elements = parse_aria_tree(str(yml_file))
        assert len(elements) == 2
        assert "No interactive elements" not in caplog.text
