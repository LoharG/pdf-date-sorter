import streamlit as st

from core.session_manager import load_session, cleanup_session, cleanup_old_sessions
from components.uploader import render_uploader
from components.viewer import render_viewer
from components.date_panel import render_date_panel
from components.sort_panel import render_sort_panel
from i18n import t

st.set_page_config(
    page_title="PDF Date Sorter",
    page_icon="📄",
    layout="wide",
)

if not st.session_state.get("_initialized"):
    cleanup_old_sessions(24)
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
        st.session_state.setdefault("sort_done", restored.get("status") == "completed")
    else:
        st.query_params.clear()
        st.warning(t("session_expired"))

if not st.session_state.get("session_id") and st.session_state.get("session"):
    st.session_state["session_id"] = st.session_state["session"]["session_id"]

if st.session_state.get("session_id"):
    session = st.session_state["session"]

    top_col1, top_col2, top_col3, top_col4 = st.columns([3, 3, 1, 1])
    with top_col1:
        st.markdown(f"### {t('app_title')}")
    with top_col2:
        fname = session["original_filename"]
        display_name = (fname[:40] + "…") if len(fname) > 40 else fname
        st.caption(display_name)
    with top_col3:
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
    with top_col4:
        if st.button("✕", key="btn_clear_top", help=t("clear_session")):
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

    left_col, right_col = st.columns([3, 1])
    with left_col:
        render_viewer(session)
    with right_col:
        updated_session = render_date_panel(session)
        updated_session = render_sort_panel(updated_session)
        st.session_state["session"] = updated_session
