"""Tests for the file-read plugin.

Uses the committed samples in data/ (sample.txt, sample.pdf) plus a couple
of ephemeral temp files for the unsupported-extension and corrupt-file
cases. Run directly with:

    venv\\Scripts\\python.exe tests\\test_file_reader.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.plugins.file_reader import read_file

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_TXT = PROJECT_ROOT / "data" / "sample.txt"
SAMPLE_PDF = PROJECT_ROOT / "data" / "sample.pdf"


def test_read_txt_file_returns_content():
    result = read_file(str(SAMPLE_TXT))

    assert result["success"] is True, result["error"]
    assert "sample text file" in result["content"]
    assert result["error"] is None


def test_read_pdf_file_extracts_text():
    result = read_file(str(SAMPLE_PDF))

    assert result["success"] is True, result["error"]
    assert "Hello PDF" in result["content"]
    assert result["error"] is None


def test_nonexistent_file_returns_error():
    result = read_file(str(PROJECT_ROOT / "data" / "does_not_exist_12345.txt"))

    assert result["success"] is False
    assert result["content"] is None
    assert "not found" in result["error"].lower()


def test_unsupported_extension_rejected():
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp.write(b"not a real docx")
        tmp_path = tmp.name

    try:
        result = read_file(tmp_path)

        assert result["success"] is False
        assert result["content"] is None
        assert "unsupported" in result["error"].lower()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_corrupt_pdf_handled_safely():
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(b"this is not a valid pdf file")
        tmp_path = tmp.name

    try:
        result = read_file(tmp_path)  # must not raise

        assert result["success"] is False
        assert result["content"] is None
        assert result["error"] is not None
    finally:
        Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    tests = [
        test_read_txt_file_returns_content,
        test_read_pdf_file_extracts_text,
        test_nonexistent_file_returns_error,
        test_unsupported_extension_rejected,
        test_corrupt_pdf_handled_safely,
    ]
    for test in tests:
        test()
        print(f"PASSED: {test.__name__}")
