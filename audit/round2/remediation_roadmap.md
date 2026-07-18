# Remediation Roadmap — Round 2 (2026-07-18)

Same 5-phase structure as the original roadmap. Phase 1 is now almost
entirely closed (3 of 4 P0 items resolved and independently re-verified
this round); the roadmap below reflects what remains, not what was
already done. Items already resolved are listed at the top of each phase
for traceability, then struck from the active task list.

---

## Phase 1 — Data and mathematical correctness

**Closed since round 1** (independently re-verified this round, see
`critical_findings.md`): stale-dataset production read (Gate #6),
reproducibility/lineage hashing (Gate #12), `alpha_rs_score` leak (Gate
#17), OHLCV validation depth, disclosure `NATURAL_KEY` widening,
disclosure/price-pipeline exclusion sync.

**Remaining**:

| Task | Reason | Affected files | Acceptance criteria | Complexity |
|---|---|---|---|---|
| Point-in-time universe (Gate #3) | Only remaining P0; blocks production-grade classification outright regardless of numeric score | New module (none exists); `src/validation/bias_checks.py::check_survivorship_bias` (run against real data as an interim step) | A backtest/factor-IC test can run against a universe that includes point-in-time-correct delisted/suspended names, or `check_survivorship_bias`'s quantified estimate is published | XL |
| Document the `fillna(0.0)` no-trade-day convention (NEW this round) | Undocumented behavior that could understate realized volatility for thinly-traded names | `src/risk/management.py::portfolio_return_series` | Docstring states the convention; NaN-day fraction per symbol surfaced in output above a materiality threshold | S |
| Corrupted-parquet-file detection | Not independently confirmed present or absent this round | `src/data/validators.py` | A deliberately-corrupted parquet file raises a clear error, not a silent partial read | S |

## Phase 2 — Portfolio and risk engine

**Closed since round 1**: none newly closed this round in this specific
phase (H1-H6 bugs were already fixed before round 1 and remain fixed;
295/295 tests including these still pass).

**Remaining**:

| Task | Reason | Affected files | Acceptance criteria | Complexity |
|---|---|---|---|---|
| Ledoit-Wolf / OAS shrinkage | Still fixed-intensity (0.1), not data-driven; `sklearn.covariance.LedoitWolf` already in requirements.txt | `src/portfolio/construction.py::shrink_covariance` | LedoitWolf available as an option, used by at least one production allocator | M |
| Compute the 4 schema-declared placeholder risk fields | `tracking_error`/`information_ratio`/`active_share`/`r_squared` confirmed this round to exist only in an unused empty-candidates branch | `src/risk/management.py::build_portfolio_risk_report` | All 4 fields computed in the live (non-empty) path or removed from the declared schema | M |
| Reconcile the two transaction-cost models | Still split 0.15% vs. 0.4%, confirmed unchanged this round | `src/backtest/portfolio_backtest.py`, `src/backtest/simulator.py` | Both engines cite one documented, VN-verified transaction-cost source | M |
| Unify the two sector-cap mechanisms | Count-based vs. weight-based, confirmed still dual this round | `src/backtest/portfolio_backtest.py`, `src/portfolio/constraints.py` | Single sector-cap definition used everywhere | M |
| Cap turnover | Currently tracked/costed, not capped, confirmed unchanged this round | `src/backtest/portfolio_backtest.py` | Turnover above a configured limit is rejected or scaled back | S |
| Seed portfolio-level Monte Carlo | `src/portfolio/monte_carlo.py` confirmed still unseeded this round, unlike its sibling `src/models/monte_carlo.py` | `src/portfolio/monte_carlo.py` | Reproducible samples given a fixed seed | S |
| Replace best-random-sample-as-optimum in notebook 14 | Not re-verified as fixed this round (would require notebook execution) | `notebooks/04_watchlist_portfolio/14_portfolio_construction.ipynb` | Notebook reports a percentile range, not a single "best" number | S |

## Phase 3 — Backtesting and validation

**Closed since round 1**: look-ahead guard now covers the score-computation
entry point (`src/alpha/scoring.py`, `scripts/run_alpha_scoring.py`).

**Remaining**:

| Task | Reason | Affected files | Acceptance criteria | Complexity |
|---|---|---|---|---|
| Board lot size enforcement | `lot_size: 100` declared, enforced nowhere (fresh grep this round: 0 matches) | `src/backtest/portfolio_backtest.py`, trade-generation code | No generated trade size violates the board lot size | M |
| Market-impact / participation-rate cap | No ADV-participation limit on trade size found this round | `src/backtest/portfolio_backtest.py` | Trade size capped as a fraction of recent ADV | M |
| Transaction-cost decomposition | Same underlying gap as Phase 2's cost-model item; needs external VN brokerage/tax verification | Same files | Commission + tax + exchange fee + spread/slippage itemized separately | M |
| Extend look-ahead guard to the backtest engine's own entry point | Only the scoring half was confirmed closed this round | `src/backtest/portfolio_backtest.py` | Guard covers every feature-consumption entry point, not just save points | S |

## Phase 4 — Robustness and statistical testing

**Closed since round 1**: Deflated Sharpe Ratio, Benjamini-Hochberg FDR
(now a standing `CLAUDE.md` rule), and bootstrap confidence intervals all
now implemented and independently confirmed present this round.

**Remaining**:

| Task | Reason | Affected files | Acceptance criteria | Complexity |
|---|---|---|---|---|
| Separate holdout for portfolio-construction hyperparameters | Confirmed still open via `PROJECT_STATE.md` mục 3 this round | New split logic wherever `portfolio_size`/`max_per_sector` are selected | Selection uses a fold never used in reported performance | M |
| Increase walk-forward fold count | Still exactly 5 calendar-year folds, confirmed unchanged this round | `scratch/concentration_null_test.py` and equivalents | Rolling monthly/quarterly windows yield >5 effective folds | L |
| PBO / White's Reality Check / Hansen's SPA | Only DSR was implemented among the 4 named formal-correction methods | New module, likely `src/validation/robustness.py` | At least one additional formal correction applied and reported | M |

## Phase 5 — Production hardening

**Closed since round 1**: dependency pinning, atomic writes, lunar-Tết
holiday calendar, the one known test failure, `run_all_notebooks.sh`
error-reporting re-test — all independently confirmed resolved this
round (full marks in Engineering category, 5/5).

**Remaining**:

| Task | Reason | Affected files | Acceptance criteria | Complexity |
|---|---|---|---|---|
| Grant Full Disk Access to `/bin/bash` (NEW this round — user action, not code) | LaunchAgent confirmed installed/loading correctly but blocked by macOS TCC on `~/Desktop`; no code fix possible | N/A — System Settings action | `launchctl`-triggered run appears in `logs/daily_run.log` without manual invocation | S (user action, not engineering) |
| Corrupted-parquet detection | Not confirmed present this round | `src/data/validators.py` | Deliberately-corrupted file raises a clear error | S |

---

## Overall priority ordering (unchanged framing from round 1, updated for what's left)

1. **Point-in-time universe (Gate #3)** — the single largest remaining
   item in the entire audit, and the only remaining critical-failure
   gate. Everything else is secondary to this in terms of blocking
   production readiness.
2. **Phase 2/3 cheap fixes** (S/M complexity: turnover cap, MC seeding,
   sector-cap unification, board-lot enforcement, fillna(0.0)
   documentation) — no new data required, mechanical changes with clear
   acceptance criteria.
3. **Phase 4 remaining items** (holdout separation, more folds, PBO) —
   benefits most from Gate #3 being resolved first (a point-in-time
   universe changes the folds/data available for these tests too, so
   sequencing after Gate #3 avoids redoing this work).
4. **User-side action**: granting Full Disk Access is a 2-minute task
   that unblocks genuine daily automation — worth doing immediately since
   it costs nothing and has been sitting blocked since 2026-07-16.
