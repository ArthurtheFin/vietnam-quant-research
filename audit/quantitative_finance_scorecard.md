# Quantitative Finance Scorecard

## Category scores

| Category | Score | Max | % | Notes |
|---|---:|---:|---:|---|
| 1. Data Quality and Governance | 9 | 15 | 60% | Strong freshness/lineage mechanics undercut by a confirmed CRITICAL finding (production path reads a known-stale dataset) and unresolved survivorship bias |
| 2. Universe and Eligibility | 6 | 8 | 75% | Eligibility gate and exclusive tiers are genuinely well-built and verified fixed in production; point-in-time universe reconstruction is missing entirely |
| 3. Signal and Alpha Quality | 4 | 12 | 33% | One well-validated core signal (alpha_score v2) buried under a much larger unvalidated/contradicted overlay in final_watchlist, including a confirmed-still-live forensically-bad component |
| 4. Expected Return Model | 1 | 8 | 13% | No expected-return model operates in the live pipeline; the one implementation is dead code |
| 5. Covariance, Correlation, Portfolio Risk | 8 | 12 | 67% | Formulas are correct and symbol-order-robust (independently confirmed); realized-return-based risk metrics are not reproducible from current data |
| 6. Portfolio Construction and Optimization | 9 | 12 | 75% | Wide range of correctly-implemented methods, all previously-documented HIGH-severity bugs confirmed fixed; some drift risk from unused/duplicated code paths |
| 7. Monte Carlo and Random Portfolio Search | 3 | 5 | 60% | Sound sampling/constraint mechanics; unseeded portfolio-level RNG and an unresolved noise-mining anti-pattern (confined to a research notebook, not production) |
| 8. Backtesting and Validation | 10 | 15 | 67% | Genuinely strong anti-look-ahead architecture (T-1 convention, verified) and an unusually good self-remediation track record; capped by structural survivorship bias and only 5 folds |
| 9. Robustness, Overfitting, Statistical Validity | 4 | 8 | 50% | A real, well-designed null test against 2,000+ random portfolios; no formal overfitting correction (DSR/PBO/FDR) anywhere despite 192 factors tested |
| 10. Engineering, Reproducibility, Production Readiness | 4 | 5 | 80% | Clean one-command pipeline, deterministic seeding, real retry/logging/metadata; unpinned dependencies and an incomplete holiday calendar |
| **TOTAL** | **58** | **100** | **58%** | |

## Rating

**58/100 → Experimental (40-59 band): "High bias, robustness, or implementation risk."**

This classification is **not** a borderline call overridden by strong
component scores — 4 critical failure gates are independently confirmed
open (see below), each of which the audit brief specifies must not be
overridden by a high total score. Even absent those gates, 58/100 lands
squarely in the Experimental band on its own.

## Critical failure gates — status

