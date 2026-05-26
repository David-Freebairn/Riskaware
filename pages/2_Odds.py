"""
pages/2_Odds.py — What are the odds?
======================================
Rainfall frequency analysis using SILO Patched Point data.
Ported from rainfall_app.py — SILO calls now use core.silo.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import date

from core.silo import search_stations, ensure_climate_cached, slice_climate
from core.styles import apply_styles, save_station, load_station

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="What are the odds?", page_icon="🎲", layout="wide")

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

apply_styles()


# ── Session state ─────────────────────────────────────────────────────────────
for key, default in [
    ("df", None), ("station_name", None), ("stations", []),
    ("last_search", ""), ("selected_station", None),
    ("search_error", None), ("search_input", ""),
    ("station_confirmed", False), ("station_chosen", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# Pre-populate from shared station if arriving from another page
_shared = load_station()
if _shared and not st.session_state.get("search_input"):
    st.session_state["search_input"]      = _shared.get("name", "")
    st.session_state["selected_station"]  = _shared
    st.session_state["stations"]          = [_shared]
    st.session_state["last_search"]       = _shared.get("name", "")
    st.session_state["station_confirmed"] = True
    st.session_state["station_chosen"]    = _shared.get("label", "")


# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def _search(term):
    return search_stations(term)


def parse_df(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure the rainfall DataFrame has year/month/day columns."""
    if "year" not in df.columns:
        df["year"] = df.index.year
    if "month" not in df.columns:
        df["month"] = df.index.month
    if "day" not in df.columns:
        df["day"] = df.index.day
    return df


def assign_season_year(df, sm, sd, em, ed):
    df = df.copy()
    mo = df.index.month if "month" not in df.columns else df["month"]
    dy = df.index.day   if "day"   not in df.columns else df["day"]
    yr = df.index.year  if "year"  not in df.columns else df["year"]

    crosses = (sm > em) or (sm == em and sd > ed)
    after_start = (mo > sm) | ((mo == sm) & (dy >= sd))
    before_end  = (mo < em) | ((mo == em) & (dy <= ed))
    mask = after_start & before_end if not crosses else after_start | before_end
    df = df[mask].copy()

    mo2 = df.index.month if "month" not in df.columns else df["month"]
    dy2 = df.index.day   if "day"   not in df.columns else df["day"]
    yr2 = df.index.year  if "year"  not in df.columns else df["year"]

    if crosses:
        after = (mo2 > sm) | ((mo2 == sm) & (dy2 >= sd))
        df["season_year"] = np.where(after, yr2, yr2 - 1)
    else:
        df["season_year"] = yr2
    return df


def season_label(sm, sd, em, ed):
    return f"{sd} {MONTHS[sm-1]} – {ed} {MONTHS[em-1]}"


# ── Header ────────────────────────────────────────────────────────────────────
st.title("🎲 What are the odds?")
st.caption("*Rainfall frequency analysis — how often has it happened before?*")

# ── Handle Change button reset (must happen before widgets render) ────────────
if st.session_state.pop("odds_reset", False):
    st.session_state["station_confirmed"] = False
    st.session_state["stations"]          = []
    st.session_state["station_chosen"]    = None
    st.session_state["last_search"]       = ""
    st.session_state["search_input"]      = ""
    st.session_state.pop("climate_df",  None)
    st.session_state.pop("climate_key", None)

# ── Panel 1 — Site ────────────────────────────────────────────────────────────
def do_search():
    term = st.session_state.search_input
    if term and term != st.session_state.last_search:
        st.session_state.last_search = term
        st.session_state.stations = []
        st.session_state.selected_station = None
        st.session_state.station_confirmed = False
        st.session_state.station_chosen = None
        st.session_state.pop("climate_df", None)
        st.session_state.pop("climate_key", None)
        st.session_state.station_confirmed = False
        st.session_state.station_chosen = None
        try:
            st.session_state.stations = _search(term)
        except Exception as e:
            st.session_state.search_error = str(e)


