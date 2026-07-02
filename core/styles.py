"""
core/styles.py
==============
Shared Streamlit CSS + station persistence helpers for RiskSmart.
"""

import streamlit as st


def apply_styles():
    """Inject shared CSS into the current Streamlit page."""
    st.markdown(_CSS, unsafe_allow_html=True)


def save_station(station_info: dict):
    """Save selected station to shared session key (persists across pages).
    Pass None to clear the shared station."""
    if station_info:
        st.session_state["_shared_station"] = station_info
    else:
        st.session_state.pop("_shared_station", None)


def load_station() -> dict | None:
    """Load shared station — returns None if none selected yet."""
    return st.session_state.get("_shared_station")


_CSS = """
<style>

/* ── Layout ──────────────────────────────────────────────────────────── */
.block-container {
    padding-top: 1.2rem !important;
    padding-bottom: 2rem !important;
    max-width: 1100px;
}

/* ── Result banner (2_Odds.py) ───────────────────────────────────────── */
.result-banner {
    background: #0b1f3a;
    border-radius: 8px;
    padding: 0.75rem 1.2rem;
    margin: 0.8rem 0;
    display: flex;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
}
.rb-label {
    font-size: 0.72rem;
    color: #5d8ab0;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
.rb-value {
    font-size: 1.4rem;
    font-weight: 800;
    color: #ffffff;
    line-height: 1;
}
.rb-pct {
    font-size: 2rem;
    font-weight: 800;
    color: #4da6ff;
    margin-left: auto;
}

/* ── Section headings inside containers ──────────────────────────────── */
.section-title {
    font-size: 1rem;
    font-weight: 600;
    color: #1A5276;
    margin-bottom: 0.4rem;
}

/* ── Result box ───────────────────────────────────────────────────────── */
.result-box {
    background: #F0F4FA;
    border: 1px solid #C5D5E8;
    border-radius: 10px;
    padding: 1.1rem 1.4rem;
    margin-bottom: 1rem;
}

.result-title { font-size: 1rem; color: #1a2332; margin-bottom: 0.4rem; }
.date-loc     { font-weight: 600; }
.loc          { font-weight: 700; color: #1A2F6B; }
.fallow-label { font-size: 0.9rem; color: #555; margin-bottom: 0.5rem; }
.paw-big      { font-size: 3rem; font-weight: 800; color: #1A3A6B; line-height: 1; }
.paw-unit     { font-size: 1.4rem; color: #1A3A6B; margin-left: 4px; }
.pawc-pct     { font-size: 1.1rem; color: #555; margin-left: 12px; }

/* ── Status messages ─────────────────────────────────────────────────── */
.status-msg {
    font-size: 0.9rem;
    color: #1A5276;
    font-style: italic;
}

/* ── Radio / selectbox labels ────────────────────────────────────────── */
div[data-testid="stRadio"] label,
div[data-testid="stSelectbox"] label {
    font-size: 0.9rem;
}

/* ── Container borders ───────────────────────────────────────────────── */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 10px !important;
    border-color: #D0DCF0 !important;
}

/* ── Divider ─────────────────────────────────────────────────────────── */
hr {
    margin: 0.6rem 0 !important;
    border-color: #E8EDF5 !important;
}

/* ── Number input label ──────────────────────────────────────────────── */
div[data-testid="stNumberInput"] > label {
    font-size: 0.82rem !important;
    color: #666 !important;
}

/* ── Tighter vertical spacing between stacked widgets (Season Tracker) ─
   Reduces the default gap Streamlit adds around each element so a form
   with many small inputs (dates, soil, crop fields) reads as compact
   rather than airy. Targets the generic block/element wrappers rather
   than anything page-specific, so should be safe to share across pages,
   but scoped here in case it ever needs isolating. ────────────────────── */
div[data-testid="stVerticalBlock"] > div[data-testid="stElementContainer"] {
    margin-bottom: 0.15rem !important;
}
div[data-testid="stHorizontalBlock"] {
    gap: 0.5rem !important;
    margin-bottom: 0.1rem !important;
}
.stMarkdown p {
    margin-bottom: 0.2rem !important;
}

/* ── Minimum width for month selectboxes in the Dates section (Season
   Tracker) ─ Column-ratio sizing alone can still truncate "Oct"/"Nov" to
   "O.."/"N.." on narrower viewports since Streamlit's selectbox shrinks
   its own width to fit its column regardless of content length. This
   forces a floor width wide enough for any 3-letter month abbreviation
   plus the dropdown chevron, targeting only the three date-month
   selectboxes via their container keys so every other selectbox in the
   app (e.g. soil type) is unaffected. ──────────────────────────────── */
div[class*="st-key-month_start_wrap"] div[data-testid="stSelectbox"],
div[class*="st-key-month_plant_wrap"] div[data-testid="stSelectbox"],
div[class*="st-key-month_harvest_wrap"] div[data-testid="stSelectbox"] {
    min-width: 78px !important;
}
div[class*="st-key-month_start_wrap"] div[data-baseweb="select"],
div[class*="st-key-month_plant_wrap"] div[data-baseweb="select"],
div[class*="st-key-month_harvest_wrap"] div[data-baseweb="select"] {
    min-width: 78px !important;
}
/* ── "Graph" buttons — quiet outline style so the gauge bars stay dominant
   The default coral/salmon Streamlit button colour reads as an alert/warning
   which competes visually with the gauge content. Replace with a neutral
   outline that recedes into the background. ──────────────────────────────── */
div[data-testid="stColumn"] button[kind="secondary"] {
    background-color: transparent !important;
    border: 1.5px solid #b0c4d8 !important;
    color: #1A5276 !important;
    font-size: 0.8rem !important;
    padding: 0.25rem 0.6rem !important;
}
div[data-testid="stColumn"] button[kind="secondary"]:hover {
    background-color: #eaf2fb !important;
    border-color: #1A5276 !important;
}

</style>
"""
