import streamlit as st

from i18n import t

CHUNK_SIZE = 50
MARKERS_PER_ROW = 10

_STATUS_EMOJI = {
    "explicit": "🟢",
    "inherited": "🔵",
}
_UNASSIGNED_EMOJI = "🟠"


def render_page_strip(session: dict) -> None:
    assignments = session["assignments"]
    page_count = session["page_count"]
    current = st.session_state.get("current_page", 0)

    total_chunks = (page_count + CHUNK_SIZE - 1) // CHUNK_SIZE

    if st.session_state.get("_strip_follow_page") != current:
        st.session_state["_strip_chunk"] = current // CHUNK_SIZE
        st.session_state["_strip_follow_page"] = current

    chunk = st.session_state.get("_strip_chunk", 0)
    chunk = max(0, min(chunk, total_chunks - 1))

    start = chunk * CHUNK_SIZE
    end = min(start + CHUNK_SIZE, page_count)

    nav_col1, nav_col2, nav_col3 = st.columns([1, 8, 1])
    with nav_col1:
        if st.button("◀", key="strip_prev_chunk", disabled=(chunk == 0), use_container_width=True):
            st.session_state["_strip_chunk"] = chunk - 1
            st.session_state["_strip_follow_page"] = current
            st.rerun()
    with nav_col2:
        st.caption(t("page_strip_range", start=start + 1, end=end, total=page_count))
    with nav_col3:
        if st.button("▶", key="strip_next_chunk", disabled=(chunk >= total_chunks - 1), use_container_width=True):
            st.session_state["_strip_chunk"] = chunk + 1
            st.session_state["_strip_follow_page"] = current
            st.rerun()

    page_indexes = list(range(start, end))
    for row_start in range(0, len(page_indexes), MARKERS_PER_ROW):
        row_indexes = page_indexes[row_start:row_start + MARKERS_PER_ROW]
        cols = st.columns(len(row_indexes))
        for col, idx in zip(cols, row_indexes):
            source = assignments[idx]["source"]
            emoji = _STATUS_EMOJI.get(source, _UNASSIGNED_EMOJI)
            label = f"{emoji} {idx + 1}"
            with col:
                if st.button(
                    label,
                    key=f"strip_marker_{idx}",
                    type="primary" if idx == current else "secondary",
                    use_container_width=True,
                ):
                    st.session_state["current_page"] = idx
                    st.session_state["_edit_page"] = None
                    st.session_state["_strip_follow_page"] = idx
                    st.rerun()
