"""
core/dashboard_metrics.py

Orchestrates the five metrics shown on the Season Tracker dashboard:
  1. fallow_water_gain    — PERFECT water balance, fallow_start -> plant_date
                             (fixed window — does NOT extend past planting,
                             even if "today" is later)
  2. fallow_nitrogen_gain — HowWetN mineralisation, fallow_start -> plant_date
                             (same fixed window as water gain)
  3. in_crop_rain         — cumulative rainfall, plant_date -> today
                             (only computed once today >= plant_date)
  4. photothermal_index   — CUMULATIVE PTQ (running sum), plant_date -> today
                             (only computed once today >= plant_date)
  5. crop_expectation (yield outlook) — French & Schultz style WUE calc
                             (only computed once today >= plant_date)

Each metric returns a percentile rank vs. comparable historical years,
using the calendar-aligned method in core.season_metrics, run once per
metric per historical year using the SAME water-balance/nitrogen engine
as the current year (so it's an apples-to-apples comparison, not just a
raw climate percentile).

Historical comparison years are floored at HIST_FLOOR_YEAR (1996) even if
the underlying climate record goes back further — SILO data quality before
1996 is treated as out of scope for this comparison per user instruction.
"""

from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd

from core.soil import init_sw
from core.waterbalance import daily_water_balance
from core.nitrogen import daily_n_mineralisation
from core.crop_metrics import calc_daily_ptq, calc_yield_outlook
from core.season_metrics import build_aligned_series, _season_year_for_end

HIST_FLOOR_YEAR = 1996


@dataclass
class MetricResult:
    label: str
    unit: str
    current_value: Optional[float]
    percentile: Optional[float]
    n_comparable_years: int
    series_by_year: dict          # {year: pd.Series, DatetimeIndex} for the detail chart
    current_year: int
    median_series: Optional[pd.Series]
    not_yet_applicable: bool = False   # True if metric isn't relevant yet (before planting)


def _empty_result(label, unit, current_year, not_yet_applicable=False):
    return MetricResult(label, unit, None, None, 0, {}, current_year, None, not_yet_applicable)


def _run_water_balance_series(met_window: pd.DataFrame, profile, sw_init_frac, green_cover, total_cover):
    """
    Run the PERFECT water balance over met_window (any contiguous date
    range), returning a DataFrame with sw_total, pasw (per-layer PASW
    summed), and per-day layer-1 SW-above-WP (for nitrogen calc reuse).
    """
    layers = profile.layers
    sw = init_sw(profile, sw_init_frac)
    sumes1 = sumes2 = dsr = 0.0
    records = []
    for dt, row in met_window.iterrows():
        rain = float(row.get("rain", 0.0) or 0.0)
        epan = float(row.get("epan", 0.0) or 0.0)
        if np.isnan(rain):
            rain = 0.0
        if np.isnan(epan):
            epan = 0.0
        out = daily_water_balance(
            sw=sw, layers=layers, soil=profile,
            rain=rain, epan=epan,
            green_cover=green_cover, total_cover=total_cover,
            root_depth_mm=0.0, crop_factor=1.0,
            sumes1=sumes1, sumes2=sumes2, t_since_wet=dsr,
        )
        sw = out["sw"]
        sumes1 = out["sumes1"]
        sumes2 = out["sumes2"]
        dsr = out["t_since_wet"]

        pasw = sum(max(0.0, float(sw[i]) - layers[i].ll_mm) for i in range(len(layers)))
        sw1_above_wp = max(0.0, float(sw[0]) - layers[0].ll_mm)

        records.append({"sw_total": float(sw.sum()), "pasw": pasw, "sw1_above_wp": sw1_above_wp})

    return pd.DataFrame(records, index=met_window.index)


