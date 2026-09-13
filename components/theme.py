import streamlit as st

# Dark palette per the design spec. Two tokens were adjusted from the
# suggested values after measuring actual WCAG contrast (not assumed):
#   --border: suggested #2B3443 measured at only ~1.1-1.6:1 against the three
#     surface tones (they're all very close in luminance to each other) —
#     panels would have been nearly indistinguishable. Raised to #5C6C82,
#     which clears 3:1 against both Main and Raised surfaces while staying in
#     the same dark blue-gray family.
#   Status colors (explicit/inherited/unassigned) weren't given exact hex
#     values ("green"/"blue"/"amber") — chose values verified at 7:1-10:1
#     against both surface tones.
# All other suggested tokens (background, surfaces, primary/secondary text,
# accent, button text) were verified as given — see chat for the full
# contrast table.
_CSS = """
<style>
:root {
    --app-bg: #090B10;
    --panel-bg: #12161F;
    --panel-raised: #1A202B;
    --border: #5C6C82;
    --text-primary: #F8FAFC;
    --text-secondary: #AAB4C3;
    --accent: #FFB36B;
    --accent-text: #17110B;
    --status-explicit: #4ADE80;
    --status-inherited: #60A5FA;
    --status-unassigned: #FBBF24;
}

@media (prefers-reduced-motion: no-preference) {
    .stButton > button, .stDownloadButton > button, .date-status-pill {
        transition: background-color 150ms ease, border-color 150ms ease,
                    transform 120ms ease, opacity 180ms ease;
    }
    .stButton > button:active, .stDownloadButton > button:active {
        transform: scale(0.98);
    }
    .save-status { transition: opacity 200ms ease; }
}

.stApp {
    background-color: var(--app-bg);
    color: var(--text-primary);
}

[data-testid="stHeader"] {
    background-color: var(--app-bg);
}

[data-testid="stAppViewContainer"], .main, body {
    background-color: var(--app-bg);
    color: var(--text-primary);
}

html, body, [class*="css"] {
    font-size: 15px;
    color: var(--text-primary);
}

h1, h2, h3, h4, h5, p, span, label, div {
    color: var(--text-primary);
}

[data-testid="stCaptionContainer"], .stCaption, small {
    color: var(--text-secondary) !important;
}

hr, [data-testid="stDivider"] {
    border-color: var(--border);
}

.stButton > button, .stDownloadButton > button,
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"] {
    min-height: 42px;
    border-radius: 12px;
    border: 1px solid var(--border) !important;
    background-color: var(--panel-raised) !important;
    color: var(--text-primary) !important;
}
[data-testid="stBaseButton-secondary"] p {
    color: var(--text-primary) !important;
    background-color: transparent !important;
}

.stButton > button[kind="primary"], [data-testid="stBaseButton-primary"] {
    background-color: var(--accent) !important;
    border-color: var(--accent);
    color: var(--accent-text) !important;
    font-weight: 600;
}
[data-testid="stBaseButton-primary"] p {
    color: var(--accent-text) !important;
    background-color: transparent !important;
}

.stButton > button:disabled, [data-testid="stBaseButton-secondary"]:disabled {
    opacity: 0.45;
}

[data-testid="stIconMaterial"] {
    color: inherit !important;
}

[data-testid="stNumberInputContainer"] {
    background-color: var(--panel-raised) !important;
}
[data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"] {
    background-color: transparent !important;
    color: var(--text-primary) !important;
}
[data-testid="stNumberInputStepDown"] svg, [data-testid="stNumberInputStepUp"] svg {
    fill: var(--text-primary) !important;
}
[data-testid="stNumberInputStepDown"]:disabled svg {
    fill: var(--border) !important;
}

div[data-baseweb="input"], div[data-baseweb="select"],
.react-aria-ComboBox, .react-aria-ComboBox [role="group"] {
    background-color: var(--panel-raised) !important;
    border-radius: 10px;
}
.react-aria-ComboBox input, .react-aria-ComboBox button {
    background-color: var(--panel-raised) !important;
    color: var(--text-primary) !important;
}
.react-aria-ComboBox button svg {
    fill: var(--text-primary) !important;
    color: var(--text-primary) !important;
}
div:has(> [role="listbox"]) {
    background-color: var(--panel-raised) !important;
    border: 1px solid var(--border);
    border-radius: 10px;
}

/* React-Aria form fields (text/number inputs) wrap the real <input> in a
   div that carries the visible background — the input itself is
   transparent. Matched generically by the "*Field" testid suffix
   Streamlit uses (stTextInputField, stNumberInputField, ...) so this
   doesn't need a one-off rule per widget type. */
div:has(> input[data-testid$="Field"]) {
    background-color: var(--panel-raised) !important;
    border-radius: 10px;
}
input[data-testid$="Field"] {
    background-color: transparent !important;
    color: var(--text-primary) !important;
}
[role="option"] {
    color: var(--text-primary) !important;
    border-radius: 8px;
}
[role="option"][aria-selected="true"], [role="option"][data-focused="true"] {
    background-color: var(--accent) !important;
    color: var(--accent-text) !important;
}
div[data-baseweb="input"] input, .stNumberInput input, div[data-baseweb="select"] * {
    min-height: 40px;
    border-radius: 10px;
    background-color: var(--panel-raised) !important;
    color: var(--text-primary) !important;
}

div[data-testid="stMetric"] {
    background-color: var(--panel-bg);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 8px 12px;
}
[data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
    color: var(--text-primary) !important;
}

[data-testid="stExpander"] {
    background-color: var(--panel-bg);
    border: 1px solid var(--border);
    border-radius: 14px;
}

[data-testid="stFileUploader"] section {
    background-color: var(--panel-raised);
    border: 1px dashed var(--border);
    border-radius: 14px;
}

div[data-testid="stAlertContainer"] {
    border-radius: 12px;
    background-color: var(--panel-raised) !important;
    color: var(--text-primary) !important;
}

[data-testid="stProgress"] > div > div {
    background-color: var(--accent) !important;
}
[data-testid="stProgress"] {
    background-color: var(--panel-raised) !important;
    border-radius: 999px;
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
.save-status.saving { color: var(--text-secondary); background: var(--panel-raised); }
.save-status.saved { color: var(--status-explicit); background: rgba(74, 222, 128, 0.12); }
.save-status.failed { color: var(--status-unassigned); background: rgba(251, 191, 36, 0.12); }

.date-status-pill {
    display: inline-block;
    font-size: 0.85rem;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 999px;
    margin-bottom: 6px;
}
.date-status-pill.explicit { color: var(--status-explicit); background: rgba(74, 222, 128, 0.12); }
.date-status-pill.inherited { color: var(--status-inherited); background: rgba(96, 165, 250, 0.12); }
.date-status-pill.none { color: var(--status-unassigned); background: rgba(251, 191, 36, 0.12); }

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

.hero-title {
    font-size: clamp(1.8rem, 3.2vw, 2.6rem);
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1.15;
    margin-bottom: 8px;
}
.hero-subtitle {
    font-size: 1rem;
    color: var(--text-secondary);
    margin-bottom: 20px;
    line-height: 1.5;
}
.hero-guidance {
    font-size: 0.88rem;
    color: var(--text-secondary);
    margin-top: 14px;
    padding: 10px 14px;
    background: var(--panel-bg);
    border: 1px solid var(--border);
    border-radius: 12px;
}
</style>
"""


def inject_theme() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
