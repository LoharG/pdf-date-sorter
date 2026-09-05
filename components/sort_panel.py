import json
from pathlib import Path

import streamlit as st

from core.date_logic import sort_assignments, display_date
from core.pdf_handler import build_sorted_pdf
from core.session_manager import get_session_dir, save_assignments
from i18n import t


def _format_size(num_bytes: int) -> str:
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024*1024):.1f} MB"


def render_sort_panel(session: dict) -> dict:
    assignments = session["assignments"]
    page_count = session["page_count"]
    assigned = sum(1 for a in assignments if a["date"] is not None)
    unassigned = page_count - assigned

    st.divider()

    col_exp, col_imp = st.columns(2)
    with col_exp:
        export_data = json.dumps(session, indent=2)
        st.download_button(
            label=t("export_json"),
            data=export_data,
            file_name=f"assignments_{session['session_id'][:8]}.json",
            mime="application/json",
            key="btn_export",
        )
    with col_imp:
        imported_file = st.file_uploader(
            t("import_json"),
            type=["json"],
            key="import_json_upload",
            label_visibility="collapsed",
        )
        if imported_file:
            try:
                imported_data = json.loads(imported_file.read())
                from core.session_manager import import_assignments
                ok, err = import_assignments(session, imported_data)
                if ok:
                    session["assignments"] = imported_data["assignments"]
                    save_assignments(session)
                    st.success(t("import_success"))
                    st.rerun()
                else:
                    st.error(t(err))
            except Exception:
                st.error(t("upload_corrupted"))

    st.divider()

    sort_done = st.session_state.get("sort_done", False)

    if unassigned > 0:
        last_date = next(
            (a["date"] for a in reversed(assignments) if a["date"] is not None), None
        )
        st.warning(t("missing_assignments", n=unassigned))
        if last_date:
            if st.button(
                f"Fill {unassigned} unassigned pages with last date ({display_date(last_date)})",
                key="btn_autofill"
            ):
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc).isoformat()
                for a in assignments:
                    if a["date"] is None:
                        a["date"] = last_date
                        a["source"] = "inherited"
                        a["updated_at"] = now
                session["assignments"] = assignments
                save_assignments(session)
                st.session_state["session"] = session
                st.rerun()
        if st.button(t("jump_to_unassigned"), key="btn_jump_sort"):
            first = next((i for i, a in enumerate(assignments) if a["date"] is None), 0)
            st.session_state["current_page"] = first
            st.rerun()
        return session

    if st.button(t("sort_pdf"), key="btn_sort", disabled=sort_done):
        st.session_state["show_sort_confirm"] = True

    if st.session_state.get("show_sort_confirm", False):
        dates = [a["date"] for a in assignments if a["date"]]
        earliest = display_date(min(dates)) if dates else ""
        latest = display_date(max(dates)) if dates else ""
        st.info(t("sort_confirm_body",
            filename=session["original_filename"],
            total=page_count,
            earliest=earliest,
            latest=latest,
        ))
        col_yes, col_no = st.columns(2)
        if col_yes.button(t("sort_confirm_yes"), key="btn_sort_yes"):
            st.session_state["show_sort_confirm"] = False
            _run_sort(session)
        if col_no.button(t("sort_confirm_no"), key="btn_sort_no"):
            st.session_state["show_sort_confirm"] = False
            st.rerun()

    if sort_done:
        st.success(t("sort_success"))
        output_path = get_session_dir(session["session_id"]) / "sorted.pdf"
        if output_path.exists():
            size = _format_size(output_path.stat().st_size)
            st.caption(t("download_size", size=size))
            st.download_button(
                label=t("download"),
                data=output_path.read_bytes(),
                file_name=f"{Path(session['original_filename']).stem}_sorted.pdf",
                mime="application/pdf",
                key="btn_download",
            )
        if st.button(t("start_over"), key="btn_start_over"):
            from core.session_manager import cleanup_session
            cleanup_session(session["session_id"])
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.query_params.clear()
            st.rerun()

    return session


def _run_sort(session: dict) -> None:
    assignments = session["assignments"]
    try:
        sorted_indexes = sort_assignments(assignments)
    except ValueError:
        st.error(t("sort_failed"))
        return

    session_dir = get_session_dir(session["session_id"])
    source_path = session_dir / session["safe_filename"]
    output_path = session_dir / "sorted.pdf"

    progress_bar = st.progress(0, text=t("sorting_progress", n=0, total=session["page_count"]))

    def progress_callback(n: int, total: int) -> None:
        progress_bar.progress(n / total, text=t("sorting_progress", n=n, total=total))

    try:
        build_sorted_pdf(source_path, sorted_indexes, output_path, progress_callback)
        session["status"] = "completed"
        save_assignments(session)
        st.session_state["sort_done"] = True
        st.session_state["session"] = session
        st.rerun()
    except Exception:
        st.error(t("sort_failed"))
        if output_path.exists():
            output_path.unlink()
