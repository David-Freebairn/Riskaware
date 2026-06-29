# sample_data/

This directory contains the bundled Dalby climate dataset used as a
fallback when SILO is unavailable.

## Files

- `dalby_sample.parquet` — real Dalby Post Office (station 41023) daily
  climate data from 1996 onwards, in the same column format as
  `core/silo.ensure_climate_cached` returns.
- `dalby_station.json` — station metadata (id, name, lat, lon, state).
- `.gitkeep` — placeholder so the directory exists in the repo before
  the parquet is generated.

## Generating / refreshing

Run this once locally when SILO is available:

```
cd <repo root>
python fetch_sample_data.py
```

Then commit both output files:

```
git add sample_data/dalby_sample.parquet sample_data/dalby_station.json
git commit -m "Update Dalby sample data"
git push
```

The parquet is ~200-400 KB, well within GitHub's limits.

## When it's used

Only when SILO returns any error (401 Unauthorized, timeout, connection
refused, etc.). The app detects the failure and offers the user a button
to switch to this sample dataset for the current session.
