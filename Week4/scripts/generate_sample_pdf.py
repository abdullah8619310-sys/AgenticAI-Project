"""One-off generator for data/sample.pdf, used by tests/test_file_reader.py.

Builds a minimal, valid single-page PDF by hand (correct xref byte offsets)
so the project does not need an extra PDF-writing dependency. Safe to
delete after data/sample.pdf exists — it is not imported by anything.

Usage:
    venv\\Scripts\\python.exe scripts\\generate_sample_pdf.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "sample.pdf"

TEXT = "Hello PDF"

CONTENT_STREAM = f"BT /F1 24 Tf 20 100 Td ({TEXT}) Tj ET"


def build_pdf_bytes() -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 200 200] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(CONTENT_STREAM)} >>\nstream\n{CONTENT_STREAM}\nendstream".encode(),
    ]

    header = b"%PDF-1.4\n"
    body_parts = []
    offsets = []
    current_offset = len(header)

    for i, obj in enumerate(objects, start=1):
        obj_bytes = f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
        offsets.append(current_offset)
        body_parts.append(obj_bytes)
        current_offset += len(obj_bytes)

    body = b"".join(body_parts)
    xref_offset = len(header) + len(body)

    xref_lines = [b"xref", f"0 {len(objects) + 1}".encode(), b"0000000000 65535 f "]
    for offset in offsets:
        xref_lines.append(f"{offset:010d} 00000 n ".encode())
    xref = b"\n".join(xref_lines) + b"\n"

    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF"
    ).encode()

    return header + body + xref + trailer


def main() -> None:
    OUTPUT_PATH.write_bytes(build_pdf_bytes())
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
