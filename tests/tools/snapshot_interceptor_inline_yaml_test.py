import logging
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.tools.snapshot_interceptor import (
    extract_snapshot_info,
    process_snapshot_stdout,
    set_system_name,
)

INLINE_YAML_STDOUT = (
    "### Page\n"
    "- Page URL: https://example.com/login\n"
    "- Page Title: Login Page\n"
    "- Console: 0 errors, 0 warnings\n"
    "### Snapshot\n"
    "```yaml\n"
    '- button "Submit" [ref=e1]\n'
    '- textbox "Username" [ref=e2]\n'
    '- link "Help" [ref=e3]\n'
    "```\n"
    "### Events\n"
)

FILE_LINK_STDOUT = (
    "### Page\n"
    "- Page URL: https://example.com/\n"
    "- Page Title: Example\n"
    "### Snapshot\n"
    "[Snapshot](.playwright-cli/page.yml)\n"
)


class TestExtractSnapshotInfoInlineYaml:
    def test_inline_yaml_returns_info(self, tmp_path):
        result = extract_snapshot_info(INLINE_YAML_STDOUT, str(tmp_path))
        assert result is not None
        assert result[0] == "https://example.com/login"
        assert result[1] == "Login Page"
        assert result[2].startswith(os.path.join(".playwright-cli", "page-"))
        assert result[2].endswith(".yml")

    def test_inline_yaml_writes_file(self, tmp_path):
        result = extract_snapshot_info(INLINE_YAML_STDOUT, str(tmp_path))
        assert result is not None
        yml_path = os.path.join(str(tmp_path), result[2])
        assert os.path.exists(yml_path)
        content = Path(yml_path).read_text(encoding="utf-8")
        assert 'button "Submit"' in content
        assert 'textbox "Username"' in content

    def test_file_link_still_works(self, tmp_path):
        result = extract_snapshot_info(FILE_LINK_STDOUT, str(tmp_path))
        assert result is not None
        assert result[0] == "https://example.com/"
        assert result[2] == ".playwright-cli/page.yml"

    def test_file_link_no_project_root_needed(self):
        result = extract_snapshot_info(FILE_LINK_STDOUT)
        assert result is not None
        assert result[2] == ".playwright-cli/page.yml"

    def test_neither_format_returns_none(self, caplog):
        stdout = "### Page\n- Page URL: https://example.com\n"
        with caplog.at_level(logging.WARNING, logger="src.tools.snapshot_interceptor"):
            result = extract_snapshot_info(stdout, "/tmp")
        assert result is None
        assert "missing" in caplog.text
        assert "inline YAML" in caplog.text

    def test_no_page_url_returns_none(self, caplog):
        stdout = "### Snapshot\n```yaml\n- button\n```\n"
        with caplog.at_level(logging.WARNING, logger="src.tools.snapshot_interceptor"):
            result = extract_snapshot_info(stdout, "/tmp")
        assert result is None
        assert "missing 'Page URL:'" in caplog.text


class TestProcessSnapshotStdoutInlineYaml:
    def test_inline_yaml_generates_cache(self, tmp_path):
        set_system_name("test_system")
        count, cache_file = process_snapshot_stdout(
            INLINE_YAML_STDOUT, str(tmp_path),
        )
        assert count == 3
        assert cache_file is not None
        assert os.path.exists(cache_file)

        with open(cache_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "button" in content
        assert "textbox" in content
        assert "link" in content

    def test_inline_yaml_updates_index(self, tmp_path):
        set_system_name("test_system")
        process_snapshot_stdout(INLINE_YAML_STDOUT, str(tmp_path))

        index_path = tmp_path / "webui_cache" / "INDEX.yaml"
        assert index_path.exists()

        import yaml
        with open(index_path, "r", encoding="utf-8") as f:
            index_data = yaml.safe_load(f)

        systems = index_data.get("systems", [])
        assert any(s["name"] == "test_system" for s in systems)

    def test_file_link_still_generates_cache(self, tmp_path):
        set_system_name("test_system")
        snapshot_dir = tmp_path / ".playwright-cli"
        snapshot_dir.mkdir()
        snapshot_file = snapshot_dir / "page.yml"
        snapshot_file.write_text(
            '- button "OK" [ref=e1]\n',
            encoding="utf-8",
        )
        count, cache_file = process_snapshot_stdout(
            FILE_LINK_STDOUT, str(tmp_path),
        )
        assert count == 1
        assert cache_file is not None

    def test_real_playwright_cli_snapshot_output(self, tmp_path):
        set_system_name("pingan_ebank")
        real_stdout = (
            "### Page\n"
            "- Page URL: https://test-ebank-fat.pingan.com.cn/stb/"
            "cimp-itl-star-web/demo/index.html#/login\n"
            "- Page Title: 数字财资系统 - Login - 登录\n"
            "- Console: 1 errors, 2 warnings\n"
            "### Snapshot\n"
            "```yaml\n"
            "- generic [ref=e3]:\n"
            "  - generic [ref=e9]:\n"
            "    - generic [ref=e11]: 账密登录\n"
            '    - textbox "请输入手机号" [ref=e22]: "13799828821"\n'
            '    - textbox "请输入账号" [ref=e28]: demo@qlgn\n'
            '    - textbox "请输入密码" [ref=e31]: qwer434654646465465\n'
            '    - button "登录" [ref=e32] [cursor=pointer]:\n'
            "```\n"
            "### Events\n"
        )
        count, cache_file = process_snapshot_stdout(
            real_stdout, str(tmp_path),
        )
        assert count > 0
        assert cache_file is not None
        assert os.path.exists(cache_file)
