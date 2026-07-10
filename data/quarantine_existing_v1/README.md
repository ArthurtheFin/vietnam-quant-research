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
