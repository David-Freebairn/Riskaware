"""
Home.py — Landing page for the rainfall-tools suite
"""

import streamlit as st

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
[data-testid="stSidebarNav"] a[href*="4_Snapshot"] span { visibility: hidden; }
[data-testid="stSidebarNav"] a[href*="4_Snapshot"]::before { content: "Snapshot"; visibility: visible; }

.tool-title { font-size: 1.3rem; font-weight: 700; color: #1a4a6e; margin-bottom: 0.3rem; }
.tool-desc  { font-size: 1rem; color: #444; line-height: 1.6; }

/* Make page_link buttons look like full cards */
div[data-testid="stPageLink"] a {
    border: 1.5px solid #d0dcea !important;
    border-radius: 10px !important;
    padding: 1.2rem 1.4rem !important;
    background: #fff !important;
    box-shadow: 0 1px 4px rgba(11,31,58,0.05) !important;
    transition: border-color 0.15s, box-shadow 0.15s !important;
    text-decoration: none !important;
    display: block !important;
    min-height: 110px !important;
    white-space: normal !important;
    word-wrap: break-word !important;
}
div[data-testid="stPageLink"] a:hover {
    border-color: #2979c4 !important;
    box-shadow: 0 2px 10px rgba(41,121,196,0.15) !important;
}
div[data-testid="stPageLink"] p {
    font-size: 0.95rem !important;
    color: #444 !important;
    margin: 0.3rem 0 0 0 !important;
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: unset !important;
    line-height: 1.5 !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("# 🌧️ RiskAware")
st.markdown(
    "*A suite of Australian rainfall/soil water analysis tools "
    "powered by climate data from [SILO](https://www.longpaddock.qld.gov.au/silo/).*"
)

with st.expander("ℹ️ About RiskAware"):
    st.markdown("""
RiskAware provides four rainfall and soil water analysis tools for Australian farmers and agronomists,
powered by the SILO climate database (Queensland Government / Bureau of Meteorology).

All tools share a single data download per session — selecting a station once loads the full record
for use across all four analyses.
""")

st.divider()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.page_link("pages/1_Season.py",
                 label="📈 **How's the season?**  \nCompare current season rainfall against selected years. This may support input decisions.")

with col2:
    st.page_link("pages/2_Odds.py",
                 label="🎲 **What are the odds?**  \nHow often has rainfall exceeded an amount over a number of days, during a chosen season?")

with col3:
    st.page_link("pages/3_Howwet.py",
                 label="💧 **How much rain stored?**  \nTrack plant available soil water gains over fallows using local BoM rainfall data.")

with col4:
    st.page_link("pages/4_Snapshot.py",
                 label="📸 **Snapshot**  \nLast year's temperature and rainfall, plus 100 years of annual rainfall with rolling averages.")

st.divider()
st.caption(
    "Climate data: Queensland Government's SILO database sourced from the Bureau of Meteorology "
    "Soil water estimates: PERFECT, HowLeaky (Littleboy et al. 1992)  ·  "
    "Interface: CliMate (Freebairn and McClymont 2025)"
)
