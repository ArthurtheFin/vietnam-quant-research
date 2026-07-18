# stock-decision-engine/ — Appendix Scorecard (NOT counted in the main 100-point score)

Scored under the identical 10-category, 100-point framework as the main
project, per this round's explicit instruction (B): `stock-decision-engine/`
is no longer read-only-protected (the user lifted this via `CLAUDE.md`
rule 10, 2026-07-17, independently of this audit), so it is audited fully
— but kept as a separate appendix so the main scorecard stays comparable
to the 2026-07-12 baseline (which excluded SDE entirely).

**This is SDE's first-ever audit under this framework** — there is no
prior SDE score to delta against. All findings below draw on SDE's own
3-round audit/fix/prereg trail from this same week
(`stock-decision-engine/AUDIT_SDE_REPORT.md`,
`stock-decision-engine/SDE_SCORING_PREREG.md`,
`stock-decision-engine/SDE_SCORING_REPORT.md`) plus fresh spot-checks
performed this round.

## Category scores

| Category | Score | Max | % | Notes |
|---|---:|---:|---:|---|
| 1. Data Quality and Governance | 10 | 15 | 67% | Now wired to the main project's `dataset_config.py` single source of truth (fixed this week, verified: AST test scope extended to `stock-decision-engine/src/`, passes). Full lineage metadata added (dataset_version/features_sha256/git_commit_hash), reusing the main project's own builder rather than a local reimplementation. No dedicated freshness check of its own; minimal input validation beyond type coercion. |
| 2. Universe and Eligibility | 2 | 8 | 25% | Not really applicable by design — SDE is a single-ticker lookup tool, not a universe-screening system. No eligibility gate, no watchlist tiers. The only implicit filter is `lookback_days=756` acting as a de facto minimum-history requirement (verified: symbols with insufficient history are correctly skipped, not silently truncated). |
| 3. Signal and Alpha Quality | 7 | 12 | 58% | The composite (`final_score`) was, for the first time ever, IC/null-tested end to end (Round 3 prereg, one shot, locked criteria) and found NOT validated — composite demoted to a pure facts table (Nhánh C), same honest-negative-result credit logic as the main project's `final_watchlist`. Look-ahead bias explicitly checked and confirmed absent (a genuine, verified positive). Statistical power was structurally limited (N=43 usable cross-sections; 3-period robustness split literally uncomputable) — acknowledged transparently in `SDE_SCORING_REPORT.md`, but a real limitation, not full main-project-grade evidence. |
| 4. Expected Return Model | 1 | 8 | 13% | No expected-return model exists in any form — same fundamental gap as the main project, un-mitigated (SDE never had a dead-code implementation to point to either). |
| 5. Covariance, Correlation, Portfolio Risk | 6 | 12 | 50% | Not applicable in the multi-asset sense (single-stock tool, no covariance matrix, no portfolio-level risk contribution). What DOES exist — CAPM alpha/beta, Sharpe/Sortino/Calmar, VaR/CVaR, max drawdown for the single stock vs. benchmark — uses standard, correctly-implemented formulas (spot-checked this round: `beta = cov(stock,bench)/var(bench)`, `alpha = excess_return - beta*bench_excess_return`, both textbook-correct). |
| 6. Portfolio Construction and Optimization | 1 | 12 | 8% | Not applicable by design — SDE analyzes one stock at a time and has never constructed a multi-asset portfolio. ATR-based entry/stop/target levels exist but are single-position risk/reward reference levels, not portfolio construction. |
| 7. Monte Carlo and Random Portfolio Search | 3 | 5 | 60% | A genuine, correctly-seeded (`seed=42` default) bootstrap Monte Carlo exists, conditioned on the current volatility regime, computing target/stop-hit probabilities correctly. Not compared against any deterministic alternative (none exists for a single-stock tool). Whether the reported probabilities are calibrated (do "45%" claims actually happen ~45% of the time historically) has never been tested — explicitly deferred as future work in `SDE_SCORING_PREREG.md`. |
| 8. Backtesting and Validation | 7 | 15 | 47% | The most substantial testing SDE has ever received: a real point-in-time re-scoring bridge was built this week and a genuine 5-fold null test run (reusing the main project's own `run_portfolio_backtest` machinery, including its transaction-cost/liquidity/sector-cap constraints). Result: `final_score` failed both the IC and null-test legs decisively. Severely limited by sample size (only 43 valid cross-sections vs. the main project's thousands of daily observations) and inherits the same survivorship-bias-affected universe as the main project. |
| 9. Robustness, Overfitting, Statistical Validity | 4 | 8 | 50% | Benjamini-Hochberg FDR (q=0.05) correctly applied to the 28-test IC battery this week, matching the main project's own methodology exactly (reused, not reinvented) — a genuine first for SDE. No DSR, PBO, or bootstrap CI computed specifically for SDE's own score (out of scope for the one-shot Round 3 test); no sensitivity analysis (appropriately withheld — "no tuning" was an explicit constraint this round). |
| 10. Engineering, Reproducibility, Production Readiness | 2 | 5 | 40% | Deterministic seeding and full lineage metadata now match main-project standard (both newly added this week). **Zero dedicated test files exist for SDE's own scoring/feature logic** — the only test coverage touching this directory is the path-hygiene AST scan (`tests/test_dataset_config.py`), which was extended to include `stock-decision-engine/src/` but does not test `enrich()`/`score_decision()`/`build_facts_table()`'s actual behavior at all. Notebook-based single entry point, not a scripted one-command pipeline. |
| **TOTAL** | **43** | **100** | **43%** | |

