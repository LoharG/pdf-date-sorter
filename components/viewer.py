import base64
import struct
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
# Fixed overhead budget (header, app-header row, toolbar, dividers, page
# strip) measured empirically at 1366x768 and given a small safety margin.
# calc(100vh - Npx) is viewport-relative (recalculates automatically on
# resize, unlike a fixed vh% which doesn't account for the app's own fixed-
# height chrome) — see components/theme.py for the block-container padding
# half of this fix.
_VIEWER_HEIGHT_OFFSET_PX = 370


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


def _png_dimensions(png_bytes: bytes) -> tuple[int, int]:
    """
    Read width/height straight out of the PNG's IHDR chunk (bytes 16-24,
    big-endian) instead of pulling in an image-decoding dependency just for
    two integers we already have on the encoder side. Fixed offset is safe
    here because fitz's pixmap.tobytes("png") always emits a standard
    8-byte signature + IHDR-first PNG.
    """
    w, h = struct.unpack(">II", png_bytes[16:24])
    return w, h


def _init_zoom_state() -> None:
    # Fit width, not fit page: opening on fit_page was the direct cause of
    # "the document looks tiny" reports — a portrait page fit into a wide
    # short viewer is width-constrained by the SHORTER dimension, shrinking
    # it far more than a reader expects on first look. Fit width instead
    # matches how a page is actually being read (top-to-bottom, one column),
    # letting it scroll vertically inside the viewer instead.
    st.session_state.setdefault("zoom_mode", "fit_width")
    st.session_state.setdefault("zoom_percent", 100)


def render_viewer(session: dict) -> None:
    page_count = session["page_count"]
    current = st.session_state.get("current_page", 0)
    _init_zoom_state()

    # Compact toolbar: page jump/count + zoom controls only. Back/Next lives
    # solely in the date panel now (previously duplicated here too — one
    # navigation group, not two).
    goto_col, count_col, z1, z2, z3, z4, z5 = st.columns(
        [1.1, 0.9, 0.5, 0.7, 0.5, 0.85, 0.85]
    )

    with goto_col:
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
        if goto - 1 != current:
            st.session_state["current_page"] = int(goto) - 1
            st.session_state["_goto_sync_page"] = int(goto) - 1
            st.rerun()

    with count_col:
        st.markdown(
            f"<div style='padding-top:10px;font-size:0.85rem;color:var(--text-secondary);white-space:nowrap;'>"
            f"{t('page_of', current=current + 1, total=page_count)}</div>",
            unsafe_allow_html=True,
        )

    zoom_mode = st.session_state["zoom_mode"]
    zoom_percent = st.session_state["zoom_percent"]

    with z1:
        if st.button("−", key="btn_zoom_out", use_container_width=True, help=t("zoom_out")):
            st.session_state["zoom_mode"] = "custom"
            st.session_state["zoom_percent"] = max(_MIN_ZOOM, zoom_percent - _ZOOM_STEP)
            st.rerun()
    with z2:
        # fit_width/fit_page are viewport-relative — the resulting on-screen
        # scale isn't a single Python-known number (it depends on the live
        # browser width/height), so the mode name is shown instead of a
        # guessed percentage. Custom zoom's percentage IS exact: it's the
        # same value the DPI in _render_dpi was computed from.
        label = f"{zoom_percent}%" if zoom_mode == "custom" else t(zoom_mode)
        st.markdown(
            "<div style='text-align:center;padding-top:10px;"
            "font-size:0.85rem;color:var(--text-secondary);white-space:nowrap;'>"
            f"{label}</div>",
            unsafe_allow_html=True,
        )
    with z3:
        if st.button("+", key="btn_zoom_in", use_container_width=True, help=t("zoom_in")):
            st.session_state["zoom_mode"] = "custom"
            st.session_state["zoom_percent"] = min(_MAX_ZOOM, zoom_percent + _ZOOM_STEP)
            st.rerun()
    with z4:
        if st.button(t("fit_width"), key="btn_fit_width", use_container_width=True,
                     type="primary" if zoom_mode == "fit_width" else "secondary"):
            st.session_state["zoom_mode"] = "fit_width"
            st.rerun()
    with z5:
        if st.button(t("fit_page"), key="btn_fit_page", use_container_width=True,
                     type="primary" if zoom_mode == "fit_page" else "secondary"):
            st.session_state["zoom_mode"] = "fit_page"
            st.rerun()

    dpi = _render_dpi(zoom_mode, zoom_percent)

    try:
        img_bytes = _load_page_image(session, current, dpi)
        _render_scrollable_image(img_bytes, zoom_mode, current)
    except Exception:
        st.error(t("page_render_error", n=current + 1))


