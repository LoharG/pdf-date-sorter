import streamlit as st

from core.session_manager import (
    load_session,
    cleanup_session,
    cleanup_old_sessions,
    cleanup_stale_staging_files,
)
from components.theme import inject_theme
from components.uploader import render_uploader
from components.viewer import render_viewer
from components.date_panel import render_date_panel, render_date_panel_secondary
from components.sort_panel import render_sort_panel
from components.sidebar_nav import render_sidebar_nav
from i18n import t

st.set_page_config(
    page_title="PDF Date Sorter",
    page_icon="📄",
    layout="wide",
)
inject_theme()

if not st.session_state.get("_initialized"):
    cleanup_old_sessions(24)
    cleanup_stale_staging_files(24)
    st.session_state["_initialized"] = True

if "lang" not in st.session_state:
    st.session_state["lang"] = "en"

params = st.query_params

if "session" in params and not st.session_state.get("session_id"):
    session_id_from_url = params["session"]
    restored = load_session(session_id_from_url)
    if restored:
        st.session_state["session_id"] = session_id_from_url
        st.session_state["session"] = restored
        st.session_state["current_page"] = 0
        st.session_state.setdefault("undo_stack", [])
        restored_done = restored.get("status") == "completed"
        st.session_state.setdefault("sort_done", restored_done)
        if restored_done:
            # Best-effort freshness seed: this is our only signal on a fresh
            # reload. If the file was edited after sorting in a prior session
            # and never re-sorted, this cannot detect that (no persisted
            # sort-time snapshot exists in the schema) — documented limitation.
            st.session_state.setdefault(
                "_sorted_dates_snapshot",
                [a["date"] for a in restored["assignments"]],
            )
    else:
        st.query_params.clear()
        st.warning(t("session_expired"))

if not st.session_state.get("session_id") and st.session_state.get("session"):
    st.session_state["session_id"] = st.session_state["session"]["session_id"]

if st.session_state.get("session_id"):
    session = st.session_state["session"]
    page_count = session["page_count"]
    current = st.session_state.get("current_page", 0)

    head1, head2, head3, head4, head5, head6 = st.columns([2.2, 2.6, 1.4, 1, 1.1, 1])
    with head1:
        st.markdown(f"<span class='app-title'>{t('app_title')}</span>", unsafe_allow_html=True)
    with head2:
        fname = session["original_filename"]
        display_name = (fname[:34] + "…") if len(fname) > 34 else fname
        st.markdown(
            f"<span class='app-filename' title='{fname}'>{display_name}</span>",
            unsafe_allow_html=True,
        )
    with head3:
        st.markdown(
            f"<span class='app-page-of'>{t('page_of', current=current + 1, total=page_count)}</span>",
            unsafe_allow_html=True,
        )
    with head4:
        status = st.session_state.get("save_status")
        if status == "saving":
            st.markdown(f"<span class='save-status saving'>{t('saving_status')}</span>", unsafe_allow_html=True)
        elif status == "saved":
            st.markdown(f"<span class='save-status saved'>{t('saved_status')}</span>", unsafe_allow_html=True)
        elif status == "failed":
            st.markdown(f"<span class='save-status failed'>{t('save_failed_status')}</span>", unsafe_allow_html=True)
    with head5:
        lang_choice = st.selectbox(
            t("language"),
            options=["en", "mr"],
            index=0 if st.session_state["lang"] == "en" else 1,
            format_func=lambda x: "EN" if x == "en" else "मर",
            label_visibility="collapsed",
            key="lang_selector",
        )
        if lang_choice != st.session_state["lang"]:
            st.session_state["lang"] = lang_choice
            st.rerun()
    with head6:
        if st.button(t("change_pdf"), key="btn_clear_top", help=t("clear_session"), use_container_width=True):
            st.session_state["confirm_clear"] = True

    if st.session_state.get("confirm_clear"):
        st.warning(t("confirm_clear_msg"))
        col_yes, col_no = st.columns(2)
        if col_yes.button(t("confirm_clear_yes"), key="btn_confirm_yes"):
            sid = st.session_state["session_id"]
            cleanup_session(sid)
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.query_params.clear()
            st.rerun()
        if col_no.button(t("confirm_clear_no"), key="btn_confirm_no"):
            st.session_state["confirm_clear"] = False
            st.rerun()

    st.divider()

if not st.session_state.get("session_id"):
    render_uploader()
else:
    session = st.session_state["session"]
    st.query_params["session"] = st.session_state["session_id"]

    with st.sidebar:
        render_sidebar_nav(session)

    left_col, right_col = st.columns([3, 1])
    with left_col:
        render_viewer(session)
    with right_col:
        updated_session = render_date_panel(session)
        with st.container(key="date_panel_scroll"):
            updated_session = render_date_panel_secondary(updated_session)
            updated_session = render_sort_panel(updated_session)
        st.session_state["session"] = updated_session

    # Thin status line only — the large multirow page-button grid that used
    # to live here moved into the collapsible sidebar (components/
    # sidebar_nav.py), which also gives the page list its own scroll area
    # instead of consuming vertical space in the main workspace.
    page_count = updated_session["page_count"]
    current = st.session_state.get("current_page", 0)
    assigned = sum(1 for a in updated_session["assignments"] if a["date"] is not None)
    pct = int(assigned / page_count * 100) if page_count else 0
    st.markdown(
        f"<div class='workspace-status-line'>{t('page_of', current=current + 1, total=page_count)}"
        f" &nbsp;·&nbsp; {t('progress', assigned=assigned, total=page_count, pct=pct)}</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        /* Safety net, not the primary mechanism: on normal laptop viewports
           (1366x768, 1440x900, 1280x720) everything above fits without this
           ever needing to scroll. It only engages on unusually short
           viewports or heavy browser text zoom, so primary actions (Save,
           Save & Next, Back/Next) are never clipped — they render before
           this container even starts. */
        .st-key-date_panel_scroll {
            /* flex:none needed for the same reason as the viewer container in
               components/viewer.py: this element is also a flex item of its
               parent's column-flex layout via Streamlit's own generated
               class (flex: 1 1 0%), which silently overrides an explicit
               max-height/height set via a DIFFERENT (even !important)
               property — confirmed by inspecting matched CSS rules. */
            flex: none !important;
            /* Matches components/viewer.py's _VIEWER_HEIGHT_OFFSET_PX —
               kept as the same number so both budgets stay conceptually
               aligned, even though this cap wasn't the one actually
               consuming the wasted vertical space (this secondary content
               was already comfortably under the old 370-based cap; the
               waste was in the unused space below the workspace, now
               reclaimed by the viewer instead). Raising this ceiling only
               makes the safety net less restrictive, never more. */
            max-height: calc(100vh - 225px) !important;
            overflow-y: auto;
            padding-right: 4px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