## Rating

**43/100 → Experimental (40-59 band): "High bias, robustness, or
implementation risk."** Directly comparable in spirit to where the main
project stood before its own remediation work (58/100 at the 2026-07-12
baseline) — SDE has had 3 intensive rounds of work this week (data-source
fix, formal IC/null-test, honest demotion to a facts table) but started
from a much lower base (a single-developer research notebook that had
never been tested at all before this week) and covers a narrower slice of
the framework by design (single-stock, no portfolio construction).

## Critical failure gates — status (same 17-gate framework)

| # | Gate | Status | Evidence |
|---|---|---|---|
| 1 | Look-ahead bias | **Not triggered** | Explicitly checked this week (`AUDIT_SDE_REPORT.md` mục 3.2): all rolling stats correctly trailing-window, no `.expanding()`, no forward-fill, Donchian breakout uses `.shift(1)` correctly |
| 2 | Target leakage | **Not triggered** | Same check as #1 |
| 3 | **Severe survivorship bias** | **TRIGGERED (inherited)** | SDE reads the same `trading_status==ACTIVE` universe as the main project for its point-in-time panel; same root cause as the main project's Gate #3, not independently caused by SDE but not independently fixed either |
| 4 | Incorrect portfolio-risk formula | Not applicable | No portfolio/covariance matrix exists |
| 5 | Covariance/weight misalignment | Not applicable | Same reason |
| 6 | Stale or invalid data silently used | **Was triggered, now RESOLVED** | 6/20 historical outputs confirmed to have used data since found corrupted (raw/adjusted-close mixing bug); fixed this week by wiring to `dataset_config.py`; verified via the same regression test as the main project |
| 7 | No out-of-sample validation | **Partially mitigated** | Round 3's point-in-time re-scoring + null test is a genuine one-shot OOS-style test, severely underpowered (N=43) |
| 8 | No transaction-cost model | Not applicable to SDE's primary use case | The borrowed null-test infrastructure includes a cost model (reused from the main project); SDE itself does not model costs for its own advisory output since it does not generate trades |
| 9 | Impossible execution assumptions | Not triggered | Entry/stop/target are advisory ATR-based reference levels, not automated executions |
| 10 | Solver failures ignored | Not applicable | No solver |
| 11 | Portfolio constraints violated | Not applicable | No portfolio |
| 12 | Results cannot be reproduced | **Was triggered, now RESOLVED** | Lineage metadata added this week; regeneration script demonstrated deterministic, reproducible re-scoring |
| 13 | Corporate actions materially distort returns | **Was triggered, now RESOLVED** | Same fix as gate #6 |
| 14 | Rejected symbols can re-enter | Not applicable | No selection/rejection mechanism (single-ticker tool) |
| 15 | Current constituents without disclosure | Not applicable | No constituent list |
| 16 | Outputs stale but reported as current | Not triggered (but weakly guarded) | Output filename embeds the actual last-available data date (honest), but no active freshness-warning mechanism exists |
| 17 | **Reports a model as validated without evidence** | **Was triggered, now RESOLVED — more thoroughly than the main project's own fix** | The composite was not patched, it was tested and, on failing, REMOVED ENTIRELY (`final_score`/`decision` no longer exist in the codebase at all, not just relabeled) |

**1 of 17 critical failure gates is currently triggered: #3 (inherited
survivorship bias).** 3 gates (#6, #12, #17) were triggered before this
week's work and are now resolved with direct evidence.

## Distinguishing code-exists from code-is-validated (SDE)

| Claim | Status |
|---|---|
| Code exists | True |
| Code is executed | True — this week, 20+ historical runs regenerated, plus a full-universe point-in-time panel (17,620 scored rows) |
| Code produces output | True |
| Output is consumed | Only by the individual user manually reading the facts table — no downstream automated consumer |
| Output is mathematically correct | True for the single-asset CAPM/VaR/CVaR/drawdown formulas (standard, spot-checked); portfolio-level math not applicable |
| **Output is statistically validated** | **Tested and found NOT validated** (Nhánh C) — the composite score no longer exists in the codebase; what remains is explicitly unvalidated raw facts, honestly labeled as such in every output |

## Recommended next phase for SDE

Do not reintroduce a composite score or decision label without new
IC/null-test evidence meeting the same locked bar (`CLAUDE.md` rule 10
already enforces this as a standing constraint). If a genuinely daily
(not 20-day-sampled) re-scoring becomes computationally feasible — e.g. a
vectorized reimplementation of `enrich()`/`score_decision()` — a new,
separately pre-registered Round 4 test could achieve the statistical
power this round's N=43 sample lacked. Until then, `stock-decision-engine`
should be treated purely as a facts-lookup tool, per
`SDE_SCORING_REPORT.md` mục 11's own recommendation.
