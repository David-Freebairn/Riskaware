# 🌧️ Risk Status — Rainfall and Soil Water Tools

A unified suite of three Australian rainfall and soil water analysis tools,
built with [Streamlit](https://streamlit.io) and powered by the
[SILO](https://www.longpaddock.qld.gov.au/silo/) climate database
(Queensland Government).

**Live app:** [rainapps.streamlit.app](https://rainapps.streamlit.app)

---

## The three tools

### 📈 How's the season?
Compares the current season's cumulative rainfall against every year on record
at a chosen weather station.

- User searches for a station by name, selects it, then chooses a lookback
  duration (1–60 months)
- The app builds a cumulative rainfall series for the current season and for
  every comparable historical year aligned to the same calendar window
- Results shown as a spaghetti chart (historical years in light blue, median
  as a dashed dark blue line, current year in bold red)
- Headline shows the **percentile rank** and **mm above or below the median**
- Chart x-axis uses calendar-aligned labels (monthly, quarterly, or biannual
  depending on duration) to avoid label crowding
- Export to JPEG

### 🎲 What are the odds?
Rolling-window rainfall frequency analysis — answers the question: *how often
has X mm of rain fallen within Y consecutive days, during a chosen season?*

- User sets a rainfall threshold (mm), window length (days), and season
  start/end dates
- The app scans every season year on record, finds the maximum rolling total
  within the window, and counts how many years met or exceeded the threshold
- Result shown as a bar chart (years exceeding threshold in bright blue,
  years below in grey) with a dashed threshold line
- Headline shows **N of M years exceeded** and **exceedance frequency %**
- Export to CSV and JPEG summary card

### 💧 How much rain stored?
Runs the PERFECT/HowLeaky daily soil water balance model over a fallow period
at a chosen weather station.

- User selects a weather station, a soil type (from `.xml` files in `data/`),
  a fallow start date, and an initial soil water condition (% of PAWC)
- The app fetches full daily climate (rain, pan evap, temperature, radiation)
  from SILO Patched Point and runs the water balance forward to today
- The same fallow window is also run for each of the previous 19 years to
  provide historical context
- Results show: plant available soil water (mm and % PAWC), fallow efficiency,
  cumulative rainfall, and a chart of the current fallow vs historical traces
- Soil profile SVG diagram shows current water content by layer
- Water balance table in expander (rainfall, runoff, soil evap, transpiration,
  drainage, Δ soil water, mass balance check)
- Temperature data (Tmax, Tmin) is fetched and stored in the output for future
  use in crop ET or heat-unit features — no pipeline changes needed to add these
- Export to JPEG

---

## Repository structure

```
howwet2026/
├── Home.py                   # Landing page — Risk Status
├── pages/
│   ├── 1_Season.py           # How's the season?
│   ├── 2_Odds.py             # What are the odds?
│   └── 3_Howwet.py           # How much rain stored?
├── core/
│   ├── __init__.py
│   ├── silo.py               # Unified SILO API layer — shared by all pages
│   ├── waterbalance.py       # PERFECT daily water balance engine
│   ├── soil.py               # Soil profile dataclasses + .PRM reader
│   ├── soil_xml.py           # Soil profile reader (.soil XML / HowLeaky format)
│   ├── soil_excel.py         # Soil profile reader (Excel format)
│   ├── vege.py               # Vegetation reader (.vege XML / HowLeaky format)
│   ├── cover_excel.py        # Cover schedule reader (Excel format)
│   ├── run_simulation.py     # Batch simulation runner
│   ├── read_p51.py           # SILO .P51 file reader
│   └── perfect_io.py         # PERFECT .MET / .CRP file readers
├── data/
│   └── *.xml                 # Soil parameter files (HowLeaky .soil format,
│                             #   renamed .xml for GitHub upload compatibility)
├── .streamlit/
│   └── config.toml           # Theme and server settings
└── requirements.txt          # Python dependencies
```

---

## Shared core: `core/silo.py`

All three pages use a single SILO module. The key public functions are:

```python
from core.silo import search_stations, fetch_station_rainfall, fetch_station_met

# Search by station name — used by all three pages
stations = search_stations("Roma")
# Returns: list of {id, name, label, lat, lon, state}

# Rainfall only — used by Season and Odds
df = fetch_station_rainfall(station_id, "19000101", "20261231")
# Returns: DataFrame with columns: rain, year, month, day, doy

# Full met variables — used by How much rain stored?
df = fetch_station_met(station_id, "20050101", "20261231")
# Returns: DataFrame with: rain, epan, tmax, tmin, tmean, radiation, vp,
#          year, month, day, doy
# Falls back to radiation-based epan estimate if station has no pan evap
```

All three pages use **SILO Patched Point** (station-based, records back to 1889).
DataDrill (gridded lat/lon interpolation) is available in `silo.py` but not
currently used — it may be useful in future for locations without a nearby station.

### SILO CSV format handling

SILO has changed its CSV response format over time. `core/silo.py` handles all
known variants:

| Format | Header starts with | Date column | Notes |
|---|---|---|---|
| New patched point | `station,YYYY-MM-DD` | ISO date string | Current API (2025+) |
| Old patched point | `date` | YYYYMMDD integer | Legacy data |
| DataDrill new | `latitude,longitude` | ISO date string | Current API |
| DataDrill old | `date` | YYYYMMDD integer | Legacy |
| Whitespace-separated | no header | YYYYMMDD integer | Very old files |

---

## Water balance model

The soil water balance in `core/waterbalance.py` is a Python port of the
PERFECT v2.0 model (Littleboy et al. 1992), implementing the same science as
HowLeaky. Daily processes in order:

1. **Runoff** — SCS curve number method, adjusted for surface cover and AMC
2. **Infiltration** — rainfall minus runoff, distributed to layers
3. **Drainage** — cascade: excess above DUL drains to layer below
4. **Soil evaporation** — two-stage Ritchie model (stage I limited by U,
   stage II by CONA × √days)
5. **Transpiration** — limited by potential ET and root water uptake by layer
6. **Deep drainage** — water draining below bottom layer

For the fallow simulation in *How much rain stored?*, the model runs with:
- Green cover = 0 (no living canopy, no transpiration)
- Total cover = 10% stubble residue (reduces CN and soil evap demand)
- Root depth = 0 (no roots, no transpiration)

### Soil input formats supported

| Format | Reader | Notes |
|---|---|---|
| HowLeaky `.soil` XML (renamed `.xml`) | `soil_xml.py` | Multi-value attribute format |
| PERFECT `.PRM` | `soil.py` | Original PERFECT text format |
| Excel soil description | `soil_excel.py` | Row-labelled spreadsheet format |

---

## Running locally

```bash
git clone https://github.com/David-Freebairn/howwet2026.git
cd howwet2026
pip install -r requirements.txt
streamlit run Home.py
```

---

## Deployment

Hosted on [Streamlit Community Cloud](https://share.streamlit.io) (free tier),
connected to the `howwet2026` GitHub repository, `main` branch, main file `Home.py`.

To update the app: edit files in GitHub directly (pencil icon) or push via
GitHub Desktop. Streamlit redeploys automatically within 1–2 minutes.

---

## Dependencies

```
streamlit>=1.32
pandas>=2.0
numpy>=1.24
matplotlib>=3.7
requests>=2.28
openpyxl>=3.1
lxml>=4.9
```

---

## Development history

The three tools were originally developed as separate standalone applications:

| Original app | Language | Entry point | Status |
|---|---|---|---|
| How's the season? | HTML / JavaScript | `season_compare.html` | Ported to Streamlit |
| What are the odds? | Python / Streamlit | `rainfall_app.py` | Refactored |
| How much rain stored? | Python / Streamlit | `app.py` | Refactored |

The unified app consolidates all three into a single Streamlit multipage app
with a shared `core/` library. Key changes from the originals:

- **Common SILO layer** — `core/silo.py` replaces three separate SILO
  implementations with one robust module handling all API response formats
- **Patched Point for all** — Howwet switched from DataDrill (lat/lon gridded)
  to Patched Point (station-based), consistent with the other two tools and
  faster to load
- **Consistent station search** — all three pages use the same search-by-name
  → select → fetch flow
- **Import fixes** — cross-module imports updated to work both standalone and
  as a package (try/except pattern for `soil_xml.py`, `soil_excel.py`,
  `run_simulation.py`)
- **SILO format fix** — parser updated to handle SILO's new patched-point CSV
  format (`station,YYYY-MM-DD,...`) introduced in 2025/2026

---

## References
Water balance
Littleboy M, Silburn DM, Freebairn DM, Woodruff DR, Hammer GL, Leslie JK (1992). Impact of soil erosion on production in dryland cropping systems. Australian Journal of Soil Research* 30, 775–788.
Ghahramani A, Freebairn DM, Sena DR, Cutajar JL, Silburn DM (2020) A pragmatic parameterisation and calibration approach to model hydrology and water quality of agricultural landscapes and catchments. Environmental Modelling and Software 130 (2020) 104733. 
Interface
Freebairn DM, McClymont D. 2025Australian CliMate - a decision support tool for agricultural decision makers. Climate: 3755700  Preprint DOI: https://doi.org/10.20944/preprints202507.1081.v1 
Freebairn DM, Ghahramani A, Robinson JB, McClymont D. 2018. A tool for monitoring soil water using modelling, on-farm data, and mobile technology Environmental Modelling & Software 104 (2018) 55e63 https://www.sciencedirect.com/science/article/pii/S1364815217312422 
Data source
SILO climate data: [longpaddock.qld.gov.au/silo](https://www.longpaddock.qld.gov.au/silo/)
