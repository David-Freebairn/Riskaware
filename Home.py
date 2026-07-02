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
[data-testid="stSidebarNav"] a[href*="5_YieldRisk"] span { visibility: hidden; }
[data-testid="stSidebarNav"] a[href*="5_YieldRisk"]::before { content: "YieldRisk"; visibility: visible; }

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
    "*Analyses to support assessing system status (now)  "
    "and chances (risks) of rainfall.*"
)

with st.expander("ℹ️ About RiskAware"):
    st.markdown("""
Agricultural decisions are generally based on our understanding of **Current conditions**
and **Future expectations**.
Current conditions are what we sense around us. Some things are obvious, some less so
e.g. how much available water and nutrient in soils. 
Future expectations are based on our experience, with a natural bias toward recent 
experiences. An example “decision” might be to plant a crop now, or delay with the
expectation of a better start later. This decision is a mix of current and future events.
RiskAware’s four analyses provide insight into both current conditions (soil water) 
and future events (rainfall) based recent and long-term weather records.
Our weather history is a rich source of “book maker odds” or probabilities of future
rainfall using what we call climatology. Application of long-term records save us from
the trap of recent history bias.

- **How’s the season** simply gives us an objective assessment of the chances of rain
     since a specified date. Is it well above, below or near average? 
- **What are the odds?** Provides an unbiased estimate of the chances of a specified 
     event (planting rain, wet harvest etc). 
- **How much rain is stored?** uses recent rainfall data to estimate how well rain
     is stored in the soil, considering evaporation, runoff and drainage losses.
- **Snapshot** provides a graphical view of a previous year’s weather and long-term 
     annual rainfall. How variable is weather? 
     
**Acknowledgements**

**Weather data:** Queensland Government's SILO database sourced from the Bureau of Meteorology
 and the many voluntary weather recorders across the Australian continent since the 1890’s

**Soil water estimate:** Applies a well-tested water balance model used in models
such as PERFECT (1989), Howwet? (1994) and ApSim (1994)

**Interface:**
 Standard graphical presentations also used in Howwet? (Dimes et al 1996)
" and Australian CliMate (Freebairn and McClymont 2025). 
Snapshot graphic is based on an image “NEW YORK CITY'S WEATHER FOR 1980” from the 
New York Times  January 11th 1982, page 32, sourced from Edward Tufte (1983)
The Visual Display of Quantitative Information.

**Disclosure**

These analyses have been developed based on previous experience in designing
climate focused decision support tools. I have used Anthropic’s Claude AI software
This software does not have the same polish as previous DSSs and was built
to demonstrate new software and App development capabilities.

**Comments welcomed** David Freebairn em: david.freebairn@gmail.com 

""")

st.divider()

st.markdown("##### 🌧️ Rainfall & soil water")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.page_link("pages/1_Season.py",
                 label="📈 **How's the season?**  \nCompare current season rainfall against past records.")

with col2:
    st.page_link("pages/2_Odds.py",
                 label="🎲 **What are the odds?**  \nHow often has rainfall exceeded an amount over a number of days, between two dates?")

with col3:
    st.page_link("pages/3_Howwet.py",
                 label="💧 **How much rain stored?**  \nTrack plant available soil water gains over fallows using a local rainfall site.")

with col4:
    st.page_link("pages/4_Snapshot.py",
                 label="📸 **Snapshot of weather**  \nGraphs of one year's temperature and rainfall, and 100 years of annual rainfall.")

st.markdown("##### 🌾 Crop & yield outlook")
col5, col6, col7, col8 = st.columns(4)
with col5:
    st.page_link("pages/5_YieldRisk.py",
                 label="🌱 **YieldRisk**  \nFallow water & nitrogen, in-crop rain, photothermal quotient and crop yield outlook — five gauge bars tracking season progress.")
st.caption(
    "An objective assessment of system status and rainfall risks "
)
