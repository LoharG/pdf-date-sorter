from pathlib import Path

import streamlit as st

from core.pdf_handler import render_page
from core.session_manager import get_session_dir
from i18n import t

_PAGE_CACHE_KEY = "page_image_cache"


def _get_pdf_path(session: dict) -> Path:
    return get_session_dir(session["session_id"]) / session["safe_filename"]


def _load_page_image(session: dict, page_index: int) -> bytes:
    cache = st.session_state.setdefault(_PAGE_CACHE_KEY, {})
    if page_index not in cache:
        pdf_path = _get_pdf_path(session)
        cache[page_index] = render_page(pdf_path, page_index)
        keys_to_evict = [k for k in cache if abs(k - page_index) > 2]
        for k in keys_to_evict:
            del cache[k]
    return cache[page_index]


def render_viewer(session: dict) -> None:
    page_count = session["page_count"]
    current = st.session_state.get("current_page", 0)

    try:
        img_bytes = _load_page_image(session, current)
        st.image(img_bytes, use_container_width=True)
    except Exception:
        st.error(t("page_render_error", n=current + 1))

    col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])

    with col1:
        if st.button(f"◀ {t('back')}", disabled=(current == 0), key="btn_back"):
            st.session_state["current_page"] = current - 1
            st.rerun()

    with col3:
        goto = st.number_input(
            t("go_to_page"),
            min_value=1,
            max_value=page_count,
            value=current + 1,
            step=1,
            label_visibility="collapsed",
            key="goto_page_input",
        )
        st.caption(f"{t('page_of', current=current + 1, total=page_count)}")
        if goto - 1 != current:
            st.session_state["current_page"] = int(goto) - 1
            st.rerun()

    with col5:
        if st.button(f"{t('next')} ▶", disabled=(current == page_count - 1), key="btn_next"):
            st.session_state["next_clicked"] = True
            st.rerun()
