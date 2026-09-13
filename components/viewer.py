import base64
from pathlib import Path

import streamlit as st

from core.pdf_handler import render_page
from core.session_manager import get_session_dir
from i18n import t

_PAGE_CACHE_KEY = "page_image_cache"
_MAX_CACHE_ENTRIES = 8
_BASE_DPI = 150
_MIN_ZOOM = 50
_MAX_ZOOM = 300
_ZOOM_STEP = 25
_VIEWER_HEIGHT_VH = 68


def _get_pdf_path(session: dict) -> Path:
    return get_session_dir(session["session_id"]) / session["safe_filename"]


def _render_dpi(zoom_mode: str, zoom_percent: int) -> int:
    if zoom_mode == "custom":
        return max(50, round(_BASE_DPI * zoom_percent / 100))
    return _BASE_DPI


def _load_page_image(session: dict, page_index: int, dpi: int) -> bytes:
    cache = st.session_state.setdefault(_PAGE_CACHE_KEY, {})
    cache_key = (page_index, dpi)
    if cache_key not in cache:
        pdf_path = _get_pdf_path(session)
        cache[cache_key] = render_page(pdf_path, page_index, dpi=dpi)
        stale_keys = [k for k in cache if abs(k[0] - page_index) > 2]
        for k in stale_keys:
            del cache[k]
        while len(cache) > _MAX_CACHE_ENTRIES:
            cache.pop(next(iter(cache)))
    return cache[cache_key]


def _init_zoom_state() -> None:
    st.session_state.setdefault("zoom_mode", "fit_page")
    st.session_state.setdefault("zoom_percent", 100)


def render_viewer(session: dict) -> None:
    page_count = session["page_count"]
    current = st.session_state.get("current_page", 0)
    _init_zoom_state()

    nav1, nav2, nav3, sep, z1, z2, z3, z4, z5 = st.columns(
        [1, 1.6, 1, 0.2, 0.7, 0.9, 0.7, 1.1, 1.1]
    )

    with nav1:
        if st.button(f"◀ {t('back')}", disabled=(current == 0), key="btn_back", use_container_width=True):
            st.session_state["current_page"] = current - 1
            st.rerun()

    with nav2:
        if st.session_state.get("_goto_sync_page") != current:
            st.session_state["goto_page_input"] = current + 1
            st.session_state["_goto_sync_page"] = current

        goto = st.number_input(
            t("go_to_page"),
            min_value=1,
            max_value=page_count,
            step=1,
            label_visibility="collapsed",
            key="goto_page_input",
        )
        st.caption(f"{t('page_of', current=current + 1, total=page_count)}")
        if goto - 1 != current:
            st.session_state["current_page"] = int(goto) - 1
            st.session_state["_goto_sync_page"] = int(goto) - 1
            st.rerun()

    with nav3:
        if st.button(f"{t('next')} ▶", disabled=(current == page_count - 1), key="btn_next", use_container_width=True):
            st.session_state["next_clicked"] = True
            st.rerun()

    zoom_mode = st.session_state["zoom_mode"]
    zoom_percent = st.session_state["zoom_percent"]

    with z1:
        if st.button("−", key="btn_zoom_out", use_container_width=True, help=t("zoom_out")):
            st.session_state["zoom_mode"] = "custom"
            st.session_state["zoom_percent"] = max(_MIN_ZOOM, zoom_percent - _ZOOM_STEP)
            st.rerun()
    with z2:
        label = f"{zoom_percent}%" if zoom_mode == "custom" else t(zoom_mode)
        st.markdown(f"<div style='text-align:center;padding-top:8px;font-size:0.85rem;color:#64748B;'>{label}</div>", unsafe_allow_html=True)
    with z3:
        if st.button("+", key="btn_zoom_in", use_container_width=True, help=t("zoom_in")):
            st.session_state["zoom_mode"] = "custom"
            st.session_state["zoom_percent"] = min(_MAX_ZOOM, zoom_percent + _ZOOM_STEP)
            st.rerun()
    with z4:
        if st.button(t("fit_page"), key="btn_fit_page", use_container_width=True,
                     type="primary" if zoom_mode == "fit_page" else "secondary"):
            st.session_state["zoom_mode"] = "fit_page"
            st.rerun()
    with z5:
        if st.button(t("fit_width"), key="btn_fit_width", use_container_width=True,
                     type="primary" if zoom_mode == "fit_width" else "secondary"):
            st.session_state["zoom_mode"] = "fit_width"
            st.rerun()

    dpi = _render_dpi(zoom_mode, zoom_percent)

    try:
        img_bytes = _load_page_image(session, current, dpi)
        _render_scrollable_image(img_bytes, zoom_mode)
    except Exception:
        st.error(t("page_render_error", n=current + 1))


def _render_scrollable_image(img_bytes: bytes, zoom_mode: str) -> None:
    b64 = base64.b64encode(img_bytes).decode("ascii")

    if zoom_mode == "fit_page":
        img_style = f"max-height:{_VIEWER_HEIGHT_VH - 2}vh; width:auto; display:block; margin:0 auto;"
    elif zoom_mode == "fit_width":
        img_style = "width:100%; height:auto; display:block;"
    else:
        img_style = "display:block;"

    with st.container(key="pdf_viewer_container"):
        st.markdown(
            f"<img src='data:image/png;base64,{b64}' style='{img_style}' />",
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <style>
        .st-key-pdf_viewer_container {{
            height: {_VIEWER_HEIGHT_VH}vh;
            overflow: auto;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            background: #FFFFFF;
            padding: 8px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