def compute_fallow_water_and_n_gain(climate_df: pd.DataFrame, profile,
                                    fallow_start_md, plant_md, today,
                                    sw_init_frac=0.05, green_cover=0.0, total_cover=0.1,
                                    min_comparable_years=3):
    """
    Fallow water/nitrogen gain over a FIXED window: fallow_start -> plant_date,
    for every historical year (>= HIST_FLOOR_YEAR) that has that window
    available. This window does not extend past planting even if "today"
    is later in the season — fallow accumulation stops once the crop is
    in the ground.

    The "current" season's window only runs to plant_date if today has
    reached or passed planting; if today is still before planting, the
    current-season window runs fallow_start -> today instead (the fallow
    is still in progress and we show what's accumulated so far), but is
    NOT compared against historical full-fallow windows in that case
    (see note below) — comparable years still use their full fallow_start
    -> plant_date window for consistency.

    Returns (water_result: MetricResult, nitrogen_result: MetricResult).
    """
    start_m, start_d = fallow_start_md
    plant_m, plant_d = plant_md
    data_years = sorted({d.year for d in climate_df.index if d.year >= HIST_FLOOR_YEAR})
    if not data_years:
        return (_empty_result("Fallow water gain", "mm", today.year),
                _empty_result("Fallow nitrogen gain", "kg/ha", today.year))

    crosses_to_plant = (start_m, start_d) > (plant_m, plant_d)
    current_season_year = _season_year_for_end(today.year, plant_m, plant_d, start_m, start_d) \
        if today >= _date_from_md(plant_md, today.year, start_md=fallow_start_md) \
        else _season_year_for_end(today.year, today.month, today.day, start_m, start_d)

    pasw_series_by_year = {}
    n_series_by_year = {}

    for sy in range(data_years[0], today.year + 1):
        stop_y = sy + 1 if crosses_to_plant else sy
        is_current = (sy == current_season_year)
        try:
            window_start = pd.Timestamp(sy, start_m, start_d)
            # Historical years always use the FULL fallow_start -> plant_date
            # window. The current year uses fallow_start -> min(today, plant_date)
            # since the fallow can't be simulated past today.
            if is_current:
                plant_date_this_year = pd.Timestamp(stop_y, plant_m, plant_d)
                window_end = min(pd.Timestamp(today), plant_date_this_year)
            else:
                window_end = pd.Timestamp(stop_y, plant_m, plant_d)
        except ValueError:
            continue
        if window_start > window_end:
            continue
        window = climate_df.loc[window_start:window_end]
        if window.empty or len(window) < 5:
            continue
        if not is_current and window["rain"].isna().mean() > 0.1:
            continue

        wb_df = _run_water_balance_series(window, profile, sw_init_frac, green_cover, total_cover)
        pasw_series_by_year[sy] = wb_df["pasw"]

        n_series = []
        cum_n = 0.0
        layer1 = profile.layers[0]
        for i, (dt, row) in enumerate(window.iterrows()):
            tmean = row.get("tmean", np.nan)
            if np.isnan(tmean):
                tmean = window["tmean"].mean()
            daily_n = daily_n_mineralisation(
                sw_layer1_mm=wb_df["sw1_above_wp"].iloc[i],
                layer1_thickness_mm=layer1.thickness,
                airdry_pct=layer1.airdry * 100,
                wilting_point_pct=layer1.ll * 100,
                field_capacity_pct=layer1.dul * 100,
                avgtemp_degc=tmean,
                organic_carbon_pct=profile.organic_carbon_pct,
                carbon_nitrogen_ratio=profile.carbon_nitrogen_ratio,
                nitrogen_mineralisation_coefficient=profile.n_mineralisation_coefficient,
            )
            cum_n += daily_n
            n_series.append(cum_n)
        n_series_by_year[sy] = pd.Series(n_series, index=window.index)

    water_result = _rank_against_history(
        pasw_series_by_year, current_season_year, "Fallow water gain", "mm", min_comparable_years
    )
    nitrogen_result = _rank_against_history(
        n_series_by_year, current_season_year, "Fallow nitrogen gain", "kg/ha", min_comparable_years
    )
    return water_result, nitrogen_result


