"""pages/5_YieldRisk.py — YieldRisk gauge analysis, merged into RiskAware."""

import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path so gauge_utils and core.* resolve correctly
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import datetime as dt
from pathlib import Path as P

import numpy as np
import pandas as pd
import streamlit as st

from core.silo import search_stations, ensure_climate_cached, SiloUnavailableError
from core.soil_xml import read_soil_xml
from core.styles import apply_styles, save_station, load_station
from core.dashboard_metrics import (
    compute_fallow_water_and_n_gain,
    compute_in_crop_rain,
    compute_photothermal_index,
    compute_crop_expectation_from_projection,
    compute_yield_projection,
    MetricResult,
)
from gauge_utils import make_gauge_bar_figure, make_detail_figure, make_yield_projection_figure
from core.sample_data import sample_data_available, load_sample_station, load_sample_climate, sample_date_range

try:
    from core.summary_doc import build_summary_docx
    _SUMMARY_DOC_AVAILABLE = True
    _SUMMARY_DOC_IMPORT_ERROR = None
except ModuleNotFoundError as e:
    # python-docx isn't installed. Don't crash the whole app over a single
    # feature — fall through and show a clear, actionable message only when
    # the user actually reaches the "Download summary" button instead.
    build_summary_docx = None
    _SUMMARY_DOC_AVAILABLE = False
    _SUMMARY_DOC_IMPORT_ERROR = str(e)

st.set_page_config(page_title="YieldRisk · RiskAware", layout="wide")
apply_styles()

HERE = _REPO_ROOT
DATA_DIR = HERE / "data"

GAUGE_COLORS = {
    "fallow_water": ("#c9c9c9", "#1f6fb4"),
    "fallow_nitrogen": ("#cfe8c9", "#256b1f"),
    "in_crop_rain": ("#dbeeff", "#0b3d6b"),
    "photothermal": ("#e8d9b0", "#e0a200"),
    "crop_expectation": ("#eafce6", "#1e7a1e"),
}

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _search(query: str):
    return search_stations(query)


def _silo_down_sample_offer():
    """The offer text shown when SILO is unavailable and sample data exists."""
    if not sample_data_available():
        return ""
    try:
        start, end = sample_date_range()
        return (
            f"Our data feed from SILO (https://www.longpaddock.qld.gov.au/silo/) "
            f"is currently unavailable. Would you like to use sample data for "
            f"**Dalby Post Office** ({start.strftime('%Y')}–{end.strftime('%Y')}) in the meantime?"
        )
    except Exception:
        return (
            "Our data feed from SILO (https://www.longpaddock.qld.gov.au/silo/) "
            "is currently unavailable. Would you like to use sample data for "
            "**Dalby Post Office** in the meantime?"
        )


def _activate_sample(site_area=None):
    """Switch the session to using the bundled Dalby sample dataset."""
    sample_station = load_sample_station()
    st.session_state["using_sample"] = True
    st.session_state["confirmed"] = True
    st.session_state["chosen"] = sample_station["label"] + "  [sample data]"
    st.session_state["stations"] = [sample_station]
    st.session_state["climate_ready"] = False
    st.session_state["silo_down"] = False
    st.session_state.pop("climate_df", None)
    st.session_state.pop("climate_key", None)
    if site_area is not None:
        site_area.empty()


def _show_silo_down_fallback(site_area):
    """Render the SILO-down message + sample data offer inside the site area."""
    st.warning(
        "⚠️ **SILO data feed is currently unavailable.**\n\n"
        + (_silo_down_sample_offer() if sample_data_available() else
           "Please try again later.")
    )
    if sample_data_available():
        if st.button("📂 Use Dalby sample data in the meantime", key="search_fallback_btn"):
            _activate_sample(site_area)
            st.rerun()



def load_soil_files():
    files = sorted(DATA_DIR.glob("*.xml")) + sorted(DATA_DIR.glob("*.soil"))
    return files


