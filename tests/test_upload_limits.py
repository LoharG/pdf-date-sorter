"""
Tests for the upload-limit and large-file-handling changes: the pure
byte-count boundary check, path-based PDF validation, staging-directory
isolation/cleanup, and fingerprint compatibility between the old
bytes-based and new path-based implementations.

Boundary tests use mocked size integers (check_upload_size) or small
real PDFs (validate_pdf_path) — neither constructs actual multi-hundred-MB
files. That is deliberate: these are fast, deterministic unit tests, not
proof that a real 500 MB/1 GB upload works end-to-end. See DEPLOYMENT.md
"Upload limits" for the separate, manual large-file test procedure and its
actual recorded results.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz

from core.pdf_handler import check_upload_size, validate_pdf_path
from core import session_manager as sm


MB = 1024 * 1024


# --- check_upload_size: pure boundary, mocked sizes -------------------

def test_below_limit_is_accepted():
    assert check_upload_size(499 * MB, max_mb=500) is True


def test_exact_limit_is_accepted():
    assert check_upload_size(500 * MB, max_mb=500) is True


def test_one_byte_above_limit_is_rejected():
    assert check_upload_size(500 * MB + 1, max_mb=500) is False


def test_1gb_boundary_matches_1024_mb_convention():
    # If a deployment sets the optional 1 GB option, it is documented as
    # 1024 MB (binary), matching Streamlit's own server.maxUploadSize unit
    # — this pins that convention so it can't silently drift to a
    # 1000 MB/decimal interpretation without a test noticing.
    assert check_upload_size(1024 * MB, max_mb=1024) is True
    assert check_upload_size(1024 * MB + 1, max_mb=1024) is False


# --- validate_pdf_path -------------------------------------------------

def _make_pdf(path: Path, n_pages: int = 1, encrypt: bool = False) -> None:
    doc = fitz.open()
    for i in range(n_pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 92), f"PAGE {i + 1}")
    if encrypt:
        doc.save(str(path), encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="user")
    else:
        doc.save(str(path))
    doc.close()


def test_valid_pdf_is_accepted_with_correct_page_count(tmp_path):
    pdf_path = tmp_path / "valid.pdf"
    _make_pdf(pdf_path, n_pages=3)
    ok, err_key, page_count = validate_pdf_path(pdf_path)
    assert ok is True
    assert err_key == ""
    assert page_count == 3


def test_missing_file_is_rejected_gracefully_not_raised():
    ok, err_key, page_count = validate_pdf_path(Path("/nonexistent/definitely.pdf"))
    assert ok is False
    assert err_key == "upload_corrupted"
    assert page_count == 0


def test_file_with_wrong_header_is_rejected(tmp_path):
    fake = tmp_path / "not_a_pdf.pdf"
    fake.write_bytes(b"this is not a pdf file at all, just text padding")
    ok, err_key, page_count = validate_pdf_path(fake)
    assert ok is False
    assert err_key == "upload_invalid_type"
    assert page_count == 0


def test_corrupted_pdf_is_rejected(tmp_path):
    corrupt = tmp_path / "corrupt.pdf"
    # Valid header, garbage body — passes the cheap header check but fails
    # to actually open as a PDF, exercising the fitz.open() failure path
    # distinctly from the header check above.
    corrupt.write_bytes(b"%PDF-1.4\n" + b"\x00" * 200)
    ok, err_key, page_count = validate_pdf_path(corrupt)
    assert ok is False
    assert err_key == "upload_corrupted"
    assert page_count == 0


def test_password_protected_pdf_is_rejected(tmp_path):
    encrypted = tmp_path / "encrypted.pdf"
    _make_pdf(encrypted, n_pages=1, encrypt=True)
    ok, err_key, page_count = validate_pdf_path(encrypted)
    assert ok is False
    assert err_key == "upload_password"
    assert page_count == 0


def test_too_many_pages_is_rejected_independent_of_size(tmp_path):
    over = tmp_path / "many_pages.pdf"
    _make_pdf(over, n_pages=10)
    ok, err_key, page_count = validate_pdf_path(over, max_pages=5)
    assert ok is False
    assert err_key == "upload_too_many_pages"
    assert page_count == 10


# --- staging isolation and cleanup --------------------------------------

def test_staging_dir_is_separate_from_any_session_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(sm, "TMP_DIR", tmp_path)
    staging = sm.get_staging_dir()
    session_dir = sm.get_session_dir("some-session-id")
    assert staging != session_dir
    assert staging.name == "_staging"
    assert staging.exists()


def test_cleanup_stale_staging_files_removes_only_old_files(tmp_path, monkeypatch):
    monkeypatch.setattr(sm, "TMP_DIR", tmp_path)
    staging = sm.get_staging_dir()

    old_file = staging / "old.pdf"
    old_file.write_bytes(b"%PDF-old")
    recent_file = staging / "recent.pdf"
    recent_file.write_bytes(b"%PDF-recent")

    old_time = time.time() - 25 * 3600  # older than the 24h default
    import os
    os.utime(old_file, (old_time, old_time))

    sm.cleanup_stale_staging_files(max_age_hours=24)

    assert not old_file.exists()
    assert recent_file.exists()  # untouched — not this session's to delete


def test_cleanup_old_sessions_does_not_touch_staging_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(sm, "TMP_DIR", tmp_path)
    staging = sm.get_staging_dir()
    marker = staging / "in_progress_upload.pdf"
    marker.write_bytes(b"%PDF-in-progress")

    old_time = time.time() - 48 * 3600
    import os
    os.utime(staging, (old_time, old_time))

    sm.cleanup_old_sessions(max_age_hours=24)

    # A failed/abandoned upload elsewhere must not delete another
    # in-progress upload's staged file just because the shared _staging
    # directory itself looks old to the session-age sweep.
    assert marker.exists()


# --- fingerprint compatibility ------------------------------------------

def test_path_based_fingerprint_matches_bytes_based_for_same_content(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    _make_pdf(pdf_path, n_pages=2)
    file_bytes = pdf_path.read_bytes()

    from_bytes = sm.compute_fingerprint(file_bytes)
    from_path = sm.compute_fingerprint_path(pdf_path)

    # Byte-identical fingerprints for identical content is what keeps
    # existing persisted source_fingerprint values (and cross-session
    # assignment-JSON imports that compare against them) valid after this
    # change — not a new hash, just a new place to read the same bytes
    # from.
    assert from_bytes == from_path
