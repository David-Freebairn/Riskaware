"""
pages/4_Snapshot.py  —  RiskAware
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Weather & climate snapshot for a selected station.

  • Last full calendar year — daily temperature (max/min + long-term averages)
                            — monthly rainfall vs long-term mean
  • Last 100 years         — annual rainfall with rolling 5/10/30-yr averages

Uses the shared SILO full-record cache from core/silo.py.
Export: JPEG (matplotlib, works on Streamlit Cloud) + interactive HTML.
"""

import io
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import numpy as np
import pandas as pd
import streamlit as st

from core.silo   import ensure_climate_cached, search_stations
from core.styles import apply_styles, save_station, load_station

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Snapshot · RiskAware", layout="wide")
apply_styles()

st.markdown("## 📸 Snapshot")
st.caption("Last year's weather · long-term rainfall")

# ── Station selector (mirrors other pages) ────────────────────────────────────
station = load_station()

# Init session keys
for k, v in [("snap_stations", []), ("snap_query", ""), ("snap_reset", False)]:
    if k not in st.session_state:
        st.session_state[k] = v

if st.session_state.snap_reset:
    st.session_state.snap_reset  = False
    st.session_state.snap_stations = []
    station = None
    save_station(None)

# Show current station + Change button
if station:
    c1, c2 = st.columns([5, 1])
    with c1:
        st.markdown(
            f"**{station['name']}** "
            f"<span style='font-size:0.8rem;color:#888'>"
            f"Station {station.get('number') or station.get('id','')} · {station.get('state','')} · "
            f"{station['lat']:.3f}, {station['lon']:.3f}</span>",
            unsafe_allow_html=True,
        )
    with c2:
        if st.button("Change", key="snap_change"):
            st.session_state.snap_reset = True
            st.rerun()
else:
    # Search form
    with st.form("snap_search"):
        c1, c2 = st.columns([4, 1])
        with c1:
            q = st.text_input("Station", placeholder="e.g. Roma, Cairns, Longreach",
                              label_visibility="collapsed",
                              value=st.session_state.snap_query)
        with c2:
            submitted = st.form_submit_button("Search", use_container_width=True)

    if submitted and q.strip():
        st.session_state.snap_query = q.strip()
        with st.spinner("Searching SILO..."):
            try:
                st.session_state.snap_stations = search_stations(q.strip())
            except Exception as e:
                st.error(f"Search failed: {e}")

    if st.session_state.snap_stations:
        stations = st.session_state.snap_stations
        if len(stations) == 1:
            station = stations[0]
            save_station(station)
            st.session_state.snap_stations = []
            st.rerun()
        else:
            st.markdown(f"**{len(stations)} stations found — select one:**")
            for s in stations:
                meta = (f"ID {s.get('number') or s.get('id','')} · {s.get('state','')} · "
                        f"{s['lat']:.3f}, {s['lon']:.3f}")
                if st.button(f"**{s['name']}** — {meta}", key=f"snap_s_{s.get('number') or s.get('id','')}"):
                    save_station(s)
                    st.session_state.snap_stations = []
                    st.rerun()

# ── Data & charts ─────────────────────────────────────────────────────────────
if not station:
    st.stop()

sid  = station.get("number") or station.get("id")
lat  = station["lat"]
lon  = station["lon"]

today     = date.today()
with st.spinner(f"Loading climate data for {station['name']}…"):
    ensure_climate_cached(sid, lat=lat, lon=lon, session_state=st.session_state)

df = st.session_state["climate_df"].copy()

# Last FULL calendar year
target_year = today.year - 1
available   = sorted(df["year"].unique())
if target_year not in available:
    target_year = available[-1]

dy   = df[df["year"] == target_year].copy()
hist = df[df["year"] < target_year].copy()

# Temperature long-term monthly averages
monthly_tmax = hist.groupby("month")["tmax"].mean()
monthly_tmin = hist.groupby("month")["tmin"].mean()
dy["avg_tmax"] = dy["month"].map(monthly_tmax)
dy["avg_tmin"] = dy["month"].map(monthly_tmin)

MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun",
               "Jul","Aug","Sep","Oct","Nov","Dec"]

monthly_actual = (dy.groupby("month")["rain"]
                    .sum()
                    .reindex(range(1, 13), fill_value=0))
monthly_mean   = (hist.groupby(["year","month"])["rain"]
                      .sum()
                      .groupby("month").mean()
                      .reindex(range(1, 13), fill_value=0))

# Annual totals
annual = (df[df["year"] <= target_year]
           .groupby("year")["rain"].sum()
           .reset_index())
annual.columns = ["year", "total_rain"]

