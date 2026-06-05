"""
Home.py — Landing page for the rainfall-tools suite
"""

import streamlit as st
from core.silo import clear_stale_cache

# Clean up disk cache files older than 7 days — runs once per session
clear_stale_cache(max_age_days=7)

st.set_page_config(
    page_title="RiskAware",
    page_icon="🌧️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@300;400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Source Sans 3', sans-serif; }

/* Rename sidebar nav items via CSS */
[data-testid="stSidebarNav"] a[href*="1_Season"] span { visibility: hidden; }
[data-testid="stSidebarNav"] a[href*="1_Season"]::before { content: "Season?"; visibility: visible; }
[data-testid="stSidebarNav"] a[href*="2_Odds"] span { visibility: hidden; }
[data-testid="stSidebarNav"] a[href*="2_Odds"]::before { content: "Odds?"; visibility: visible; }
[data-testid="stSidebarNav"] a[href*="3_Howwet"] span { visibility: hidden; }
[data-testid="stSidebarNav"] a[href*="3_Howwet"]::before { content: "Water stored?"; visibility: visible; }

.tool-card {
    border: 1.5px solid #d0dcea;
    border-radius: 10px;
    padding: 1.4rem 1.6rem;
    background: #fff;
    margin-bottom: 0.5rem;
    box-shadow: 0 1px 4px rgba(11,31,58,0.05);
    cursor: pointer;
    transition: border-color 0.15s, box-shadow 0.15s;
}
.tool-card:hover {
    border-color: #2979c4;
    box-shadow: 0 2px 10px rgba(41,121,196,0.15);
}
.tool-title { font-size: 1.3rem; font-weight: 700; color: #1a4a6e; margin-bottom: 0.3rem; }
.tool-desc  { font-size: 1rem; color: #444; line-height: 1.6; }

/* Hide the page_link button text — card itself is the clickable area */
.tool-link { margin-top: 0 !important; }
.tool-link a {
    display: block !important;
    position: absolute !important;
    inset: 0 !important;
    opacity: 0 !important;
}
.card-wrap {
    position: relative;
}
</style>
""", unsafe_allow_html=True)

st.markdown("# 🌧️ RiskAware")
st.markdown(
    "*A suite of Australian rainfall/soil water analysis tools "
    "powered by climate data from [SILO](https://www.longpaddock.qld.gov.au/silo/).*"
)
st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    with st.container():
        st.markdown("""
        <div class="tool-card">
            <div class="tool-title">📈 How's the season?</div>
            <div class="tool-desc">
                Compare current season rainfall against selected years.
                This may support input decisions.
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.page_link("pages/1_Season.py", label="Open", icon="📈")

with col2:
    with st.container():
        st.markdown("""
        <div class="tool-card">
            <div class="tool-title">🎲 What are the odds?</div>
            <div class="tool-desc">
                How often has rainfall exceeded an amount over a 
                number of days, during a chosen season?
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.page_link("pages/2_Odds.py", label="Open", icon="🎲")

with col3:
    with st.container():
        st.markdown("""
        <div class="tool-card">
            <div class="tool-title">💧 How much rain stored?</div>
            <div class="tool-desc">
                Track plant available soil water gains over fallows using local BoM rainfall data.
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.page_link("pages/3_Howwet.py", label="Open", icon="💧")

st.divider()
st.caption(
    "Climate data: Queensland Government's SILO database sourced from the Bureau of Meteorology "
    "Soil water estimates: PERFECT, HowLeaky (Littleboy et al. 1992)  ·  "
    "Interface: CliMate (Freebairn and McClymont 2025)"
)
