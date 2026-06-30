# 🌧️ RiskAware

A suite of five Australian rainfall, soil water, and crop outlook analysis
tools, built with [Streamlit](https://streamlit.io) and powered by the
[SILO](https://www.longpaddock.qld.gov.au/silo/) climate database
(Queensland Government / Bureau of Meteorology).

**Live app:** [riskaware.streamlit.app](https://riskaware.streamlit.app)

---

## The five tools

### 📈 How's the season?
Compares the current season's cumulative rainfall against every year on
record at a chosen weather station.

- Search for a station, choose a start year and lookback duration (1–60 months)
- Spaghetti chart: historical years in light blue, dashed median in dark blue, current year in bold red
- Headline shows the **percentile rank** and **mm above or below the median**
- Interactive — hover any line to see its year
- Auto-runs on input change. Export to JPEG

### 🎲 What are the odds?
Rolling-window rainfall frequency analysis — how often has a rainfall
threshold been exceeded within a given number of days, during a chosen
season?

- Set a rainfall threshold (mm), window length (days), and season start/end dates
- Interactive bar chart — hover shows the year and number of times the threshold was exceeded
- Headline shows the **exceedance frequency %**
- Auto-runs on input change. Export to JPEG

### 💧 How much rain stored?
Runs the PERFECT/HowLeaky daily soil water balance model over a fallow
period at a chosen weather station.

- Select a station, soil type, fallow start date, end date, and initial soil water (% PAWC)
- Compares the current fallow against the previous 20 years of history
- Plant available soil water (mm and % PAWC), fallow efficiency, cumulative rainfall
- Soil profile SVG diagram and interactive water balance chart
- Auto-runs on input change. Export to JPEG

### 📸 Snapshot
Weather and climate summary for a selected station and year.

- Daily temperature (max/min with long-term averages) and monthly rainfall vs. long-term mean
- 100-year annual rainfall bar chart with 5-, 10-, and 30-year rolling averages
- Year input (defaults to last full year). Export to JPEG

### 🌾 YieldRisk
Five gauge bars tracking fallow and in-crop conditions against 30 years of
comparable history at the same site, soil, and dates.

- Set up paddock: soil type, fallow start, plant, and harvest dates, WUE, and threshold water
- **Fallow water gain** and **fallow nitrogen gain** (HowWetN mineralisation, moisture- and temperature-limited)
- **In-crop rain to date**, **photothermal quotient**, and **crop yield outlook** (French & Schultz WUE model)
- Each gauge ranks the current season's value as a percentile against comparable historical years
- Handles crops that cross the calendar year (e.g. summer crops planted October, harvested January/February) — automatically shows the most recently completed season ("📅 Looking back") once the real current date falls before the next plant date
- Download a Word summary of setup, results, and charts

---

## Shared SILO data layer

All five pages share a single SILO download per session. The first page run
fetches the full station record (1900 → today) and caches it in session
state and on disk (`.silo_cache/`, 24-hour TTL). Switching pages or
changing analysis periods uses in-memory slices — no repeated downloads.

Changing station (via the **Change** button) clears the cache and triggers
a fresh download for the new station.

### SILO-down fallback

If SILO is unreachable, every page offers a **📂 Use Dalby sample data**
button, loading a bundled real climate dataset (Dalby Post Office, 1996
onwards) so the app remains usable for exploration even during an outage.

---

## Repository structure

```
RiskAware/
├── Home.py                   # Landing page — two tool groups
├── gauge_utils.py             # Gauge bar + detail chart rendering
├── requirements.txt
├── README.md
├── .streamlit/
│   └── config.toml           # Theme and server settings
├── pages/
│   ├── 1_Season.py           # How's the season?
│   ├── 2_Odds.py             # What are the odds?
│   ├── 3_Howwet.py           # How much rain stored?
│   ├── 4_Snapshot.py         # Snapshot
│   └── 5_YieldRisk.py        # YieldRisk gauge dashboard
├── core/
│   ├── __init__.py
│   ├── silo.py                # SILO API — fetch, disk cache, SILO-down fallback
│   ├── styles.py              # Shared CSS and station persistence
│   ├── soil.py                 # Soil profile dataclasses, .PRM reader
│   ├── soil_xml.py            # HowLeaky .soil XML reader (incl. nitrogen tags)
│   ├── waterbalance.py        # PERFECT water balance + transpiration/erosion
│   ├── nitrogen.py             # HowWetN nitrogen mineralisation engine
│   ├── dashboard_metrics.py   # YieldRisk's five gauge calculations
│   ├── crop_metrics.py        # Photothermal quotient, yield outlook
│   ├── season_metrics.py      # Calendar-aligned historical comparison
│   ├── sample_data.py         # Bundled Dalby sample dataset loader
│   └── summary_doc.py         # YieldRisk Word summary export
├── sample_data/
│   ├── dalby_sample.parquet   # Bundled fallback climate data
│   └── dalby_station.json     # Bundled fallback station metadata
└── data/
    └── *.xml                  # Soil parameter files (HowLeaky .soil format)
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

Hosted on [Streamlit Community Cloud](https://share.streamlit.io) (free
tier), connected to the `RiskAware` GitHub repository, `main` branch, main
file `Home.py`.

Push changes to GitHub and Streamlit redeploys automatically within 1–2
minutes. The free tier spins the app down after a period of inactivity —
the first visit after idle time can take 10–30 seconds to wake up.

---

## Dependencies

```
streamlit>=1.58
pandas>=2.0
numpy>=1.26
matplotlib>=3.7
plotly>=6.0
python-docx>=1.1
kaleido==0.2.1
pyarrow>=14.0
requests>=2.28
openpyxl>=3.1
lxml>=4.9
```

`kaleido` is pinned to `0.2.1` (rather than the newer `>=1.0`) because that
version bundles its own headless browser, avoiding a system Chrome/Chromium
dependency — needed for exporting YieldRisk's Plotly gauge charts to PNG
inside the Word summary document.

---

## Water balance model

The soil water balance in `core/waterbalance.py` is a Python port of the
PERFECT v2.0 model (Littleboy et al. 1992), implementing the same science
as HowLeaky. Daily processes:

1. **Runoff** — SCS curve number, adjusted for surface cover and antecedent moisture
2. **Infiltration** — rainfall minus runoff, distributed to layers
3. **Drainage** — cascade: excess above DUL drains to layer below
4. **Soil evaporation** — two-stage Ritchie model (stage I limited by U, stage II by CONA × √days)
5. **Transpiration** — crop water use during the growing season (YieldRisk only)
6. **Deep drainage** — water draining below the bottom layer

The Howwet fallow simulation runs with zero green cover, zero transpiration,
and 10% residue cover (stubble) — the same assumptions YieldRisk uses for
its fallow water gain gauge, so results from the two tools are directly
comparable when initial soil water is set to the same value.

## Nitrogen mineralisation model

`core/nitrogen.py` is a Python port of DHM Environmental Software
Engineering's HowWetN engine (used with permission). Daily mineralisable
nitrogen is released from a potential pool derived from soil organic carbon
and the carbon:nitrogen ratio, at a rate limited by the slower of two 0–1
factors: a moisture factor (layer-1 soil water relative to field
capacity/wilting point) and a temperature factor (linear in mean daily air
temperature). On a dry fallow, the moisture factor is zero and no
mineralisation occurs — this is expected model behaviour, not a bug.

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

**Nitrogen**
DHM Environmental Software Engineering Pty Ltd (2011). HowWetN nitrogen
mineralisation engine, ported to Python with permission.

**Yield outlook**
French RJ, Schultz JE (1984). Water use efficiency of wheat in a
Mediterranean-type environment. *Australian Journal of Agricultural
Research* 35, 743–764.

**Photothermal quotient**
Fischer RA (1985). Number of kernels in wheat crops and the influence of
solar radiation and temperature. *Journal of Agricultural Science* 105,
447–461.

**Interface**
Freebairn DM, McClymont D (2025). Australian CliMate — a decision support
tool for agricultural decision makers.
Preprint DOI: https://doi.org/10.20944/preprints202507.1081.v1

Freebairn DM, Ghahramani A, Robinson JB, McClymont D (2018). A tool for
monitoring soil water using modelling, on-farm data, and mobile technology.
*Environmental Modelling & Software* 104, 55–63.

**Data**
SILO climate data: [longpaddock.qld.gov.au/silo](https://www.longpaddock.qld.gov.au/silo/)
