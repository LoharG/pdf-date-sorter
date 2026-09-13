import base64
import os
from pathlib import Path

import streamlit as st

from core.pdf_handler import validate_pdf, save_uploaded_pdf
from core.session_manager import create_session, save_assignments, compute_fingerprint
from i18n import t

MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "200"))

_LANTERN_BG_PATH = Path(__file__).resolve().parent.parent / "assets" / "lantern-bg.jpg"


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

    with st.container(key="hero_content"):
        st.markdown(f"<div class='hero-title'>{t('app_title')}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='hero-subtitle'>{t('hero_subtitle')}</div>", unsafe_allow_html=True)

        uploaded = st.file_uploader(
            t("upload_drag"),
            type=["pdf"],
            label_visibility="collapsed",
        )

        st.markdown(f"<div class='hero-guidance'>{t('hero_guidance')}</div>", unsafe_allow_html=True)

    if uploaded is None:
        return

    file_bytes = uploaded.read()

    with st.spinner(t("upload_loading")):
        ok, err_key, page_count = validate_pdf(file_bytes, max_mb=MAX_UPLOAD_MB)

    if not ok:
        if err_key == "upload_too_many_pages":
            st.error(t(err_key, n=page_count))
        elif err_key == "upload_too_large":
            st.error(t(err_key, limit=MAX_UPLOAD_MB))
        else:
            st.error(t(err_key))
        return

    fingerprint = compute_fingerprint(file_bytes)
    session = create_session(
        original_filename=uploaded.name,
        page_count=page_count,
        fingerprint=fingerprint,
    )
    save_uploaded_pdf(session["session_id"], file_bytes, session["safe_filename"])
    save_assignments(session)

    st.session_state["session"] = session
    st.session_state["current_page"] = 0
    st.session_state["screen"] = "workspace"
    st.session_state["undo_stack"] = []
    st.session_state["sort_done"] = False
    st.rerun()