# ---------------------------------------------------------------------------
# TITLE + SUBHEADING + INFORMATION BUTTON
# ---------------------------------------------------------------------------
st.markdown(
    "<h1 style='color:#1f6fb4; margin-bottom:0;'>Yieldrisk</h1>"
    "<p style='color:#1f6fb4; font-size:1.05rem; margin-top:0.1em; margin-bottom:0.6em;'>"
    "following soil water and nitrogen gains in a fallow and crop prospects through the season"
    "</p>",
    unsafe_allow_html=True,
)

if "show_info" not in st.session_state:
    st.session_state["show_info"] = False

info_col = st.columns([1, 2, 1])[1]
with info_col:
    if st.button("ℹ️ About YieldRisk", key="info_btn", width="stretch"):
        st.session_state["show_info"] = not st.session_state["show_info"]

if st.session_state["show_info"]:
    with st.container(border=True):
        st.markdown("""
**About YieldRisk**

Many agricultural decisions are based on our understanding of expectations.
Such expectations are based on a blend of **current conditions** (knowable) and
**future expectations.** Future expectations relating to weather can be derived from
long term weather data providing a probabilistic picture of the range of possible outcomes.
Simple models support better information relating to the current and future outcomes.

**Yieldrisk** provides a comparative analysis of five aspects of crop outcomes:
- Effectiveness of fallow in storing **soil water** (Howwet? 1984).
- **Nitrogen mineralisation** influenced by surface moisture and temperature (ApSim 1998).
- **In-crop rain** to date and expected rain to harvest.
- **Photothermal quotient** — an index of favourable radiation and temperature.
- Summarised as a **yield index** based on water use efficiency (French and Schultz 1984)
  which is informed by: soil water at planting, nitrogen mineralisation
  and in-crop rain to date.

Set up each paddock with a **soil type, dates** a start of fallow, plant and harvest date
along with a **Water Use Efficiency** and **Threshold water** value for the WUE model.

**Select a weather data site** by typing the name of a nearby BoM weather site (hit Enter).
A list of sites will drop down — select the closest match and hit Select.
It may take up to 1 minute to load 30 years of data but once loaded the analysis
will be faster for further exploration of this site (for 1 day).


**Interpretation**

Each gauge bar shows this season's value against a band built from 30 years of
daily weather data at the same site, soil and dates.

Select the graph button on the right of each bar to see more detail

**Focus on the relativities** of the current season compared to historic years rather
than on the absolute values (mm soil water, kg/ha). The five attributes are presented as:
- **low** (lowest 25% of years)
- **below average** (25–45%)
- **average** (middle 45–55%)
- **above average** (55–75%)
- **high** (top 25% of years)

Weather history provides us with a robust source of probabilities of future events by
applying climatology. **No forecasts** are included in these analyses.

---
Applications
-  Provides an objective assessment of this season in relation to longer term conditions.
-  Use to adjust expectations: fallow rainfall, in-crop rain and yield, fertilizer requirements. 

Assumptions
- It can be difficult to estimate a starting soil water unless the fallow starts after
   a prolonged dry crop finish. An initial value of 5% is suggested – this can be changed
   if you have more information.
-  Soil cover is set at 50%. Water storage  with less cover may be lower than estimated.
-  Starting soil water is assumed to be evenly distributed in the profile

**Acknowledgements**

**Weather data:** Queensland Government's SILO database sourced from the Bureau of Meteorology.

**Soil water estimates:** Applies a well-tested water balance model that considers evaporation,
runoff and drainage losses on a daily basis, as used in Howwet? (Dimes et al., 1996).

**Nitrogen mineralisation:** Conversion of organic nitrogen to plant available forms is
controlled by the moisture content of the surface layers and temperature using a simplified
version of a model in APSim (Probert et al., 1998) and implemented in Howwet? (Freebairn et al., 1994).

**Yield estimates** are based on a version of the Water Use Efficiency (WUE) model
(French and Schultz, 1984) as implemented in Potential Yield Calculator (Tennant and Tennant, 2000).

**Interface:** Interface designs are a blend of several early decision support tools
(Howwet?, Howoften? and Australian CliMate, Freebairn and McClymont 2025) and many other
products developed since the widespread uptake of computers in agriculture.

---

**Disclosure**

These analyses have been developed based on previous experience in designing climate-focused
decision support tools using Anthropic's Claude AI software (Anthropic, 2026).
This software was built to demonstrate new software and App development capabilities.

Comments welcomed — David Freebairn · david.freebairn@gmail.com

---

**References**

Anthropic. (2026). *Claude (Sonnet 4.6)* [Large language model]. https://claude.ai

Dimes, J. P., Freebairn, D. M., & Glanville, S. F. (1996). HOWWET? A tool for predicting
fallow water storage. *Proceedings of the 8th Australian Agronomy Conference*, Toowoomba, pp. 207–210.
https://agronomyaustraliaproceedings.org

French, R. J., & Schultz, J. E. (1984). Water use efficiency of wheat in a Mediterranean-type
environment. I. The relation between yield, water use and climate.
*Australian Journal of Agricultural Research, 35*, 743–764.

Freebairn, D. M., Hamilton, A. H., Cox, P. G., & Holzworth, D. (1994). *HOWWET? Estimating
the storage of water in your soil using rainfall records: A computer program.*
Agricultural Production Systems Research Unit, Queensland DPI–CSIRO.

Freebairn, D. M., & McClymont, D. (2025). Australian CliMate – A decision support tool
for agricultural decision makers. *Climate* (preprint 3755700).
https://doi.org/10.20944/preprints202507.1081.v1

Probert, M. E., Dimes, J. P., Keating, B. A., Dalal, R. C., & Strong, W. M. (1998).
APSIM's water and nitrogen modules and simulation of the dynamics of water and nitrogen
in fallow systems. *Agricultural Systems, 56*(1), 1–28.

Tennant, S., & Tennant, D. (2000). *Potential Yield Calculator (Version 2.31)* [
Computer software]. Agriculture Western Australia.
""")


