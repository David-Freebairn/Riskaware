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

/* Rename sidebar nav items */
[data-testid="stSidebarNav"] a[href*="1_Season"] span { visibility: hidden; }
[data-testid="stSidebarNav"] a[href*="1_Season"]::before { content: "Season?"; visibility: visible; }
[data-testid="stSidebarNav"] a[href*="2_Odds"] span { visibility: hidden; }
[data-testid="stSidebarNav"] a[href*="2_Odds"]::before { content: "Odds?"; visibility: visible; }
[data-testid="stSidebarNav"] a[href*="3_Howwet"] span { visibility: hidden; }
[data-testid="stSidebarNav"] a[href*="3_Howwet"]::before { content: "Water stored?"; visibility: visible; }
[data-testid="stSidebarNav"] a[href*="4_Snapshot"] span { visibility: hidden; }
[data-testid="stSidebarNav"] a[href*="4_Snapshot"]::before { content: "Snapshot"; visibility: visible; }

/* Card */
.tool-card {
    border: 1px solid #e0e6ee;
    border-bottom: none;
    border-radius: 8px 8px 0 0;
    padding: 1.3rem 1.4rem 1rem 1.4rem;
    background: #fff;
    min-height: 120px;
}
.tool-title { font-size: 1.05rem; font-weight: 600; color: #1a4a6e; margin-bottom: 0.4rem; }
.tool-desc  { font-size: 0.9rem; color: #555; line-height: 1.55; }

/* Open link — subtle, joins the card */
[data-testid="stPageLink"] { width: 100% !important; margin-top: 0 !important; }
[data-testid="stPageLink"] a {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 5px !important;
    width: 100% !important;
    padding: 0.45rem 1rem !important;
    background: #f4f7fb !important;
    color: #1a4a6e !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    border: 1px solid #e0e6ee !important;
    border-top: 1px solid #e8eef5 !important;
    border-radius: 0 0 8px 8px !important;
    text-decoration: none !important;
    transition: background 0.15s, color 0.15s !important;
}
[data-testid="stPageLink"] a:hover {
    background: #e8f0fa !important;
    color: #2979c4 !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("# 🌧️ RiskAware")
st.markdown(
    "*A suite of Australian rainfall/soil water analysis tools "
    "powered by climate data from [SILO](https://www.longpaddock.qld.gov.au/silo/).*"
)
st.divider()

TOOLS = [
    {
        "page":  "pages/1_Season.py",
        "icon":  "📈",
        "title": "📈 How's the season?",
        "desc":  "Compare seasons rain with previous years.",
    },
    {
        "page":  "pages/2_Odds.py",
        "icon":  "🎲",
        "title": "🎲 What are the odds?",
        "desc":  "Of getting rain over x days during a critical date window?",
    },
    {
        "page":  "pages/3_Howwet.py",
        "icon":  "💧",
        "title": "💧 How much water stored?",
        "desc":  "Track soil water gains over the fallow.",
    },
    {
        "page":  "pages/4_Snapshot.py",
        "icon":  "📸",
        "title": "📸  Snapshot",
        "desc":  "Review last year's temperatures, rainfall and long-term rainfall.",
    },
]

cols = st.columns(4)
for col, tool in zip(cols, TOOLS):
    with col:
        st.markdown(f"""
        <div class="tool-card">
            <div class="tool-title">{tool['title']}</div>
            <div class="tool-desc">{tool['desc']}</div>
        </div>
        """, unsafe_allow_html=True)
        st.page_link(tool["page"], label="Open", icon=tool["icon"])

st.divider()
st.caption(
    "Climate data: Queensland Government's SILO database sourced from the Bureau of Meteorology  ·  "
    "Soil water estimates: PERFECT, HowLeaky (Littleboy et al. 1992)  ·  "
    "Interface: CliMate (Freebairn and McClymont 2025)"
)
