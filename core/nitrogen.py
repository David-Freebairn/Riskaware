"""
core/nitrogen.py

Daily soil nitrogen mineralisation during fallow, ported from DHM
Environmental Software Engineering's HowWetN engine
(A4_HowWetN_Engine.cs, CalculateN method).

Ported with permission — user has confirmed DHM client/licensee status
authorising this port into RiskAware. Original copyright notice:

    DHM Environmental Software Engineering Pty. Ltd. Copyright 2011.
    Per the original file: "Where permission has been granted to modify
    this file, changes must be clearly identified... and a description of
    the changes (including who has made the changes) must be included."

Change description: ported from C# (CliMate HowWetN engine) to Python by
Claude (Anthropic) for David Freebairn, June 2026, as part of the RiskAware
Season Tracker prototype. Logic translated as directly as possible from the
original CalculateN() method; variable names kept close to the original
for traceability. Operates on layer-1 soil water only, exactly as the
original (comment in source: "All calculated in first layer").

Model summary
-------------
Each day, mineralisable N is released from a potential pool (derived from
soil organic carbon and C:N ratio) at a rate limited by the SLOWER of two
0-1 factors:
  - moistfactor : layer-1 soil water relative to field capacity / wilting point
  - tempfactor  : linear function of mean daily air temperature

  Org_n     = OrganicCarbon / CarbonNitrogenRatio            (if C:N != 0)
  potm      = (Org_n / 100) * 200 * 10 * 1000
  moistfactor = clip( soilwater_pct / (field_capacity_pct - wilting_point_pct), 0, 1 )
  tempfactor  = clip( 0.035 * avgtemp_C - 0.1, 0, 1 )
  multiplier  = min(moistfactor, tempfactor)
  daily_N_release = multiplier * NitrogenMineralisationCoefficient * potm

TotalN accumulates daily_N_release over the period (mg N / unit area per
the original units — see note in calc_fallow_nitrogen_gain below on units,
which were not fully disambiguated in the source and should be checked
against a known CliMate/HowLeaky result before relying on absolute values).
"""

import numpy as np


def daily_n_mineralisation(
    sw_layer1_mm: float,
    layer1_thickness_mm: float,
    airdry_pct: float,
    wilting_point_pct: float,
    field_capacity_pct: float,
    avgtemp_degc: float,
    organic_carbon_pct: float,
    carbon_nitrogen_ratio: float,
    nitrogen_mineralisation_coefficient: float,
) -> float:
    """
    One day's nitrogen mineralisation release, layer 1 only.

    sw_layer1_mm         : layer-1 soil water (mm), relative to wilting point
                            (i.e. SoilWater_rel_wp[0] in the original — NOT
                            absolute soil water; this is sw - ll_mm if your
                            sw array is stored in absolute mm).
    layer1_thickness_mm  : thickness of layer 1 (mm) — used to convert
                            sw_layer1_mm to a %-of-layer-depth figure exactly
                            as the original (`depth[1]` in the C# refers to
                            the cumulative depth to bottom of layer 1).
    airdry_pct, wilting_point_pct, field_capacity_pct : layer-1 soil
                            parameters as %vol (0-100), straight from the
                            .soil XML (InSituAirDryMoist, WiltingPoint,
                            FieldCapacity for layer 1).
    avgtemp_degc          : mean daily air temperature (tmax+tmin)/2.
    organic_carbon_pct, carbon_nitrogen_ratio, nitrogen_mineralisation_coefficient :
                            soil chemistry parameters — OrganicCarbon,
                            CarbonNitrogenRatio, NitrateMineralisationCoefficient
                            from the .soil XML (not currently parsed by
                            core/soil_xml.py — see note below).

    Returns daily N release for layer 1 (same units as the original engine;
    not independently re-derived here — see module docstring caveat).
    """
    soilwater_percent = (sw_layer1_mm / layer1_thickness_mm) * 100.0 if layer1_thickness_mm > 0 else 0.0

    org_n = (
        organic_carbon_pct / carbon_nitrogen_ratio
        if abs(carbon_nitrogen_ratio) > 1e-6
        else 0.0
    )
    potm = (org_n / 100.0) * 200.0 * 10.0 * 1000.0

    if soilwater_percent > 0:
        denom = field_capacity_pct - wilting_point_pct
        moistfactor = 0.0 if denom == 0 else max(0.0, min(1.0, soilwater_percent / denom))
    else:
        moistfactor = 0.0

    tempfactor = max(0.0, min(1.0, 0.035 * avgtemp_degc - 0.1))

    multiplier = min(moistfactor, tempfactor)
    daily_release = multiplier * nitrogen_mineralisation_coefficient * potm
    return daily_release


def run_n_mineralisation_series(met_df, sw_layer1_series, layer1_thickness_mm,
                                airdry_pct, wilting_point_pct, field_capacity_pct,
                                organic_carbon_pct, carbon_nitrogen_ratio,
                                nitrogen_mineralisation_coefficient):
    """
    Run the daily mineralisation model over a date-indexed climate frame
    and a matching layer-1 soil-water-above-wilting-point series, returning
    a cumulative N series (same index).

    met_df            : DataFrame with 'tmean' column, DatetimeIndex
    sw_layer1_series  : array-like, layer-1 soil water ABOVE wilting point
                        (mm), same length/order as met_df — i.e.
                        max(0, sw[0] - layers[0].ll_mm) from the water
                        balance output for each day.
    """
    tmean = met_df["tmean"].fillna(met_df["tmean"].mean()).values
    sw1 = np.asarray(sw_layer1_series, dtype=float)
    n = len(tmean)
    cumulative = np.zeros(n)
    total = 0.0
    for i in range(n):
        daily = daily_n_mineralisation(
            sw_layer1_mm=sw1[i],
            layer1_thickness_mm=layer1_thickness_mm,
            airdry_pct=airdry_pct,
            wilting_point_pct=wilting_point_pct,
            field_capacity_pct=field_capacity_pct,
            avgtemp_degc=tmean[i],
            organic_carbon_pct=organic_carbon_pct,
            carbon_nitrogen_ratio=carbon_nitrogen_ratio,
            nitrogen_mineralisation_coefficient=nitrogen_mineralisation_coefficient,
        )
        total += daily
        cumulative[i] = total
    import pandas as pd
    return pd.Series(cumulative, index=met_df.index, name="cumulative_n")
