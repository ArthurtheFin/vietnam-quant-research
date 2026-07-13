# QUARANTINE — pre-backfill (v1) equity OHLCV and derived features

**Do not use these files for any calculation, factor test, or research
report.** They are known to be corrupted for a large, uncatalogued
fraction of the actively-traded universe by the raw/adjusted-close
mixing bug fixed in commit `d12a6ac` (see `BACKFILL_DESIGN_REPORT.md`
Rounds 2-4 and `DATA_BASELINE.md` for full detail).

**Kept only for forensic comparison** — e.g. quantifying how much a
specific symbol's `close`/derived indicators were distorted before vs.
after the fix (see `BACKFILL_DESIGN_REPORT.md` Round 4 / NV3 sanity check
for an example using HPG, TCB, VCB).

## Contents

- `raw_daily_ohlcv/` — the old `data/raw/daily_ohlcv/` directory (per-symbol
  raw OHLCV, moved here verbatim). Superseded by `data/full_history_v2/raw/`.
- `clean_daily_ohlcv.parquet` — old `data/processed/clean_daily_ohlcv.parquet`
  (standardized OHLCV built from the directory above).
- `stock_features.parquet` — old `data/processed/stock_features.parquet`,
  the "existing" dataset referenced throughout `BACKFILL_DESIGN_REPORT.md`.
  Confirmed to carry the ~29-day piecewise raw/adjusted-close corruption
  on at least 75/501 symbols (broad pattern) plus 165/501 with a narrower
  recent-tail version, per the Task 4b quality suite.
- `market_features.parquet` — old `data/processed/market_features.parquet`,
  derived transitively from the stock_features above (market breadth/regime
  computed over the corrupted per-symbol series).

## What replaced these

`scripts/generate_features.py` now reads from `data/full_history_v2/raw/`
(the verified, bug-immune-method backfill — see `DATA_BASELINE.md`) and
writes to the same canonical paths (`data/processed/stock_features.parquet`,
`data/processed/clean_daily_ohlcv.parquet`, `data/processed/market_features.parquet`)
these files used to occupy. Every downstream consumer
(`src/screening/`, `src/alpha/`, `scratch/diagnose_*.py`, etc.) picks up
the new data automatically without needing its own path changes.

## Execution log

This move was described here but not actually performed until **2026-07-13**
(audit gate #6 / NV2 remediation, commit history on `main`). Before that
date `data/processed/stock_features.parquet` etc. were still the
pre-backfill files despite this README — a background daily-update process
kept writing into the legacy `data/raw/daily_ohlcv/` directory, and
`generate_features.py`, though already reading from `full_history_v2/raw`
in code, had not been re-run since the final backfill (see
`SCORE_FORENSIC_REPORT.md` / `critical_findings.md` P0-2 for the forensic
trail). On 2026-07-13 the following were physically moved into this
directory for the first time:

- `data/raw/daily_ohlcv/*.parquet` (567 files) → `raw_daily_ohlcv/`
- `data/processed/clean_daily_ohlcv.parquet` → `clean_daily_ohlcv.parquet`
- `data/processed/stock_features.parquet` → `stock_features.parquet`
- `data/processed/market_features.parquet` → `market_features.parquet`

Immediately after, `scripts/generate_features.py` was re-run against
`data/full_history_v2/raw/` to regenerate the three canonical files fresh.
All path references across the codebase were also consolidated to import
from `src/data/dataset_config.py` (the single source of truth introduced
in this same change) instead of hardcoding these strings — see that
module for the canonical vs. legacy/quarantine path constants, and
`tests/test_dataset_config.py` for the regression test that fails if any
module reads a hardcoded legacy/quarantine path outside of it.