def _date_from_md(md, year, start_md=None):
    """Helper: build a date from a (month, day) tuple, year-crossing aware
    relative to a start (month, day) if the window could cross a year
    boundary. Used only for picking the right 'current season year'."""
    m, d = md
    try:
        return pd.Timestamp(year, m, d).date()
    except ValueError:
        return pd.Timestamp(year, m, 1).date()


def compute_in_crop_rain(climate_df: pd.DataFrame, plant_md, today, min_comparable_years=3):
    """
    In-crop cumulative rainfall, plant_date -> today, vs. historical years.
    Returns not_yet_applicable=True (no calculation) if today is before
    plant_date for the current season.

    Handles crops that cross the calendar year (e.g. plant Oct, harvest
    Feb): if today's (month, day) falls before plant_md, the relevant
    plant date is in today.year - 1, not today.year — otherwise a
    just-completed crossing-year crop would incorrectly read as
    "not yet applicable" when today is anchored to the harvest date
    (which is chronologically before plant_md within the calendar year).
    """
    plant_m, plant_d = plant_md
    if (today.month, today.day) < (plant_m, plant_d):
        plant_year = today.year - 1
    else:
        plant_year = today.year
    try:
        plant_date_this_year = pd.Timestamp(plant_year, plant_m, plant_d).date()
    except ValueError:
        plant_date_this_year = today
    if today < plant_date_this_year:
        return _empty_result("In-crop rain", "mm", today.year, not_yet_applicable=True)

    rain_floor = climate_df[climate_df.index.year >= HIST_FLOOR_YEAR]["rain"].fillna(0.0)
    result = build_aligned_series(rain_floor, plant_md, today, min_comparable_years)
    return _to_metric_result(result, "In-crop rain", "mm")


def compute_photothermal_index(climate_df: pd.DataFrame, plant_md, today, min_comparable_years=3):
    """
    CUMULATIVE PTQ (running sum, not mean) from plant date to today.
    Returns not_yet_applicable=True (no calculation) if today is before
    plant_date for the current season.

    Handles crossing-year crops the same way as compute_in_crop_rain —
    see that function's docstring for why plant_year can be today.year - 1.
    """
    plant_m, plant_d = plant_md
    if (today.month, today.day) < (plant_m, plant_d):
        plant_year = today.year - 1
    else:
        plant_year = today.year
    try:
        plant_date_this_year = pd.Timestamp(plant_year, plant_m, plant_d).date()
    except ValueError:
        plant_date_this_year = today
    if today < plant_date_this_year:
        return _empty_result("Photothermal quotient", "Cum MJ/m²/°C", today.year, not_yet_applicable=True)

    climate_floor = climate_df[climate_df.index.year >= HIST_FLOOR_YEAR]
    ptq_daily = pd.Series(
        calc_daily_ptq(climate_floor["radiation"].values, climate_floor["tmean"].values),
        index=climate_floor.index,
    ).fillna(0.0)
    result = build_aligned_series(ptq_daily, plant_md, today, min_comparable_years)
    return _to_metric_result(result, "Photothermal quotient", "Cum MJ/m²/°C")


