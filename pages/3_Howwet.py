"""
pages/3_Howwet.py — Soil Water Monitor
========================================
PERFECT/HowLeaky water balance model for any Australian location.
Ported from app.py — all SILO fetching now via core.silo.

Climate data fetched:
  rain, epan, tmax, tmin, tmean, radiation
  (temperatures not currently used by the fallow water balance but
   fetched and stored so adding crop ET or heat-unit features later
   requires no change to the data pipeline)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.dates as mdates
import plotly.graph_objects as go
import matplotlib.dates as mdates
import io
from datetime import date, timedelta

from core.silo import search_stations, ensure_climate_cached, slice_climate
from core.soil_xml import read_soil_xml
from core.soil import read_prm, init_sw
from core.waterbalance import daily_water_balance
from core.styles import apply_styles, save_station, load_station

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="How much rain stored?",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ─────────────────────────────────────────────────────────────────
HERE          = Path(__file__).resolve().parent.parent
HISTORY_YEARS = 20
MAX_MONTHS_RECENT = 24
FIXED_GREEN   = 0.0
FIXED_TOTAL   = 0.1
C_HIST        = "#A8C4E0"
C_MEAN        = "#7B5EA7"
C_RECENT      = "#1A2F6B"
C_BG          = "#F4F6F9"

apply_styles()


# ── Cached helpers ────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def _search(query: str):
    return search_stations(query)


def load_soil_files():
    # Check both data/ subfolder and repo root — handles local and Streamlit Cloud
    for candidate in [HERE / "data", HERE / "Data", HERE]:
        if candidate.exists():
            files = (sorted(candidate.glob("*.soil")) +
                     sorted(candidate.glob("*.xml")) +
                     sorted(candidate.glob("*.PRM")))
            if files:
                return files
    return []


def load_profile(soil_path: Path):
    if soil_path.suffix.lower() in (".soil", ".xml"):
        return read_soil_xml(soil_path)
    return read_prm(soil_path)


# ── Water balance ─────────────────────────────────────────────────────────────

def run_water_balance(met_df: pd.DataFrame, profile, init_fraction: float = 0.5):
    layers = profile.layers
    sw     = init_sw(profile, init_fraction)
    sw0    = float(sw.sum())
    # sumes1/sumes2: stage-I and stage-II evap accumulators (mm)
    # dsr: days-since-rain equivalent for stage-II (replaces t_since_wet)
    sumes1 = sumes2 = dsr = 0.0
    records = []

    for dt, row in met_df.iterrows():
        rain = float(row.get("rain", 0) or 0)
        epan = float(row.get("epan", 0) or 0)
        if np.isnan(rain): rain = 0.0
        if np.isnan(epan): epan = 0.0

        sw_before = float(sw.sum())
        out = daily_water_balance(
            sw=sw, layers=layers, soil=profile,
            rain=rain, epan=epan,
            green_cover=FIXED_GREEN,
            total_cover=FIXED_TOTAL,
            root_depth_mm=0.0,
            crop_factor=1.0,
            sumes1=sumes1, sumes2=sumes2, t_since_wet=dsr,
        )
        sw     = out["sw"]
        sumes1 = out["sumes1"]
        sumes2 = out["sumes2"]
        dsr    = out["t_since_wet"]   # engine returns dsr in this slot

        sw_total = float(sw.sum())
        # PASW: layer-by-layer, clamped at zero
        pasw = sum(
            max(0.0, float(sw[i]) - layers[i].ll_mm)
            for i in range(len(layers))
        )
        # Back-calculate actual soil evap from mass balance — works regardless
        # of which engine version is in core/ (robust to old and new engine)
        actual_es = max(0.0,
            sw_before + rain - out["runoff"] - out["drainage"] - out["transp"] - sw_total
        )

        records.append({
            "rain"      : rain,
            "epan"      : epan,
            "tmax"      : float(row.get("tmax") or np.nan),
            "tmin"      : float(row.get("tmin") or np.nan),
            "radiation" : float(row.get("radiation") or 0),
            "runoff"    : out["runoff"],
            "soil_evap" : actual_es,
            "transp"    : out["transp"],
            "drainage"  : out["drainage"],
            "et"        : actual_es + out["transp"],
            "sw_total"  : sw_total,
            "pasw"      : round(pasw, 2),
            "sw_layers" : sw.copy().tolist(),
        })

    df  = pd.DataFrame(records, index=met_df.index)
    swf = float(df["sw_total"].iloc[-1])
    return df, sw0, swf


def calc_fallow_efficiency(df: pd.DataFrame, profile) -> float:
    rain_total = df["rain"].sum()
    if rain_total <= 0:
        return 0.0
    return max(0.0, (df["pasw"].iloc[-1] - df["pasw"].iloc[0]) / rain_total * 100.0)


# ── Chart ─────────────────────────────────────────────────────────────────────

def make_pasw_chart(recent_df, hist_dfs, profile, station_name, start_date, end_date):
    plt.rcParams.update({
        "font.family": "sans-serif",
        "axes.facecolor": "#FAFBFC",
        "figure.facecolor": C_BG,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.8,
    })
    fig, ax = plt.subplots(figsize=(12, 5))
    fig.patch.set_facecolor(C_BG)

    pawc     = profile.pawc_total
    n_recent = len(recent_df)
    x_vals   = recent_df.index

    hist_aligned = []
    for hdf in hist_dfs:
        seg = hdf["pasw"].values[:n_recent]
        if not len(seg):
            continue
        n = min(len(seg), n_recent)
        hist_aligned.append(seg[:n])
        ax.plot(x_vals[:n], seg[:n], color=C_HIST, lw=0.8, alpha=0.55, zorder=1)

    if hist_aligned:
        min_len   = min(len(s) for s in hist_aligned)
        mean_pasw = np.mean([s[:min_len] for s in hist_aligned], axis=0)
        ax.plot(x_vals[:min_len], mean_pasw, color=C_MEAN, lw=2.0, ls="--", zorder=3,
                label=f"Historical mean ({len(hist_aligned)} yrs)")

    ax.plot(recent_df.index, recent_df["pasw"],
            color=C_RECENT, lw=2.8, zorder=4,
            label=f"Recent  ({start_date.strftime('%d %b %Y')} – "
                  f"{end_date.strftime('%d %b %Y')})")
    ax.axhline(pawc, color="#CC4422", lw=0.9, ls="--", alpha=0.6,
               label=f"PAWC  {pawc:.0f} mm", zorder=2)

    ax.set_ylabel("Plant available soil water (mm)", fontsize=10, color="#333")
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=6, integer=True))
    ax.tick_params(labelsize=9)
    ax.grid(axis="y", color="#E0E4EC", lw=0.6, zorder=0)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b\n%Y"))
    ax.tick_params(axis="x", labelsize=8.5)
    ax.legend(loc="upper left", fontsize=9, frameon=True, framealpha=0.9, edgecolor="#CCCCCC")
    plt.tight_layout(pad=1.5)
    return fig


def soil_profile_svg(profile, final_pasw, sw_layers=None) -> str:
    layers       = profile.layers
    BAR_W, BAR_H = 81, 200
    elements = []
    y = 0
    for i, lyr in enumerate(layers):
        h      = max(4, round(lyr.thickness / 2000.0 * BAR_H))
        sat_mm = lyr.sat_mm or lyr.dul_mm * 1.15
        scale  = BAR_W / sat_mm
        x_ll   = round(lyr.ll_mm  * scale)
        x_dul  = round(lyr.dul_mm * scale)
        x_sat  = BAR_W
        sw_this = (
            float(sw_layers[i]) if sw_layers and i < len(sw_layers)
            else lyr.ll_mm + max(0.0, min(
                final_pasw * lyr.pawc / profile.pawc_total if profile.pawc_total > 0 else 0,
                lyr.pawc))
        )
        x_sw = max(x_ll, min(round(sw_this * scale), x_dul))
        if y > 0:
            elements.append(f'<line x1="1" y1="{y}" x2="{BAR_W-1}" y2="{y}" stroke="white" stroke-width="0.6" opacity="0.45"/>')
        elements.append(f'<rect x="1" y="{y}" width="{x_ll-1}" height="{h}" fill="#9A9488"/>')
        elements.append(f'<rect x="{x_sw}" y="{y}" width="{x_dul-x_sw}" height="{h}" fill="#C8C2B8"/>')
        elements.append(f'<rect x="{x_ll}" y="{y}" width="{x_sw-x_ll}" height="{h}" fill="#4A96D4" opacity="0.85"/>')
        elements.append(f'<rect x="{x_dul}" y="{y}" width="{x_sat-x_dul}" height="{h}" fill="#B0A89A"/>')
        elements.append(f'<line x1="{x_ll}" y1="{y}" x2="{x_ll}" y2="{y+h}" stroke="white" stroke-width="1.6"/>')
        elements.append(f'<line x1="{x_dul}" y1="{y}" x2="{x_dul}" y2="{y+h}" stroke="white" stroke-width="0.9" stroke-dasharray="3,2" opacity="0.7"/>')
        y += h
    body = "\n".join(elements)
    return (
        f'<svg width="{BAR_W}" height="{y+18}" viewBox="0 0 {BAR_W} {y+18}" '
        'xmlns="http://www.w3.org/2000/svg" style="display:block">'
        f'<rect x="1" y="0" width="{BAR_W-2}" height="{y}" rx="3" fill="#9A9488"/>'
        f'{body}'
        f'<rect x="1" y="0" width="{BAR_W-2}" height="{y}" rx="3" fill="none" stroke="#7A7468" stroke-width="1"/>'
        f'<text x="{BAR_W//2}" y="{y+13}" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#555">PAWC {profile.pawc_total:.0f}mm</text>'
        "</svg>"
    )


# ── UI ────────────────────────────────────────────────────────────────────────

st.title("💧 How much rain stored?")
st.caption("*Accumulated **plant available** soil water over a fallow*")

# ── Pre-populate search from shared station ───────────────────────────────────
_shared = load_station()
if _shared and not st.session_state.get("hw_query"):
    st.session_state["hw_query"]      = _shared.get("name", "")
    st.session_state["hw_saved_station"] = _shared
    st.session_state["hw_stations"]   = [_shared]
    st.session_state["hw_last_query"] = _shared.get("name", "")
    st.session_state["hw_confirmed"]  = True
    st.session_state["hw_chosen"]     = _shared.get("label", "")

soil_files  = load_soil_files()
soil_labels = [f.stem for f in soil_files]
today       = date.today()
yesterday   = today - timedelta(days=1)
min_start   = today - timedelta(days=MAX_MONTHS_RECENT * 30)

# ── Handle Change button reset (must happen before widgets render) ────────────
if st.session_state.pop("hw_reset", False):
    st.session_state["hw_confirmed"]  = False
    st.session_state["hw_stations"]   = []
    st.session_state["hw_chosen"]     = None
    st.session_state["hw_last_query"] = ""
    st.session_state["hw_query"]      = ""
    st.session_state.pop("climate_df",  None)
    st.session_state.pop("climate_key", None)

with st.container(border=True):
    st.markdown('<p class="section-title">Select site</p>', unsafe_allow_html=True)

    confirmed    = st.session_state.get("hw_confirmed", False)
    station_info = None

    if not confirmed:
        query = st.text_input(
            "station", label_visibility="collapsed",
            placeholder="Search station — e.g. Dalby, Emerald  (press Enter)",
            key="hw_query",
        )
        if query and len(query) >= 3:
            if st.session_state.get("hw_last_query") != query:
                with st.spinner("Searching..."):
                    try:
                        st.session_state["hw_stations"] = _search(query)
                    except Exception as e:
                        st.error(f"Search failed: {e}")
                        st.session_state["hw_stations"] = []
                st.session_state["hw_last_query"] = query
                st.session_state["hw_sel_idx"] = 0
                st.session_state.pop("climate_df", None)
                st.session_state.pop("climate_key", None)
                st.session_state.pop("hw_result",  None)

            stations = st.session_state.get("hw_stations", [])
            if stations:
                labels = [s["label"] for s in stations]
                chosen = st.session_state.get("hw_chosen") or labels[0]
                if chosen not in labels:
                    chosen = labels[0]
                if len(labels) == 1:
                    st.session_state["hw_chosen"]    = labels[0]
                    st.session_state["hw_confirmed"] = True
                    st.session_state["hw_stations"]  = [stations[0]]
                    st.rerun()
                else:
                    st.caption(f"**{len(labels)} stations found** — select one:")
                    def on_station_pick_hw():
                        chosen_now = st.session_state["hw_radio"]
                        st.session_state["hw_chosen"]    = chosen_now
                        st.session_state["hw_confirmed"] = True
                        matching = [s for s in st.session_state.get("hw_stations", [])
                                    if s["label"] == chosen_now]
                        if matching:
                            st.session_state["hw_stations"] = [matching[0]]
                    rc1, rc2 = st.columns([5, 1])
                    with rc1:
                        chosen = st.radio(
                            "Station", options=labels,
                            index=labels.index(chosen) if chosen in labels else 0,
                            key="hw_radio", label_visibility="collapsed",
                            on_change=on_station_pick_hw,
                        )
                        st.session_state["hw_chosen"] = chosen
                    with rc2:
                        st.markdown('<div style="margin-top:4px">', unsafe_allow_html=True)
                        if st.button("Select", key="hw_select", width="stretch"):
                            st.session_state["hw_chosen"]    = chosen
                            st.session_state["hw_confirmed"] = True
                            st.session_state["hw_stations"]  = [next(s for s in stations if s["label"] == chosen)]
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)
            elif st.session_state.get("hw_last_query"):
                st.warning("No stations found. Try a shorter search term.")

    else:
        chosen   = st.session_state.get("hw_chosen", "")
        stations = st.session_state.get("hw_stations", [])
        c1, c2, c3, c4 = st.columns([3.5, 1.3, 1.3, 1.4])
        with c1:
            st.success(f"📍 {chosen}")
        with c2:
            st.markdown('<div style="margin-top:8px; font-size:0.9rem; color:#555;">Start record</div>',
                        unsafe_allow_html=True)
        with c3:
            hw_start_rec = st.number_input(
                "hw_start_rec", label_visibility="collapsed",
                min_value=1889, max_value=date.today().year,
                value=st.session_state.get("hw_start_rec", 1900),
                step=1, key="hw_start_rec_input",
            )
            st.session_state["hw_start_rec"] = hw_start_rec
        with c4:
            st.markdown('<div style="margin-top:4px">', unsafe_allow_html=True)
            if st.button("Change", key="hw_change", width="stretch"):
                st.session_state["hw_reset"] = True
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        if stations:
            station_info = next((s for s in stations if s["label"] == chosen), None)
            if station_info:
                st.session_state["hw_saved_station"] = station_info
                save_station(station_info)

st.markdown('<p class="section-title">Set up the soil</p>', unsafe_allow_html=True)

s1a, s1b = st.columns([1.2, 4])
with s1a:
    st.markdown('<span style="font-size:1.1rem">Soil type</span>', unsafe_allow_html=True)
with s1b:
    if soil_labels:
        soil_idx = st.selectbox("soil", range(len(soil_labels)),
                                format_func=lambda i: soil_labels[i],
                                label_visibility="collapsed", key="hw_soil")
        soil_path = soil_files[soil_idx]
    else:
        st.error("No .soil files found in data/ folder")
        soil_path = None

s2a, s2b, s2c, s2d = st.columns([1.2, 1.8, 1.2, 1.8])
with s2a:
    st.markdown('<span style="font-size:1.1rem">Start date</span>', unsafe_allow_html=True)
with s2b:
    start_date = st.date_input("start", label_visibility="collapsed",
                               value=today - timedelta(days=180),
                               min_value=min_start, max_value=yesterday,
                               format="DD/MM/YYYY", key="hw_start")
with s2c:
    st.markdown('<span style="font-size:1.1rem">End date</span>', unsafe_allow_html=True)
with s2d:
    end_date_input = st.date_input("end", label_visibility="collapsed",
                                   value=today - timedelta(days=3),
                                   min_value=min_start, max_value=today,
                                   format="DD/MM/YYYY", key="hw_end")

s3a, s3b, s3c = st.columns([1.2, 0.8, 2])
with s3a:
    st.markdown('<span style="font-size:1.1rem">Start soil water</span>', unsafe_allow_html=True)
with s3b:
    init_pct = st.number_input("init_pct", label_visibility="collapsed",
                               min_value=0, max_value=100, value=5,
                               step=5, key="hw_init")
with s3c:
    st.markdown('<span style="font-size:1.1rem">% PAWC</span>', unsafe_allow_html=True)

with st.expander("ℹ️ About this analysis"):
    st.markdown("""
