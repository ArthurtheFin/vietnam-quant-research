# Critical Findings — Round 2 — P0 and P1 only

3 of the original 4 P0 findings (2026-07-12) are now RESOLVED_VERIFIED
(direct evidence below, not a re-read of the remediation reports' own
claims). 1 P0 remains open. 13 P1 findings follow — 3 newly closed since
round 1, the rest unchanged.

---

## P0-1 — No point-in-time universe; every backtest and factor test has severe, unaddressed survivorship bias

**STATUS (2026-07-18): STILL OPEN.** KNOWN_OPEN — unchanged since round 1,
re-confirmed independently this round.

**Severity**: CRITICAL. **Confidence**: CONFIRMED (fresh independent
verification this round, not a re-read of the prior finding).

**Exact location**: structural — no file constructs a point-in-time
listing/delisting table anywhere in `src/` or `scripts/`.
`src/validation/bias_checks.py::check_survivorship_bias` exists; a
repo-wide grep this round (`grep -rn "check_survivorship_bias" src/ scripts/`)
confirms zero call sites outside its own definition and the
`src/validation/__init__.py` re-export.

**What changed since round 1**: `src/validation/trading_status.py` was
added (a genuine, real partial step) — a 3-state `ACTIVE`/`STALE_SHORT`/
`INACTIVE_LONG` classification with real point-in-time history starting
2026-07-13. Queried live this round: 462 `ACTIVE` / 19 `STALE_SHORT` / 20
`INACTIVE_LONG`. The module's own docstring and `PROJECT_STATE.md` mục 3
are explicit that this is NOT a full point-in-time universe: `INACTIVE_LONG`
symbols are excluded from the eligible universe at EVERY historical date
(not just from when they actually stopped trading), and the classification
has no data before 2026-07-13.

**Evidence**: the 500-symbol universe (`data/full_history_v2/raw/*.parquet`
minus `GEE`) is still "symbols listed today, backfilled to 2020." Any
company delisted, merged away, or suspended indefinitely since 2020 is
invisible to every backtest (`src/backtest/portfolio_backtest.py`) and
every factor-IC test run against this universe.

**Impact**: unchanged from round 1 — every CAGR, Sharpe, drawdown, and IC
figure in every report in this repository, including all the reports
produced during the improvement work this delta covers, is computed on a
survivorship-biased sample.

**Recommended fix**: unchanged — acquire or construct a point-in-time
listing table (SSI/HOSE/HNX/UPCOM bulletins or a third-party vendor).

**Required validation test**: unchanged — re-run the walk-forward backtest
and factor retests including delisted/suspended names; quantify the
magnitude of the bias.

**Cross-referenced gap-matrix rows**: Data Quality/"Survivorship bias /
point-in-time universe", Universe-Eligibility/"Point-in-time universe
reconstruction", Backtesting-Validation/"Survivorship bias in every
backtest".

---

## P0-2 (was) — Production portfolio pipeline reads the known-corrupted, superseded dataset

