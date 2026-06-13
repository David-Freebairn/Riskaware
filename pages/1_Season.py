"""
pages/1_Season.py — How is the season going?
==============================================
Compares current season's cumulative rainfall against all years on record.
Ported from season_compare.html — SILO calls via core.silo.

Analysis logic (faithful port from JS):
  - Window: last N months, starting 1st of month
  - Each historical year is aligned to the same calendar window
  - Percentile = fraction of comparable years with less rain than current
  - Median series computed day-by-day across all comparable years
  - Chart: spaghetti of historical years + dashed median + bold current year
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import plotly.graph_objects as go
import io
from datetime import date, timedelta
from calendar import monthrange

from core.silo import search_stations, ensure_climate_cached, slice_climate
from core.styles import apply_styles, save_station, load_station

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="How's the season?",
    page_icon="📈",
    layout="wide",
)

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun",
          "Jul","Aug","Sep","Oct","Nov","Dec"]

apply_styles()


# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def _search(query: str):
    return search_stations(query)


def days_in_month(y: int, m: int) -> int:
    return monthrange(y, m)[1]


def build_series(df: pd.DataFrame, months_back: int):
    """
    Build cumulative rainfall series for every historical year aligned
    to the same calendar window as the current season.

    Returns
    -------
    series      : dict  end_year -> pd.Series (cumulative rain, DatetimeIndex)
    current_year: int
    median_ser  : pd.Series  day-by-day median across comparable years (same index as current)
    pctile      : int   percentile rank of current year (0-100)
    diff_mm     : int   mm above (+) or below (-) median at today
    stats       : dict  summary stats for chips
    """
    today  = df.index.max().date()
    end_y  = today.year
    end_m  = today.month
    end_d  = today.day

    # Window start = 1st of month, months_back months ago
    start_m = end_m - months_back
    start_y = end_y
    while start_m <= 0:
        start_m += 12
        start_y -= 1

    year_offset = end_y - start_y  # 0 or positive integer

    # Build fast lookup: (year, month, day) -> rain
    lookup = {}
    for idx, row in df.iterrows():
        lookup[(idx.year, idx.month, idx.day)] = row["rain"]

    data_years = sorted(df.index.year.unique())
    min_data_y = data_years[0]

    series = {}
    first_end_y = min_data_y + year_offset

    for ey in range(first_end_y, end_y + 1):
        sy = ey - year_offset
        is_current = (ey == end_y)
        cum = 0.0
        dates, cums = [], []
        missing_streak = 0

        wy, wm, wd = sy, start_m, 1
        stop_m = end_m
        stop_d = end_d if is_current else days_in_month(ey, end_m)

        ok = True
        while True:
            if wy > ey: break
            if wy == ey and wm > stop_m: break
            if wy == ey and wm == stop_m and wd > stop_d: break

            rain = lookup.get((wy, wm, wd), None)
            if rain is None:
                if not is_current:
                    missing_streak += 1
                    if missing_streak > 5:
                        ok = False
                        break
                rain = 0.0
            else:
                missing_streak = 0

            cum += rain
            dates.append(pd.Timestamp(wy, wm, wd))
            cums.append(cum)

            wd += 1
            if wd > days_in_month(wy, wm):
                wd = 1; wm += 1
            if wm > 12:
                wm = 1; wy += 1

        if ok and dates:
            s = pd.Series(cums, index=dates)
            series[ey] = s

    if not series or end_y not in series:
        return None, end_y, None, None, None, None

    current = series[end_y]
    current_total = float(current.iloc[-1])
    n_current = len(current)

    # Comparable years: not current year, has at least as many days
    comp_years  = [y for y in series if y != end_y and len(series[y]) >= n_current]
    comp_totals = [float(series[y].iloc[n_current - 1]) for y in comp_years]

    if not comp_years:
        return series, end_y, None, None, None, None

    better = sum(1 for t in comp_totals if t > current_total)
    pctile = round((1 - better / len(comp_years)) * 100)

    # Median series — day by day
    median_vals = []
    current_dates = current.index
    for i in range(n_current):
        vals = sorted([float(series[y].iloc[i]) for y in comp_years if len(series[y]) > i])
        if not vals:
            median_vals.append(np.nan)
            continue
        mid = len(vals) // 2
        med = (vals[mid - 1] + vals[mid]) / 2 if len(vals) % 2 == 0 else vals[mid]
        median_vals.append(med)

    median_ser  = pd.Series(median_vals, index=current_dates)
    median_final = float(median_ser.iloc[-1])
    diff_mm = round(current_total - median_final)

    # Summary stats
    ann_totals = df.groupby(df.index.year)["rain"].sum()
    stats = {
        "period"    : f"{data_years[0]}–{data_years[-1]}",
        "ann_mean"  : round(float(ann_totals.mean())),
        "ann_max"   : round(float(ann_totals.max())),
        "n_years"   : len(data_years),
        "curr_total": round(current_total),
    }
    return series, end_y, median_ser, pctile, diff_mm, stats


def make_chart(series, current_year, median_ser, station_name,
               months_back, start_year_from):
    """
    Spaghetti chart: historical years (light blue) + median (dashed dark blue)
    + current year (bold red). X-axis = calendar dates aligned to current window.
    """
    C_HIST    = "#7ab4d8"
    C_MEDIAN  = "#1a4a6e"
    C_CURRENT = "#cc2200"
    C_BG      = "#ffffff"
    C_GRID    = "#e0e8f0"

    plt.rcParams.update({
        "font.family"        : "sans-serif",
        "axes.facecolor"     : C_BG,
        "figure.facecolor"   : C_BG,
        "axes.spines.top"    : False,
        "axes.spines.right"  : False,
        "axes.linewidth"     : 0.8,
    })

    fig, ax = plt.subplots(figsize=(12, 4.5))

    current = series[current_year]

    # All historical years
    for ey, s in series.items():
        if ey == current_year:
            continue
        # Align historical dates to current window dates for plotting
        n = min(len(s), len(current))
        ax.plot(current.index[:n], s.values[:n],
                color=C_HIST, lw=0.9, alpha=0.45, zorder=1)

    # Median
    if median_ser is not None:
        ax.plot(median_ser.index, median_ser.values,
                color=C_MEDIAN, lw=2, ls="--", zorder=3, label="Median")
        # Label at end
        last_valid = median_ser.dropna()
        if len(last_valid):
            ax.annotate(
                "median",
                xy=(last_valid.index[-1], last_valid.iloc[-1]),
                xytext=(6, 0), textcoords="offset points",
                fontsize=8, color=C_MEDIAN, va="center",
            )

    # Current year
    ax.plot(current.index, current.values,
            color=C_CURRENT, lw=2.5, zorder=4,
            label=f"{current_year} (current)")
    ax.plot(current.index[-1], current.values[-1],
            "o", color=C_CURRENT, ms=7, mfc="none", mew=2, zorder=5)

    # Today vertical line
    ax.axvline(current.index[-1], color="#888", lw=1, ls=":", zorder=2)

    # Axes
    ax.set_ylabel("Cumulative rainfall (mm)", fontsize=10, color="#555")
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=5, integer=True))
    ax.tick_params(labelsize=9)
    ax.grid(axis="y", color=C_GRID, lw=0.7, zorder=0)

    # X-axis — calendar-aligned labels
    n_months = months_back
    if n_months <= 14:
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    elif n_months <= 30:
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1,4,7,10]))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    else:
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1,7]))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))

    ax.tick_params(axis="x", labelsize=8.5)
    plt.setp(ax.xaxis.get_majorticklabels(), ha="center")

    ax.set_title(
        f"{station_name}   ·   looking back {months_back} months",
        fontsize=11, color="#1a2332", pad=8, loc="left",
    )

    plt.tight_layout(pad=1.2)
    return fig


def ordinal(n: int) -> str:
    s = ["th","st","nd","rd"] + ["th"] * 16
    return f"{n}{s[n % 20] if n % 20 < 4 else 'th'}"


# ── UI ────────────────────────────────────────────────────────────────────────

st.title("📈 How's the season?")
st.caption("*Comparing this season's rainfall against all years on record*")

# ── Pre-populate search from shared station ───────────────────────────────────
_shared = load_station()
if _shared and not st.session_state.get("se_query"):
    st.session_state["se_query"]      = _shared.get("name", "")
    st.session_state["se_saved"]      = _shared
    st.session_state["se_stations"]   = [_shared]
    st.session_state["se_last_query"] = _shared.get("name", "")
    st.session_state["se_confirmed"]  = True
    st.session_state["se_chosen"]     = _shared.get("label", "")

# ── Handle Change button reset (must happen before widgets render) ────────────
if st.session_state.pop("se_reset", False):
    st.session_state["se_confirmed"]  = False
    st.session_state["se_stations"]   = []
    st.session_state["se_chosen"]     = None
    st.session_state["se_last_query"] = ""
    st.session_state["se_query"]      = ""
    st.session_state.pop("climate_df",  None)
    st.session_state.pop("climate_key", None)

# ── Step 1: Select site ───────────────────────────────────────────────────────
with st.container(border=True):
    st.markdown('<p class="section-title">Select site</p>', unsafe_allow_html=True)

    confirmed    = st.session_state.get("se_confirmed", False)
    station_info = None

    if not confirmed:
        query = st.text_input(
            "station", label_visibility="collapsed",
            placeholder="Search station — e.g. Roma, Cairns  (press Enter)",
            key="se_query",
        )
        start_year = st.session_state.get("se_start_year", 1900)

        if query and len(query) >= 3:
            if st.session_state.get("se_last_query") != query:
                with st.spinner("Searching..."):
                    try:
                        st.session_state["se_stations"] = _search(query)
                    except Exception as e:
                        st.error(f"Search failed: {e}")
                        st.session_state["se_stations"] = []
                st.session_state["se_last_query"] = query
                st.session_state["se_sel_idx"]    = 0
                st.session_state.pop("climate_df", None)
                st.session_state.pop("climate_key", None)
                st.session_state.pop("se_result",  None)

            stations = st.session_state.get("se_stations", [])
            if stations:
                labels = [s["label"] for s in stations]
                chosen = st.session_state.get("se_chosen") or labels[0]
                if chosen not in labels:
                    chosen = labels[0]
                if len(labels) == 1:
                    st.session_state["se_chosen"]    = labels[0]
                    st.session_state["se_confirmed"] = True
                    st.session_state["se_stations"]  = [stations[0]]
                    st.rerun()
                else:
                    st.caption(f"**{len(labels)} stations found** — select one:")
                    def on_station_pick():
                        chosen_now = st.session_state["se_radio"]
                        st.session_state["se_chosen"]    = chosen_now
                        st.session_state["se_confirmed"] = True
                        matching = [s for s in st.session_state.get("se_stations", [])
                                    if s["label"] == chosen_now]
                        if matching:
                            st.session_state["se_stations"] = [matching[0]]
                    rc1, rc2 = st.columns([5, 1])
                    with rc1:
                        chosen = st.radio(
                            "Station", options=labels,
                            index=labels.index(chosen) if chosen in labels else 0,
                            key="se_radio", label_visibility="collapsed",
                            on_change=on_station_pick,
                        )
                        st.session_state["se_chosen"] = chosen
                    with rc2:
                        st.markdown('<div style="margin-top:4px">', unsafe_allow_html=True)
                        if st.button("Select", key="se_select", width="stretch"):
                            st.session_state["se_chosen"]    = chosen
                            st.session_state["se_confirmed"] = True
                            st.session_state["se_stations"]  = [next(s for s in stations if s["label"] == chosen)]
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)
            elif st.session_state.get("se_last_query"):
                st.warning("No stations found — try a shorter name.")

    else:
        chosen   = st.session_state.get("se_chosen", "")
        stations = st.session_state.get("se_stations", [])
        c1, c2, c3, c4 = st.columns([3.5, 1.3, 1.3, 1.4])
        with c1:
            st.success(f"📍 {chosen}")
        with c2:
            st.markdown('<div style="margin-top:8px; font-size:0.9rem; color:#555;">Start record</div>',
                        unsafe_allow_html=True)
        with c3:
            start_year = st.number_input(
                "start_year", label_visibility="collapsed",
                min_value=1889, max_value=date.today().year,
                value=st.session_state.get("se_start_year", 1900),
                step=1, key="se_start_year_input",
            )
            st.session_state["se_start_year"] = start_year
        with c4:
            st.markdown('<div style="margin-top:4px">', unsafe_allow_html=True)
            if st.button("Change", key="se_change", width="stretch"):
                st.session_state["se_reset"] = True
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        if stations:
            station_info = next((s for s in stations if s["label"] == chosen), None)
            if station_info:
                st.session_state["se_saved"] = station_info
                save_station(station_info)

# ── Step 2: Duration ─────────────────────────────────────────────────────────
r1a, r1b, r1c = st.columns([2.2, 0.6, 3.5])
with r1a:
    st.markdown('<span style="font-size:1.1rem">How do the last</span>', unsafe_allow_html=True)
with r1b:
    months_back = st.number_input(
        "months", label_visibility="collapsed",
        min_value=1, max_value=60, value=6, step=1,
    )
with r1c:
    st.markdown('<span style="font-size:1.1rem">months compare?</span>', unsafe_allow_html=True)

# ── Info expander ─────────────────────────────────────────────────────────────
with st.expander("ℹ️ About this analysis"):
    st.markdown("""
