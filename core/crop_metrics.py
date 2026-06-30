"""
core/crop_metrics.py

PTQ (photothermal quotient) and crop yield outlook calculations for the
Season Tracker prototype.

PTQ = Solar Radiation (MJ/m2/day) / Average Temperature (degC)
    A higher PTQ generally indicates better grain-set conditions in cereals
    (e.g. wheat) — high radiation with cool temperatures. This is the
    classic Fischer (1985) photothermal quotient used around flowering.

Yield outlook (WUE-based, French & Schultz style):
    Yield outlook = (soil water at planting + in-crop rain to date
                      - threshold water) * WUE

    soil_water_at_planting : mm, plant-available soil water at sowing
    in_crop_rain_to_date    : mm, cumulative rain since planting
    threshold_water         : mm, water "lost" to evaporation before
                               crop starts using water effectively
                               (French & Schultz constant, commonly ~100-110mm
                               for wheat but user-configurable here, matching
                               the mockup's "Threshold water" field)
    WUE                      : kg/ha per mm of water used beyond the threshold
"""

import numpy as np
import pandas as pd


def calc_daily_ptq(radiation_mj_m2, tmean_degc):
    """
    Daily photothermal quotient. Returns NaN where tmean <= 0 to avoid
    division blow-ups (PTQ is undefined / not meaningful near or below 0C).
    """
    radiation_mj_m2 = np.asarray(radiation_mj_m2, dtype=float)
    tmean_degc = np.asarray(tmean_degc, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        ptq = np.where(tmean_degc > 0, radiation_mj_m2 / tmean_degc, np.nan)
    return ptq


def calc_mean_ptq_to_date(met_df: pd.DataFrame, plant_date, today) -> float:
    """
    Mean PTQ over the in-crop period to date (plant_date -> today inclusive).
    met_df must have 'radiation' and 'tmean' columns with a DatetimeIndex.
    """
    window = met_df.loc[pd.Timestamp(plant_date):pd.Timestamp(today)]
    if window.empty:
        return float("nan")
    ptq_daily = calc_daily_ptq(window["radiation"].values, window["tmean"].values)
    return float(np.nanmean(ptq_daily))


def calc_yield_outlook(soil_water_at_planting_mm, in_crop_rain_to_date_mm,
                       threshold_water_mm, wue_kg_ha_per_mm):
    """
    Yield outlook = (soil water at planting + in-crop rain to date
                      - threshold water) * WUE

    Returns yield outlook in kg/ha. Clamped at 0 (can't have negative yield
    outlook in this simple linear model — water below threshold means the
    crop hasn't yet reached the point of effective water use).
    """
    available_water = (
        soil_water_at_planting_mm + in_crop_rain_to_date_mm - threshold_water_mm
    )
    yield_outlook = max(0.0, available_water) * wue_kg_ha_per_mm
    return yield_outlook