# ---------------------------------------------------------------------------
# SETUP PANEL — soil, dates, crop, then site (site moved to bottom to avoid
# blocking the rest of the form while the climate data download is pending)
# ---------------------------------------------------------------------------
if "reset_station" not in st.session_state:
    st.session_state["reset_station"] = False
if st.session_state.pop("reset_station", False):
    st.session_state["confirmed"] = False
    st.session_state["chosen"]    = None
    st.session_state["stations"]  = []
    st.session_state.pop("climate_df",  None)
    st.session_state.pop("climate_key", None)
    save_station(None)
    st.session_state["stations"] = []
    st.session_state["chosen"] = None
    st.session_state["last_query"] = ""
    st.session_state["query"] = ""
    st.session_state["climate_ready"] = False
    st.session_state["using_sample"] = False
    st.session_state["silo_down"] = False
    st.session_state.pop("silo_error", None)
    st.session_state.pop("climate_df", None)
    st.session_state.pop("climate_key", None)

with st.container(border=True):
    st.markdown('<p class="section-title">Soil type</p>', unsafe_allow_html=True)
    soil_files = load_soil_files()
    soil_labels = [f.stem.replace("_", " ") for f in soil_files]

    # ── Restore persisted setup values (survives navigating to other pages) ──
    _yr_setup = st.session_state.get("yr_setup", {})
    if soil_labels and "soil_select" not in st.session_state and "soil_idx" in _yr_setup:
        st.session_state["soil_select"] = min(_yr_setup["soil_idx"], len(soil_labels) - 1)
    for _k in ("start_day", "plant_day", "harvest_day"):
        if _k not in st.session_state and _k in _yr_setup:
            st.session_state[_k] = _yr_setup[_k]
    for _k in ("start_month", "plant_month", "harvest_month"):
        if _k not in st.session_state and _k in _yr_setup:
            st.session_state[_k] = _yr_setup[_k]
    for _k in ("wue", "threshold_water"):
        if _k not in st.session_state and _k in _yr_setup:
            st.session_state[_k] = _yr_setup[_k]

    if soil_labels:
        soil_idx = st.selectbox(
            "soil", range(len(soil_labels)), format_func=lambda i: soil_labels[i],
            label_visibility="collapsed", key="soil_select",
        )
        soil_path = soil_files[soil_idx]
    else:
        st.error(f"No .xml/.soil files found in {DATA_DIR}")
        soil_path = None

    st.markdown("**Dates**")
    dates_row, _dates_spacer = st.columns([5, 1])
    with dates_row:
        date_group1, date_group2, date_group3 = st.columns(3)

        with date_group1:
            st.markdown(
                "<p style='font-weight:600; color:#1A5276; margin-bottom:0.2rem;'>Fallow start</p>",
                unsafe_allow_html=True,
            )
            with st.container(border=True):
                g1a, g1b = st.columns([1, 1.6])
                with g1a:
                    start_day = st.number_input(
                        "Start day", 1, 31, 1, label_visibility="collapsed",
                        key="start_day", format="%d",
                    )
                with g1b:
                    with st.container(key="month_start_wrap"):
                        start_month = st.selectbox(
                            "Start month", MONTH_NAMES, index=0,
                            label_visibility="collapsed", key="start_month",
                        )

        with date_group2:
            st.markdown(
                "<p style='font-weight:600; color:#1A5276; margin-bottom:0.2rem;'>Plant</p>",
                unsafe_allow_html=True,
            )
            with st.container(border=True):
                g2a, g2b = st.columns([1, 1.6])
                with g2a:
                    plant_day = st.number_input(
                        "Plant day", 1, 31, 1, label_visibility="collapsed",
                        key="plant_day", format="%d",
                    )
                with g2b:
                    with st.container(key="month_plant_wrap"):
                        plant_month = st.selectbox(
                            "Plant month", MONTH_NAMES, index=2,
                            label_visibility="collapsed", key="plant_month",
                        )

        with date_group3:
            st.markdown(
                "<p style='font-weight:600; color:#1A5276; margin-bottom:0.2rem;'>Harvest</p>",
                unsafe_allow_html=True,
            )
            with st.container(border=True):
                g3a, g3b = st.columns([1, 1.6])
                with g3a:
                    harvest_day = st.number_input(
                        "Harvest day", 1, 31, 1, label_visibility="collapsed",
                        key="harvest_day", format="%d",
                    )
                with g3b:
                    with st.container(key="month_harvest_wrap"):
                        harvest_month = st.selectbox(
                            "Harvest month", MONTH_NAMES, index=10,
                            label_visibility="collapsed", key="harvest_month",
                        )

    st.markdown("**Crop**")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        wue = st.number_input(
            "WUE (kg/ha/mm)", min_value=0, value=20, step=1, key="wue",
        )
    with c3:
        threshold_water = st.number_input(
            "Threshold water (mm)", min_value=0, value=100, step=5, key="threshold_water",
        )

    # ── Persist setup values for when the user navigates away and back ──────
    st.session_state["yr_setup"] = {
        "soil_idx": soil_idx if soil_labels else 0,
        "start_day": start_day, "start_month": start_month,
        "plant_day": plant_day, "plant_month": plant_month,
        "harvest_day": harvest_day, "harvest_month": harvest_month,
        "wue": wue, "threshold_water": threshold_water,
    }

    st.markdown('<p class="section-title">Select site</p>', unsafe_allow_html=True)
    confirmed = st.session_state.get("confirmed", False)
    station_info = None

    # Pre-populate from shared station (set by any other RiskAware page)
    if not confirmed:
        _shared = load_station()
        if _shared:
            st.session_state["confirmed"] = True
            st.session_state["chosen"]    = _shared.get("label", "")
            st.session_state["stations"]  = [_shared]
            confirmed = True

    # Render the entire site-selection area inside a single st.empty()
    # placeholder, rebuilt fresh every run. This guarantees the "confirmed"
    # view (green banner + downloading message) and the "searching" view
    # (text input / radio list / Select button) can never both be visible
    # at once, even transiently — st.empty() fully replaces its previous
    # contents on every render rather than relying on Streamlit's normal
    # element-diffing across the if/else branches, which is what allowed
    # the stale radio list to bleed through after confirmation.
    site_area = st.empty()
    with site_area.container():
        if not confirmed:
            query = st.text_input(
                "station", label_visibility="collapsed",
                placeholder="Search station — e.g. Dalby, Emerald  (press Enter)",
                key="query",
            )
            if query and len(query) >= 3:
                # Check silo_down FIRST, before the last_query guard, so
                # the fallback persists across reruns without re-running the search.
                if st.session_state.get("silo_down") and st.session_state.get("last_query") == query:
                    _show_silo_down_fallback(site_area)
                elif st.session_state.get("last_query") != query:
                    with st.spinner("Searching..."):
                        try:
                            st.session_state["stations"] = _search(query)
                            st.session_state["silo_down"] = False
                            st.session_state.pop("silo_error", None)
                        except Exception as e:
                            st.session_state["stations"] = []
                            st.session_state["silo_error"] = str(e)
                            st.session_state["silo_down"] = True
                    st.session_state["last_query"] = query
                    st.session_state.pop("climate_df", None)
                    st.session_state.pop("climate_key", None)
                    st.session_state["climate_ready"] = False

                    if st.session_state.get("silo_down"):
                        _show_silo_down_fallback(site_area)
                    else:
                        stations = st.session_state.get("stations", [])
                        if stations:
                            labels = [s["label"] for s in stations]
                            if len(labels) == 1:
                                st.session_state["chosen"] = labels[0]
                                st.session_state["confirmed"] = True
                                st.session_state["climate_ready"] = False
                                site_area.empty()
                                st.rerun()
                            else:
                                st.caption(f"**{len(labels)} stations found** — select one:")
                                chosen = st.radio("Station", options=labels, label_visibility="collapsed", key="station_radio")
                                if st.button("Select"):
                                    st.session_state["chosen"] = chosen
                                    st.session_state["confirmed"] = True
                                    st.session_state["stations"] = [s for s in stations if s["label"] == chosen]
                                    st.session_state["climate_ready"] = False
                                    site_area.empty()
                                    st.rerun()
                        elif st.session_state.get("last_query"):
                            st.warning("No stations found. Try a shorter search term.")
                else:
                    # Same query, no error — show existing results
                    stations = st.session_state.get("stations", [])
                    if stations:
                        labels = [s["label"] for s in stations]
                        if len(labels) == 1:
                            st.session_state["chosen"] = labels[0]
                            st.session_state["confirmed"] = True
                            st.session_state["climate_ready"] = False
                            site_area.empty()
                            st.rerun()
                        else:
                            st.caption(f"**{len(labels)} stations found** — select one:")
                            chosen = st.radio("Station", options=labels, label_visibility="collapsed", key="station_radio")
                            if st.button("Select"):
                                st.session_state["chosen"] = chosen
                                st.session_state["confirmed"] = True
                                st.session_state["stations"] = [s for s in stations if s["label"] == chosen]
                                st.session_state["climate_ready"] = False
                                site_area.empty()
                                st.rerun()
                    elif st.session_state.get("last_query"):
                        st.warning("No stations found. Try a shorter search term.")
        else:
            chosen = st.session_state.get("chosen", "")
            stations = st.session_state.get("stations", [])
            c1, c2 = st.columns([5, 1.4])
            with c1:
                if st.session_state.get("using_sample"):
                    st.warning("📂 Using **Dalby sample data** — SILO unavailable. Change site when SILO is restored.")
                else:
                    st.success(f"📍 {chosen}")
            with c2:
                if st.button("Change", width="stretch"):
                    st.session_state["reset_station"] = True
                    site_area.empty()
                    st.rerun()
            station_info = next((s for s in stations if s["label"] == chosen or
                                 s["label"] + "  [sample data]" == chosen), None)
            # For sample path, station_info may not match by label — load directly
            if station_info is None and st.session_state.get("using_sample"):
                station_info = load_sample_station()
            if station_info:
                save_station(station_info)
            if not st.session_state.get("climate_ready", False) and not st.session_state.get("using_sample"):
                st.warning("⏳ Downloading 30 years of daily data may take 30-60 seconds. Please wait!")


