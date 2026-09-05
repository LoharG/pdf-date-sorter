import os

import streamlit as st

from core.pdf_handler import validate_pdf, save_uploaded_pdf
from core.session_manager import create_session, save_assignments, compute_fingerprint
from i18n import t

MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "200"))


def render_uploader() -> None:
    st.title(t("app_title"))
    st.write(t("upload_prompt"))

    uploaded = st.file_uploader(
        t("upload_drag"),
        type=["pdf"],
        label_visibility="collapsed",
    )

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
