"""
Gauge bar + detail chart rendering for the Season Tracker, operating on
core.dashboard_metrics.MetricResult objects.

Visual design (redesigned):
  1. Five-zone overlays (low/below avg/avg/above avg/high) with faint
     boundary lines at x=25, 45, 55, 75 on every bar.
  2. Triangle/wedge marker that sits ABOVE the bar, not cut into it —
     more legible, especially near the edges.
  3. Two visually distinct annotations: metric name + value in one weight,
     band descriptor in a smaller, lighter colour below it.
  4. Graph button styled as a quiet outline, not coral/alarm-red.
  5. Fallow / Crop section grouping handled in app.py (section labels +
     extra gap), not in the figure itself.
  6. Context line below the gauge stack (also in app.py).
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go


# ── Percentile-to-descriptor mapping ────────────────────────────────────────

def percentile_to_descriptor(pct):
    """
    Map a percentile (0-100) to a plain-language band descriptor:
      0-25%   -> "low"
      25-45%  -> "below average"
      45-55%  -> "average"
      55-75%  -> "above average"
      >75%    -> "high"
    """
    if pct is None:
        return None
    if pct <= 25:
        return "low"
    if pct <= 45:
        return "below average"
    if pct <= 55:
        return "average"
    if pct <= 75:
        return "above average"
    return "high"


# Band boundary positions (percentile x-axis, 0-100) and their label colours
ZONE_BOUNDS = [25, 45, 55, 75]
ZONE_LABELS = ["low", "below\navg", "avg", "above\navg", "high"]
ZONE_COLORS = [
    "rgba(180,40,40,0.07)",    # low: very faint red tint
    "rgba(220,140,40,0.07)",   # below average: very faint amber
    "rgba(220,220,40,0.07)",   # average: very faint yellow
    "rgba(80,160,80,0.07)",    # above average: very faint green
    "rgba(20,100,20,0.07)",    # high: very faint dark green
]


# ── Gauge bar figure ─────────────────────────────────────────────────────────

def make_gauge_bar_figure(result, color_low, color_high, height=80):
    """
    Build a horizontal gradient bar with:
      - Five faint zone overlays (low / below avg / avg / above avg / high)
        separated by subtle boundary lines at x=25, 45, 55, 75
      - A solid filled triangle marker sitting ABOVE the bar showing the
        percentile position — more legible than the old rectangle cut into
        the bar, especially near the edges
      - Two annotations: metric name + value (bold, larger) on the bar
        centre, and the band descriptor (smaller, lighter) below it
    """
    fig = go.Figure()

    # ── Gradient background ─────────────────────────────────────────────────
    n_segments = 60
    is_flat = result.not_yet_applicable or result.percentile is None

    for i in range(n_segments):
        t = i / (n_segments - 1)
        color = "#e8e8e8" if is_flat else _interpolate_hex(color_low, color_high, t)
        fig.add_shape(
            type="rect",
            x0=i / n_segments * 100, x1=(i + 1) / n_segments * 100,
            y0=0, y1=1,
            line=dict(width=0), fillcolor=color, layer="below",
        )

    if not is_flat:
        # ── Zone tints (very faint, confirmatory not dominant) ───────────────
        bounds = [0] + ZONE_BOUNDS + [100]
        for z in range(5):
            fig.add_shape(
                type="rect",
                x0=bounds[z], x1=bounds[z + 1],
                y0=0, y1=1,
                line=dict(width=0),
                fillcolor=ZONE_COLORS[z],
                layer="above",
            )

        # ── Zone boundary lines ──────────────────────────────────────────────
        for bx in ZONE_BOUNDS:
            fig.add_shape(
                type="line",
                x0=bx, x1=bx, y0=0, y1=1,
                line=dict(color="rgba(255,255,255,0.55)", width=1.5, dash="dot"),
            )

        # ── Triangle marker: a filled downward-pointing triangle sitting
        #    ABOVE the bar, pointing down to the percentile position ──────────
        pct = result.percentile
        hw = 2.5   # half-width of triangle base in percentile units
        # SVG path: top-left, top-right, then down to point at pct position,
        # all in figure-coordinate space (x=0-100, y=-0.3 to 1.3 extended)
        path = (
            f"M {pct - hw} 1.35 "
            f"L {pct + hw} 1.35 "
            f"L {pct} 1.08 Z"
        )
        fig.add_shape(
            type="path", path=path,
            fillcolor="rgba(0,0,0,0.70)",
            line=dict(width=0),
        )

    # ── Text annotations ─────────────────────────────────────────────────────
    if result.not_yet_applicable:
        # Single greyed-out message
        fig.add_annotation(
            x=50, y=0.5,
            text=f"<i>{result.label} — not yet relevant (before plant date)</i>",
            showarrow=False,
            font=dict(size=12, color="#999999"),
            xanchor="center", yanchor="middle",
        )

    elif result.percentile is not None:
        value_str = (
            f"{result.current_value:.0f} {result.unit}"
            if result.current_value is not None else "—"
        )
        descriptor = percentile_to_descriptor(result.percentile)

        # Line 1: metric name · value  (bold, readable against gradient)
        fig.add_annotation(
            x=50, y=0.62,
            text=f"<b>{result.label}</b>  ·  {value_str}",
            showarrow=False,
            font=dict(size=13.5, color="#1a1a1a"),
            xanchor="center", yanchor="middle",
        )
        # Line 2: band descriptor  (smaller, italic, slightly lighter)
        fig.add_annotation(
            x=50, y=0.22,
            text=f"<i>{descriptor}</i>",
            showarrow=False,
            font=dict(size=11, color="#333333"),
            xanchor="center", yanchor="middle",
        )

    else:
        # Insufficient history or no data
        if result.current_value is not None:
            fig.add_annotation(
                x=50, y=0.62,
                text=f"<b>{result.label}</b>  ·  {result.current_value:.0f} {result.unit}",
                showarrow=False,
                font=dict(size=13.5, color="#1a1a1a"),
                xanchor="center", yanchor="middle",
            )
            fig.add_annotation(
                x=50, y=0.22,
                text=f"<i>only {result.n_comparable_years} comparable years — need more history</i>",
                showarrow=False,
                font=dict(size=10, color="#888888"),
                xanchor="center", yanchor="middle",
            )
        else:
            fig.add_annotation(
                x=50, y=0.5,
                text=f"<b>{result.label}</b>  ·  no data for this period yet",
                showarrow=False,
                font=dict(size=13, color="#1a1a1a"),
                xanchor="center", yanchor="middle",
            )

    fig.update_xaxes(range=[0, 100], visible=False, fixedrange=True)
    fig.update_yaxes(range=[-0.2, 1.55], visible=False, fixedrange=True)
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    return fig


# ── Colour helpers ───────────────────────────────────────────────────────────

def _interpolate_hex(hex_low, hex_high, t):
    low = _hex_to_rgb(hex_low)
    high = _hex_to_rgb(hex_high)
    rgb = tuple(int(low[i] + (high[i] - low[i]) * t) for i in range(3))
    return f"rgb({rgb[0]},{rgb[1]},{rgb[2]})"


def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


# ── Detail chart helpers ─────────────────────────────────────────────────────

def _project_onto_current_dates(series: pd.Series, current_dates: pd.DatetimeIndex) -> pd.Series:
    """Re-index positionally onto current season's calendar dates."""
    n = min(len(series), len(current_dates))
    return pd.Series(series.values[:n], index=current_dates[:n])


