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

## Upload limits

**Effective default: 500 MB** (`.streamlit/config.toml`, `server.maxUploadSize = 500`).
**1 GB is configurable but not enabled by default and not fully capacity-tested** — see
below.

### Two enforcement layers, two different units — found, not assumed

Reading the installed Streamlit version's (1.63.0) own source turned up a real
inconsistency, confirmed empirically against a real file, not just from the code:

- **Server-side** (`streamlit/web/server/starlette/starlette_routes.py`,
  `_upload_put`): hard-rejects any upload over
  `server.maxUploadSize * 1024 * 1024` bytes — i.e. **binary MiB**.
- **Client-side** (the dropzone widget, `utils.BY03HRfb.js`): its own size check uses a
  unit base that resolves to **decimal MB** (1,000,000 bytes) in this build, not the
  server's 1024-based MiB.

Confirmed by generating a real 471.8 MiB (494.7 million-byte) test PDF and uploading it
through an actual browser (Playwright/Chromium) against a 500 MB config: the browser's
own dropzone rejected it outright — "File must be 500.0MB or smaller" — **before the
file ever reached this app's code or the server's own check**, even though 471.8 MiB is
comfortably under the server's 500 MiB limit.

**Practical consequence:** the limit a user actually experiences is the smaller of the
two conventions, roughly **476 MiB** (500,000,000 bytes), not the full 500 MiB the
server would otherwise accept. Files between ~476 MiB and 500 MiB are rejected by the
browser and never reach the server at all. This is a real, verified Streamlit behavior,
not a bug introduced by this app — `components/uploader.py` and `.streamlit/config.toml`
document it and read the single `server.maxUploadSize` config value everywhere in this
app's own code (widget hint, size validation, user-facing label) specifically so none of
*this app's* messaging can itself drift from what the server enforces; the
browser-vs-server gap above is a Streamlit-internal inconsistency this app cannot close
from Python.

### The 1 GB option

To enable it, change `.streamlit/config.toml`:

```toml
[server]
maxUploadSize = 1024
```

1024 here means **1024 MiB (1 GiB)**, consistent with the server-side binary
convention confirmed above — not 1000 MB. Given the client/server unit gap above, the
practically-reachable limit at that setting would be smaller than 1024 MiB for the same
reason 500 became ~476 in practice; this has **not been measured** at the 1 GB setting
(see "Not tested" below).

**Do this before enabling it in any real deployment:**
1. Re-run the memory measurements below at whatever size the target hosting plan needs
   to support, on that actual hosting plan (not a local dev machine) — peak memory
   scales with file size in this app (see measurements below), and hosting plans vary
   widely in available memory.
2. Confirm the hosting platform's own request/upload limits and timeouts allow a file
   that size (Streamlit Community Cloud and most PaaS platforms impose their own
   independent caps that `server.maxUploadSize` cannot override).
3. Re-run the six-page date-logic regression scenario and the full pytest suite after
   any change here.

### Large-file capacity testing — what was actually measured

Environment: local dev machine (Apple Silicon Mac, **16 GB RAM**), Chromium via
Playwright, Streamlit dev server (`streamlit run app.py`), single session, single
concurrent user. **This is not the target deployment machine** (per the original
request, a 4 GB RAM laptop) — the peak-memory numbers below are what this app's server
process used on a machine with 4x that headroom, not a projection of what will happen on
a 4 GB machine. Treat the gap between "peak measured" and "4 GB total, shared with the
OS, browser, and everything else" as the real risk, not something this testing clears.

Test files were generated on demand with `pypdf`/`fitz` + `Pillow`-rendered per-page
JPEG "scanned page" images (unique noise per page, ~2000×2600px, quality 92) — not
meaningless trailing padding — and were never committed to the repository. Each run
executed the complete pipeline through a real browser: upload → first page render →
navigate to a middle page → type and save a date → autofill remaining pages → sort →
download the result.

| File | Actual size | Pages | Upload→first page | Mid-page nav | Sort | Download | Downloaded size | Peak server RSS |
|---|---|---|---|---|---|---|---|---|
| Above old 200 MB limit | 250.4 MB (238.8 MiB) | 1,075 | 1.3 s | 0.5 s | 1.3 s | 7.8 s | 253.0 MB | **~1.24 GB** |
| Near the 500 MB config (below the ~476 MiB practical ceiling above) | 471.8 MiB (494.7 MB) | 2,025 | 2.5 s | 0.6 s | 2.3 s | 14.4 s | 476.7 MB | **~1.34 GB** |

Both completed successfully end to end: correct page count on upload, correct page
rendered after mid-document navigation, the date save succeeded, sorting completed, and
the downloaded file opened with the expected page count and content.

**Peak memory takeaway:** server-process RSS peaked at roughly **2.5-2.9x the uploaded
file's size** in both runs (dominated by: this app's own on-disk staging copy being
read back during validation/rendering, PyMuPDF's in-memory document object during sort,
and — despite the deferred-read fix in `sort_panel.py` — the download step itself still
requiring the full sorted file in memory once, since Streamlit's `download_button` has
no true streaming path even for a callable; see `components/sort_panel.py`). For a
device with 4 GB total RAM running the *browser* alongside the server (a likely local,
single-machine setup for this app), a ~1.3 GB *server-only* peak leaves comparatively
little headroom once the OS and an active browser tab are also accounted for. This is a
measured number, not a guess — treat a single-machine 4 GB deployment as marginal at
250-470 MB files, and budget accordingly (more RAM, or a server/browser on separate
machines) rather than assuming it will be fine.

**Not tested, per explicit instruction this session:** the 1 GB file itself (a
1025.3 MB / 4,400-page test file was generated and then deliberately deleted unused,
without running the upload/render/sort/download pipeline against it, and without
measuring its memory profile). The 1 GB option is implemented and documented above as
configurable, but its end-to-end behavior and memory profile are **unverified** — do not
treat it as capacity-proven from this session's testing.

### Reproducing this test procedure

```python
# Minimal generator sketch — adjust target_mb; never commit the output.
import fitz, io, random
from PIL import Image, ImageDraw

def make_scan_like_image(seed, w=2000, h=2600):
    random.seed(seed)
    img = Image.new("RGB", (w, h), (250, 248, 244))
    draw = ImageDraw.Draw(img)
    for _ in range(4000):
        x, y = random.randint(0, w-1), random.randint(0, h-1)
        s = random.randint(150, 230)
        draw.point((x, y), fill=(s, s, s))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()

doc = fitz.open()
rect = fitz.Rect(0, 0, 612, 792)
target_bytes = 470 * 1024 * 1024  # adjust per target size
page_num = 0
while page_num * 250_000 < target_bytes:  # ~245KB/page at this quality/resolution
    page = doc.new_page(width=612, height=792)
    page.insert_image(rect, stream=make_scan_like_image(page_num))  # unique seed per
    page_num += 1                                                    # page — MuPDF
doc.save("large_test.pdf", deflate=True)                             # deduplicates
                                                                       # identical
                                                                       # image streams
```

The `make_scan_like_image(page_num)` — a **unique seed per page** — matters: an earlier
attempt in this session cycled through only 50 distinct images (`page_num % 50`), and
MuPDF's own save-time deduplication of identical image streams silently collapsed a
supposedly-250MB file down to ~12MB. Confirmed by inspecting the actual output size
before trusting any of the numbers above.

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
and pull request to `main`. `tests/test_upload_limits.py` covers the upload-size
boundary and path-based PDF validation with mocked sizes and small real PDFs — see
"Upload limits" above for the separate, non-automated large-file procedure and its
actual recorded results, which this fast unit suite does not and cannot substitute for.
