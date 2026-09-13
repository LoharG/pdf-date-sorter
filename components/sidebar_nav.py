import base64

import streamlit as st

from core.pdf_handler import render_page
from core.session_manager import get_session_dir
from i18n import t

# Thumbnails are real rendered pages, not just numbered buttons — but only a
# bounded WINDOW of them ever exists in the DOM at once (never "thousands of
# thumbnails mounted"), and the window auto-centers on the current page so
# it's visible without the sidebar needing to auto-scroll (which would need
# JS — confirmed elsewhere in this app that Streamlit's markdown sanitizer
# strips inline scripts/handlers, so this sidebar avoids depending on any).
_THUMB_DPI = 28
_WINDOW_SIZE = 10
_THUMB_CACHE_KEY = "sidebar_thumb_cache"
_MAX_THUMB_CACHE = 30

_STATUS_EMOJI = {"explicit": "🟢", "inherited": "🔵"}
_UNASSIGNED_EMOJI = "🟠"


def _get_pdf_path(session: dict):
    return get_session_dir(session["session_id"]) / session["safe_filename"]


def _load_thumbnail(session: dict, page_index: int) -> bytes:
    cache = st.session_state.setdefault(_THUMB_CACHE_KEY, {})
    if page_index not in cache:
        cache[page_index] = render_page(_get_pdf_path(session), page_index, dpi=_THUMB_DPI)
        current = st.session_state.get("current_page", 0)
        stale = [k for k in cache if abs(k - current) > _WINDOW_SIZE * 2]
        for k in stale:
            del cache[k]
        while len(cache) > _MAX_THUMB_CACHE:
            cache.pop(next(iter(cache)))
    return cache[page_index]


def _window_bounds(page_count: int, current: int) -> tuple[int, int]:
    override_start = st.session_state.get("_sidebar_window_start")
    if st.session_state.get("_sidebar_window_follow") != current:
        # Current page moved (Save & Next, Back/Next, jump) — recenter the
        # window on it so the active item is visible without scrolling.
        override_start = None
        st.session_state["_sidebar_window_follow"] = current

    if override_start is None:
        half = _WINDOW_SIZE // 2
        start = max(0, min(current - half, max(0, page_count - _WINDOW_SIZE)))
    else:
        start = override_start
    start = max(0, min(start, max(0, page_count - _WINDOW_SIZE)))
    end = min(start + _WINDOW_SIZE, page_count)
    return start, end


def render_sidebar_nav(session: dict) -> None:
    assignments = session["assignments"]
    page_count = session["page_count"]
    current = st.session_state.get("current_page", 0)

    st.markdown(f"<span class='sidebar-nav-title'>{t('pages_nav_title')}</span>", unsafe_allow_html=True)
    st.markdown(
        f"<span class='strip-legend'>🟢 {t('date_status_explicit')} &nbsp; "
        f"🔵 {t('date_status_inherited')} &nbsp; 🟠 {t('date_status_none')}</span>",
        unsafe_allow_html=True,
    )

    start, end = _window_bounds(page_count, current)

    nav_prev, nav_range, nav_next = st.columns([1, 3, 1])
    with nav_prev:
        if st.button("◀", key="sidebar_win_prev", disabled=(start == 0), use_container_width=True,
                      help=t("previous_pages")):
            st.session_state["_sidebar_window_start"] = max(0, start - _WINDOW_SIZE)
            st.session_state["_sidebar_window_follow"] = current
            st.rerun()
    with nav_range:
        st.caption(t("page_strip_range", start=start + 1, end=end, total=page_count))
    with nav_next:
        if st.button("▶", key="sidebar_win_next", disabled=(end >= page_count), use_container_width=True,
                      help=t("next_pages")):
            st.session_state["_sidebar_window_start"] = min(
                max(0, page_count - _WINDOW_SIZE), start + _WINDOW_SIZE
            )
            st.session_state["_sidebar_window_follow"] = current
            st.rerun()

    for idx in range(start, end):
        source = assignments[idx]["source"]
        emoji = _STATUS_EMOJI.get(source, _UNASSIGNED_EMOJI)
        status_word = {
            "explicit": t("date_status_explicit"),
            "inherited": t("date_status_inherited"),
        }.get(source, t("date_status_none"))
        is_current = idx == current

        try:
            thumb_bytes = _load_thumbnail(session, idx)
            b64 = base64.b64encode(thumb_bytes).decode("ascii")
            highlight = "outline: 2px solid var(--accent);" if is_current else ""
            st.markdown(
                f"<img src='data:image/png;base64,{b64}' class='sidebar-thumb' "
                f"style='{highlight}' alt='{t('page_of', current=idx + 1, total=page_count)}' />",
                unsafe_allow_html=True,
            )
        except Exception:
            pass  # Numbered fallback below still lets this page be reached.

        marker = "▣" if is_current else emoji
        if st.button(
            f"{marker} {idx + 1}",
            key=f"sidebar_page_{idx}",
            type="primary" if is_current else "secondary",
            use_container_width=True,
            help=f"{t('page_of', current=idx + 1, total=page_count)} — {status_word}",
        ):
            st.session_state["current_page"] = idx
            st.session_state["_edit_page"] = None
            st.session_state["_sidebar_window_follow"] = idx
            st.rerun()