def compute_crop_expectation(in_crop_rain_result: MetricResult, soil_water_at_planting_mm: float,
                             threshold_water_mm: float, wue_kg_ha_per_mm: float,
                             min_comparable_years=3):
    """
    Yield outlook (crop_expectation) derived from in-crop rain result, using
    the same soil-water-at-planting and threshold/WUE for every historical
    year (so the comparison isolates the effect of in-crop rain variability).
    Inherits not_yet_applicable from in_crop_rain_result (no yield outlook
    is meaningful before planting).
    """
    if in_crop_rain_result.not_yet_applicable:
        return _empty_result("Crop yield outlook", "kg/ha", in_crop_rain_result.current_year, not_yet_applicable=True)

    if not in_crop_rain_result.series_by_year:
        return _empty_result("Crop yield outlook", "kg/ha", in_crop_rain_result.current_year)

    yield_series_by_year = {}
    for y, rain_series in in_crop_rain_result.series_by_year.items():
        yield_series_by_year[y] = rain_series.apply(
            lambda r: calc_yield_outlook(soil_water_at_planting_mm, r, threshold_water_mm, wue_kg_ha_per_mm)
        )

    result = {
        "series": yield_series_by_year,
        "current_year": in_crop_rain_result.current_year,
        "current_total": None,
        "pctile": None,
        "comp_years": [],
        "median_series": None,
    }
    cy = in_crop_rain_result.current_year
    if cy in yield_series_by_year:
        current = yield_series_by_year[cy]
        result["current_total"] = float(current.iloc[-1])
        n_current = len(current)
        comp_years = [y for y in yield_series_by_year if y != cy and len(yield_series_by_year[y]) >= n_current]
        if len(comp_years) >= min_comparable_years:
            comp_totals = [float(yield_series_by_year[y].iloc[n_current - 1]) for y in comp_years]
            better = sum(1 for t in comp_totals if t > result["current_total"])
            result["pctile"] = round((1 - better / len(comp_years)) * 100, 1)
            result["comp_years"] = comp_years

            median_vals = []
            for i in range(n_current):
                vals = sorted(float(yield_series_by_year[y].iloc[i]) for y in comp_years if len(yield_series_by_year[y]) > i)
                if vals:
                    mid = len(vals) // 2
                    med = (vals[mid - 1] + vals[mid]) / 2 if len(vals) % 2 == 0 else vals[mid]
                    median_vals.append(med)
                else:
                    median_vals.append(np.nan)
            result["median_series"] = pd.Series(median_vals, index=current.index)

    return _to_metric_result(result, "Crop yield outlook", "kg/ha")


@dataclass
class YieldProjection:
    """
    Extended result for the yield outlook detail chart: a full plant_date
    -> harvest_date 10th/50th/90th percentile band (built from historical
    years' rainfall-to-yield trajectories), the actual season-to-date
    trajectory (plant_date -> today, real data), a projected continuation
    (today -> harvest, using the historical MEDIAN year's day-to-day
    rainfall increments added on top of today's actual value), and a
    CONDITIONAL inner 10th/90th percentile band (today -> harvest) that
    narrows as harvest approaches, since it conditions on what has
    actually happened so far this season rather than only on the planting
    date.
    """
    dates: pd.DatetimeIndex                  # full plant_date -> harvest_date date range
    p10: Optional[pd.Series]                  # unconditional (outer) band, full season
    p50: Optional[pd.Series]
    p90: Optional[pd.Series]
    actual: Optional[pd.Series]               # plant_date -> today, real data
    projected: Optional[pd.Series]             # today -> harvest_date, projected (median path)
    cond_p10: Optional[pd.Series]               # conditional (inner) band, today -> harvest
    cond_p50: Optional[pd.Series]                # conditional median, today -> harvest
    cond_p90: Optional[pd.Series]
    today: object
    harvest_date: object
    n_comparable_years: int


