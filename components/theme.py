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
    --tooltip-bg: #202938;
    --tooltip-text: #F8FAFC;
    --tooltip-border: #475569;
    --focus-ring: #FFB36B;
    --viewer-surface: #2B2F38;
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

/* Tooltips (st.button help=, etc.) render as a direct child of <body>,
   outside stAppViewContainer entirely (verified: parent chain is
   body > wrapper div > stTooltipContent, no ancestor in the app tree).
   Streamlit's default here is a WHITE box with dark text — readable on
   its own, but our earlier broad "p, span, div { color: text-primary }"
   rule (now scoped, see above) was still reaching this portaled element
   and forcing its text near-white too, causing literal white-on-white.
   Explicit, narrowly-scoped override, independent of that broader rule.
   No arrow/caret exists on this Streamlit version's tooltip (confirmed:
   ::before/::after both compute to `content: none`) — nothing to color. */
[data-testid="stTooltipContent"] {
    background-color: var(--tooltip-bg) !important;
    color: var(--tooltip-text) !important;
    border: 1px solid var(--tooltip-border) !important;
    border-radius: 8px;
}
[data-testid="stTooltipContent"] p {
    color: var(--tooltip-text) !important;
}

/* block-container ships with ~90px top / ~150px bottom padding by
   default (measured) — on a 768px-tall laptop viewport that's 240px of
   pure padding before any content, the single largest cause of the PDF
   viewer growing past the visible window. Reduced to just enough top
   padding to clear Streamlit's own absolute-positioned header (56px). */
.block-container {
    padding-top: 60px !important;
    padding-bottom: 12px !important;
}

/* Streamlit's default 15px flexbox gap between every stacked element
   (measured via computed style on stVerticalBlock) compounds across the
   15-20+ stacked elements on the workspace screen — header row, divider,
   toolbar, every date-panel widget, every page-strip row — into a large
   share of why the page grew taller than the viewport. Tightened
   globally rather than patched element-by-element. Not touching the
   hero/upload screen's own spacing (.hero-* classes set their own margins
   explicitly and are unaffected by this). */
[data-testid="stVerticalBlock"] {
    gap: 6px !important;
}
[data-testid="stHorizontalBlock"] {
    gap: 8px !important;
}
hr, [data-testid="stDivider"] {
    margin-top: 8px !important;
    margin-bottom: 8px !important;
}

html, body, [class*="css"] {
    font-size: 15px;
    color: var(--text-primary);
}

/* Scoped to the app's own container, NOT global — tooltips, dropdown
   popovers, and other portaled elements render as direct children of
   <body>, outside stAppViewContainer, and must not inherit this or their
   own (differently-colored) surfaces become unreadable. See the tooltip
   fix below: that bug was caused by exactly this rule being unscoped. */
[data-testid="stAppViewContainer"] h1,
[data-testid="stAppViewContainer"] h2,
[data-testid="stAppViewContainer"] h3,
[data-testid="stAppViewContainer"] h4,
[data-testid="stAppViewContainer"] h5,
[data-testid="stAppViewContainer"] p,
[data-testid="stAppViewContainer"] span,
[data-testid="stAppViewContainer"] label,
[data-testid="stAppViewContainer"] div {
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
/* Entered text: primary color, fully opaque (readable). Placeholder:
   secondary color at full opacity — Streamlit's own default placeholder
   style (rgba(49,51,63,0.6), a dark gray meant for a light input) is
   invisible against our dark input background; not just dim, invisible. */
input[data-testid$="Field"]::placeholder {
    color: var(--text-secondary) !important;
    opacity: 1 !important;
}
/* Focus ring: Streamlit's own default focus border is a bright red
   (rgb(255,75,75)) — its baseline focus color, not an error state, but it
   reads as one and clashes with this theme. Replaced with an accent ring
   that stays clearly visible (a visible focus indicator is required) without
   implying invalid input. */
div:has(> input[data-testid$="Field"]):focus-within {
    border-color: var(--focus-ring) !important;
    box-shadow: 0 0 0 2px rgba(255, 179, 107, 0.35) !important;
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

/* stProgress structure (verified via computed styles, not assumed):
     stProgress > div(ProgressBar) > div[data-testid="stProgressBarTrack"]  <- the track,
       ALWAYS full width regardless of value
         > div (no testid)  <- the actual fill; always 100% width and
           accent-colored, made to LOOK like it's at N% via
           `transform: translateX(-(100-N)%)` set inline by Streamlit.
   Coloring the track instead of the inner fill div (an earlier mistake
   here) makes the bar look 100% full at every value, since the
   always-full-width track was the accent color and the correctly
   0%-translated fill underneath was invisible regardless. */
[data-testid="stProgressBarTrack"] {
    background-color: var(--panel-raised) !important;
    border-radius: 999px;
}
[data-testid="stProgressBarTrack"] > div {
    background-color: var(--accent) !important;
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

/* Collapsible page navigator: Streamlit's own st.sidebar already provides
   the collapse/expand behavior natively (a supported API, not a custom
   CSS-driven toggle) — this just narrows its default width and gives its
   contents their own scroll region, independent of the main workspace. */
[data-testid="stSidebar"] {
    min-width: 160px !important;
    max-width: 200px !important;
    /* Streamlit's default sidebar background is a light grey — confirmed
       via computed style (rgb(240,242,246)) — while the rest of this app's
       CSS already makes text inside it light-colored for the dark theme,
       producing the same light-on-light unreadability class of bug already
       fixed once for tooltips. */
    background-color: var(--panel-bg) !important;
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
    padding-top: 16px;
}
.sidebar-nav-title {
    font-size: 0.9rem;
    font-weight: 700;
    color: var(--text-primary);
}
.sidebar-thumb {
    display: block;
    width: 100%;
    height: auto;
    border-radius: 4px;
    margin-top: 8px;
    margin-bottom: 2px;
    background: #FFFFFF;
}
.workspace-status-line {
    font-size: 0.78rem;
    color: var(--text-secondary);
    padding: 4px 2px 0;
}

/* Upload-screen content column: kept to a readable measure instead of
   stretching full-width now that the lantern background spans the whole
   page (previously this space held a separate two-column animation
   panel). */
.st-key-hero_content {
    max-width: 640px;
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