# ---------------------------------------------------------------------------
# "How are we going as of [date] ?" — today's date + gauge stack
# ---------------------------------------------------------------------------
fallow_start_md = (MONTH_NAMES.index(start_month) + 1, start_day)
plant_md = (MONTH_NAMES.index(plant_month) + 1, plant_day)
harvest_md = (MONTH_NAMES.index(harvest_month) + 1, harvest_day)

_crosses_year = (plant_md[0], plant_md[1]) > (harvest_md[0], harvest_md[1])
_looking_back = _crosses_year and (
    (dt.date.today().month, dt.date.today().day) < plant_md
)

if _looking_back:
    _harvest_label_year = dt.date.today().year
    _harvest_label_date = f"{harvest_md[1]} {MONTH_NAMES[harvest_md[0]-1]} {_harvest_label_year}"
    st.markdown(
        f"<h1 style='color:#888; margin-top:1em; margin-bottom:0.1em;'>"
        f"📅 Looking back — season harvested {_harvest_label_date}</h1>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Today's date falls before this season's plant date, so the dashboard "
        "is showing the most recently completed crop cycle (harvest date above) "
        "rather than an in-progress one."
    )
    header_cols = st.columns([0.7, 8.3])
    with header_cols[0]:
        if st.button("❓", key="gauge_help_btn"):
            st.session_state["show_gauge_help"] = not st.session_state.get("show_gauge_help", False)
    # today_day/today_month still need to exist for downstream code, but the
    # actual date used for calculations is resolved later from the harvest
    # date — these widgets are hidden while looking back since picking a
    # date here can't represent "last season" (see _looking_back logic above).
    today_day = dt.date.today().day
    today_month = MONTH_NAMES[dt.date.today().month - 1]
