from __future__ import annotations

from pathlib import Path
from typing import Callable

import fitz  # PyMuPDF

from core.session_manager import get_session_dir


def validate_pdf(file_bytes: bytes, max_mb: int = 200, max_pages: int = 5000) -> tuple[bool, str, int]:
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > max_mb:
        return False, "upload_too_large", 0
    if file_bytes[:4] != b"%PDF":
        return False, "upload_invalid_type", 0
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
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


def save_uploaded_pdf(session_id: str, file_bytes: bytes, safe_filename: str) -> Path:
    session_dir = get_session_dir(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    dest = session_dir / safe_filename
    dest.write_bytes(file_bytes)
    return dest


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
