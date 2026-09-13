import copy

import streamlit as st

from core.date_logic import validate_date, display_date, apply_next, apply_backward_edit, get_sticky_date
from core.session_manager import save_assignments
from i18n import t


def _find_explicit_source_page(assignments: list[dict], current_idx: int) -> int | None:
    """Read-only lookup of the nearest explicit ancestor page (for helper text only)."""
    for i in range(current_idx, -1, -1):
        if assignments[i]["source"] == "explicit":
            return i
    return None


def _save_with_status(session: dict) -> None:
    st.session_state["save_status"] = "saving"
    try:
        save_assignments(session)
        st.session_state["save_status"] = "saved"
    except Exception:
        st.session_state["save_status"] = "failed"
        raise


def render_date_panel(session: dict) -> dict:
    assignments = session["assignments"]
    current = st.session_state.get("current_page", 0)
    page_count = session["page_count"]
    assignment = assignments[current]

    if st.session_state.get("_edit_page") != current:
        st.session_state["current_date_edit"] = display_date(assignment["date"])
        st.session_state["_edit_page"] = current

    max_explicit = max(
        (i for i, a in enumerate(assignments) if a["source"] == "explicit"),
        default=-1
    )
    would_be_backward = assignment["date"] is not None and current < max_explicit

    st.markdown(f"##### {t('date_for_page', n=current + 1)}")

    source = assignment["source"]
    if source == "explicit":
        st.markdown(f"<span class='date-status-pill explicit'>● {t('date_status_explicit')}</span>", unsafe_allow_html=True)
    elif source == "inherited":
        st.markdown(f"<span class='date-status-pill inherited'>○ {t('date_status_inherited')}</span>", unsafe_allow_html=True)
    else:
        st.markdown(f"<span class='date-status-pill none'>○ {t('date_status_none')}</span>", unsafe_allow_html=True)

    if source == "inherited":
        origin = _find_explicit_source_page(assignments, current)
        if origin is not None:
            st.markdown(
                f"<div class='helper-text'>{t('using_date_from_page', date=display_date(assignment['date']), n=origin + 1)}</div>",
                unsafe_allow_html=True,
            )
    elif source is None:
        st.markdown(f"<div class='helper-text'>{t('find_date_here')}</div>", unsafe_allow_html=True)

    if would_be_backward:
        st.markdown(f"<div class='helper-text'>⤺ {t('backward_edit_notice')}</div>", unsafe_allow_html=True)

    st.text_input(
        t("date_label"),
        placeholder=t("date_placeholder"),
        key="current_date_edit",
    )

    sticky = get_sticky_date(assignments, current)
    if sticky and source is None:
        st.caption(t("sticky_date", date=display_date(sticky)))

    save_col, save_next_col = st.columns(2)
    with save_col:
        save_clicked = st.button(t("save_date"), key="btn_save_date", use_container_width=True)
    with save_next_col:
        save_next_clicked = st.button(
            t("save_and_next"), key="btn_save_next", use_container_width=True, type="primary",
            disabled=(current == page_count - 1),
        )

    if save_clicked or save_next_clicked:
        st.session_state["next_clicked"] = True
        st.session_state["explicit_save"] = True
        st.session_state["also_advance"] = bool(save_next_clicked)

    if st.session_state.pop("next_clicked", False):
        explicit_save = st.session_state.pop("explicit_save", False)
        also_advance = st.session_state.pop("also_advance", False)
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

                is_backward = would_be_backward

                if is_backward:
                    session["assignments"] = apply_backward_edit(assignments, current, result)
                    _save_with_status(session)
                    st.toast(t("date_updated", n=current + 1))
                    st.session_state["_edit_page"] = None
                    if also_advance and current < page_count - 1:
                        st.session_state["current_page"] = current + 1
                    st.rerun()
                else:
                    session["assignments"] = apply_next(assignments, current, result)
                    _save_with_status(session)
                    if explicit_save:
                        st.toast(t("date_updated", n=current + 1))
                    st.session_state["_edit_page"] = None
                    if (also_advance or not explicit_save) and current < page_count - 1:
                        st.session_state["current_page"] = current + 1
                    st.rerun()
        else:
            st.session_state["_edit_page"] = None
            if not explicit_save and current < page_count - 1:
                st.session_state["current_page"] = current + 1
            st.rerun()

    nav_back, nav_next = st.columns(2)
    with nav_back:
        if st.button(f"◀ {t('back')}", key="btn_panel_back", disabled=(current == 0), use_container_width=True):
            st.session_state["current_page"] = current - 1
            st.session_state["_edit_page"] = None
            st.rerun()
    with nav_next:
        if st.button(f"{t('next')} ▶", key="btn_panel_next", disabled=(current == page_count - 1), use_container_width=True):
            st.session_state["next_clicked"] = True
            st.rerun()

    return session


def render_date_panel_secondary(session: dict) -> dict:
    """
    Progress + undo + next-unassigned. Split from render_date_panel() so
    the essential controls above (status, input, Save/Save & Next, Back/
    Next) can render outside the bounded-height safety-net container in
    app.py and are never the part that ends up scrolled out of view on an
    unusually short viewport — only this secondary content is.
    """
    assignments = session["assignments"]
    page_count = session["page_count"]

    undo_stack = st.session_state.get("undo_stack", [])
    if undo_stack:
        if st.button(t("undo"), key="btn_undo"):
            last = undo_stack.pop()
            session["assignments"] = last["assignments_snapshot"]
            _save_with_status(session)
            st.session_state["_edit_page"] = None
            st.rerun()

    assigned = sum(1 for a in assignments if a["date"] is not None)
    unassigned = page_count - assigned
    pct = int(assigned / page_count * 100) if page_count > 0 else 0

    st.progress(assigned / page_count if page_count > 0 else 0)
    st.caption(t("progress", assigned=assigned, total=page_count, pct=pct))

    if unassigned > 0:
        if st.button(t("next_unassigned"), key="btn_jump", use_container_width=True):
            first_unassigned = next(
                (i for i, a in enumerate(assignments) if a["date"] is None), 0
            )
            st.session_state["_edit_page"] = None
            st.session_state["current_page"] = first_unassigned
            st.rerun()

    return session