| # | Gate | Status | Evidence |
|---|---|---|---|
| 1 | Look-ahead bias | **Not triggered** (in the primary engine) | T-1 convention confirmed correct in `portfolio_backtest.py`; guard coverage gaps noted (P1) but not exploited today |
| 2 | Target leakage | **Not triggered** | No exploitation found; guard coverage gaps are the same as #1 |
| 3 | **Severe survivorship bias** | **TRIGGERED — CONFIRMED** | No point-in-time universe exists anywhere; every backtest/factor test runs on today's listed universe projected backward. See `critical_findings.md` P0-1. |
| 4 | Incorrect portfolio-risk formula | **Not triggered** | `w^T Sigma w`, MCR/CR/%CR all confirmed correct via independent recomputation (Phase D) |
| 5 | Covariance/weight misalignment | **Not triggered** | Confirmed robust via a reversed-order test (Phase D) |
| 6 | **Stale or invalid data silently used** | **TRIGGERED — CONFIRMED** | Production portfolio pipeline reads `data/processed/stock_features.parquet`, documented by this repo's own `docs/reports/data/docs/reports/data/DATA_BASELINE.md` as still corrupted for an uncatalogued subset of symbols. See `critical_findings.md` P0-2. |
| 7 | No out-of-sample validation | **Partially mitigated, not fully triggered** | Walk-forward (5 folds) and a train/validation split for breakout stop-loss selection both exist; portfolio-construction hyperparameters were tuned on the same folds used for reporting (P1, not a full gate trigger) |
| 8 | No transaction-cost model | **Not triggered** | A cost model exists (flat %); it is under-decomposed (P1), not absent |
| 9 | Impossible execution assumptions | **Not triggered (minor idealization only)** | Portfolio backtest executes at same-day close (a common, disclosed idealization, not literally impossible); breakout engine uses realistic next-open entry |
| 10 | Solver failures ignored | **Not triggered** | Every optimizer call site checks `res.success` with an equal-weight fallback, confirmed by independent agent review |
| 11 | Portfolio constraints violated | **Not triggered** | All core constraints (sum-to-1, non-negative, max position, sector, liquidity) confirmed enforced; turnover tracked-not-constrained is a P1, not a violation observed |
| 12 | **Results cannot be reproduced** | **TRIGGERED — CONFIRMED (empirically)** | Independent Phase D recomputation could not reproduce the committed `portfolio_risk_report.json`'s realized-return metrics using the documented method and the report's own stated parameters. See `critical_findings.md` P0-3. |
| 13 | Corporate actions materially distort returns | **Live residual risk (same root as #6)** | The raw/adjusted-close bug is fixed for `full_history_v2`; the production pipeline doesn't yet use that fixed dataset |
| 14 | Rejected symbols can re-enter the portfolio | **Not triggered** | Exclusive-tier construction confirmed with no bypass path (two independent verification passes) |
| 15 | Backtest uses current constituents without disclosure | **Not triggered (bias exists but is disclosed)** | Survivorship bias (#3) is real but is explicitly disclosed in multiple existing reports — the gate's specific concern ("without disclosure") does not apply; the underlying bias itself is captured by gate #3 |
| 16 | Outputs stale but reported as current | **Not triggered — demonstrated strength** | Freshness check actively fired `ERROR` status on real data, observed directly in `data/output/pipeline_metadata.json` |
| 17 | **Reports a model as validated without statistical evidence** | **TRIGGERED — CONFIRMED** | `final_watchlist`'s live composite is majority-weighted toward unvalidated/contradicted factors, including one (`alpha_rs_score`) this repo's own forensic report calls a primary driver of a real -59.7% loss — yet the composite feeds client-facing tiers without that caveat surfacing. See `critical_findings.md` P0-4. |

**4 of 17 critical failure gates are triggered and confirmed**: #3, #6,
#12, #17.

## Distinguishing code-exists from code-is-validated

Per the audit brief's explicit instruction, these are not equivalent —
applied throughout this audit:

| Claim | Status for this system |
|---|---|
| Code exists | True for nearly everything scored above |
| Code is executed | True — confirmed via the daily pipeline orchestration and 235 passing tests |
| Code produces output | True — `data/output/`, `data/signals/` artifacts inspected directly |
| Output is consumed | True — final_watchlist tiers feed client reports, portfolio_weights feeds capital planning |
| **Output is mathematically correct** | **True for the formula layer** (portfolio variance, risk contribution, symbol alignment — independently confirmed), **false/unverified for the realized-return layer** (not reproducible) |
| **Output is statistically validated** | **True only for `alpha_score` v2's two factors**; false or unverified for the majority of `final_watchlist`'s own composite weight, and for the deployed selection method's overfitting-correction posture |

## Recommended next phase

Per the brief's next-phase language, and given 4 confirmed critical
failure gates: **do not proceed to a real-capital pilot.** The
appropriate next phase is **Phase 1 of the remediation roadmap** (data
and mathematical correctness — repoint the stale dataset, fix the
`alpha_rs_score` leak, add reproducibility hashing, begin the
point-in-time universe effort), followed by re-running this audit's
Phase D validation once those are in place. Paper-trading / shadow-mode
operation (which already exists via `alpha_score_shadow_v1`'s logging)
may reasonably continue in parallel, since it does not commit real
capital and is explicitly disclosed as young/low-statistical-value at
this stage.
