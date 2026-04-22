import pytest
from pathlib import Path

from src.tools.file_converter import (
    is_text_based, is_convertible, is_supported, get_file_type, convert_to_text
)


class TestFileTypeChecks:
    def test_text_based_extensions(self):
        assert is_text_based("test.md") is True
        assert is_text_based("test.txt") is True
        assert is_text_based("test.py") is True
        assert is_text_based("test.json") is True
        assert is_text_based("test.yaml") is True

    def test_non_text_extensions(self):
        assert is_text_based("test.docx") is False
        assert is_text_based("test.pdf") is False
        assert is_text_based("test.xlsx") is False

    def test_convertible_extensions(self):
        assert is_convertible("test.docx") is True
        assert is_convertible("test.pdf") is True
        assert is_convertible("test.pptx") is True
        assert is_convertible("test.xlsx") is True

    def test_non_convertible(self):
        assert is_convertible("test.md") is False
        assert is_convertible("test.txt") is False

    def test_supported(self):
        assert is_supported("test.md") is True
        assert is_supported("test.docx") is True
        assert is_supported("test.xyz") is False

    def test_get_file_type(self):
        assert get_file_type("test.md") == "text"
        assert get_file_type("test.docx") == "document"
        assert get_file_type("test.pptx") == "presentation"
        assert get_file_type("test.xlsx") == "spreadsheet"
        assert get_file_type("test.pdf") == "pdf"
        assert get_file_type("test.xyz") == "unknown"


class TestConvertToText:
    def test_convert_text_file(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello World", encoding="utf-8")
        result = convert_to_text(str(test_file))
        assert result == "Hello World"

    def test_convert_md_file(self, tmp_path):
        test_file = tmp_path / "test.md"
        test_file.write_text("# Title\n\nContent", encoding="utf-8")
        result = convert_to_text(str(test_file))
        assert "Title" in result

    def test_convert_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            convert_to_text("/nonexistent/file.docx")

    def test_convert_unsupported_format(self, tmp_path):
        test_file = tmp_path / "test.xyz"
        test_file.write_text("data", encoding="utf-8")
        with pytest.raises(ValueError, match="不支持的文件格式"):
            convert_to_text(str(test_file))
