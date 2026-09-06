import copy

import streamlit as st

from core.date_logic import (
    validate_date,
    display_date,
    apply_next,
    apply_backward_edit,
    get_sticky_date,
    is_suspiciously_out_of_order,
)
from core.session_manager import save_assignments
from i18n import t


def render_date_panel(session: dict) -> dict:
    assignments = session["assignments"]
    current = st.session_state.get("current_page", 0)
    page_count = session["page_count"]
    assignment = assignments[current]

    if st.session_state.get("_edit_page") != current:
        st.session_state["current_date_edit"] = display_date(assignment["date"])
        st.session_state["_edit_page"] = current
        st.session_state.pop("out_of_order_warning", None)

    source = assignment["source"]
    if source == "explicit":
        status_label = f"● {t('date_status_explicit')}"
        status_color = "green"
    elif source == "inherited":
        status_label = f"○ {t('date_status_inherited')}"
        status_color = "blue"
    else:
        status_label = f"○ {t('date_status_none')}"
        status_color = "orange"

    st.markdown(f":{status_color}[{status_label}]")

    date_input = st.text_input(
        t("date_label"),
        placeholder=t("date_placeholder"),
        key="current_date_edit",
    )

    sticky = get_sticky_date(assignments, current)
    if sticky:
        st.caption(t("sticky_date", date=display_date(sticky)))
    else:
        st.caption(t("no_sticky_date"))

    save_clicked = st.button("💾 " + t("save_date"), key="btn_save_date", use_container_width=True)
    if save_clicked:
        st.session_state["next_clicked"] = True
        st.session_state["explicit_save"] = True

    if st.session_state.pop("next_clicked", False):
        explicit_save = st.session_state.pop("explicit_save", False)
        typed = st.session_state.get("current_date_edit", "").strip()
        effective = typed or display_date(assignment["date"])
        if effective:
            ok, result = validate_date(effective)
            if not ok:
                st.error(t(result))
            elif result == assignment["date"] and not explicit_save:
                # Value unchanged AND this was passive navigation (Next), not an
                # explicit Save click — navigate without touching the status.
                st.session_state["_edit_page"] = None
                if current < page_count - 1:
                    st.session_state["current_page"] = current + 1
                st.rerun()
            else:
                undo_stack = st.session_state.setdefault("undo_stack", [])
                undo_stack.append({
                    "assignments_snapshot": copy.deepcopy(assignments),
                })
                if len(undo_stack) > 1:
                    undo_stack.pop(0)

                max_explicit = max(
                    (i for i, a in enumerate(assignments) if a["source"] == "explicit"),
                    default=-1
                )
                is_backward = assignment["date"] is not None and current < max_explicit

                if is_backward:
                    session["assignments"] = apply_backward_edit(assignments, current, result)
                    st.toast(t("date_updated", n=current + 1))
                    save_assignments(session)
                    st.session_state["_edit_page"] = None
                    st.rerun()
                else:
                    session["assignments"] = apply_next(assignments, current, result)
                    save_assignments(session)
                    if explicit_save:
                        st.toast(t("date_updated", n=current + 1))
                    st.session_state["_edit_page"] = None
                    if not explicit_save and current < page_count - 1:
                        st.session_state["current_page"] = current + 1
                    st.rerun()
        else:
            st.session_state["_edit_page"] = None
            if not explicit_save and current < page_count - 1:
                st.session_state["current_page"] = current + 1
            st.rerun()

    undo_stack = st.session_state.get("undo_stack", [])
    if undo_stack:
        if st.button(t("undo"), key="btn_undo"):
            last = undo_stack.pop()
            session["assignments"] = last["assignments_snapshot"]
            save_assignments(session)
            st.session_state["_edit_page"] = None
            st.rerun()

    st.divider()

    assigned = sum(1 for a in assignments if a["date"] is not None)
    unassigned = page_count - assigned
    pct = int(assigned / page_count * 100) if page_count > 0 else 0

    st.progress(assigned / page_count if page_count > 0 else 0)
    st.caption(t("progress", assigned=assigned, total=page_count, pct=pct))

    col_a, col_b = st.columns(2)
    col_a.metric(t("assigned_pages"), assigned)
    col_b.metric(t("unassigned_pages"), unassigned)

    if unassigned > 0:
        if st.button(t("jump_to_unassigned"), key="btn_jump"):
            first_unassigned = next(
                (i for i, a in enumerate(assignments) if a["date"] is None), 0
            )
            st.session_state["_edit_page"] = None
            st.session_state["current_page"] = first_unassigned
            st.rerun()

    return session
