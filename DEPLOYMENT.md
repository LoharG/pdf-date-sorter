# Deployment notes

## Hosting requirements

Confirmed against Streamlit Community Cloud's current requirements (checked at the
time of this UI upgrade):

- `requirements.txt` — Python dependencies (unchanged by this upgrade; no new
  packages were added — zoom/theme/page-strip use only Streamlit and the
  Python standard library).
- `packages.txt` — apt package `libmupdf-dev`, required by PyMuPDF.
- `runtime.txt` — pins `python-3.12`.

No changes were required to any of these three files for this UI upgrade.

## Does progress survive... ?

This app persists session/assignment data to a local `tmp/<session_id>/` directory
on whatever disk the Streamlit process is running on (see `core/session_manager.py`).
That has real implications depending on what "survive" means:

- **Browser refresh (same server process still running):** Yes. The app puts
  `?session=<id>` in the URL, and reloading that URL re-reads
  `tmp/<session_id>/assignments.json` from disk. Confirmed working in this session's
  browser testing.

- **Server restart (same container/disk, process restarted):** Depends entirely on
  whether the platform's disk is persistent across restarts. On Streamlit Community
  Cloud, app "sleep" due to inactivity and waking back up generally reuses the same
  container's disk, so this usually survives — but this is a platform behavior, not
  something this app guarantees or controls.

- **Hosting redeployment (new push, new build):** **No.** Streamlit Community Cloud
  builds a fresh container on redeploy. `tmp/` is local to the old container and is
  gone. Any in-progress session (uploaded PDF + assignments) is lost and the user
  will see "Session not found or expired" if they reload an old session URL after a
  redeploy.

This app does not implement any durable, redeploy-surviving storage (e.g. an
external database or object store) — that would be a real architecture change, out
of scope for this UI-only upgrade, and is not implemented here. If that guarantee is
needed, it should be scoped as its own task.

## Local run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mkdir -p tmp
streamlit run app.py
```

## Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v --cov=core --cov-report=term-missing
```

GitHub Actions (`.github/workflows/tests.yml`) runs this same suite on every push
and pull request to `main`.
