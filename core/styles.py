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
    """Save selected station to shared session key (persists across pages)."""
    if station_info:
        st.session_state["_shared_station"] = station_info


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

</style>
"""