**How much rain stored?** estimates the effectiveness of fallow rain after accounting
   for evaporation, runoff and drainage losses on a daily basis. 
   Select a **soil type** that best describes your paddock. A list of 12 soil types are
    available (shallow, average and deep phases of four texture groups). 
    Results are presented as:
-  Plant available soil water **(mm)** and **% of PAWC** (how full is the bucket?)
-  **Fallow efficiency (%)**, a measure of how much rain was captured as plant 
        available water (PAW).
-  A graph tracking soil water during the fallow, the average for this soil
        (dotted line) and previous years (blue lines). 
-  Hover mouse over graph for more detail.
-  An image showing where water is stored throughout the soil profile.
 
**Applications**
-  A robust estimate of each paddocks water status and an indication of how the
      current season compared with other years.
-  The amount of soil water at planting may influence crop choice and inputs levels.
-  In some environments, soil water available at planting can be a major component
    of a crops water use and critical towards flowering. Soil water provides an
     important buffer for crop performance.
-  A better appreciation of how fallows vary from year to year.
""")

# ── Auto-run whenever inputs are ready ────────────────────────────────────────
_hw_start_rec = st.session_state.get("hw_start_rec", 1900)
_input_key = (f"{station_info['id'] if station_info else 'none'}_"
              f"{soil_idx if soil_path else 'none'}_{start_date}_{end_date_input}_{init_pct}_{_hw_start_rec}")
_has_result = st.session_state.get("hw_result") is not None

if station_info and soil_path and (
    _input_key != st.session_state.get("hw_input_key") or not _has_result
):
    st.session_state["hw_input_key"] = _input_key

    sid      = station_info["id"]
    stn_name = station_info["name"]
    _lat     = station_info.get("lat")
    _lon     = station_info.get("lon")
    safe_end   = end_date_input
    hist_end   = start_date - timedelta(days=1)
    hist_start = date(hist_end.year - HISTORY_YEARS, hist_end.month, hist_end.day)

    try:
        profile = load_profile(soil_path)
        pawc    = profile.pawc_total
    except Exception as e:
        st.error(f"Could not load soil: {e}")
        st.stop()

    status = st.empty()
    status.markdown('<p class="status-msg">Loading climate data… (first load may take 30–60 seconds)</p>',
                    unsafe_allow_html=True)
    try:
        full_met   = ensure_climate_cached(sid, _lat, _lon,
                                           session_state=st.session_state)
        recent_met = slice_climate(full_met, start=start_date, end=safe_end)
        if recent_met.empty:
            raise RuntimeError(f"No data between {start_date} and {safe_end}.")
        end_date = recent_met.index.max().date()
        hist_met = slice_climate(full_met, start=hist_start, end=hist_end)
    except Exception as e:
        status.empty()
        st.error(f"Climate data load failed: {e}")
        st.stop()

    epan_sum = recent_met["epan"].fillna(0).sum() if "epan" in recent_met.columns else 0
    if epan_sum < 1.0:
        st.warning("⚠️ Pan evaporation missing from SILO — soil evaporation may be underestimated.")

    status.markdown('<p class="status-msg">Running water balance...</p>', unsafe_allow_html=True)
    try:
        recent_df, _, _ = run_water_balance(recent_met, profile, init_pct / 100.0)
    except Exception as e:
        st.error(f"Simulation failed: {e}")
        st.stop()

    n_days, hist_dfs = len(recent_df), []
    for yr in sorted(hist_met.index.year.unique()):
        try:
            yr_start = pd.Timestamp(yr, start_date.month, start_date.day)
        except ValueError:
            continue
        yr_met = hist_met.loc[yr_start: yr_start + pd.Timedelta(days=n_days - 1)]
        if len(yr_met) < 30:
            continue
        try:
            hdf, _, _ = run_water_balance(yr_met, profile, init_pct / 100.0)
            hist_dfs.append(hdf)
        except Exception:
            continue

    status.empty()
    st.session_state["hw_result"] = {
        "recent_df": recent_df, "hist_dfs": hist_dfs,
        "recent_met": recent_met, "profile": profile,
        "stn_name": stn_name, "start_date": start_date,
        "end_date": end_date, "init_pct": init_pct,
    }

# ── Output ────────────────────────────────────────────────────────────────────
if st.session_state.get("hw_result"):
    r          = st.session_state["hw_result"]
    recent_df  = r["recent_df"]
    hist_dfs   = r["hist_dfs"]
    recent_met = r["recent_met"]
    profile    = r["profile"]
    stn_name   = r["stn_name"]
    start_date = r["start_date"]
    end_date   = r["end_date"]
    init_pct   = r["init_pct"]
    pawc       = profile.pawc_total

    final_pasw  = float(recent_df["pasw"].iloc[-1])
    pawc_pct    = final_pasw / pawc * 100 if pawc > 0 else 0.0
    fe          = calc_fallow_efficiency(recent_df, profile)
    cum_rain    = float(recent_df["rain"].sum())
    end_label   = end_date.strftime("%d %b %Y")
    start_label = start_date.strftime("%d %b %Y")

    profile_svg = soil_profile_svg(profile, final_pasw, recent_df["sw_layers"].iloc[-1])

    # ── Soil water header (matches Season/Odds style) ─────────────────────────
    st.markdown(f"""