else:
    st.markdown(
        "<h1 style='color:#1f6fb4; margin-top:1em; margin-bottom:0.3em;'>How are we going as of</h1>",
        unsafe_allow_html=True,
    )
    header_cols = st.columns([1, 1, 0.7, 7])
    with header_cols[0]:
        today_day = st.number_input("Today's day", 1, 31, dt.date.today().day, label_visibility="collapsed", key="today_day")
    with header_cols[1]:
        today_month = st.selectbox(
            "Today's month", MONTH_NAMES, index=dt.date.today().month - 1,
            label_visibility="collapsed", key="today_month",
        )
    with header_cols[2]:
        if st.button("❓", key="gauge_help_btn"):
            st.session_state["show_gauge_help"] = not st.session_state.get("show_gauge_help", False)

if st.session_state.get("show_gauge_help", False):
    st.info(
        "**Reading the gauges below**\n\n"
        "Each bar shows this season's value as a marker on a gradient built "
        "from comparable historical years (1996 onwards) at this site, soil "
        "and dates. The text next to the value is a plain-language band: "
        "**low** (bottom 25% of years), **below average** (25-45th "
        "percentile), **average** (45-55th percentile), **above average** "
        "(55-75th percentile), or **high** (top 25% of years). "
        "Click **Graph** on any bar to see this season's trajectory against "
        "the historical spread in detail."
    )

