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
| Fetch window | 2026-07-09 15:31 UTC → 2026-07-09 16:51 UTC (main run), + supplementary re-fetch pass same day for 48 symbols, **+ full-universe sync 2026-07-13 (see "Sync to a common date" below — closes the gap between these two original batches)** |
| Requested date range | 2020-01-01 → 2026-07-06 (2026-07-10 for the 48 supplemented symbols); **now current through 2026-07-13 for 441/501 symbols after the sync** |
| Code commit | `2ebd2b0` (includes the Task 1 fix `d12a6ac`: `_normalize_daily_ohlc_response` now correctly maps `closepriceadjusted` → `close` on fallback-sourced chunks, and derives adjusted `open`/`high`/`low` consistently — see BACKFILL_DESIGN_REPORT.md Round 3). Sync commit: see PUSH_REVIEW.md's 2026-07-13 price-sync entry. |
| Symbols | 501 (all currently-listed HOSE/HNX/UPCOM symbols per `data/processed/stock_features.parquet`'s current universe) |
| Total rows | 716,725 as of the 2026-07-13 sync (mean 1,431/symbol, median 1,613, min 100, max 1,627 [full 2020-01-02→2026-07-13 coverage]) |
| Size on disk | 47 MB |
| Errors | 0/501 (0 failed fetches, 0 empty responses) across both the original backfill and the 2026-07-13 sync |

### Sync to a common date (2026-07-13)

The original backfill's two-batch fetch window (above) left 411/501 symbols
capped at 2026-07-06 and 28 capped at 2026-07-09, with no mechanism to keep
the universe current afterward -- root-caused in
`audit/ELIGIBILITY_GATE_STALE_DATA_DIAGNOSIS.md` as the reason the
eligibility gate rejected 100% of candidates (`data_age_days` measured
against a 28-symbol outlier's max date). Ran `scripts/update_prices_daily.py
--universe` (new script, see PUSH_REVIEW.md for the operating procedure) to
close this: single-call `get_daily_ohlc` per symbol from each symbol's own
existing max(date) through the live-detected latest VNINDEX trading date
(2026-07-13), merged in (existing history before the re-fetch window
untouched, de-duplicated by date). 501/501 symbols attempted, 0 fetch
errors, 2,584 new rows total.

**Result**: 441/501 symbols (88%) now share max(date) = 2026-07-13. The
remaining 60 split into two groups, both confirmed via this same live
fetch through today (not a stale snapshot):
- **42 symbols, 3-10 calendar days behind** -- thin/illiquid names with no
  matched-volume session in the last 1-2 trading days per the `get_daily_ohlc`
  "real sessions only" convention (caveat #3 below), not a fetch defect.
- **18 symbols, 12-1,634 days behind** -- ASA (last trade 2022-01-21), ART
  (2022-11-18), AMD (2023-03-08), KPF (2025-02-25), PSH (2025-03-11), ATB
  (2025-05-30), TCD/BCG (2025-10-08), BBC (2026-01-15), SVI (2026-02-13),
  ARM (2026-03-16), LGC (2026-04-29), APL (2026-06-24), SSC/ACS (2026-06-29),
  ATS (2026-06-30), ADC/TTE (2026-07-01). A live fetch requesting each
  symbol's full gap window through 2026-07-13 returned no rows past their
  existing max date, i.e. these are confirmed (as of today, not inferred)
  to have had zero matched-volume trading sessions since that date --
  consistent with long-term suspension or a genuinely dead market for the
  shares, not a data-collection gap. Not independently verified against an
  official delisting/suspension registry (no such source available to this
  pipeline) -- treat as "confirmed inactive in the price feed," not
  "officially delisted."

### Point-in-time trading_status table (first step toward Gate #3, not a full solution)

audit/PATH_TO_100.md Universe/Eligibility item: `src/validation/trading_status.py`
now maintains an append-only, point-in-time table
(`data/full_history_v2/trading_status.parquet`) classifying every symbol's
own gap-to-latest-trading-date into `ACTIVE` (<=2 days), `STALE_SHORT` (3-10
days, thin/illiquid but real), or `INACTIVE_LONG` (>10 days) -- the exact
thresholds that fell out naturally from the 2026-07-13 sync above (42
symbols clustered 3-10 days, the next was 12). Updated by
`scripts/update_prices_daily.py` on every run; a new row is appended only
when a symbol's status actually changes, so `status_as_of(date)` can
reconstruct what was known at any past point without the table growing
unboundedly. The eligibility gate (`src/screening/final_watchlist.py::apply_eligibility_gate`)
now rejects `INACTIVE_LONG` symbols with that reason, sourced live from this
table (`excluded_symbols_by_status()`) -- **not a hardcoded symbol list**.
Current classification: 441 ACTIVE, 42 STALE_SHORT, 18 INACTIVE_LONG (ASA,
ART, AMD, KPF, PSH, ATB, TCD, BCG, BBC, SVI, ARM, LGC, APL, SSC, ACS, ATS,
ADC, TTE — same 18 identified in the sync above). These 18 symbols'
**historical price data is kept, not deleted** -- only excluded from the
*current* eligible universe via status, so they remain available for any
backtest that correctly reconstructs point-in-time eligibility later.

**This is explicitly a first step, not Gate #3's solution.** It only tracks
symbols that are already in today's listed-symbol universe and have gone
quiet -- it still cannot see a symbol that was delisted/merged/suspended
*before* it would have entered `data/full_history_v2`'s symbol list at all
(the core survivorship-bias gap P0-1 describes). A real point-in-time
universe still needs an external historical listing/delisting source.

### Coverage-ratio suspension proxy (audit PATH_TO_100.md Universe/Eligibility item)

`src/validation/trading_status.py::compute_coverage_ratio` adds a second,
complementary signal to the gap-based status above: the ratio of observed
trading days to expected trading sessions (holiday-aware, same
`config/vn_market_holidays.csv`) over the last 60 sessions. A day with no
row is a day with no matched trade -- valid for a genuinely low-liquidity
name (DATA_BASELINE.md caveat #3), so this is a liquidity signal, not by
itself a suspension one.

**Empirically checked before wiring this in**: STALE_SHORT (real thin
trading) and INACTIVE_LONG symbols' 60-session coverage ratios *overlap*
(STALE_SHORT ranges 0.12-0.95, INACTIVE_LONG 0.0-0.40) -- coverage ratio
alone cannot reliably separate "thin but real" from "suspended" the way
gap_days can. Per the task's explicit consistency requirement, this is
**folded into the existing `LOW_LIQUIDITY` eligibility reason**, not a
third competing status -- `min_coverage_ratio=0.30` catches 38 symbols
(the 18 INACTIVE_LONG plus 20 additional real-but-chronically-thin names:
ACM, ADC, AGF, AGM, AME, APT, ATA, ATG, BTT, CMV, COM, DCF, DTT, GTA, HU1,
LM8, PNC, POM, SFC, TIX). Precomputed once per `scripts/update_prices_daily.py`
run into `data/full_history_v2/coverage_ratios.parquet` (overwritten each
run, not append-only like `trading_status.parquet` -- coverage ratio is a
continuously-drifting number, not a discrete point-in-time fact) since
computing it live inside the eligibility gate means scanning all ~500
symbols' full raw price history (measured: ~20s per gate call -- too slow
to do more than once a day).

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

   **EXPLORATORY quantification, 2026-07-14** (not a confirmed decomposition —
   see `SURVIVORSHIP_BIAS_ESTIMATE.md` for full caveats): using
   `DISCLOSURE_EVENT_STUDY_REPORT.md`'s S3 (sell-registration) placebo finding
   as a starting point, an independent unconditional cross-check (mean excess
   return vs. VNINDEX of every `(symbol, day)` in the same eligible universe,
   not conditioned on any disclosure event, N=325k-347k) estimates a
   same-order-of-magnitude positive drift floor: **roughly +0.4% / +1.2% /
   +2.9% at 20/60/120 trading days**, growing with horizon, CI touching 0 at
   the short end. Proposed as an interpretive correction floor for any
   long-only backtest's reported excess return, until this is superseded by a
   real point-in-time universe (Gate #3). Not a validated causal decomposition
   — alternative explanations (general risk premium of the liquidity-filtered
   panel, residual beta not fully netted by the VNINDEX subtraction) are not
   ruled out.
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