def compute_yield_projection(climate_df: pd.DataFrame, plant_md, harvest_md, today,
                             soil_water_at_planting_mm: float, threshold_water_mm: float,
                             wue_kg_ha_per_mm: float, min_comparable_years=3):
    """
    Build the full plant_date -> harvest_date yield outlook projection used
    by the yield detail chart's 10-90%ile plume + projected continuation.

    Historical years (>= HIST_FLOOR_YEAR) each contribute a full
    plant_date -> harvest_date cumulative-rainfall-derived yield trajectory
    (using the SAME soil_water_at_planting/threshold/WUE inputs as the
    current season, so the spread reflects rainfall variability only).
    Day-by-day 10th/50th/90th percentiles across those years form the band.

    The current season's "actual" trajectory runs plant_date -> today using
    real rainfall. The "projected" trajectory continues from today's actual
    cumulative rain by adding the historical MEDIAN year's day-to-day
    rainfall INCREMENTS (not its absolute level) from today through harvest,
    converting the resulting cumulative rain to yield outlook at each step.
    """
    plant_m, plant_d = plant_md
    harvest_m, harvest_d = harvest_md
    crosses_year = (plant_m, plant_d) > (harvest_m, harvest_d)

    # Anchor plant_date_this_year to whichever crop cycle "today" actually
    # belongs to. For a crop that crosses the calendar year (e.g. plant Oct,
    # harvest Jan), if today's (month, day) falls BEFORE the plant date in
    # calendar terms, today is either still in-crop from a cycle that
    # started LAST year, or already in the next fallow after that cycle's
    # harvest — either way the relevant plant year is today.year - 1, not
    # today.year (which would incorrectly project a future, not-yet-started
    # season). This mirrors _season_year_for_end's logic in season_metrics.py.
    if crosses_year and (today.month, today.day) < (plant_m, plant_d):
        plant_year = today.year - 1
    else:
        plant_year = today.year

    try:
        plant_date_this_year = pd.Timestamp(plant_year, plant_m, plant_d).date()
    except ValueError:
        plant_date_this_year = today

    harvest_year = plant_year + 1 if crosses_year else plant_year
    try:
        harvest_date_this_year = pd.Timestamp(harvest_year, harvest_m, harvest_d).date()
    except ValueError:
        harvest_date_this_year = today

    full_dates = pd.date_range(plant_date_this_year, harvest_date_this_year, freq="D")

    climate_floor = climate_df[climate_df.index.year >= HIST_FLOOR_YEAR]
    rain_floor = climate_floor["rain"].fillna(0.0)
    data_years = sorted({d.year for d in rain_floor.index})

    if not data_years:
        return YieldProjection(full_dates, None, None, None, None, None, None, None, None, today, harvest_date_this_year, 0)

    # Build full plant->harvest cumulative rainfall trajectory for every
    # historical year that has complete data for that window.
    rain_traj_by_year = {}
    for sy in data_years:
        stop_y = sy + 1 if crosses_year else sy
        try:
            w_start = pd.Timestamp(sy, plant_m, plant_d)
            w_end = pd.Timestamp(stop_y, harvest_m, harvest_d)
        except ValueError:
            continue
        if sy == today.year and stop_y >= today.year:
            continue  # current year handled separately (incomplete real data)
        window = rain_floor.loc[w_start:w_end]
        expected_len = (w_end - w_start).days + 1
        if len(window) < expected_len * 0.9:
            continue
        rain_traj_by_year[sy] = window.cumsum()

    n_comparable = len(rain_traj_by_year)
    if n_comparable < min_comparable_years:
        actual = _build_actual_yield_series(climate_df, plant_date_this_year, today,
                                            soil_water_at_planting_mm, threshold_water_mm, wue_kg_ha_per_mm)
        return YieldProjection(full_dates, None, None, None, actual, None, None, None, None, today, harvest_date_this_year, n_comparable)

    # Re-project every year's trajectory onto full_dates positionally, then
    # convert rainfall -> yield outlook, then take day-by-day percentiles.
    n_full = len(full_dates)
    yield_matrix = []
    for sy, traj in rain_traj_by_year.items():
        n = min(len(traj), n_full)
        rain_vals = traj.values[:n]
        yield_vals = np.array([
            calc_yield_outlook(soil_water_at_planting_mm, r, threshold_water_mm, wue_kg_ha_per_mm)
            for r in rain_vals
        ])
        if n < n_full:
            yield_vals = np.concatenate([yield_vals, np.full(n_full - n, np.nan)])
        yield_matrix.append(yield_vals)
    yield_matrix = np.array(yield_matrix)

    p10 = pd.Series(np.nanpercentile(yield_matrix, 10, axis=0), index=full_dates)
    p50 = pd.Series(np.nanpercentile(yield_matrix, 50, axis=0), index=full_dates)
    p90 = pd.Series(np.nanpercentile(yield_matrix, 90, axis=0), index=full_dates)

    actual = _build_actual_yield_series(climate_df, plant_date_this_year, today,
                                        soil_water_at_planting_mm, threshold_water_mm, wue_kg_ha_per_mm)

    # Projected continuation: today -> harvest, using the MEDIAN historical
    # year's day-to-day RAINFALL INCREMENTS added on top of today's actual
    # cumulative rain (not the median yield level itself).
    projected = None
    if actual is not None and len(actual) > 0 and today < harvest_date_this_year:
        median_year_rain = _select_median_year_rain_trajectory(rain_traj_by_year, n_full)
        if median_year_rain is not None:
            today_idx_in_full = (pd.Timestamp(today) - pd.Timestamp(plant_date_this_year)).days
            today_idx_in_full = max(0, min(today_idx_in_full, n_full - 1))

            current_cum_rain = climate_df["rain"].fillna(0.0).loc[
                pd.Timestamp(plant_date_this_year):pd.Timestamp(today)
            ].sum()

            proj_dates = full_dates[today_idx_in_full:]
            proj_rain = [current_cum_rain]
            for i in range(today_idx_in_full + 1, n_full):
                increment = median_year_rain[i] - median_year_rain[i - 1] if i > 0 else 0.0
                increment = max(0.0, increment)
                proj_rain.append(proj_rain[-1] + increment)
            proj_yield = [
                calc_yield_outlook(soil_water_at_planting_mm, r, threshold_water_mm, wue_kg_ha_per_mm)
                for r in proj_rain
            ]
            projected = pd.Series(proj_yield, index=proj_dates)

    # Conditional (inner, narrowing) plume: today -> harvest, 10th/90th
    # percentile band built by taking EACH historical year's own rainfall
    # INCREMENTS from that year's equivalent "today" position onward, and
    # adding them on top of THIS season's actual cumulative rain at today.
    # This conditions on what has actually happened so far, so the spread
    # narrows toward harvest (fewer remaining days = less accumulated
    # uncertainty) rather than reflecting full-season variability from
    # planting, which is what the unconditional p10/p90 above represent.
    cond_p10 = cond_p50 = cond_p90 = None
    if actual is not None and len(actual) > 0 and today < harvest_date_this_year:
        today_idx_in_full = (pd.Timestamp(today) - pd.Timestamp(plant_date_this_year)).days
        today_idx_in_full = max(0, min(today_idx_in_full, n_full - 1))
        current_cum_rain = climate_df["rain"].fillna(0.0).loc[
            pd.Timestamp(plant_date_this_year):pd.Timestamp(today)
        ].sum()

        cond_dates = full_dates[today_idx_in_full:]
        n_cond = len(cond_dates)
        cond_yield_matrix = []
        for sy, traj in rain_traj_by_year.items():
            traj_vals = traj.values
            if len(traj_vals) <= today_idx_in_full:
                continue  # this year's record doesn't reach today's position
            # This year's cumulative rain AT its own equivalent "today"
            base_at_today = traj_vals[today_idx_in_full]
            row = [current_cum_rain]
            for i in range(today_idx_in_full + 1, today_idx_in_full + n_cond):
                if i < len(traj_vals):
                    increment = max(0.0, traj_vals[i] - traj_vals[i - 1])
                else:
                    increment = 0.0
                row.append(row[-1] + increment)
            row = row[:n_cond]
            if len(row) < n_cond:
                row.extend([row[-1]] * (n_cond - len(row)))
            yield_row = np.array([
                calc_yield_outlook(soil_water_at_planting_mm, r, threshold_water_mm, wue_kg_ha_per_mm)
                for r in row
            ])
            cond_yield_matrix.append(yield_row)

        if len(cond_yield_matrix) >= min_comparable_years:
            cond_yield_matrix = np.array(cond_yield_matrix)
            cond_p10 = pd.Series(np.nanpercentile(cond_yield_matrix, 10, axis=0), index=cond_dates)
            cond_p50 = pd.Series(np.nanpercentile(cond_yield_matrix, 50, axis=0), index=cond_dates)
            cond_p90 = pd.Series(np.nanpercentile(cond_yield_matrix, 90, axis=0), index=cond_dates)

    return YieldProjection(full_dates, p10, p50, p90, actual, projected, cond_p10, cond_p50, cond_p90,
                           today, harvest_date_this_year, n_comparable)


