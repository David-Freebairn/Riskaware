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
**Weather data:** Queensland Government's SILO database sourced from the Bureau 
of Meteorology and the many voluntary weather recorders across the 
Australian continent since the 1890’s
**Soil water estimates:** Applies a well-tested daily water balance model - also 
used in models such as PERFECT (1989), Howwet? (1994) and ApSim (1996)·
**Interface:** Standard graphical presentations also used in Howwet? (1994) and 
Australian CliMate (2025); New York 1982, sourced from Edward Tufte (1983)
**Development software** Anthropic. (2026). Claude (Sonnet 4.6) 
[Large language model]. https://claude.ai
**Support team**  Ken Brooke for encouragement, quality control and pushing me and Claude.

**References**
- Freebairn, D.M., Hamilton, A.H., Cox, P.G. and Holzworth, D. (1994). HOWWET? Estimating
   the storage of water in your soil using rainfall records: A computer program. 
   Agricultural Production Systems Research Unit, QDPI–CSIRO, Toowoomba, 
 - Freebairn, D.M. and McClymont, D. (2025). Australian CliMate – a decision support tool
    for agricultural decision makers. Climate, preprint 3755700.
    https://doi.org/10.20944/preprints202507.1081.v1  Queensland, Australia. 
- Littleboy, M., Silburn, D.M., Freebairn, D.M., Woodruff, D.R. and Hammer, G.L. (1989). 
    PERFECT: A simulation model of Productivity Erosion Runoff Functions to Evaluate 
    Conservation Techniques. QDPI Bulletin QB89005. Queensland Department of Primary 
    Industries, Brisbane, Australia. 
- McCown, R.L., Hammer, G.L., Hargreaves, J.N.G., Holzworth, D. and Freebairn, D.M. (1996).
    APSIM: A novel software system for model development, model testing, and simulation
    in agricultural systems research. Agricultural Systems, 50, 255–271. 
- New York Times (1982). New York City's weather for 1980. The New York Times, 
    11 January 1982, p. 32. Cited in Tufte, E.R. (1983). The Visual Display of 
    Quantitative Information. Cheshire, CT: Graphics Press.
- Jeffrey, S.J.; Carter, J.O.; Moodie, K.B.; Beswick, A.R. Using spatial interpolation
    to construct a comprehensive archive of Aus-tralian climate data. Environ. Model. 
    Softw. 2001, 16, 309–330. https://doi.org/10.1016/S1364-8152(01)00008-1.
- Queensland Government. SILO (Scientific Information for Land Owners). Available online:
    https://www.longpaddock.qld.gov.au/silo/about/ (accessed on 12 June 2025).


**Disclosure**

These analyses have been developed based on previous experience in designing
climate focused decision support tools since 1994. We have used Anthropic’s Claude AI software
This software does not have the same polish as previous DSSs and was built
to demonstrate new software and App development capabilities.

**Comments welcomed** David Freebairn em: david.freebairn@gmail.com 

""")

st.divider()

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

st.divider()
st.caption(
    "An objective assessment of system status and rainfall risks "
)