**STATUS (2026-07-18): RESOLVED, VERIFIED FRESH THIS ROUND.** (Gate #6)

Confirmed by direct grep of `scripts/build_portfolio_stack.py:18,233`
(imports and reads via `dataset_config.OFFICIAL_FEATURES_PATH`) and a
fresh run of `tests/test_dataset_config.py` (6/6 pass). Independently
re-derived confirmation beyond the code citation: this round's Gate #12
reproducibility check (below) would not have been possible to reproduce
exactly if the underlying data path were still wrong — the exact 1e-9
match is itself corroborating evidence that Gate #6's fix holds in
practice, not just in the source code.

**No further action required.** See `quantitative_finance_gap_matrix.csv`
row "Corporate actions / stale dataset still in use" for full detail.

---

## P0-3 (was) — The committed portfolio risk report cannot be reproduced

**STATUS (2026-07-18): RESOLVED, VERIFIED FRESH THIS ROUND.** (Gate #12)

This round independently rebuilt the return matrix using the exact
documented method, the currently-committed 10 symbols/weights, and the
committed report's own stated `features_latest_date` cutoff. Result: 1626
rows recomputed vs. 1626 reported (exact match — round 1 found 1621 vs.
1317, a mismatch). All 4 headline metrics (`annual_return`,
`annual_volatility`, `sharpe_ratio`, `max_drawdown`) reproduced to 1e-9.
Ran the identical recompute twice for a determinism check — bit-identical
both times. Full detail and script in `portfolio_math_validation.md`.

**No further action required.** Continue embedding `lineage` on every
future report (already the default behavior, guarded by
`validate_lineage_metadata` raising if any field is missing).

---

## P0-4 (was) — `final_watchlist.py`'s live scoring included a confirmed-harmful factor

**STATUS (2026-07-18): RESOLVED, VERIFIED FRESH THIS ROUND, AND
STRUCTURALLY SUPERSEDED.** (Gate #17)

Confirmed by direct grep (`alpha_rs_score` removed from
`relative_strength_score`'s average, comment cites "audit P0-4 / gate
#17"), a fresh run of the 3 relevant regression tests (all pass), and
direct inspection of the live `data/signals/final_watchlist.parquet`
artifact (34 columns, zero shadow-field columns).

**Beyond the original fix**: the broader pattern this gate warned about
(a composite presenting itself as validated while majority-weighted
toward unvalidated/contradicted factors) is now structurally prevented,
not just patched at the component level — `docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md`'s
pre-registered IC/null-test found the FULL composite does not clear the
validation bar, and `final_watchlist.py` now runs in Nhánh C: it no
longer claims to rank by alpha at all, sorting purely by liquidity with
an explicit disclaimer in every output row.

**No further action required.**

---

## P1 findings (13 rows; 3 newly closed since round 1, marked below)

**Data validation depth — CLOSED since round 1.** `validate_ohlcv` now
covers the full OHLC relationship, calendar gaps, return outliers, and
dtype/schema drift, with a new dedicated test file
(`tests/test_validators.py`, 10/10 passing, confirmed fresh this round).

**Data lineage (git hash / config version) — CLOSED since round 1.**
Both fields now present and populated in every inspected metadata/report
artifact.

**Signal composite validation — LARGELY CLOSED since round 1.**
`final_watchlist`'s two largest weights (trend 25, momentum 20) are no
longer live-ranking anything (Nhánh C). The look-ahead guard
(`assert_no_forward_columns`) now covers `src/alpha/scoring.py` and
`scripts/run_alpha_scoring.py` (confirmed by direct grep this round) —
previously only 2 unrelated output/save points. **Still open**: the
backtest engine itself (`src/backtest/portfolio_backtest.py`) was not
independently re-checked this round for a guard call site at its own
feature-consumption entry point.

**Execution realism — STILL OPEN, unchanged.** `lot_size: 100` remains
declared in `config/vn_market_rules.yaml` and enforced nowhere (fresh
repo-wide grep this round: zero matches in `src/backtest/` or
`src/portfolio/`). The flat 0.15%/0.4% transaction-cost split across the
two backtest engines is unchanged (fresh grep confirms both values
present, unreconciled).

**Statistical rigor — SUBSTANTIALLY IMPROVED, structural cap unchanged.**
The 5-calendar-year-fold structural cap on statistical confidence is
unchanged (fresh grep confirms `FOLDS` still has exactly 5 entries), but
is now much more honestly quantified: Deflated Sharpe Ratio (0.0083),
Benjamini-Hochberg FDR (214 combined tests, 38 survive), and a
block-bootstrap confidence interval (both CAGR and Sharpe intervals
honestly contain 0) all independently confirmed present in
`docs/reports/scoring/ROBUSTNESS_REPORT.md` this round. `CLAUDE.md` rule 9 now makes FDR
reporting mandatory for every future multi-factor test table.

**Operational — CLOSED since round 1.** `config/vn_market_holidays.csv`
now includes lunar Tết dates, derived empirically from real no-trade days
in `full_history_v2` rather than a hardcoded formula (confirmed by direct
read this round).

**Still-open P1 items carried forward unchanged, confirmed via fresh
checks this round**: Ledoit-Wolf shrinkage not implemented (fixed
0.1-intensity blend confirmed unchanged); 4 risk-report schema fields
(`tracking_error`/`information_ratio`/`active_share`/`r_squared`)
confirmed present only in an unused empty-candidates placeholder branch,
never actually computed; turnover computed/costed but not capped;
board-lot size not enforced; market-impact/participation-rate cap
missing; dual, unreconciled sector-cap mechanisms; portfolio-level Monte
Carlo unseeded; notebook 14's best-random-sample-as-optimum pattern not
re-verified as fixed; portfolio-construction-hyperparameter holdout still
not separated from performance-reporting folds.

**NEW P1-adjacent findings this round** (MEDIUM severity, see
`delta_scorecard.md` for full detail): (1) daily automation blocked by
macOS TCC, requiring one-time manual user action, no code fix possible;
(2) `portfolio_return_series`'s silent `fillna(0.0)` convention for
no-trade days, surfaced during this round's independent Phase D math
validation, undocumented and could understate volatility for thinly-traded
names.
