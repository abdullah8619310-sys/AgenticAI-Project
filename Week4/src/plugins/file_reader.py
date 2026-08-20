"""File-read plugin for local .txt and .pdf files.

Given a file path, returns its extracted text content for the agent to
reason over.

This module only knows how to read files — it is not wired into the Claude
tool-calling loop yet. That happens later, in src/tools/registry.py.
"""

from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

SUPPORTED_EXTENSIONS = {".txt", ".pdf"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def read_file(path: str) -> dict:
    """Read a .txt or .pdf file and return its text content.

    Returns a dict shaped like:
        {
            "success": bool,
            "path": str,
            "content": str | None,
            "error": str | None,
        }

    Handles missing files, unsupported extensions, oversized files, and
    unreadable/corrupt files without raising — callers only need to check
    "success".
    """
    file_path = Path(path)

    if not file_path.exists():
        return _error_result(path, "File not found")

    if not file_path.is_file():
        return _error_result(path, "Path is not a file")

    extension = file_path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        return _error_result(
            path, f"Unsupported file extension '{extension}' (expected .txt or .pdf)"
        )

    try:
        size_bytes = file_path.stat().st_size
    except OSError:
        return _error_result(path, "Could not read file metadata")

    if size_bytes > MAX_FILE_SIZE_BYTES:
        return _error_result(
            path, f"File too large ({size_bytes} bytes, limit is {MAX_FILE_SIZE_BYTES})"
        )

    if extension == ".txt":
        return _read_txt(file_path)
    return _read_pdf(file_path)


def _read_txt(file_path: Path) -> dict:
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return _error_result(str(file_path), f"Could not read file: {exc}")

    return _success_result(str(file_path), content)


def _read_pdf(file_path: Path) -> dict:
    try:
        reader = PdfReader(str(file_path))
        pages_text = []
        for page in reader.pages:
            try:
                pages_text.append(page.extract_text() or "")
            except Exception:
                # Skip pages that fail to extract rather than failing the
                # whole read, so one bad page doesn't hide the rest.
                pages_text.append("")
        content = "\n".join(pages_text)
    except (PdfReadError, OSError, ValueError) as exc:
        return _error_result(str(file_path), f"Could not read PDF: {exc}")

    return _success_result(str(file_path), content)


def _success_result(path: str, content: str) -> dict:
    return {"success": True, "path": path, "content": content, "error": None}


def _error_result(path: str, message: str) -> dict:
    return {"success": False, "path": path, "content": None, "error": message}