if not station_info or not soil_path:
    st.info("Select a site and confirm a soil type above to see the dashboard.")
    st.stop()

month_idx = MONTH_NAMES.index(today_month) + 1
try:
    today = dt.date(dt.date.today().year, month_idx, today_day)
except ValueError:
    st.error("Invalid today's date.")
    st.stop()

# When looking back at a just-completed crossing-year season, anchor "today"
# to that season's harvest date rather than the real current date. This
# makes every downstream calculation (fallow window, in-crop rain, PTQ,
# yield) consistently resolve to the COMPLETED season rather than treating
# the real current date as mid-fallow for a season that hasn't started yet.
# The harvest that just passed falls in the SAME calendar year as the real
# "today" — _looking_back only fires when today's (month, day) is before
# plant_md, which for a crossing crop (e.g. plant Oct, harvest Jan) means
# today is somewhere in Jan-Sep, i.e. after this calendar year's harvest.
if _looking_back:
    harvest_year = dt.date.today().year
    try:
        today = dt.date(harvest_year, harvest_md[0], harvest_md[1])
    except ValueError:
        today = dt.date(harvest_year, harvest_md[0], 28)

# ── Fetch climate + soil (cached) ───────────────────────────────────────────
_was_ready_before_fetch = st.session_state.get("climate_ready", False)