def _render_scrollable_image(img_bytes: bytes, zoom_mode: str, page_index: int) -> None:
    b64 = base64.b64encode(img_bytes).decode("ascii")
    nat_w, nat_h = _png_dimensions(img_bytes)

    # Sized entirely in CSS, deliberately without any JS: an earlier attempt
    # computed the fitted box with a <script> tag (inert — Streamlit injects
    # st.markdown HTML via innerHTML, and the HTML spec never executes a
    # script inserted that way) and then with an onload="" attribute
    # (stripped outright — Streamlit's markdown sanitizer removes inline
    # event-handler attributes from unsafe_allow_html content). Both
    # confirmed empirically, not assumed. CSS also has the advantage of
    # recalculating for free on any resize or sidebar collapse, with no
    # ResizeObserver needed.
    if zoom_mode == "fit_width":
        # Aspect ratio preserved by the browser's standard width:100% +
        # height:auto scaling — the wrap shrink-wraps to whatever height
        # that resolves to, so its shadow/border hug the true page edges.
        wrap_style = "width:100%;"
        img_style = "display:block; width:100%; height:auto;"
    elif zoom_mode == "fit_page":
        # aspect-ratio (a known exact value from the rendered PNG, not
        # guessed) + max-width/max-height:100% is the modern-CSS equivalent
        # of min(width_ratio, height_ratio): the browser picks the largest
        # box under that ratio that still fits both bounds. Needs the
        # ancestor chain to have a DEFINITE height for the percentage to
        # resolve against — handled by the :has() rule below, same fix
        # this codebase already needed for the old object-fit approach.
        wrap_style = (
            f"aspect-ratio:{nat_w}/{nat_h}; max-width:100%; max-height:100%; "
            "width:auto; height:auto;"
        )
        img_style = "display:block; width:100%; height:100%;"
    else:
        # Custom zoom: rendered at a DPI matching the chosen percentage
        # already (see _render_dpi), so the wrap is pinned to that exact
        # pixel size — enlarging further here would just blur a bitmap
        # instead of asking Python to re-render at the right resolution.
        wrap_style = f"width:{nat_w}px; height:{nat_h}px;"
        img_style = "display:block; width:100%; height:100%;"

    with st.container(key=f"pdf_viewer_container_{page_index}"):
        st.markdown(
            f"""
            <div class="pdf-sheet-wrap" style="{wrap_style}">
                <img src="data:image/png;base64,{b64}" style="{img_style}" />
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <style>
        /* Viewer surface: dark neutral grey, distinct from the white page
           sitting on it — previously this container's own background WAS
           white, so a letterboxed page just looked like a smaller white
           rectangle floating inside a bigger white rectangle, reported as
           "the document appears inside a wide white rectangle". Confirmed
           via computed-style inspection before this fix (the container
           painted #FFFFFF at full width/height regardless of the actual
           fitted image size). */
        [class*="st-key-pdf_viewer_container_"] {{
            flex: none !important;
            height: calc(100vh - {_VIEWER_HEIGHT_OFFSET_PX}px) !important;
            min-height: 260px !important;
            overflow: auto;
            border: 1px solid var(--border);
            border-radius: 12px;
            background: var(--viewer-surface);
            padding: 20px;
        }}
        /* Every wrapper Streamlit inserts between the container and our sheet
           div becomes a centering flex row with a definite height (needed
           for fit_page's max-height:100% to resolve at all) — rather than
           chasing down each wrapper's stable testid individually, which
           proved fragile last time. :has() without a direct-child
           combinator matches every ancestor level at once. */
        [class*="st-key-pdf_viewer_container_"] div:has(.pdf-sheet-wrap) {{
            display: flex !important;
            justify-content: center;
            align-items: flex-start;
            width: 100% !important;
            height: 100% !important;
        }}
        .pdf-sheet-wrap {{
            flex: none;
            background: #FFFFFF;
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.45);
            border-radius: 2px;
            overflow: hidden;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