def _build_actual_yield_series(climate_df, plant_date, today, soil_water_at_planting_mm,
                               threshold_water_mm, wue_kg_ha_per_mm):
    if today < plant_date:
        return None
    window = climate_df["rain"].fillna(0.0).loc[pd.Timestamp(plant_date):pd.Timestamp(today)]
    if window.empty:
        return None
    cum_rain = window.cumsum()
    yield_vals = [
        calc_yield_outlook(soil_water_at_planting_mm, r, threshold_water_mm, wue_kg_ha_per_mm)
        for r in cum_rain.values
    ]
    return pd.Series(yield_vals, index=cum_rain.index)


def _select_median_year_rain_trajectory(rain_traj_by_year, n_full):
    """
    Pick the historical year whose FINAL cumulative rainfall (full season
    total) is closest to the median of all years' final totals — used as
    the representative "median year" for day-to-day increments in the
    projected continuation.
    """
    finals = {y: traj.iloc[-1] for y, traj in rain_traj_by_year.items()}
    if not finals:
        return None
    sorted_years = sorted(finals, key=lambda y: finals[y])
    median_year = sorted_years[len(sorted_years) // 2]
    traj = rain_traj_by_year[median_year].values
    if len(traj) < n_full:
        traj = np.concatenate([traj, np.full(n_full - len(traj), traj[-1])])
    return traj[:n_full]


def compute_crop_expectation_from_projection(yield_proj, min_comparable_years=3):
    """
    Build the "Crop yield outlook" gauge MetricResult from a YieldProjection.

    Reports THIS SEASON'S OWN projected yield AT HARVEST
    (yield_proj.projected's last value — the same endpoint as the orange
    "maturity" marker on the detail chart) as current_value, rather than
    today's actual cumulative yield outlook to date (a fundamentally
    different and less useful number for a "yield outlook" gauge, since
    in-crop rain typically hasn't fully accumulated yet mid-season).

    The percentile/band descriptor is computed by ranking that
    projected-at-harvest value against the OUTER (unconditional)
    distribution of historical years' yield-at-harvest outcomes
    (yield_proj.p10/p50/p90 at the final date) — answering "is this
    season tracking toward a low/average/high outcome relative to all
    historical years", which is the natural comparator once the reported
    value is itself a forward projection rather than a backward-looking
    actual.
    """
    if yield_proj is None or yield_proj.p10 is None:
        current_year = yield_proj.today.year if yield_proj is not None else None
        return _empty_result("Crop yield outlook", "kg/ha", current_year, not_yet_applicable=False)

    if yield_proj.projected is not None and len(yield_proj.projected) > 0:
        expected_at_harvest = float(yield_proj.projected.iloc[-1])
    elif yield_proj.actual is not None and len(yield_proj.actual) > 0:
        # Past harvest, or no projection available (e.g. right at harvest
        # with zero remaining days) — fall back to the last actual value,
        # which at that point IS the value at harvest.
        expected_at_harvest = float(yield_proj.actual.iloc[-1])
    else:
        expected_at_harvest = None

    if expected_at_harvest is None:
        return _empty_result("Crop yield outlook", "kg/ha", yield_proj.today.year)

    pctile = None
    if yield_proj.n_comparable_years >= min_comparable_years:
        # Reconstruct the per-year distribution at harvest from the
        # already-computed p10/p50/p90 isn't possible directly (those are
        # just three percentiles, not the full per-year set), so rank
        # against the three-point outer distribution as a coarse fallback
        # is insufficiently precise. Instead, approximate the percentile
        # by linear interpolation against the known p10/p50/p90 anchor
        # points at harvest — reasonable for a single forward-looking
        # gauge value without re-deriving the full per-year matrix here.
        p10_h = float(yield_proj.p10.iloc[-1])
        p50_h = float(yield_proj.p50.iloc[-1])
        p90_h = float(yield_proj.p90.iloc[-1])
        pctile = _interpolate_percentile_from_anchors(expected_at_harvest, p10_h, p50_h, p90_h)

    series_by_year = {yield_proj.today.year: yield_proj.projected if yield_proj.projected is not None else yield_proj.actual}
    return MetricResult(
        label="Crop yield outlook",
        unit="kg/ha",
        current_value=expected_at_harvest,
        percentile=pctile,
        n_comparable_years=yield_proj.n_comparable_years,
        series_by_year=series_by_year,
        current_year=yield_proj.today.year,
        median_series=None,
    )


def _interpolate_percentile_from_anchors(value, p10, p50, p90):
    """Piecewise-linear percentile estimate given only the 10th/50th/90th
    percentile anchor points (not the full distribution) — extrapolates
    flatly beyond the 10-90 range rather than guessing further tails."""
    if value <= p10:
        return 10.0
    if value >= p90:
        return 90.0
    if value <= p50:
        if p50 == p10:
            return 50.0
        frac = (value - p10) / (p50 - p10)
        return 10.0 + frac * 40.0
    else:
        if p90 == p50:
            return 50.0
        frac = (value - p50) / (p90 - p50)
        return 50.0 + frac * 40.0


def _rank_against_history(series_by_year, current_year, label, unit, min_comparable_years):
    if current_year not in series_by_year or not series_by_year[current_year].size:
        return MetricResult(label, unit, None, None, 0, series_by_year, current_year, None)

    current = series_by_year[current_year]
    current_total = float(current.iloc[-1])
    n_current = len(current)

    comp_years = [y for y in series_by_year if y != current_year and len(series_by_year[y]) >= n_current]
    if len(comp_years) < min_comparable_years:
        return MetricResult(label, unit, current_total, None, len(comp_years), series_by_year, current_year, None)

    comp_totals = [float(series_by_year[y].iloc[n_current - 1]) for y in comp_years]
    better = sum(1 for t in comp_totals if t > current_total)
    pctile = round((1 - better / len(comp_years)) * 100, 1)

    median_vals = []
    for i in range(n_current):
        vals = sorted(float(series_by_year[y].iloc[i]) for y in comp_years if len(series_by_year[y]) > i)
        if vals:
            mid = len(vals) // 2
            med = (vals[mid - 1] + vals[mid]) / 2 if len(vals) % 2 == 0 else vals[mid]
            median_vals.append(med)
        else:
            median_vals.append(np.nan)
    median_series = pd.Series(median_vals, index=current.index)

    return MetricResult(label, unit, current_total, pctile, len(comp_years), series_by_year, current_year, median_series)


def _to_metric_result(result_dict, label, unit) -> MetricResult:
    return MetricResult(
        label=label,
        unit=unit,
        current_value=result_dict["current_total"],
        percentile=result_dict["pctile"],
        n_comparable_years=len(result_dict["comp_years"]),
        series_by_year=result_dict["series"],
        current_year=result_dict["current_year"],
        median_series=result_dict["median_series"],
    )