with st.container(border=True):
    st.markdown('<p class="section-title">Select site</p>', unsafe_allow_html=True)
    col1, col2 = st.columns([2.5, 1.0])
    with col1:
        st.text_input(
            "station", label_visibility="collapsed",
            placeholder="Search station — e.g. Roma, Cairns  (press Enter)",
            key="search_input", on_change=do_search,
        )
    with col2:
        start_year = st.number_input(
            "Records from year", min_value=1889,
            max_value=date.today().year, value=1900, step=1,
        )
    start_date = date(int(start_year), 1, 1)

    if st.session_state.get("search_error"):
        st.error(f"Search failed: {st.session_state.search_error}")
        st.session_state.search_error = None

    if st.session_state.stations:
        labels = [s["label"] for s in st.session_state.stations]
        confirmed = st.session_state.get("station_confirmed", False)
        chosen    = st.session_state.get("station_chosen") or labels[0]
        if chosen not in labels:
            chosen = labels[0]
        if not confirmed:
            if len(labels) == 1:
                st.session_state.station_chosen    = labels[0]
                st.session_state.station_confirmed = True
                confirmed = True
                chosen    = labels[0]
            else:
                current_index = labels.index(chosen) if chosen in labels else 0
                st.caption(f"**{len(labels)} stations found** — click to select:")
                def on_station_pick():
                    st.session_state.station_chosen    = st.session_state.station_select
                    st.session_state.station_confirmed = True
                chosen = st.radio(
                    "Station", options=labels, index=current_index,
                    key="station_select", label_visibility="collapsed",
                    on_change=on_station_pick,
                )
                st.session_state.station_chosen = chosen
        if confirmed:
            c1, c2 = st.columns([6, 1])
            with c1:
                st.success(f"📍 {chosen}")
            with c2:
                if st.button("Change", key="change_btn"):
                    st.session_state["odds_reset"] = True
                    st.rerun()
        st.session_state.selected_station = next(
            s for s in st.session_state.stations if s["label"] == chosen
        )
        save_station(st.session_state.selected_station)
    elif st.session_state.last_search:
        st.warning("No stations found. Try a shorter search term.")

selected_station = st.session_state.get("selected_station") or load_station()


# ── Panel 2 — Query ───────────────────────────────────────────────────────────
with st.container(border=True):
    st.markdown('<p class="section-title">Set up query</p>', unsafe_allow_html=True)

    r1a, r1b, r1c, r1d, r1e, r1f, r1g = st.columns([2.0, 0.9, 0.7, 1.1, 0.9, 0.5, 1.5])
    with r1a: st.markdown('<span style="font-size:1rem">Explore how often</span>',
                          unsafe_allow_html=True)
    with r1b: threshold = st.number_input("mm", label_visibility="collapsed",
                                          min_value=1, max_value=9999, value=25, step=5)
    with r1c: st.markdown('<span style="font-size:1rem">mm rain occurs over</span>',
                          unsafe_allow_html=True)
    with r1d: win_days = st.number_input("days", label_visibility="collapsed",
                                         min_value=1, max_value=365, value=5, step=1)
    with r1e: st.markdown('<span style="font-size:1rem">days</span>', unsafe_allow_html=True)

    st.markdown("")
    r2a, r2b, r2c, r2d, r2e, r2f, r2g = st.columns([1.6, 1.5, 0.9, 0.4, 1.5, 0.9, 1.0])
    with r2a: st.markdown('<span style="font-size:1rem">during the season</span>',
                          unsafe_allow_html=True)
    with r2b: start_mon = st.selectbox("sm", MONTHS, index=0, label_visibility="collapsed")
    with r2c: start_day = st.number_input("sd", min_value=1, max_value=31, value=1,
                                          label_visibility="collapsed")
    with r2d: st.markdown('<span style="font-size:1rem">to</span>', unsafe_allow_html=True)
    with r2e: end_mon = st.selectbox("em", MONTHS, index=11, label_visibility="collapsed")
    with r2f: end_day = st.number_input("ed", min_value=1, max_value=31, value=31,
                                         label_visibility="collapsed")

