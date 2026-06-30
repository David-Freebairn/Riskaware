"""
core/season_metrics.py

Generalised version of 1_Season.py's calendar-aligned historical comparison
logic (build_series), adapted to anchor on the user's actual fallow-start /
plant / harvest dates rather than a fixed "months back from today" window.

Used by the Season Tracker prototype to build:
  - fallow_water_gain   (fallow start -> today,   PERFECT water balance)
  - in_crop_rain        (plant date  -> today,    cumulative rainfall)
  - photothermal_index  (plant date  -> today,    mean PTQ)
for every historical year that has a comparable window, then ranks the
current year's value as a percentile against those historical years.
"""

import numpy as np
import pandas as pd


def days_in_month(y: int, m: int) -> int:
    import calendar
    return calendar.monthrange(y, m)[1]


def build_aligned_series(daily_values: pd.Series, window_start_md, window_end_date,
                          min_comparable_years: int = 3):
    """
    Build a calendar-aligned cumulative series for every historical year,
    using the same (month, day) window as the current season.

    Parameters
    ----------
    daily_values : pd.Series, DatetimeIndex -> daily value (e.g. rain mm,
                   or a daily metric to be cumulative-summed).
    window_start_md : (month, day) tuple — window start, e.g. plant date's
                   (month, day). The year is inferred per historical year.
    window_end_date : date — the *current* season's end-of-window date
                   (e.g. today). Its (month, day) defines the stop point
                   for every year; its year defines the "current" series.
    min_comparable_years : minimum historical years with a long-enough
                   window required to compute a percentile.

    Returns
    -------
    dict with keys:
      series         : {year -> pd.Series of cumulative values, DatetimeIndex}
      current_year   : int
      current_total  : float or None
      pctile         : float or None (0-100)
      comp_years     : list of comparable historical years used
      median_series  : pd.Series (day-by-day median across comparable years,
                        aligned to current season's date index) or None
    """
    start_m, start_d = window_start_md
    end_y = window_end_date.year
    end_m = window_end_date.month
    end_d = window_end_date.day

    lookup = {}
    for idx, val in daily_values.items():
        lookup[(idx.year, idx.month, idx.day)] = val

    data_years = sorted({idx.year for idx in daily_values.index})
    if not data_years:
        return dict(series={}, current_year=end_y, current_total=None,
                    pctile=None, comp_years=[], median_series=None)

    series = {}
    # The "season year" for a window that starts at (start_m, start_d) and
    # may run into the next calendar year is keyed by its START year, except
    # for current season where the relevant identifying year is end_y if the
    # window doesn't cross into a new year. We key every series by the year
    # in which the window *starts*.
    min_data_y = data_years[0]

    for sy in range(min_data_y, end_y + 1):
        # Does this start year's window reach window_end (month,day)?
        # We just walk forward from (sy, start_m, start_d) to the stop date,
        # which is either this same calendar year or the next, depending on
        # whether start_m > end_m (window crosses new year) — for crop
        # in-season windows (plant -> harvest/today) this is rare but handled.
        is_current = (sy == _season_year_for_end(end_y, end_m, end_d, start_m, start_d))

        wy, wm, wd = sy, start_m, start_d
        # Determine stop year: if start month/day is AFTER end month/day,
        # the window must span into the following calendar year.
        crosses_year = (start_m, start_d) > (end_m, end_d)
        stop_y = sy + 1 if crosses_year else sy
        stop_d_this_year = end_d if is_current else min(end_d, days_in_month(stop_y, end_m))

        cum = 0.0
        dates, cums = [], []
        missing_streak = 0
        ok = True

        while True:
            if wy > stop_y:
                break
            if wy == stop_y and wm > end_m:
                break
            if wy == stop_y and wm == end_m and wd > stop_d_this_year:
                break

            val = lookup.get((wy, wm, wd), None)
            if val is None:
                if not is_current:
                    missing_streak += 1
                    if missing_streak > 5:
                        ok = False
                        break
                val = 0.0
            else:
                missing_streak = 0

            cum += val
            dates.append(pd.Timestamp(wy, wm, wd))
            cums.append(cum)

            wd += 1
            if wd > days_in_month(wy, wm):
                wd = 1
                wm += 1
            if wm > 12:
                wm = 1
                wy += 1

        if ok and dates:
            series[sy] = pd.Series(cums, index=dates)

    current_year = _season_year_for_end(end_y, end_m, end_d, start_m, start_d)
    if current_year not in series:
        return dict(series=series, current_year=current_year, current_total=None,
                    pctile=None, comp_years=[], median_series=None)

    current = series[current_year]
    current_total = float(current.iloc[-1])
    n_current = len(current)

    comp_years = [y for y in series if y != current_year and len(series[y]) >= n_current]
    comp_totals = [float(series[y].iloc[n_current - 1]) for y in comp_years]

    if len(comp_years) < min_comparable_years:
        return dict(series=series, current_year=current_year, current_total=current_total,
                    pctile=None, comp_years=comp_years, median_series=None)

    better = sum(1 for t in comp_totals if t > current_total)
    pctile = round((1 - better / len(comp_years)) * 100, 1)

    # Day-by-day median across comparable years, aligned to current dates
    median_vals = []
    for i in range(n_current):
        vals = sorted(float(series[y].iloc[i]) for y in comp_years if len(series[y]) > i)
        if not vals:
            median_vals.append(np.nan)
            continue
        mid = len(vals) // 2
        med = (vals[mid - 1] + vals[mid]) / 2 if len(vals) % 2 == 0 else vals[mid]
        median_vals.append(med)
    median_series = pd.Series(median_vals, index=current.index)

    return dict(series=series, current_year=current_year, current_total=current_total,
                pctile=pctile, comp_years=comp_years, median_series=median_series)


def _season_year_for_end(end_y, end_m, end_d, start_m, start_d):
    """The 'season year' label is the year the window STARTS in."""
    crosses_year = (start_m, start_d) > (end_m, end_d)
    return end_y - 1 if crosses_year else end_y