**How's the season?** compares cumulative rainfall for the current season against 
other years on record. Results are presented as:
- **Percentile** value indicates where this season sits relative to history.
- The **dashed line** is the median or 50%ile – half year’s wetter, half year’s drier.
- All years shown as light blue lines.

**Applications**
- Provides an objective assessment of this season in relation to longer term conditions.
- Use to adjust expectations: fallow, in-crop rain and yield,fertiliser inputs. 

Results can be downloaded as an image below.
""")

# ── Auto-run whenever station and inputs are ready ────────────────────────────
_start_year = st.session_state.get("se_start_year", 1900)
_input_key  = f"{station_info['id'] if station_info else 'none'}_{_start_year}_{months_back}"
_has_result = st.session_state.get("se_result") is not None

if station_info and (_input_key != st.session_state.get("se_input_key") or not _has_result):
    st.session_state["se_input_key"] = _input_key
    sid  = station_info["id"]
    _lat = station_info.get("lat")
    _lon = station_info.get("lon")
    name = station_info["name"]

    with st.spinner(f"Loading {name}… (first load may take 30–60 seconds)"):
        try:
            full_df = ensure_climate_cached(sid, _lat, _lon,
                                            session_state=st.session_state)
            df = slice_climate(full_df, start=f"{int(_start_year)}0101")[
                ["rain", "year", "month", "day", "doy"]
            ]
        except Exception as e:
            st.error(f"Data fetch failed: {e}")
            st.stop()

    if df.empty:
        st.error("No data found for this station and period.")
        st.stop()

    st.session_state["se_result"] = {
        "df": df, "name": name, "station_info": station_info,
    }

# ── Analysis ──────────────────────────────────────────────────────────────────
if st.session_state.get("se_result"):
    res  = st.session_state["se_result"]
    df   = res["df"]
    name = res["name"]
    station_info = res.get("station_info", {})

    # Run analysis
    ann_totals = df.groupby(df.index.year)["rain"].sum()
    data_years = sorted(df.index.year.unique())
    min_y, max_y = data_years[0], data_years[-1]
    ann_mean = int(ann_totals.mean())

    series, current_year, median_ser, pctile, diff_mm, stats = build_series(
        df, int(months_back)
    )

    if series is None:
        st.warning("Not enough data for this window.")
        st.stop()

    if pctile is None:
        st.warning("Not enough comparable years to calculate a percentile.")
        st.stop()

    diff_sign = "+" if diff_mm >= 0 else ""
    diff_dir  = "above" if diff_mm >= 0 else "below"
    abs_diff  = abs(diff_mm)

    # ── Season's comparison header (matches Probability analysis style) ──────
    st.markdown(f"""