<div style="background:#f0f6ff; border-radius:10px; padding:18px 22px 14px 22px; margin-bottom:4px;">
  <div style="font-size:1.45rem; font-weight:700; color:#1a3a5c; margin-bottom:2px;">
    Soil water estimation
  </div>
  <div style="font-size:0.95rem; color:#444; margin-bottom:10px;">
    <b>{stn_name}</b>&nbsp;&nbsp;
    <span style="color:#888;">{profile.name}</span>&nbsp;&nbsp;·&nbsp;&nbsp;
    <span style="color:#888;">{start_label} to {end_label}</span>
  </div>
  <div style="display:flex; align-items:baseline; gap:0; flex-wrap:wrap;">
    <span style="font-size:1.02rem; color:#444; font-weight:800;">Plant available soil water&nbsp;</span>
    <span style="font-size:1.5rem; color:#1a3a5c; font-weight:800;">{final_pasw:.0f} mm</span>
    <span style="font-size:1.02rem; color:#2979c4; font-weight:800;">&nbsp;({pawc_pct:.0f}% of PAWC)</span>
    <span style="flex:1; min-width:20px;"></span>
    <span style="font-size:1.02rem; color:#888; font-weight:600;">Fallow efficiency&nbsp;</span>
    <span style="font-size:1.02rem; color:#e06b00; font-weight:800;">{fe:.0f}%</span>
    <span style="font-size:1.02rem; color:#888; font-weight:600;">&nbsp;from {cum_rain:.0f} mm rainfall</span>
  </div>