def roll(s, n):
    return s.rolling(n, min_periods=n).mean()

annual["r5"]  = roll(annual["total_rain"], 5)
annual["r10"] = roll(annual["total_rain"], 10)
annual["r30"] = roll(annual["total_rain"], 30)
annual = annual[annual["year"] >= target_year - 99]

# ── Plotly interactive charts (screen) ───────────────────────────────────────
import plotly.graph_objects as go
from plotly.subplots import make_subplots

TITLE_FONT = dict(size=13, color="#444")
AXIS_FONT  = dict(size=11)
GRID_COLOR = "rgba(0,0,0,0.07)"

# Chart 1 — last year
st.subheader(f"Last year ({target_year})")

fig1 = make_subplots(rows=2, cols=1, shared_xaxes=False,
                     row_heights=[0.58, 0.42], vertical_spacing=0.14,
                     subplot_titles=[f"Temperature (°C) — {target_year}",
                                     f"Rainfall (mm) — {target_year} monthly vs long-term mean"])

x = dy.index
fig1.add_trace(go.Scatter(x=x, y=dy["tmax"], name="Daily max",
    line=dict(color="rgba(192,57,43,0.9)", width=1), mode="lines"), row=1, col=1)
fig1.add_trace(go.Scatter(x=x, y=dy["tmin"], name="Daily min",
    line=dict(color="rgba(41,128,185,0.9)", width=1),
    fill="tonexty", fillcolor="rgba(150,180,210,0.12)", mode="lines"), row=1, col=1)
fig1.add_trace(go.Scatter(x=x, y=dy["avg_tmax"], name="Avg max",
    line=dict(color="rgba(230,126,34,1)", width=1.5, dash="dash"), mode="lines"), row=1, col=1)
fig1.add_trace(go.Scatter(x=x, y=dy["avg_tmin"], name="Avg min",
    line=dict(color="rgba(142,68,173,1)", width=1.5, dash="dash"), mode="lines"), row=1, col=1)

fig1.add_trace(go.Bar(x=MONTH_NAMES, y=monthly_actual.values.round(1),
    name=f"{target_year} monthly total", marker_color="rgba(26,82,118,0.75)"), row=2, col=1)
fig1.add_trace(go.Scatter(x=MONTH_NAMES, y=monthly_mean.values.round(1),
    name="Long-term mean", line=dict(color="rgba(26,188,156,0.95)", width=2),
    mode="lines+markers", marker=dict(size=5)), row=2, col=1)

fig1.update_layout(height=500, margin=dict(l=50, r=20, t=50, b=80),
    legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.12, font=AXIS_FONT),
    plot_bgcolor="white", paper_bgcolor="white", hovermode="x unified", bargap=0.15)
for ann in fig1.layout.annotations:
    ann.update(font=TITLE_FONT, x=0.5, xanchor="center")
fig1.update_xaxes(showgrid=False, tickformat="%b", tickfont=AXIS_FONT, row=1, col=1)
fig1.update_xaxes(showgrid=False, tickfont=AXIS_FONT, row=2, col=1)
fig1.update_yaxes(gridcolor=GRID_COLOR, tickfont=AXIS_FONT)
fig1.update_yaxes(title_text="°C", row=1, col=1, title_font=AXIS_FONT)
fig1.update_yaxes(title_text="mm", row=2, col=1, title_font=AXIS_FONT, rangemode="tozero")
st.plotly_chart(fig1, width="stretch", key="snap_fig1")

# Chart 2 — 100-year
st.subheader("Last 100 years rainfall (annual)")

fig2 = go.Figure()
fig2.add_trace(go.Bar(x=annual["year"], y=annual["total_rain"].round(),
    name="Annual", marker_color="rgba(44,62,80,0.45)"))
fig2.add_trace(go.Scatter(x=annual["year"], y=annual["r5"].round(),
    name="5-yr avg", line=dict(color="#e74c3c", width=1.5), mode="lines"))
fig2.add_trace(go.Scatter(x=annual["year"], y=annual["r10"].round(),
    name="10-yr avg", line=dict(color="#e67e22", width=1.5), mode="lines"))
fig2.add_trace(go.Scatter(x=annual["year"], y=annual["r30"].round(),
    name="30-yr avg", line=dict(color="#27ae60", width=2), mode="lines"))
fig2.update_layout(
    title=dict(text="Annual rainfall (mm) — last 100 years",
               x=0.5, xanchor="center", font=TITLE_FONT),
    height=320, margin=dict(l=50, r=20, t=45, b=80),
    legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.2, font=AXIS_FONT),
    plot_bgcolor="white", paper_bgcolor="white",
    hovermode="x unified", bargap=0.1)