<div style="background:#f0f6ff; border-radius:10px; padding:18px 22px 14px 22px; margin-bottom:4px;">
  <div style="font-size:1.45rem; font-weight:700; color:#1a3a5c; margin-bottom:2px;">
    Season's comparison
  </div>
  <div style="font-size:0.95rem; color:#444; margin-bottom:10px;">
    <b>{name}</b>&nbsp;&nbsp;
    <span style="color:#888;">({min_y}–{max_y})</span>&nbsp;&nbsp;
    Mean annual rainfall <b>{ann_mean} mm</b>
  </div>
  <div style="display:flex; align-items:baseline; gap:0; flex-wrap:wrap;">
    <span style="font-size:1.02rem; color:#444; font-weight:500;">Rainfall in the last&nbsp;</span>
    <span style="font-size:1.02rem; color:#e06b00; font-weight:700;">{months_back} month{"s" if months_back != 1 else ""}</span>
    <span style="font-size:1.02rem; color:#444; font-weight:500;">&nbsp;is in the&nbsp;</span>
    <span style="font-size:1.02rem; color:#2979c4; font-weight:700;">{pctile} %ile</span>
    <span style="font-size:1.02rem; color:#888; font-weight:400;">&nbsp;( {abs_diff} mm {diff_dir} the average )</span>
  </div>
