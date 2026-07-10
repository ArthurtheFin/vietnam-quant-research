# DATA_BASELINE — data/full_history_v2, the new price/volume dataset baseline

**Required citation**: any factor-test, backtest, or research report produced
from this point forward must cite `data/full_history_v2/raw/` (fetched
2026-07-09/10, code commit `2ebd2b0` + the Task 1 fix `d12a6ac`) as its price
data source, and note whether it has been reconciled against or replaces
`data/processed/stock_features.parquet` — see the caveats below before
assuming the two are interchangeable.

Full derivation, root-cause analysis, and verification methodology: see
`BACKFILL_DESIGN_REPORT.md` (Rounds 1-4). This document is the operational
summary for consumers of the data, not a repeat of that investigation.

## Dataset identity

| | |
|---|---|
| Path | `data/full_history_v2/raw/{symbol}.parquet` (501 files) + `manifest.json` + `quality_report.csv` |
| Fetch method | Single direct `get_daily_ohlc` call per symbol, `page_size=1000`, `max_pages=10` (primary/adjusted SSI FCData endpoint; deliberately never uses the chunked `fetch_symbol_history`/fallback path) |
| Fetch window | 2026-07-09 15:31 UTC → 2026-07-09 16:51 UTC (main run), + supplementary re-fetch pass same day for 48 symbols (see caveats) |
| Requested date range | 2020-01-01 → 2026-07-06 (2026-07-10 for the 48 supplemented symbols) |
| Code commit | `2ebd2b0` (includes the Task 1 fix `d12a6ac`: `_normalize_daily_ohlc_response` now correctly maps `closepriceadjusted` → `close` on fallback-sourced chunks, and derives adjusted `open`/`high`/`low` consistently — see BACKFILL_DESIGN_REPORT.md Round 3) |
| Symbols | 501 (all currently-listed HOSE/HNX/UPCOM symbols per `data/processed/stock_features.parquet`'s current universe) |
| Total rows | 714,627 (mean 1,426/symbol, median 1,608, min 100 [very recent/thin IPOs], max 1,622 [full 2020-01-02→2026-07-06 coverage]) |
| Size on disk | 33 MB |
| Errors | 0/501 (0 failed fetches, 0 empty responses) |

**Market breakdown**: HOSE 394, UPCOM 61 (+3 more resolved via `data/raw/securities/UPCOM.parquet` — AMD, ART, ASA), HNX 41 (+2 more resolved via `data/raw/securities/HOSE.parquet` — KPF, PSH). 5 symbols have no `market` value anywhere in `data/processed/stock_features.parquet`'s history; resolved via the raw securities-listing fallback files.

## Verification summary (full detail: BACKFILL_DESIGN_REPORT.md Round 4)

- **Fetch correctness**: mechanism-proven via Task 3's 20-symbol pilot —
  data fetched through this exact method matched an independent bug-immune
  oracle at ratio = 1.0 exactly for all 20 pilot symbols (only
  discrepancies were shared, identical zero-price halt days on both
  sides). The full 501-symbol run uses the identical method.
- **Session coverage**: of 208/501 symbols that showed a raw gap against
  an idealized VNINDEX trading-calendar check, **all 208 are explained and
  are not defects**: 160 are genuine market halts/suspensions (this
  dataset matches `data/processed/stock_features.parquet` exactly on
  those gaps), and 48 are zero-matched-volume "no real trade" days that
  `get_daily_ohlc` correctly omits but the older dataset pads in with a
  flat, unchanged reference price (confirmed directly via
  `get_daily_stock_price`, e.g. ATS held an identical 27,400 price with
  `totalmatchvol=0` across an 8-day span existing shows as "trading
  days"). **True unexplained coverage defects: 0/501.**
- **Magnitude sanity**: 455/501 clean; the 46 flagged are securities
  firms with genuine multi-year traded-value growth (VN brokerage-sector
  boom), not units/scale errors.
- **Outlier scan**: 227 outlier-days (|return| > 20%) across the universe
  — expected real corporate actions/halts, handled downstream by the
  existing G4 mechanism, not a data defect.

## Open caveats (do not treat as resolved)

1. **`data/processed/stock_features.parquet` (current production data) is
   corrupted for a large, previously-unknown-in-scope fraction of the
   actively-traded universe.** The raw/adjusted-close mixing bug (fixed in
   commit `d12a6ac`) silently corrupted `close`/`open`/`high`/`low` on any
   ~29-day chunk where the daily-update pipeline's coverage dipped below
   80% and triggered the (until-now-buggy) fallback endpoint. Originally
   found on HPG/TCB only; **this backfill's quality suite found the same
   signature on the majority of top-liquidity blue chips checked**
   (VCB, TCB, MBB, HDB, BID, VNM, MWG, VIC, and more — 75/501 symbols show
   the broad multi-chunk pattern, another 165/501 show a narrower
   recent-tail version from ongoing daily updates). **`data/full_history_v2`
   is not yet merged into `data/processed/` — any code still reading
   `data/processed/stock_features.parquet` directly is reading data known
   to be wrong for a large, uncatalogued subset of symbols until that
   merge happens.**
2. **Survivorship bias, unresolved** (carried over from `DATA_AUDIT_REPORT.md`
   and Round 1 Task 2): the 501-symbol universe is "symbols listed today,
   backfilled to 2020" — any company delisted, merged away, or suspended
   indefinitely since 2020 is invisible to this dataset regardless of how
   far back it's backfilled. This inflates the apparent quality of any
   factor found to predict "explosive move" or similar, since the
   comparison population silently excludes names that had matching
   characteristics but disappeared from today's listing.
3. **Zero-volume/no-trade day handling is a real definitional choice, not
   a bug, but changes downstream session counts for illiquid names**: this
   dataset (via `get_daily_ohlc`) reports only sessions with actual matched
   volume; the older dataset pads in flat-price, zero-volume placeholder
   rows for very illiquid symbols. Code that assumes "one row per calendar
   trading day" for thin/micro-cap names will see fewer rows here than
   against `data/processed/`. Affects at least 48 symbols identified so
   far, likely more among the long tail not specifically checked.
4. **`update_symbol_history` (ongoing daily incremental updates) now runs
   the fixed normalization code** (same commit, same function) — future
   incremental updates should no longer reintroduce the raw/adjusted-close
   corruption. **Not separately re-verified with a live incremental run
   this round** — worth confirming the next time a daily update actually
   executes.
5. **GEE has a small, unexplained 9-day gap** (2023-01-16 to 2024-07-23,
   scattered, not the recent-tail zero-volume pattern) not investigated
   further — low priority given GEE's overall coverage is otherwise clean
   (1,049 rows, listed since 2022-03-08).
6. **This dataset has not been run through `generate_features.py` or
   merged into `data/processed/`.** It is raw OHLCV only
   (`symbol, market, tradingdate, close, open, high, low, volume, value,
   date`), not features. Any consumer needs the standard feature pipeline
   applied first.