fig2.update_xaxes(showgrid=False, dtick=10, tickfont=AXIS_FONT)
fig2.update_yaxes(gridcolor=GRID_COLOR, title_text="mm",
                  title_font=AXIS_FONT, tickfont=AXIS_FONT, rangemode="tozero")
st.plotly_chart(fig2, width="stretch", key="snap_fig2")

# ── Export ────────────────────────────────────────────────────────────────────
st.divider()

meta_str = (f"Station {sid} · {station.get('state','')} · "
            f"{lat:.3f}, {lon:.3f}")
safe_name = station["name"].replace(" ", "_")

def _build_jpeg() -> io.BytesIO:
    C = dict(
        tmax="tab:red", tmin="tab:blue", fill="lightsteelblue",
        avg_tmax="#e67e22", avg_tmin="#8e44ad",
        rain_bar="#1a5276", rain_mean="#1abc9c",
        annual_bar="#7f8c8d", r5="#e74c3c", r10="#e67e22", r30="#27ae60",
    )
    fig = plt.figure(figsize=(14, 14), dpi=120, facecolor="white")
    fig.suptitle(f"{station['name']}  ·  {meta_str}",
                 fontsize=13, y=0.98, color="#333")

    gs = gridspec.GridSpec(3, 1, figure=fig,
                           height_ratios=[2.2, 1.6, 2.8],
                           hspace=0.42, top=0.94, bottom=0.08,
                           left=0.07, right=0.97)

    # Panel 1 — Temperature
    ax1 = fig.add_subplot(gs[0])
    xd  = dy.index
    ax1.fill_between(xd, dy["tmin"], dy["tmax"],
                     color=C["fill"], alpha=0.35, linewidth=0)
    ax1.plot(xd, dy["tmax"],     color=C["tmax"],     lw=0.8, label="Daily max")
    ax1.plot(xd, dy["tmin"],     color=C["tmin"],     lw=0.8, label="Daily min")
    ax1.plot(xd, dy["avg_tmax"], color=C["avg_tmax"], lw=1.4, ls="--", label="Avg max")
    ax1.plot(xd, dy["avg_tmin"], color=C["avg_tmin"], lw=1.4, ls="--", label="Avg min")
    ax1.set_title(f"Temperature (°C) — {target_year}", fontsize=11, pad=6, color="#444")
    ax1.set_ylabel("°C", fontsize=10)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator())
    ax1.set_xlim(xd[0], xd[-1])
    ax1.tick_params(labelsize=9)
    ax1.grid(axis="y", color="0.92", linewidth=0.7)
    ax1.spines[["top","right"]].set_visible(False)

    # Panel 2 — Rainfall monthly
    ax2  = fig.add_subplot(gs[1])
    xi   = np.arange(12)
    ax2.bar(xi, monthly_actual.values, color=C["rain_bar"],
            alpha=0.85, label=f"{target_year} monthly total", zorder=2)
    ax2.plot(xi, monthly_mean.values, color=C["rain_mean"],
             lw=2, marker="o", ms=4, label="Long-term mean", zorder=3)
    ax2.set_title(f"Rainfall (mm) — {target_year} monthly vs long-term mean",
                  fontsize=11, pad=6, color="#444")
    ax2.set_ylabel("mm", fontsize=10)
    ax2.set_xticks(xi)
    ax2.set_xticklabels(MONTH_NAMES, fontsize=9)
    ax2.set_ylim(bottom=0)
    ax2.tick_params(labelsize=9)
    ax2.grid(axis="y", color="0.92", linewidth=0.7)
    ax2.spines[["top","right"]].set_visible(False)

    # Panel 3 — Annual
    ax3 = fig.add_subplot(gs[2])
    ax3.bar(annual["year"], annual["total_rain"],
            color=C["annual_bar"], alpha=0.55, label="Annual", zorder=2)
    ax3.plot(annual["year"], annual["r5"],  color=C["r5"],  lw=1.4, label="5-yr avg",  zorder=3)
    ax3.plot(annual["year"], annual["r10"], color=C["r10"], lw=1.4, label="10-yr avg", zorder=3)
    ax3.plot(annual["year"], annual["r30"], color=C["r30"], lw=2.0, label="30-yr avg", zorder=3)
    ax3.set_title("Annual rainfall (mm) — last 100 years",
                  fontsize=11, pad=6, color="#444")
    ax3.set_ylabel("mm", fontsize=10)
    ax3.set_ylim(bottom=0)
    ax3.tick_params(labelsize=9)
    ax3.grid(axis="y", color="0.92", linewidth=0.7)
    ax3.spines[["top","right"]].set_visible(False)

    # Unified legend
    legend_elements = [
        Line2D([0],[0], color=C["tmax"],     lw=1.2, label="Daily max"),
        Line2D([0],[0], color=C["tmin"],     lw=1.2, label="Daily min"),
        Line2D([0],[0], color=C["avg_tmax"], lw=1.4, ls="--", label="Avg max"),
        Line2D([0],[0], color=C["avg_tmin"], lw=1.4, ls="--", label="Avg min"),
        Patch(facecolor=C["rain_bar"],   alpha=0.85, label=f"{target_year} monthly total"),
        Line2D([0],[0], color=C["rain_mean"], lw=1.8, marker="o", ms=4, label="Long-term mean"),
        Patch(facecolor=C["annual_bar"], alpha=0.55, label="Annual"),
        Line2D([0],[0], color=C["r5"],  lw=1.4, label="5-yr avg"),
        Line2D([0],[0], color=C["r10"], lw=1.4, label="10-yr avg"),
        Line2D([0],[0], color=C["r30"], lw=2.0, label="30-yr avg"),
    ]
    fig.legend(handles=legend_elements, loc="lower center", ncol=5,
               fontsize=9, frameon=False, bbox_to_anchor=(0.5, 0.01))

    buf = io.BytesIO()
    fig.savefig(buf, format="jpeg", dpi=150,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf

col1, col2 = st.columns(2)

with col1:
    with st.spinner("Generating JPEG…"):
        jpeg_buf = _build_jpeg()
    st.download_button(
        "⬇ Download snapshot (JPEG)",
        data=jpeg_buf,
        file_name=f"{safe_name}_{target_year}_snapshot.jpg",
        mime="image/jpeg",
        width="stretch",
    )

with col2:
    # Interactive HTML — combined figure
    fig_c = make_subplots(rows=3, cols=1,
                          row_heights=[0.33, 0.27, 0.40],
                          vertical_spacing=0.07,
                          subplot_titles=[
                              f"Temperature (°C) — {target_year}",
                              f"Rainfall (mm) — {target_year} monthly vs long-term mean",
                              "Annual rainfall (mm) — last 100 years"])
    for tr in fig1.data[:4]:
        t = tr.__class__(**{k: v for k, v in tr.to_plotly_json().items()
                            if k not in ("xaxis","yaxis")})
        fig_c.add_trace(t, row=1, col=1)
    for tr in fig1.data[4:]:
        t = tr.__class__(**{k: v for k, v in tr.to_plotly_json().items()
                            if k not in ("xaxis","yaxis")})
        fig_c.add_trace(t, row=2, col=1)
    for tr in fig2.data:
        t = tr.__class__(**{k: v for k, v in tr.to_plotly_json().items()
                            if k not in ("xaxis","yaxis")})
        fig_c.add_trace(t, row=3, col=1)
    fig_c.update_layout(
        height=1150,
        title=dict(text=f"{station['name']}  ·  {meta_str}",
                   x=0.5, xanchor="center", font=dict(size=14, color="#333")),
        margin=dict(l=65, r=30, t=70, b=110),
        plot_bgcolor="white", paper_bgcolor="white",
        bargap=0.15,
        legend=dict(orientation="h", x=0.5, xanchor="center",
                    y=-0.07, font=dict(size=11)),
        showlegend=True)
    for ann in fig_c.layout.annotations:
        ann.update(font=TITLE_FONT, x=0.5, xanchor="center")
    fig_c.update_xaxes(showgrid=False, tickfont=AXIS_FONT)
    fig_c.update_yaxes(gridcolor=GRID_COLOR, tickfont=AXIS_FONT)
    fig_c.update_xaxes(tickformat="%b", row=1, col=1)
    fig_c.update_yaxes(title_text="°C", row=1, col=1, title_font=AXIS_FONT)
    fig_c.update_yaxes(title_text="mm", row=2, col=1,
                       title_font=AXIS_FONT, rangemode="tozero")
    fig_c.update_yaxes(title_text="mm", row=3, col=1,
                       title_font=AXIS_FONT, rangemode="tozero")
    fig_c.update_xaxes(dtick=10, row=3, col=1)

    html_bytes = fig_c.to_html(full_html=True, include_plotlyjs="cdn").encode()
    st.download_button(
        "⬇ Download interactive HTML",
        data=io.BytesIO(html_bytes),
        file_name=f"{safe_name}_{target_year}_snapshot.html",
        mime="text/html",
        width="stretch",
    )
    st.caption("Interactive version — hover, zoom, and use the 📷 icon to save individual charts.")
