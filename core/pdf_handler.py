from __future__ import annotations

from pathlib import Path
from typing import Callable

import fitz  # PyMuPDF


def check_upload_size(size_bytes: int, max_mb: int) -> bool:
    """
    Pure byte-count boundary check, deliberately separate from PDF
    parsing/validation so it's cheap to unit-test at exact boundaries with
    a mocked size and doesn't require constructing real files of a given
    size. max_mb is MiB (1024*1024 bytes) — matches Streamlit's own
    server.maxUploadSize unit, confirmed by reading its enforcement code
    (max_size_bytes = maxUploadSize * 1024 * 1024 in
    streamlit/web/server/starlette/starlette_routes.py), not assumed.
    """
    return size_bytes <= max_mb * 1024 * 1024


def validate_pdf_path(pdf_path: Path, max_pages: int = 5000) -> tuple[bool, str, int]:
    """
    Validates a PDF already saved to disk. Deliberately takes a path, not
    bytes: opening from a path lets fitz read/buffer the file itself
    instead of requiring a second full in-memory copy on top of whatever
    Python bytes object the caller might otherwise be holding — the
    difference matters once uploads reach hundreds of MB. Size must be
    checked by the caller (see check_upload_size) before staging the file
    at all, so an oversized upload is rejected without ever being written
    to disk or opened here.
    """
    try:
        with open(pdf_path, "rb") as f:
            header = f.read(4)
    except OSError:
        return False, "upload_corrupted", 0
    if header != b"%PDF":
        return False, "upload_invalid_type", 0
    try:
        doc = fitz.open(str(pdf_path))
    except fitz.FileDataError:
        return False, "upload_corrupted", 0
    except Exception:
        return False, "upload_corrupted", 0
    try:
        if doc.needs_pass:
            return False, "upload_password", 0
        page_count = len(doc)
        if page_count == 0:
            return False, "upload_too_few_pages", 0
        if page_count > max_pages:
            return False, "upload_too_many_pages", page_count
        return True, "", page_count
    finally:
        doc.close()


def render_page(pdf_path: Path, page_index: int, dpi: int = 150) -> bytes:
    doc = fitz.open(str(pdf_path))
    try:
        if page_index < 0 or page_index >= len(doc):
            raise IndexError(f"Page index {page_index} out of range (0-{len(doc) - 1})")
        page = doc[page_index]
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        return pix.tobytes("png")
    finally:
        doc.close()


def build_sorted_pdf(
    source_path: Path,
    sorted_page_indexes: list[int],
    output_path: Path,
    progress_callback: Callable[[int, int], None],
) -> None:
    total = len(sorted_page_indexes)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        src = fitz.open(str(source_path))
        page_count = len(src)
        for idx in sorted_page_indexes:
            if idx < 0 or idx >= page_count:
                src.close()
                raise IndexError(f"Page index {idx} out of range (0-{page_count - 1})")
        out = fitz.open()
        for n, idx in enumerate(sorted_page_indexes, 1):
            out.insert_pdf(src, from_page=idx, to_page=idx)
            progress_callback(n, total)
        out.save(str(output_path))
        out.close()
        src.close()
    except Exception:
        if output_path.exists():
            output_path.unlink()
        raise
