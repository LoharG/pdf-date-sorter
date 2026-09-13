import json
from pathlib import Path

import streamlit as st

_DIST_JS_PATH = (
    Path(__file__).resolve().parent.parent / "frontend" / "blackhole" / "dist" / "blackhole.js"
)


@st.cache_resource
def _load_bundle() -> str:
    return _DIST_JS_PATH.read_text(encoding="utf-8")


def render_blackhole_hero(*, paused: bool, height: int = 460) -> None:
    """
    Purely decorative. No PDF bytes or assignment data are ever passed in —
    only animation-tuning options (focus point, scrim edge, pause flag).
    Runs inside a sandboxed same-origin iframe via st.iframe; never reaches
    into the parent Streamlit page's DOM.
    """
    try:
        js_code = _load_bundle()
    except OSError:
        _render_static_fallback(height)
        return

    opts = {
        "paused": paused,
        "focus": [0.68, 0.42],
        "scrim": "left",
        "scrimStrength": 0.85,
        "starBrightness": 0.5,
    }

    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body {{ margin:0; padding:0; overflow:hidden; background:#090B10; }}
  #bh-host {{
    position: relative;
    width: 100%;
    height: 100vh;
    background: radial-gradient(ellipse at 68% 42%, #2a1608 0%, #0d0704 38%, #090B10 72%);
  }}
  #bh-canvas {{ position:absolute; inset:0; width:100%; height:100%; display:block; }}
</style>
</head>
<body>
  <div id="bh-host">
    <canvas id="bh-canvas" aria-hidden="true"></canvas>
  </div>
  <script>window.__BLACKHOLE_OPTS__ = {json.dumps(opts)};</script>
  <script>{js_code}</script>
</body>
</html>"""

    st.iframe(html, height=height, width="stretch")


def _render_static_fallback(height: int) -> None:
    st.markdown(
        f"""
        <div style="
            height:{height}px;
            border-radius:14px;
            background: radial-gradient(ellipse at 68% 42%, #2a1608 0%, #0d0704 38%, #090B10 72%);
        "></div>
        """,
        unsafe_allow_html=True,
    )