# If using sample data, load it directly — no spinner needed
if st.session_state.get("using_sample"):
    try:
        climate_df = load_sample_climate()
        st.session_state["climate_ready"] = True
    except Exception as e:
        st.error(f"Could not load sample data: {e}")
        st.stop()
else:
    with st.spinner("Fetching SILO climate data (first run only — cached after)..."):
        try:
            climate_df = ensure_climate_cached(
                station_id=station_info["id"],
                lat=station_info.get("lat"), lon=station_info.get("lon"),
                session_state=st.session_state,
            )
            st.session_state["climate_ready"] = True
            st.session_state["silo_down"] = False
        except Exception as e:
            # SILO fetch failed — offer the sample data fallback
            st.session_state["silo_down"] = True
            st.session_state["silo_error"] = str(e)
            st.warning(
                f"⚠️ Could not fetch climate data from SILO: {e}\n\n"
                + (_silo_down_sample_offer() if sample_data_available() else
                   "SILO data is currently unavailable. Please try again later.")
            )
            if sample_data_available():
                if st.button("📂 Use Dalby sample data in the meantime", key="fetch_fallback_btn"):
                    _activate_sample(site_area=None)
                    st.rerun()
            st.stop()

# The "downloading" message above (inside the setup box) was already drawn
# earlier in this same script run, before climate_ready flipped to True —
# Streamlit doesn't retroactively remove elements within a run. Force one
# more rerun right after the FIRST successful fetch so the very next pass
# renders with the message correctly suppressed, without needing the user
# to interact with anything else first.
if not _was_ready_before_fetch:
    st.rerun()

profile = read_soil_xml(soil_path)

# ── Compute the five metrics ────────────────────────────────────────────────
water_res, nitrogen_res = compute_fallow_water_and_n_gain(
    climate_df, profile, fallow_start_md, plant_md, today, sw_init_frac=0.05,
)
rain_res = compute_in_crop_rain(climate_df, plant_md, today)
ptq_res = compute_photothermal_index(climate_df, plant_md, today)

soil_water_at_planting = (
    water_res.current_value if water_res.current_value is not None else 0.0
)
yield_projection = compute_yield_projection(
    climate_df, plant_md, harvest_md, today,
    soil_water_at_planting_mm=soil_water_at_planting,
    threshold_water_mm=threshold_water, wue_kg_ha_per_mm=wue,
) if not rain_res.not_yet_applicable else None
yield_res = (
    compute_crop_expectation_from_projection(yield_projection)
    if yield_projection is not None
    else MetricResult("Crop yield outlook", "kg/ha", None, None, 0, {}, today.year, None, not_yet_applicable=True)
)

st.write("")

GAUGES = [
    (water_res, GAUGE_COLORS["fallow_water"]),
    (nitrogen_res, GAUGE_COLORS["fallow_nitrogen"]),
    (rain_res, GAUGE_COLORS["in_crop_rain"]),
    (ptq_res, GAUGE_COLORS["photothermal"]),
    (yield_res, GAUGE_COLORS["crop_expectation"]),
]

if "graph_open" not in st.session_state:
    st.session_state["graph_open"] = {}

YIELD_GAUGE_INDEX = 4

gauge_figures_for_summary = []
yield_detail_fig_for_summary = None

# ── Section labels: Fallow | Crop season ──────────────────────────────────
SECTION_LABELS = {
    0: "🌱 Fallow",
    2: "🌾 Crop season",
}