</div>
""", unsafe_allow_html=True)

    col_chart, col_prof = st.columns([6, 1])
    with col_prof:
        st.markdown(profile_svg, unsafe_allow_html=True)
    with col_chart:
        fig = make_pasw_chart(recent_df, hist_dfs, profile, stn_name, start_date, end_date)

        # ── Interactive Plotly chart ──────────────────────────────────────
        pawc     = profile.pawc_total
        n_recent = len(recent_df)
        x_vals   = recent_df.index

        fig_plotly = go.Figure()

        # Historical years
        hist_aligned = []
        for hdf in hist_dfs:
            seg = hdf["pasw"].values[:n_recent]
            if not len(seg):
                continue
            n = min(len(seg), n_recent)
            hist_aligned.append(seg[:n])
            fig_plotly.add_trace(go.Scatter(
                x=x_vals[:n], y=seg[:n],
                mode="lines",
                line=dict(color=C_HIST, width=0.8),
                opacity=0.55,
                hovertemplate="%{x|%d/%m/%y}  %{y:.0f} mm<extra></extra>",
                legendgroup="history",
                showlegend=False,
            ))

        # Historical mean
        if hist_aligned:
            min_len   = min(len(s) for s in hist_aligned)
            mean_pasw = np.mean([s[:min_len] for s in hist_aligned], axis=0)
            fig_plotly.add_trace(go.Scatter(
                x=x_vals[:min_len], y=mean_pasw,
                mode="lines",
                line=dict(color=C_MEAN, width=2, dash="dash"),
                name=f"Historical mean ({len(hist_aligned)} yrs)",
                hovertemplate="%{x|%d/%m/%y}  %{y:.0f} mm<extra></extra>",
            ))

        # Recent fallow
        fig_plotly.add_trace(go.Scatter(
            x=recent_df.index, y=recent_df["pasw"],
            mode="lines",
            line=dict(color=C_RECENT, width=2.8),
            name=f"Recent  ({start_date.strftime('%d %b %Y')} – {end_date.strftime('%d %b %Y')})",
            hovertemplate="%{x|%d/%m/%y}  %{y:.0f} mm<extra></extra>",
        ))

        # PAWC line
        fig_plotly.add_hline(
            y=pawc, line_dash="dash", line_color="#CC4422",
            line_width=0.9, opacity=0.6,
            annotation_text=f"  PAWC {pawc:.0f} mm",
            annotation_position="right",
            annotation_font=dict(color="#CC4422", size=10),
        )

        fig_plotly.update_layout(
            height=360,
            plot_bgcolor="#FAFBFC", paper_bgcolor="#FAFBFC",
            margin=dict(l=60, r=20, t=20, b=50),
            hovermode="closest",
            legend=dict(
                orientation="h", x=0, y=1.02, xanchor="left", yanchor="bottom",
                font=dict(size=10), bgcolor="rgba(0,0,0,0)",
            ),
            xaxis=dict(
                tickfont=dict(size=9, color="#333"),
                gridcolor="#E0E4EC", showgrid=False,
                fixedrange=True,
            ),
            yaxis=dict(
                title="Plant available soil water (mm)",
                title_font=dict(size=10, color="#333"),
                tickfont=dict(size=9, color="#333"),
                gridcolor="#E0E4EC", showgrid=True,
                rangemode="tozero", fixedrange=True,
            ),
        )

        st.plotly_chart(fig_plotly, width="stretch", key="hw_chart")

    # ── Composite JPEG (header + chart) ───────────────────────────────────────
    import matplotlib.gridspec as _gs
    import matplotlib.ticker as _ticker
    import matplotlib.dates as _mdates

    PANEL_H = 1.5
    CHART_H = 5.0
    DPI     = 150

    comp_fig = plt.figure(figsize=(12, PANEL_H + CHART_H), facecolor="white")
    spec = _gs.GridSpec(2, 1, figure=comp_fig,
                        height_ratios=[PANEL_H, CHART_H], hspace=0.0)

    hax = comp_fig.add_subplot(spec[0])
    hax.set_facecolor("#f0f6ff")
    hax.set_xlim(0, 1); hax.set_ylim(0, 1)
    hax.axis("off")
    hax.text(0.012, 0.95, "Soil water tracker",
             ha="left", va="top", fontsize=14, fontweight="bold", color="#1a3a5c",
             transform=hax.transAxes)
    hax.text(0.012, 0.68,
             f"{stn_name}    {profile.name}    {start_label} to {end_label}",
             ha="left", va="top", fontsize=9.5, color="#444",
             transform=hax.transAxes)

    parts = [
        ("Plant available soil water  ", "#444", False),
        (f"{final_pasw:.0f} mm", "#1a3a5c", True),
        (f"  ({pawc_pct:.0f}% of PAWC)", "#2979c4", True),
        ("      Fallow efficiency  ", "#888", False),
        (f"{fe:.0f}%", "#e06b00", True),
        (f"  from {cum_rain:.0f} mm rainfall", "#888", False),
    ]
    comp_fig.canvas.draw()
    renderer = comp_fig.canvas.get_renderer()
    ax_bbox  = hax.get_window_extent(renderer=renderer)
    x_cur = 0.012
    y_row = 0.28
    for txt, col, bold in parts:
        t = hax.text(x_cur, y_row, txt,
                     ha="left", va="top", fontsize=10.5,
                     fontweight="bold" if bold else "normal",
                     color=col, transform=hax.transAxes)
        comp_fig.canvas.draw()
        bb = t.get_window_extent(renderer=renderer)
        x_cur += bb.width / ax_bbox.width

    cax = comp_fig.add_subplot(spec[1])
    cax.set_facecolor("#FAFBFC")
    n_recent2 = len(recent_df)
    x_vals2   = recent_df.index
    hist_aligned2 = []
    for hdf in hist_dfs:
        seg = hdf["pasw"].values[:n_recent2]
        n = min(len(seg), n_recent2)
        cax.plot(x_vals2[:n], seg[:n], color=C_HIST, lw=0.8, alpha=0.55, zorder=1)
        hist_aligned2.append(seg[:n])
    if hist_aligned2:
        min_len2   = min(len(s) for s in hist_aligned2)
        mean_pasw2 = np.mean([s[:min_len2] for s in hist_aligned2], axis=0)
        cax.plot(x_vals2[:min_len2], mean_pasw2, color=C_MEAN, lw=2.0, ls="--", zorder=3,
                 label=f"Historical mean ({len(hist_aligned2)} yrs)")
    cax.plot(recent_df.index, recent_df["pasw"],
             color=C_RECENT, lw=2.8, zorder=4,
             label=f"Recent  ({start_label} – {end_label})")
    cax.axhline(profile.pawc_total, color="#CC4422", lw=0.9, ls="--", alpha=0.6,
                label=f"PAWC  {profile.pawc_total:.0f} mm", zorder=2)
    cax.set_ylabel("Plant available soil water (mm)", fontsize=9.5, color="#333")
    cax.set_ylim(bottom=0)
    cax.yaxis.set_major_locator(_ticker.MaxNLocator(nbins=6, integer=True))
    cax.tick_params(labelsize=8.5)
    cax.grid(axis="y", color="#E0E4EC", lw=0.6, zorder=0)
    cax.xaxis.set_major_locator(_mdates.MonthLocator())
    cax.xaxis.set_major_formatter(_mdates.DateFormatter("%d %b\n%Y"))
    cax.tick_params(axis="x", labelsize=8.5)
    cax.legend(loc="upper left", fontsize=8.5, frameon=True, framealpha=0.9, edgecolor="#CCCCCC")
    for sp in ["top", "right"]:
        cax.spines[sp].set_visible(False)
    comp_fig.tight_layout(pad=0.8)

    buf = io.BytesIO()
    comp_fig.savefig(buf, format="jpeg", dpi=DPI, bbox_inches="tight", facecolor="white")
    buf.seek(0)
    plt.close(comp_fig)
    plt.close(fig)

    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.download_button(
            "📥  Download chart (JPEG)", data=buf,
            file_name=f"SoilWater_{stn_name.replace(' ','_')}_"
                      f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.jpg",
            mime="image/jpeg",
            width="stretch",
        )

    with st.expander("📊 Water balance details"):
        rain_t = recent_df["rain"].sum()
        ro_t   = recent_df["runoff"].sum()
        es_t   = recent_df["soil_evap"].sum()
        tr_t   = recent_df["transp"].sum()
        dr_t   = recent_df["drainage"].sum()
        dsw    = recent_df["sw_total"].iloc[-1] - recent_df["sw_total"].iloc[0]
        err    = rain_t - ro_t - es_t - tr_t - dr_t - dsw

        has_temps = recent_met["tmax"].notna().any() if "tmax" in recent_met.columns else False
        temp_note = (
            f"Mean Tmax: {recent_met['tmax'].mean():.1f}°C  |  "
            f"Mean Tmin: {recent_met['tmin'].mean():.1f}°C  |  "
        ) if has_temps else ""

        st.markdown(f"""
| Component | mm | % of rainfall |
|---|---:|---:|
| Rainfall | {rain_t:.0f} | 100 |
| Runoff | {ro_t:.0f} | {ro_t/rain_t*100:.0f} |
| Soil evaporation | {es_t:.0f} | {es_t/rain_t*100:.0f} |
| Deep drainage | {dr_t:.0f} | {dr_t/rain_t*100:.0f} |
| **Change in soil water** | {dsw:.0f} | {dsw/rain_t*100:.0f} |
        """)
        epan_mean = recent_df['epan'].mean() if 'epan' in recent_df.columns else 0.0
        epan_src  = "SILO pan evap" if recent_met["epan"].fillna(0).sum() > 10 else "estimated from radiation/temp"
        st.caption(
            f"{temp_note}"
            f"Epan: {epan_mean:.1f} mm/day mean ({epan_src})  |  "
            f"PAW start: {recent_df['pasw'].iloc[0]:.0f} mm  "
            f"PAW end: {recent_df['pasw'].iloc[-1]:.0f} mm  |  "
            f"PAWC: {pawc:.0f} mm  |  Init: {init_pct}% of PAWC"
        )