</div>
""", unsafe_allow_html=True)

    # Chart — remove old suptitle, use clean subtitle inside axes instead
    fig = make_chart(series, current_year, median_ser, name,
                     int(months_back), int(start_year))

    ax = fig.axes[0]
    ax.set_title("")  # keep matplotlib fig clean for JPEG

    # ── Interactive Plotly chart ──────────────────────────────────────────
    C_HIST    = "#7ab4d8"
    C_MEDIAN  = "#1a4a6e"
    C_CURRENT = "#cc2200"
    C_GRID    = "#e0e8f0"
    C_BG      = "#ffffff"

    current    = series[current_year]
    fig_plotly = go.Figure()

    # Historical years — year shown on hover
    for ey, s in series.items():
        if ey == current_year:
            continue
        n = min(len(s), len(current))
        fig_plotly.add_trace(go.Scatter(
            x=current.index[:n], y=s.values[:n],
            mode="lines",
            line=dict(color=C_HIST, width=0.9),
            opacity=0.45,
            name=str(ey),
            hovertemplate=f"{ey}<extra></extra>",
            legendgroup="history",
            showlegend=False,
        ))

    # Median
    if median_ser is not None:
        fig_plotly.add_trace(go.Scatter(
            x=median_ser.index, y=median_ser.values,
            mode="lines",
            line=dict(color=C_MEDIAN, width=2, dash="dash"),
            name="Median",
            hovertemplate="Median<extra></extra>",
        ))

    # Current year
    fig_plotly.add_trace(go.Scatter(
        x=current.index, y=current.values,
        mode="lines",
        line=dict(color=C_CURRENT, width=2.5),
        name=f"{current_year} (current)",
        hovertemplate=f"{current_year}<extra></extra>",
    ))

    # Today vertical line
    fig_plotly.add_vline(
        x=current.index[-1].timestamp() * 1000,
        line_dash="dot", line_color="#888", line_width=1,
    )

    fig_plotly.update_layout(
        height=360,
        plot_bgcolor=C_BG, paper_bgcolor=C_BG,
        margin=dict(l=60, r=20, t=30, b=50),
        hovermode="closest",
        legend=dict(
            orientation="h", x=0, y=1.02, xanchor="left", yanchor="bottom",
            font=dict(size=10), bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            tickfont=dict(size=9, color="#555"),
            gridcolor=C_GRID, showgrid=False,
            fixedrange=True,
        ),
        yaxis=dict(
            title="Cumulative rainfall (mm)",
            title_font=dict(size=10, color="#555"),
            tickfont=dict(size=9, color="#555"),
            gridcolor=C_GRID, showgrid=True,
            rangemode="tozero", fixedrange=True,
        ),
    )

    st.plotly_chart(fig_plotly, width="stretch", key="season_chart")

    # ── Composite JPEG download (header panel + chart) ─────────────────────
    import matplotlib.gridspec as _gs
    import matplotlib.patches as _mp

    PANEL_H = 1.5
    CHART_H = 4.5
    DPI     = 150

    comp_fig = plt.figure(figsize=(12, PANEL_H + CHART_H), facecolor="white")
    spec = _gs.GridSpec(2, 1, figure=comp_fig,
                        height_ratios=[PANEL_H, CHART_H], hspace=0.0)

    # ── Header panel ──────────────────────────────────────────────────────
    hax = comp_fig.add_subplot(spec[0])
    hax.set_facecolor("#f0f6ff")
    hax.set_xlim(0, 1); hax.set_ylim(0, 1)
    hax.axis("off")

    hax.text(0.012, 0.95, "Season's comparison",
             ha="left", va="top", fontsize=14, fontweight="bold", color="#1a3a5c",
             transform=hax.transAxes)
    hax.text(0.012, 0.68,
             f"{name}    ({min_y}–{max_y})    Mean annual rainfall {ann_mean} mm",
             ha="left", va="top", fontsize=9.5, color="#444",
             transform=hax.transAxes)

    # Sentence with colour-coded spans
    parts = [
        ("Rainfall in the last ", "#444", False),
        (f"{months_back} month{'s' if months_back != 1 else ''}", "#e06b00", True),
        (" is in the ", "#444", False),
        (f"{pctile} %ile", "#2979c4", True),
        (f"  ( {abs_diff} mm {diff_dir} the average )", "#888", False),
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

    # ── Chart panel ───────────────────────────────────────────────────────
    C_HIST    = "#7ab4d8"
    C_MEDIAN  = "#1a4a6e"
    C_CURRENT = "#cc2200"
    C_BG      = "#ffffff"
    C_GRID    = "#e0e8f0"

    import matplotlib.dates as _mdates
    import matplotlib.ticker as _ticker

    cax = comp_fig.add_subplot(spec[1])
    cax.set_facecolor(C_BG)

    current = series[current_year]
    for ey, s in series.items():
        if ey == current_year:
            continue
        n = min(len(s), len(current))
        cax.plot(current.index[:n], s.values[:n],
                 color=C_HIST, lw=0.9, alpha=0.45, zorder=1)

    if median_ser is not None:
        cax.plot(median_ser.index, median_ser.values,
                 color=C_MEDIAN, lw=2, ls="--", zorder=3)
        last_valid = median_ser.dropna()
        if len(last_valid):
            cax.annotate("median",
                         xy=(last_valid.index[-1], last_valid.iloc[-1]),
                         xytext=(6, 0), textcoords="offset points",
                         fontsize=8, color=C_MEDIAN, va="center")

    cax.plot(current.index, current.values,
             color=C_CURRENT, lw=2.5, zorder=4)
    cax.plot(current.index[-1], current.values[-1],
             "o", color=C_CURRENT, ms=7, mfc="none", mew=2, zorder=5)
    cax.axvline(current.index[-1], color="#888", lw=1, ls=":", zorder=2)

    cax.set_ylabel("Cumulative rainfall (mm)", fontsize=9.5, color="#555")
    cax.set_ylim(bottom=0)
    cax.yaxis.set_major_locator(_ticker.MaxNLocator(nbins=5, integer=True))
    cax.tick_params(labelsize=8.5)
    cax.grid(axis="y", color=C_GRID, lw=0.7, zorder=0)

    n_months = int(months_back)
    if n_months <= 14:
        cax.xaxis.set_major_locator(_mdates.MonthLocator())
        cax.xaxis.set_major_formatter(_mdates.DateFormatter("%b\n%Y"))
    elif n_months <= 30:
        cax.xaxis.set_major_locator(_mdates.MonthLocator(bymonth=[1,4,7,10]))
        cax.xaxis.set_major_formatter(_mdates.DateFormatter("%b %Y"))
    else:
        cax.xaxis.set_major_locator(_mdates.MonthLocator(bymonth=[1,7]))
        cax.xaxis.set_major_formatter(_mdates.DateFormatter("%b %Y"))

    plt.setp(cax.xaxis.get_majorticklabels(), ha="center")
    for sp in ["top", "right"]:
        cax.spines[sp].set_visible(False)
    cax.spines["left"].set_linewidth(0.8)
    cax.spines["bottom"].set_linewidth(0.8)

    comp_fig.tight_layout(pad=0.8)

    buf = io.BytesIO()
    comp_fig.savefig(buf, format="jpeg", dpi=DPI, bbox_inches="tight", facecolor="white")
    buf.seek(0)
    plt.close(comp_fig)
    plt.close(fig)

    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.download_button(
            "📥  Download chart (JPEG)",
            data=buf,
            file_name=f"season_{name.replace(' ', '_')}_{months_back}mo.jpg",
            mime="image/jpeg",
            width="stretch",
        )