for i, (result, (color_low, color_high)) in enumerate(GAUGES):
    if i in SECTION_LABELS:
        if i > 0:
            st.write("")   # extra gap between sections
        st.markdown(
            f"<p style='font-size:0.8rem; font-weight:700; color:#1A5276; "
            f"letter-spacing:0.08em; text-transform:uppercase; "
            f"margin-bottom:0.15rem; margin-top:0.1rem;'>"
            f"{SECTION_LABELS[i]}</p>",
            unsafe_allow_html=True,
        )

    bar_col, btn_col = st.columns([10, 1])
    with bar_col:
        fig = make_gauge_bar_figure(result, color_low, color_high)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=f"gauge_{i}")
        gauge_figures_for_summary.append(fig)
    with btn_col:
        st.write("")
        if st.button("Graph", key=f"graph_btn_{i}"):
            st.session_state["graph_open"][i] = not st.session_state["graph_open"].get(i, False)

    if st.session_state["graph_open"].get(i, False):
        if i == YIELD_GAUGE_INDEX:
            detail_fig = make_yield_projection_figure(yield_projection)
        else:
            detail_fig = make_detail_figure(result)
        st.plotly_chart(detail_fig, width="stretch", config={"displayModeBar": False}, key=f"detail_{i}")

# Context line — anchors the gauges to their inputs without scrolling
# back up to the setup panel
month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
def _fmt(md): return f"{md[1]} {month_names[md[0]-1]}"
sample_flag = "  ·  ⚠️ Sample data (Dalby) — SILO unavailable" if st.session_state.get("using_sample") else ""
st.caption(
    f"📍 {station_info.get('name', station_info.get('label',''))}  ·  "
    f"{profile.name}  ·  "
    f"Fallow {_fmt(fallow_start_md)} → Plant {_fmt(plant_md)} → Harvest {_fmt(harvest_md)}  ·  "
    f"WUE {wue} kg/ha/mm  ·  Threshold {threshold_water} mm"
    + sample_flag
)

# The yield detail chart is always built fresh for the summary document,
# independent of whether the user has clicked "Graph" to view it on screen
# — the summary should always include it when the metric is applicable,
# per the request to always embed "the five bars plus the detailed yield".
if yield_projection is not None:
    yield_detail_fig_for_summary = make_yield_projection_figure(yield_projection)

st.write("")
dl_col = st.columns(3)[1]
with dl_col:
    if not _SUMMARY_DOC_AVAILABLE:
        st.error(
            "**Download summary** needs the `python-docx` package, which isn't "
            "installed yet. Run `pip install -r requirements.txt` in this "
            "project's folder, then restart the app.\n\n"
            f"(Import error: {_SUMMARY_DOC_IMPORT_ERROR})"
        )
    else:
        try:
            summary_bytes, image_warnings = build_summary_docx(
                today=today,
                station_name=station_info.get("name", station_info.get("label", "")),
                soil_name=profile.name,
                fallow_start_md=fallow_start_md, plant_md=plant_md, harvest_md=harvest_md,
                wue=wue, threshold_water=threshold_water,
                gauge_results=[result for result, _ in GAUGES],
                gauge_figures=gauge_figures_for_summary,
                yield_figure=yield_detail_fig_for_summary,
            )
            st.download_button(
                "📥 Download summary",
                data=summary_bytes,
                file_name=f"season_summary_{station_info.get('id', 'site')}_{today.isoformat()}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                width="stretch",
            )
            if image_warnings:
                st.warning(
                    "The summary downloaded, but one or more charts couldn't be "
                    "included as images (the rest of the document is still "
                    "complete):\n\n"
                    + "\n".join(f"- {w}" for w in image_warnings)
                    + "\n\nThis usually means the `kaleido` chart-export package "
                    "needs reinstalling — try `pip install -r requirements.txt` "
                    "and restart the app."
                )
        except Exception as e:
            st.error(f"Could not build summary document: {e}")

st.caption(
    f"Soil: {profile.name} (PAWC {profile.pawc_total:.0f}mm)  ·  "
    f"Station: {station_info.get('name', '')}  ·  "
    "Fallow water/nitrogen gain covers fallow start → plant date only. "
    "In-crop rain, photothermal quotient and yield outlook only apply from "
    "the plant date onwards. Historical comparisons use 1996 onwards. "
    "Percentiles rank this season's value vs. comparable historical years, "
    "using the same calculation engine for every year."
)