run_btn = st.button("Fetch data and run analysis", type="primary",
                    disabled=selected_station is None,
                    width='stretch')


# ── Analysis ──────────────────────────────────────────────────────────────────
if run_btn and selected_station:
    sid  = selected_station["id"]
    name = selected_station["name"]
    _lat = selected_station.get("lat")
    _lon = selected_station.get("lon")

    with st.spinner(f"Fetching data for {name}..."):
        try:
            full_df = ensure_climate_cached(sid, _lat, _lon,
                                            session_state=st.session_state)
            df = slice_climate(full_df, start=start_date.strftime("%Y%m%d"))
            df = parse_df(df)
        except Exception as e:
            st.error(f"Data fetch failed: {e}")
            st.stop()

    years    = sorted(df["year"].unique())
    yr_from, yr_to = years[0], years[-1]
    ann_mean = df.groupby("year")["rain"].sum().mean()

    try:
        sm = MONTHS.index(start_mon) + 1
        em = MONTHS.index(end_mon)   + 1
        sd_i, ed_i = int(start_day), int(end_day)
        slabel = season_label(sm, sd_i, em, ed_i)

        sub = assign_season_year(df, sm, sd_i, em, ed_i)
        sub = sub[(sub["season_year"] >= yr_from) & (sub["season_year"] <= yr_to)]

        if sub.empty:
            st.warning("No data in that season/year range.")
            st.stop()

        results = []
        for sy, grp in sub.sort_values("season_year").groupby("season_year"):
            rolled = grp["rain"].rolling(window=int(win_days), min_periods=int(win_days)).sum()
            mx = rolled.max()
            if not np.isnan(mx):
                results.append({"season_year": sy, "max_roll_mm": mx,
                                 "met_criteria": int(mx >= threshold)})

        if not results:
            st.warning("Not enough days to compute rolling window.")
            st.stop()

        annual_max = pd.DataFrame(results)
        rain       = annual_max["max_roll_mm"].values
        n          = len(rain)
        n_exceed   = int(np.sum(rain >= threshold))
        pct        = n_exceed / n * 100
        pct_display = int(round(pct))
        ann_mean   = round(df.groupby("year")["rain"].sum().mean())

        # ── Probability analysis header ────────────────────────────────────
        st.markdown(f"""
<div style="background:#f0f6ff; border-radius:10px; padding:18px 22px 14px 22px; margin-bottom:4px;">
  <div style="font-size:1.45rem; font-weight:700; color:#1a3a5c; margin-bottom:6px;">
    Probability analysis
  </div>
  <div style="display:flex; align-items:baseline; gap:0; flex-wrap:wrap;">
    <span style="font-size:1.02rem; color:#444; font-weight:500;">Rainfall exceeded&nbsp;</span>
    <span style="font-size:1.02rem; color:#e06b00; font-weight:700;">{int(threshold)} mm</span>
    <span style="font-size:1.02rem; color:#444; font-weight:500;">&nbsp;in&nbsp;</span>
    <span style="font-size:1.02rem; color:#e06b00; font-weight:700;">{int(win_days)} days</span>
    <span style="font-size:1.02rem; color:#444; font-weight:500;">&nbsp;between&nbsp;</span>
    <span style="font-size:1.02rem; color:#2979c4; font-weight:600;">{sd_i} {MONTHS[sm-1]}</span>
    <span style="font-size:1.02rem; color:#444; font-weight:500;">&nbsp;and&nbsp;</span>
    <span style="font-size:1.02rem; color:#2979c4; font-weight:600;">{ed_i} {MONTHS[em-1]}</span>
    <span style="flex:1; min-width:20px;"></span>
    <span style="font-size:1.5rem; font-weight:800; color:#0b1f3a;">
      {pct_display}%&nbsp;<span style="font-size:1.02rem; font-weight:500; color:#444;">of years</span>
    </span>
  </div>
</div>
""", unsafe_allow_html=True)

        # ── Chart ──────────────────────────────────────────────────────────
        NAVY = "#0b1f3a"; BLUE = "#2979c4"; BRIGHT = "#4da6ff"
        MISS = "#b8cfe8"; BG = "#f7fafd"; GRID = "#dde5ee"

        fig, ax = plt.subplots(figsize=(14, 4.0))
        fig.patch.set_facecolor(BG); ax.set_facecolor(BG)

        colours = [BRIGHT if r >= threshold else MISS for r in annual_max["max_roll_mm"]]
        bars = ax.bar(annual_max["season_year"], annual_max["max_roll_mm"],
                      color=colours, width=0.72, zorder=3, linewidth=0, alpha=0.95)
        for bar, r in zip(bars, annual_max["max_roll_mm"]):
            if r >= threshold:
                bar.set_edgecolor(BLUE); bar.set_linewidth(0.8)

        ax.axhline(threshold, color=NAVY, lw=1.8, ls="--", zorder=4)
        x_right = annual_max["season_year"].max()
        ax.annotate(f"{int(threshold)} mm",
                    xy=(x_right, threshold), xytext=(6, 4),
                    textcoords="offset points", fontsize=9.5, color=NAVY,
                    fontweight="bold", va="bottom", ha="left",
                    annotation_clip=False)

        ax.set_xlabel("Season year", fontsize=10, color="#3a5a7a", labelpad=6)
        ax.set_ylabel(f"Max {int(win_days)}-day rainfall  (mm)",
                      fontsize=10, color="#3a5a7a", labelpad=6)
        ax.tick_params(colors="#3a5a7a", labelsize=9)
        if n > 30: ax.tick_params(axis="x", rotation=45)
        ax.grid(True, axis="y", color=GRID, lw=0.9, zorder=0)
        ax.set_axisbelow(True)
        for sp in ["top", "right", "left"]: ax.spines[sp].set_visible(False)
        ax.spines["bottom"].set_color(GRID)

        from matplotlib.patches import Patch as _Patch
        ax.legend(handles=[
            _Patch(facecolor=BRIGHT, edgecolor=BLUE, linewidth=0.8,
                   label=f"≥ {int(threshold)} mm  ({n_exceed} yrs)"),
            _Patch(facecolor=MISS, label=f"< {int(threshold)} mm  ({n - n_exceed} yrs)"),
        ], fontsize=9, loc="upper left", framealpha=0.95, edgecolor=GRID, fancybox=False)
        fig.tight_layout(pad=1.1)

        # ── Save JPEG before closing fig ───────────────────────────────────
        import io as _io
        import matplotlib.gridspec as _gs

        PANEL_H = 1.4
        CHART_H = 4.0
        DPI     = 150

        comp_fig = plt.figure(figsize=(14, PANEL_H + CHART_H), facecolor="white")
        spec = _gs.GridSpec(2, 1, figure=comp_fig,
                            height_ratios=[PANEL_H, CHART_H], hspace=0.0)

        hax = comp_fig.add_subplot(spec[0])
        hax.set_facecolor("#f0f6ff")
        hax.set_xlim(0, 1); hax.set_ylim(0, 1)
        hax.axis("off")
        hax.text(0.012, 0.95, f"Station: {name}",
                 ha="left", va="top", fontsize=9, fontweight="bold",
                 color="#0b1f3a", transform=hax.transAxes)
        hax.text(0.012, 0.78, f"{yr_from}-{yr_to} period",
                 ha="left", va="top", fontsize=8.5, color="#444",
                 transform=hax.transAxes)
        hax.text(0.012, 0.60, f"Annual mean {ann_mean} mm",
                 ha="left", va="top", fontsize=8.5, fontweight="bold",
                 color="#444", transform=hax.transAxes)
        hax.text(0.012, 0.36, "Probability analysis",
                 ha="left", va="top", fontsize=13, fontweight="bold",
                 color="#1a3a5c", transform=hax.transAxes)

        parts = [
            ("Rainfall exceeded ", "#444", False),
            (f"{int(threshold)} mm", "#e06b00", True),
            (" in ", "#444", False),
            (f"{int(win_days)} days", "#e06b00", True),
            (" between ", "#444", False),
            (f"{sd_i} {MONTHS[sm-1]}", "#2979c4", True),
            (" and ", "#444", False),
            (f"{ed_i} {MONTHS[em-1]}", "#2979c4", True),
        ]
        comp_fig.canvas.draw()
        renderer = comp_fig.canvas.get_renderer()
        ax_bbox  = hax.get_window_extent(renderer=renderer)
        x_cur = 0.012; y_row = 0.10
        for txt, col, bold in parts:
            t = hax.text(x_cur, y_row, txt, ha="left", va="top", fontsize=10,
                         fontweight="bold" if bold else "normal",
                         color=col, transform=hax.transAxes)
            comp_fig.canvas.draw()
            bb = t.get_window_extent(renderer=renderer)
            x_cur += bb.width / ax_bbox.width
        hax.text(0.988, 0.10, f"{pct_display}% of years",
                 ha="right", va="top", fontsize=13, fontweight="bold",
                 color="#0b1f3a", transform=hax.transAxes)

        cax = comp_fig.add_subplot(spec[1])
        cax.set_facecolor(BG)
        colours2 = [BRIGHT if r >= threshold else MISS for r in annual_max["max_roll_mm"]]
        bars2 = cax.bar(annual_max["season_year"], annual_max["max_roll_mm"],
                        color=colours2, width=0.72, zorder=3, linewidth=0, alpha=0.95)
        for bar, r in zip(bars2, annual_max["max_roll_mm"]):
            if r >= threshold:
                bar.set_edgecolor(BLUE); bar.set_linewidth(0.8)
        cax.axhline(threshold, color=NAVY, lw=1.8, ls="--", zorder=4)
        cax.annotate(f"{int(threshold)} mm",
                     xy=(annual_max["season_year"].max(), threshold),
                     xytext=(6, 4), textcoords="offset points",
                     fontsize=9, color=NAVY, fontweight="bold",
                     va="bottom", ha="left", annotation_clip=False)
        cax.set_xlabel("Season year", fontsize=9.5, color="#3a5a7a", labelpad=5)
        cax.set_ylabel(f"Max {int(win_days)}-day rainfall  (mm)",
                       fontsize=9.5, color="#3a5a7a", labelpad=5)
        cax.tick_params(colors="#3a5a7a", labelsize=8.5)
        if n > 30: cax.tick_params(axis="x", rotation=45)
        cax.grid(True, axis="y", color=GRID, lw=0.9, zorder=0)
        cax.set_axisbelow(True)
        for sp in ["top", "right", "left"]: cax.spines[sp].set_visible(False)
        cax.spines["bottom"].set_color(GRID)
        cax.legend(handles=[
            _Patch(facecolor=BRIGHT, edgecolor=BLUE, linewidth=0.8,
                   label=f"≥ {int(threshold)} mm  ({n_exceed} yrs)"),
            _Patch(facecolor=MISS, label=f"< {int(threshold)} mm  ({n - n_exceed} yrs)"),
        ], fontsize=8.5, loc="upper left", framealpha=0.95, edgecolor=GRID, fancybox=False)
        comp_fig.tight_layout(pad=0.8)

        jpeg_buf = _io.BytesIO()
        comp_fig.savefig(jpeg_buf, format="jpeg", dpi=DPI,
                         bbox_inches="tight", facecolor="white")
        jpeg_buf.seek(0)
        plt.close(comp_fig)

        # ── Display chart on screen ────────────────────────────────────────
        st.pyplot(fig)
        plt.close(fig)

        # ── Download button ────────────────────────────────────────────────
        st.download_button(
            "🖼️  Download summary image",
            data=jpeg_buf,
            file_name=f"rain_summary_{name.replace(' ', '_')}.jpg",
            mime="image/jpeg",
        )

    except Exception as e:
        st.error(f"Analysis error: {e}")
