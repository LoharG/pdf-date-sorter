import streamlit as st

_CSS = """
<style>
:root {
    --app-bg: #F5F7FB;
    --panel-bg: #FFFFFF;
    --text-primary: #172033;
    --text-secondary: #64748B;
    --accent: #2563EB;
    --border: #E2E8F0;
    --success: #15803D;
    --warning: #B45309;
}

.stApp {
    background-color: var(--app-bg);
}

html, body, [class*="css"] {
    font-size: 15px;
}

h1, h2, h3 {
    color: var(--text-primary);
}

.stButton > button, .stDownloadButton > button {
    min-height: 42px;
    border-radius: 10px;
    border: 1px solid var(--border);
}

.stButton > button[kind="primary"] {
    background-color: var(--accent);
    border-color: var(--accent);
}

div[data-baseweb="input"] input, .stNumberInput input {
    min-height: 40px;
    border-radius: 10px;
}

div[data-testid="stMetric"] {
    background-color: var(--panel-bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 8px 12px;
}

.app-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
}

.app-header .app-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--text-primary);
    white-space: nowrap;
}

.app-header .app-filename {
    font-size: 0.85rem;
    color: var(--text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 320px;
}

.app-header .app-page-of {
    font-size: 0.85rem;
    color: var(--text-secondary);
    white-space: nowrap;
}

.save-status {
    font-size: 0.8rem;
    padding: 2px 10px;
    border-radius: 999px;
    white-space: nowrap;
}
.save-status.saving { color: var(--text-secondary); background: #EEF2F7; }
.save-status.saved { color: var(--success); background: #EAF7EE; }
.save-status.failed { color: var(--warning); background: #FDF1E4; }

.date-status-pill {
    display: inline-block;
    font-size: 0.85rem;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 999px;
    margin-bottom: 6px;
}
.date-status-pill.explicit { color: var(--success); background: #EAF7EE; }
.date-status-pill.inherited { color: var(--accent); background: #EAF0FE; }
.date-status-pill.none { color: var(--warning); background: #FDF1E4; }

.helper-text {
    font-size: 0.85rem;
    color: var(--text-secondary);
    margin-top: -4px;
    margin-bottom: 8px;
}

.strip-legend {
    font-size: 0.8rem;
    color: var(--text-secondary);
}
</style>
"""


def inject_theme() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
