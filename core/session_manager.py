from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

TMP_DIR = Path("tmp")


def get_session_dir(session_id: str) -> Path:
    safe_id = os.path.basename(session_id)
    return TMP_DIR / safe_id


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_session(original_filename: str, page_count: int, fingerprint: str) -> dict:
    session_id = str(uuid.uuid4())
    session_dir = get_session_dir(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    assignments = [
        {
            "page_index": i,
            "original_page_number": i + 1,
            "date": None,
            "source": None,
            "updated_at": None,
        }
        for i in range(page_count)
    ]
    return {
        "session_id": session_id,
        "original_filename": original_filename,
        "safe_filename": f"{uuid.uuid4().hex}.pdf",
        "source_fingerprint": fingerprint,
        "page_count": page_count,
        "created_at": _now(),
        "updated_at": _now(),
        "status": "ready",
        "assignments": assignments,
    }


def save_assignments(session: dict) -> None:
    session_dir = get_session_dir(session["session_id"])
    session_dir.mkdir(parents=True, exist_ok=True)
    session["updated_at"] = _now()
    path = session_dir / "assignments.json"
    path.write_text(json.dumps(session, indent=2), encoding="utf-8")


def load_session(session_id: str) -> dict | None:
    path = get_session_dir(session_id) / "assignments.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def compute_fingerprint(file_bytes: bytes) -> str:
    chunk = file_bytes[:4096]
    return hashlib.sha256(chunk).hexdigest()[:16]


def compute_fingerprint_path(path: Path) -> str:
    """
    Same algorithm as compute_fingerprint (first 4096 bytes, sha256,
    truncated to 16 hex chars) so fingerprints for identical PDF content
    are byte-for-byte identical either way — existing persisted
    source_fingerprint values, and cross-session assignment-JSON imports
    that compare against them, keep working unchanged. Reads from disk
    instead of an in-memory buffer purely to avoid requiring the caller to
    still be holding the whole upload in memory just to fingerprint it.
    """
    with open(path, "rb") as f:
        chunk = f.read(4096)
    return hashlib.sha256(chunk).hexdigest()[:16]


def get_staging_dir() -> Path:
    """
    Uploads are streamed here in chunks and validated BEFORE a session_id
    exists — keeping this separate from any session's own directory means
    a rejected or abandoned upload never touches, and can never be
    mistaken for, another session's files. cleanup_old_sessions only walks
    TMP_DIR's session subdirectories (see below); this staging dir is
    swept by cleanup_stale_staging_files instead, on the same age-based
    policy.
    """
    d = TMP_DIR / "_staging"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cleanup_stale_staging_files(max_age_hours: int = 24) -> None:
    staging_dir = get_staging_dir()
    if not staging_dir.exists():
        return
    cutoff = datetime.now(timezone.utc).timestamp() - max_age_hours * 3600
    for entry in staging_dir.iterdir():
        if entry.is_file() and entry.stat().st_mtime < cutoff:
            entry.unlink(missing_ok=True)


def cleanup_session(session_id: str) -> None:
    session_dir = get_session_dir(session_id)
    if session_dir.exists():
        shutil.rmtree(session_dir)


def cleanup_old_sessions(max_age_hours: int = 24) -> None:
    if not TMP_DIR.exists():
        return
    cutoff = datetime.now(timezone.utc).timestamp() - max_age_hours * 3600
    for entry in TMP_DIR.iterdir():
        if entry.name == "_staging":
            continue  # handled by cleanup_stale_staging_files instead
        if entry.is_dir() and entry.stat().st_mtime < cutoff:
            shutil.rmtree(entry, ignore_errors=True)


def import_assignments(current_session: dict, imported: dict) -> tuple[bool, str]:
    if imported.get("source_fingerprint") != current_session["source_fingerprint"]:
        return False, "import_fingerprint_mismatch"
    if len(imported.get("assignments", [])) != current_session["page_count"]:
        return False, "import_fingerprint_mismatch"
    return True, ""
