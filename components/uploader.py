import base64
import shutil
import uuid
from pathlib import Path

import streamlit as st

from core.pdf_handler import check_upload_size, validate_pdf_path
from core.session_manager import (
    create_session,
    save_assignments,
    compute_fingerprint_path,
    get_session_dir,
    get_staging_dir,
)
from i18n import t

_LANTERN_BG_PATH = Path(__file__).resolve().parent.parent / "assets" / "lantern-bg.jpg"


def _effective_max_upload_mb() -> int:
    """
    The one true upload limit: server.maxUploadSize is enforced by
    Streamlit's own upload HTTP handler regardless of anything set in
    Python (confirmed by reading that handler — see .streamlit/config.toml
    for the full explanation). file_uploader's own max_upload_size=
    parameter is only a client-side dropzone hint and does NOT change what
    the server accepts, so it isn't a second source of truth to keep in
    sync — reading get_option here and reusing it for the widget hint,
    this app's own validation, and the user-facing label means all three
    can never disagree with each other or with a deployment-level
    override of this same option.
    """
    return int(st.get_option("server.maxUploadSize"))


@st.cache_resource
def _load_lantern_bg_b64() -> str:
    return base64.b64encode(_LANTERN_BG_PATH.read_bytes()).decode("ascii")


def render_uploader() -> None:
    # Marker element + a :has() rule below scope the background to only this
    # screen's .stApp — the review workspace never renders this marker, so it
    # never picks up the rule or pays for the image payload.
    st.markdown('<div class="upload-lantern-marker"></div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <style>
        .stApp:has(.upload-lantern-marker) {{
            background-image: url("data:image/jpeg;base64,{_load_lantern_bg_b64()}");
            background-repeat: no-repeat;
            background-position: center center;
            /* contain (not cover): guarantees the whole lantern stays visible
               on any laptop viewport instead of risking it being cropped out
               by an aspect-ratio mismatch. The image's own background is
               solid black, matched by background-color below so the
               letterboxed edges blend in rather than showing a seam. */
            background-size: contain;
            background-color: #000000;
        }}
        /* stAppViewContainer and stHeader each paint their own opaque
           background-color (set globally in theme.py) directly on top of
           .stApp, fully hiding whatever is behind them — confirmed via
           computed-style inspection, not assumed. Made transparent only
           here so the lantern actually shows through instead of being
           painted over. */
        .stApp:has(.upload-lantern-marker) [data-testid="stAppViewContainer"],
        .stApp:has(.upload-lantern-marker) [data-testid="stHeader"] {{
            background-color: transparent !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    max_upload_mb = _effective_max_upload_mb()

    with st.container(key="hero_content"):
        st.markdown(f"<div class='hero-title'>{t('app_title')}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='hero-subtitle'>{t('hero_subtitle')}</div>", unsafe_allow_html=True)

        uploaded = st.file_uploader(
            t("upload_drag"),
            type=["pdf"],
            label_visibility="collapsed",
            # Client-side dropzone hint only (see _effective_max_upload_mb) —
            # set to the same resolved value so the UI never advertises a
            # different limit than the server will actually enforce.
            max_upload_size=max_upload_mb,
        )

        st.markdown(
            f"<div class='hero-guidance'>{t('hero_guidance')}</div>"
            f"<div class='hero-guidance'>{t('upload_limit_note', limit=max_upload_mb)}</div>",
            unsafe_allow_html=True,
        )

    if uploaded is None:
        return

    # Session isolation for a file that hasn't passed validation yet: an
    # upload is staged under a random name in a shared _staging/ directory
    # (not yet a session_id, since one doesn't exist until validation
    # succeeds) rather than ever touching another session's own directory.
    # Streamed to disk in bounded chunks instead of uploaded.read() (one
    # big Python bytes object) — halves this app's own peak memory for a
    # large upload, on top of whatever Streamlit's own upload handler has
    # already buffered before this script runs (that part is outside this
    # app's control; see DEPLOYMENT.md "Upload limits" for what that does
    # and doesn't mean for total memory use).
    uploaded.seek(0, 2)
    size_bytes = uploaded.tell()
    uploaded.seek(0)

    if not check_upload_size(size_bytes, max_upload_mb):
        st.error(t("upload_too_large", limit=max_upload_mb))
        return

    staging_path = get_staging_dir() / f"{uuid.uuid4().hex}.pdf"
    try:
        with st.spinner(t("upload_opening")):
            with open(staging_path, "wb") as f:
                shutil.copyfileobj(uploaded, f, length=1024 * 1024)

        with st.spinner(t("upload_preparing_first_page")):
            ok, err_key, page_count = validate_pdf_path(staging_path)

        if not ok:
            # A rejected upload never touches session state — whatever
            # document/session was already active (if any) is untouched,
            # since nothing above this point wrote to it.
            if err_key == "upload_too_many_pages":
                st.error(t(err_key, n=page_count))
            else:
                st.error(t(err_key))
            return

        fingerprint = compute_fingerprint_path(staging_path)
        session = create_session(
            original_filename=uploaded.name,
            page_count=page_count,
            fingerprint=fingerprint,
        )
        dest = get_session_dir(session["session_id"]) / session["safe_filename"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        # A rename within the same filesystem, not a copy — the already
        # on-disk bytes just get a new path, no re-reading or re-writing
        # the (potentially very large) file a second time.
        shutil.move(str(staging_path), str(dest))
        save_assignments(session)

        st.session_state["session"] = session
        st.session_state["current_page"] = 0
        st.session_state["screen"] = "workspace"
        st.session_state["undo_stack"] = []
        st.session_state["sort_done"] = False
        st.rerun()
    finally:
        # No-ops once the file has been moved into the session directory
        # above; only fires for a rejected/failed upload, cleaning up its
        # own staged file and nothing else.
        if staging_path.exists():
            staging_path.unlink(missing_ok=True)
