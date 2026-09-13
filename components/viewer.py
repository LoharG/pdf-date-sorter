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


def _init_zoom_state() -> None:
    st.session_state.setdefault("zoom_mode", "fit_page")
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
        label = f"{zoom_percent}%" if zoom_mode == "custom" else t(zoom_mode)
        st.markdown(f"<div style='text-align:center;padding-top:10px;font-size:0.85rem;color:var(--text-secondary);white-space:nowrap;'>{label}</div>", unsafe_allow_html=True)
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
        _render_scrollable_image(img_bytes, zoom_mode, current)
    except Exception:
        st.error(t("page_render_error", n=current + 1))


def _render_scrollable_image(img_bytes: bytes, zoom_mode: str, page_index: int) -> None:
    b64 = base64.b64encode(img_bytes).decode("ascii")

    if zoom_mode == "fit_page":
        # Smaller-of-width-or-height fit. Tried max-height:100%/max-width:100%
        # first (leaving width/height:auto to resolve from whichever bound), which
        # is the textbook approach — but verified empirically it does not work
        # here: max-height:100% failed to resolve against the flex container's
        # definite height at all (rendered image came out ~3x the container's
        # height, confirmed via getBoundingClientRect before this fix). This is
        # a known Chromium gotcha with percentage max-height inside a flex
        # item. object-fit:contain on a box explicitly sized to 100%/100% of
        # the container does the same "min(width_ratio, height_ratio)" fit
        # without depending on that percentage-resolution edge case.
        img_style = "width:100%; height:100%; object-fit:contain;"
    elif zoom_mode == "fit_width":
        img_style = "width:100%; height:auto;"
    else:
        # Custom zoom (e.g. 150%): rendered at a proportionally higher DPI
        # (see _render_dpi) so it should display at its natural pixel size,
        # exceeding the container and triggering horizontal/vertical scroll
        # once larger than it. Streamlit applies its own default
        # `img { max-width: 100% }` to any image rendered via st.markdown
        # (confirmed via matched-rules inspection) — harmless for fit_page/
        # fit_width above since their own width:100% already matches it, but
        # it silently capped every custom zoom level back down to the
        # container's width. Overridden here only for this mode.
        img_style = "max-width: none;"

    # Key includes the page index deliberately: st.container(key=...) with a
    # STABLE key persists the same underlying DOM node across reruns (React
    # reconciliation matching by key) — including its scroll position, which
    # verified as NOT resetting to top on page change with a fixed key. A
    # per-page key makes it a genuinely different element when the page
    # changes, forcing a real unmount/remount, which naturally starts a
    # fresh scroll position at 0. The CSS below matches on a class-substring
    # selector accordingly, since the literal class name now varies by page.
    with st.container(key=f"pdf_viewer_container_{page_index}"):
        st.markdown(
            f"<img src='data:image/png;base64,{b64}' style='{img_style}' />",
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <style>
        [class*="st-key-pdf_viewer_container_"] {{
            /* Two layered Streamlit defaults had to be overridden here, found
               by inspecting matched CSS rules and computed styles rather than
               assumed:
               1. st.container(key=...) also carries Streamlit's own generated
                  st-emotion-cache-* class on the same element, which sets
                  height:auto — !important on our own height rule handles that
                  half.
               2. That same generated class ALSO sets `flex: 1 1 0%`, because
                  this element is itself a flex ITEM inside its parent's
                  column-flex layout. In flexbox, flex-basis/flex-grow govern
                  an item's main-axis size and can silently override an
                  explicit height even with !important on the height property
                  — they're different properties, so no cascade conflict ever
                  triggers, the flex algorithm just wins. Pinning flex to
                  `none` here stops it from being grown/shrunk by its parent
                  so the explicit height actually takes effect. */
            flex: none !important;
            height: calc(100vh - {_VIEWER_HEIGHT_OFFSET_PX}px) !important;
            min-height: 260px !important;
            overflow: auto;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            background: #FFFFFF;
            padding: 8px;
            text-align: center;
        }}
        /* fit_page's height:100% (needed for object-fit:contain to do the
           min(width_ratio, height_ratio) fit) has to survive a percentage-
           height chain down through several layers Streamlit wraps the
           markdown-rendered <img> in — stElementContainer, stMarkdown, an
           inner wrapper div — none of which have a defined height by
           default, so they resolve to auto/content-size (i.e. the image's
           own intrinsic size) and the percentage chain breaks before ever
           reaching the img. Confirmed by walking the actual parent chain:
           our container correctly computed to 398px, but every layer
           between it and the <img> reported ~1137px (content-driven), so
           height:100% on the img itself had nothing valid to resolve
           against and silently fell back to auto. Naming each intermediate
           layer individually (stElementContainer, stMarkdown,
           stMarkdownContainer) fixed some but not all of them — there's at
           least one more with no stable class or testid at all — so instead
           of an increasingly fragile per-layer list, every div descendant
           in this scoped chain gets height:100% with !important (needed:
           Streamlit's own generated classes set explicit non-important
           heights on some of these same elements). Safe here specifically
           because this container holds a single unbroken vertical chain
           down to one <img> — there are no sibling branches this could
           mis-size. */
        [class*="st-key-pdf_viewer_container_"] div {{
            height: 100% !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
