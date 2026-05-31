# 🌧️ RiskAware — Rainfall and Soil Water Tools

A suite of four Australian rainfall and soil water analysis tools,
built with [Streamlit](https://streamlit.io) and powered by the
[SILO](https://www.longpaddock.qld.gov.au/silo/) climate database
(Queensland Government / Bureau of Meteorology).

**Live app:** [riskaware.streamlit.app](https://riskaware.streamlit.app)

---

## The four tools

### 📈 How's the season?
Compares the current season's cumulative rainfall against every year on record
at a chosen weather station.

- Search for a station by name, choose a lookback duration (1–60 months)
- Spaghetti chart: historical years in light blue, dashed median in dark blue, current year in bold red
- Headline shows the **percentile rank** and **mm above or below the median**
- Export to JPEG

### 🎲 What are the odds?
Rolling-window rainfall frequency analysis — how often has a rainfall threshold
been exceeded within a given number of days, during a chosen season?

- Set a rainfall threshold (mm), window length (days), and season start/end dates
- Bar chart showing years that met or exceeded the threshold
- Headline shows **exceedance frequency %**
- Export to JPEG

### 💧 How much rain stored?
Runs the PERFECT/HowLeaky daily soil water balance model over a fallow period
at a chosen weather station.

- Select a weather station, soil type, fallow start date, and initial soil water (% of PAWC)
- Fetches full daily climate from SILO and runs the water balance forward to today
- Compares current fallow against the previous 20 years of history
- Shows plant available soil water (mm and % PAWC), fallow efficiency, and cumulative rainfall
- Soil profile SVG diagram shows current water content by layer
- Water balance summary table (rainfall, runoff, soil evap, drainage, Δ soil water)
- Export to JPEG

### 📸 Snapshot
Weather and climate summary for a selected station — a quick reference for
the last full year and the long-term rainfall record.

- **Last full calendar year** — daily temperature (max/min with long-term averages as dashed lines)
  and monthly rainfall compared against the long-term monthly mean
- **Last 100 years** — annual rainfall bar chart with 5-, 10-, and 30-year rolling averages
- Interactive Plotly charts in the browser (hover, zoom, save)
- Export to JPEG (static three-panel figure) or interactive HTML

---

## Shared SILO data layer

All four pages share a single SILO download per session. The first page run
fetches the full station record (1900 → today) and caches it in session state.
Switching between pages or changing analysis periods uses in-memory slices —
no repeated downloads.

Changing station (via the **Change** button) clears the cache and triggers a
fresh download for the new station.

---

## Repository structure

```
RiskAware/
├── Home.py                   # Landing page
├── requirements.txt
├── README.md
├── .streamlit/
│   └── config.toml           # Theme and server settings
├── pages/
│   ├── 1_Season.py           # How's the season?
│   ├── 2_Odds.py             # What are the odds?
│   ├── 3_Howwet.py           # How much rain stored?
│   └── 4_Snapshot.py         # Climate snapshot
├── core/
│   ├── __init__.py
│   ├── silo.py               # SILO API — shared fetch, cache, and slice helpers
│   ├── styles.py             # Shared CSS and station persistence
│   ├── soil.py               # Soil profile dataclasses and .PRM reader
│   ├── soil_xml.py           # Soil profile reader (HowLeaky .soil XML format)
│   └── waterbalance.py       # PERFECT daily water balance engine
└── data/
    └── *.xml                 # Soil parameter files (HowLeaky .soil format)
```

---

## Running locally

```bash
git clone https://github.com/David-Freebairn/RiskAware.git
cd RiskAware
pip install -r requirements.txt
streamlit run Home.py
```

---

## Deployment

Hosted on [Streamlit Community Cloud](https://share.streamlit.io) (free tier),
connected to the `RiskAware` GitHub repository, `main` branch, main file `Home.py`.

Push changes to GitHub and Streamlit redeploys automatically within 1–2 minutes.

---

## Dependencies

```
streamlit>=1.32
pandas>=2.0
numpy>=1.24
matplotlib>=3.7
plotly>=5.0
requests>=2.28
openpyxl>=3.1
lxml>=4.9
```

Note: `plotly` is required for the interactive charts in the Snapshot page.

---

## Water balance model

The soil water balance in `core/waterbalance.py` is a Python port of the
PERFECT v2.0 model (Littleboy et al. 1992), implementing the same science as
HowLeaky. Daily processes:

1. **Runoff** — SCS curve number, adjusted for surface cover and antecedent moisture
2. **Infiltration** — rainfall minus runoff, distributed to layers
3. **Drainage** — cascade: excess above DUL drains to layer below
4. **Soil evaporation** — two-stage Ritchie model (stage I limited by U, stage II by CONA × √days)
5. **Deep drainage** — water draining below the bottom layer

The fallow simulation runs with zero green cover, zero transpiration, and 10%
residue cover (stubble).

---

## References

**Water balance**
Littleboy M, Silburn DM, Freebairn DM, Woodruff DR, Hammer GL, Leslie JK (1992).
Impact of soil erosion on production in dryland cropping systems.
*Australian Journal of Soil Research* 30, 775–788.

Ghahramani A, Freebairn DM, Sena DR, Cutajar JL, Silburn DM (2020).
A pragmatic parameterisation and calibration approach to model hydrology and
water quality of agricultural landscapes and catchments.
*Environmental Modelling and Software* 130, 104733.

**Interface**
Freebairn DM, McClymont D (2025). Australian CliMate — a decision support tool
for agricultural decision makers.
Preprint DOI: https://doi.org/10.20944/preprints202507.1081.v1

Freebairn DM, Ghahramani A, Robinson JB, McClymont D (2018). A tool for monitoring
soil water using modelling, on-farm data, and mobile technology.
*Environmental Modelling & Software* 104, 55–63.

**Data**
SILO climate data: [longpaddock.qld.gov.au/silo](https://www.longpaddock.qld.gov.au/silo/)