# ── Yield projection detail chart ────────────────────────────────────────────

def make_yield_projection_figure(yield_proj):
    """
    Render the yield outlook detail chart: shaded 10-90%ile band across
    the full plant→harvest window, actual trajectory (red) to today,
    projected continuation (orange) to harvest, and conditional inner band.
    """
    fig = go.Figure()

    if yield_proj is None or yield_proj.p10 is None:
        fig.add_annotation(
            x=0.5, y=0.5, xref="paper", yref="paper",
            text="Not enough historical years to build a yield outlook range yet.",
            showarrow=False, font=dict(size=14),
        )
        fig.update_layout(height=300)
        return fig

    unit = "kg/ha"
    hover_fmt = f"%{{x|%d %b}}<br>%{{customdata}}: %{{y:.0f}} {unit}<extra></extra>"

    # 10-90%ile shaded band (outer)
    fig.add_trace(go.Scatter(
        x=yield_proj.p90.index, y=yield_proj.p90.values,
        mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=yield_proj.p10.index, y=yield_proj.p10.values,
        mode="lines", line=dict(width=0), fill="tonexty",
        fillcolor="rgba(99,132,255,0.25)", name="10-90%ile range", hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=yield_proj.p90.index, y=yield_proj.p90.values,
        mode="lines", line=dict(color="rgba(99,132,255,0.55)", width=1),
        name="90%ile", customdata=["90%ile"] * len(yield_proj.p90), hovertemplate=hover_fmt,
    ))
    fig.add_trace(go.Scatter(
        x=yield_proj.p10.index, y=yield_proj.p10.values,
        mode="lines", line=dict(color="rgba(99,132,255,0.55)", width=1),
        name="10%ile", customdata=["10%ile"] * len(yield_proj.p10), hovertemplate=hover_fmt,
    ))

    # Conditional (inner) band
    if yield_proj.cond_p10 is not None and yield_proj.cond_p90 is not None:
        fig.add_trace(go.Scatter(
            x=yield_proj.cond_p90.index, y=yield_proj.cond_p90.values,
            mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=yield_proj.cond_p10.index, y=yield_proj.cond_p10.values,
            mode="lines", line=dict(width=0), fill="tonexty",
            fillcolor="rgba(40,60,180,0.30)", name="10-90%ile range (from today)", hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=yield_proj.cond_p90.index, y=yield_proj.cond_p90.values,
            mode="lines", line=dict(color="rgba(40,60,180,0.5)", width=1, dash="dot"),
            name="90%ile (from today)", customdata=["90%ile (from today)"] * len(yield_proj.cond_p90),
            hovertemplate=hover_fmt,
        ))
        fig.add_trace(go.Scatter(
            x=yield_proj.cond_p10.index, y=yield_proj.cond_p10.values,
            mode="lines", line=dict(color="rgba(40,60,180,0.5)", width=1, dash="dot"),
            name="10%ile (from today)", customdata=["10%ile (from today)"] * len(yield_proj.cond_p10),
            hovertemplate=hover_fmt,
        ))

    # Median line
    if yield_proj.p50 is not None:
        fig.add_trace(go.Scatter(
            x=yield_proj.p50.index, y=yield_proj.p50.values,
            mode="lines", line=dict(color="rgba(40,60,180,0.85)", width=2),
            name="Median", customdata=["Median"] * len(yield_proj.p50), hovertemplate=hover_fmt,
        ))

    # Actual trajectory (red)
    if yield_proj.actual is not None and len(yield_proj.actual) > 0:
        fig.add_trace(go.Scatter(
            x=yield_proj.actual.index, y=yield_proj.actual.values,
            mode="lines", line=dict(color="#d6262c", width=3),
            name="This season (actual)",
            customdata=["Actual"] * len(yield_proj.actual), hovertemplate=hover_fmt,
        ))
        today_x = pd.Timestamp(yield_proj.actual.index[-1]).isoformat()
        fig.add_trace(go.Scatter(
            x=[today_x], y=[float(yield_proj.actual.values[-1])],
            mode="markers+text", marker=dict(color="#d6262c", size=9, line=dict(color="white", width=1)),
            text=["today"], textposition="top center",
            showlegend=False, customdata=["Today"], hovertemplate=hover_fmt,
        ))

    # Projected continuation (orange)
    if yield_proj.projected is not None and len(yield_proj.projected) > 0:
        fig.add_trace(go.Scatter(
            x=yield_proj.projected.index, y=yield_proj.projected.values,
            mode="lines", line=dict(color="#e8932a", width=3),
            name="Projected yield (median path)",
            customdata=["Projected"] * len(yield_proj.projected), hovertemplate=hover_fmt,
        ))
        maturity_x = pd.Timestamp(yield_proj.projected.index[-1]).isoformat()
        fig.add_trace(go.Scatter(
            x=[maturity_x], y=[float(yield_proj.projected.values[-1])],
            mode="markers+text", marker=dict(color="#e8932a", size=9, line=dict(color="white", width=1)),
            text=["maturity"], textposition="top center",
            showlegend=False, customdata=["Maturity"], hovertemplate=hover_fmt,
        ))

    fig.update_layout(
        xaxis_title="Date", yaxis_title=unit,
        height=420,
        margin=dict(l=40, r=20, t=30, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="closest",
    )
    fig.update_xaxes(fixedrange=True, tickformat="%d %b")
    fig.update_yaxes(fixedrange=True)
    return fig


# ── Generic detail chart ─────────────────────────────────────────────────────

def make_detail_figure(result, plant_date=None):
    """
    Detail chart for a MetricResult: historical year trajectories on
    the current season's calendar dates, historical median, current season
    highlighted. Tooltips show date, year, and value (0 decimals) with unit.
    """
    fig = go.Figure()

    if result.not_yet_applicable:
        fig.add_annotation(
            x=0.5, y=0.5, xref="paper", yref="paper",
            text=f"{result.label} is not yet relevant — applies from the plant date onwards.",
            showarrow=False, font=dict(size=14),
        )
        fig.update_layout(height=220, margin=dict(l=20, r=20, t=20, b=20))
        return fig

    if not result.series_by_year or result.current_year not in result.series_by_year:
        fig.add_annotation(
            x=0.5, y=0.5, xref="paper", yref="paper",
            text="No data available for this period.",
            showarrow=False, font=dict(size=14),
        )
        fig.update_layout(height=300)
        return fig

    current = result.series_by_year[result.current_year]
    current_dates = current.index
    unit = result.unit
    hover_fmt = f"%{{x|%d %b}}<br>%{{customdata}}: %{{y:.0f}} {unit}<extra></extra>"

    for y, s in result.series_by_year.items():
        if y == result.current_year:
            continue
        projected = _project_onto_current_dates(s, current_dates)
        fig.add_trace(go.Scatter(
            x=projected.index, y=projected.values,
            mode="lines", line=dict(color="rgba(150,150,150,0.35)", width=1),
            name=str(y), showlegend=False,
            customdata=[str(y)] * len(projected), hovertemplate=hover_fmt,
        ))

    if result.median_series is not None:
        projected_med = _project_onto_current_dates(result.median_series, current_dates)
        fig.add_trace(go.Scatter(
            x=projected_med.index, y=projected_med.values,
            mode="lines", line=dict(color="rgba(60,60,60,0.9)", width=2, dash="dash"),
            name=f"Historical median ({result.n_comparable_years} yrs)",
            customdata=["Median"] * len(projected_med), hovertemplate=hover_fmt,
        ))

    fig.add_trace(go.Scatter(
        x=current.index, y=current.values,
        mode="lines+markers", line=dict(color="#d6604d", width=3), marker=dict(size=4),
        name=f"This season ({result.current_year})",
        customdata=[str(result.current_year)] * len(current), hovertemplate=hover_fmt,
    ))

    # Plant date vertical line (for nitrogen full-season graph)
    if plant_date is not None:
        import pandas as _pd
        fig.add_vline(
            x=_pd.Timestamp(plant_date).timestamp() * 1000,
            line_dash="dash", line_color="#1A4A6E", line_width=1.5,
            annotation_text="  Plant",
            annotation_position="top right",
            annotation_font=dict(color="#1A4A6E", size=11),
        )

    chart_title = result.label if result.label != result.unit else ""

    fig.update_layout(
        title=dict(text=chart_title, font=dict(size=13, color="#1A4A6E"), x=0, pad=dict(l=0)),
        xaxis_title="Date", yaxis_title=unit,
        height=380,
        margin=dict(l=40, r=20, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="closest",
    )
    fig.update_xaxes(fixedrange=True, tickformat="%d %b")
    fig.update_yaxes(fixedrange=True)
    return fig
