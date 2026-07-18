# Delta Scorecard — Round 1 (2026-07-12) → Round 2 (2026-07-18)

Required deliverable per this round's brief. Every "why" cites the exact
evidence re-checked this round — see `quantitative_finance_gap_matrix.csv`
for the row-level detail and `test_execution_log.md` for every command run.

## 1. Category-by-category score delta

| # | Category | Old | New | Max | Δ | Why |
|---|---|---:|---:|---:|---:|---|
| 1 | Data Quality and Governance | 9 | 13 | 15 | **+4** | Gate #6 resolved+verified (production pipeline now reads via `dataset_config.py`, AST regression test passes). OHLCV validation expanded to cover full OHLC relationship, calendar gaps, return outliers, dtype/schema drift, with a new dedicated test file (10/10 pass). Git-commit-hash + config-hash lineage added and confirmed live in `pipeline_metadata.json`/`portfolio_risk_report.json`. Disclosure `NATURAL_KEY` widened; GEE exclusion unified across price/disclosure pipelines. Held back from full marks by Gate #3 (survivorship bias) remaining open, cross-referenced in this category. |
| 2 | Universe and Eligibility | 6 | 7 | 8 | +1 | Zero-volume coverage-ratio suspension proxy added (folded into `LOW_LIQUIDITY`). Sector-mapping eligibility question explicitly decided and documented (not required for eligibility, required for sector-cap). Point-in-time universe reconstruction — the dominant original deduction — remains fully MISSING, capping this category same as before. |
| 3 | Signal and Alpha Quality | 4 | 9 | 12 | **+5 (largest gain)** | The original #1 finding here ("75/100 points of the composite never validated at composite level") has been directly closed: a pre-registered IC/null-test of the full `final_watchlist` composite ran once, found it did not clear the locked bar, and the live system was honestly changed to match (Nhánh C — liquidity sort, explicit no-alpha disclaimer in every output row). Per this round's explicit instruction, a validated-negative research conclusion followed by honest behavior change is a credit, not a gap. `liquidity_score`'s wrong-signed direction was removed from ranking entirely (not just flipped). Weight-citation and look-ahead-guard gaps both closed with direct evidence. |
| 4 | Expected Return Model | 1 | 2 | 8 | +1 | Still no live expected-return model (`estimate_expected_returns` remains dead code) — the fundamental gap is unchanged. Small credit for the system's no-alpha-ranking position now being explicit and consistent across `SCORE_V2_REPORT.md`/`WATCHLIST_VALIDATION_REPORT.md`; withheld full credit because README.md/`DEPLOY_REPORT.md` still lack an explicit "this is risk-based by validated decision" statement, which is where a new reader would look first. |
| 5 | Covariance, Correlation, Portfolio Risk | 8 | 11 | 12 | +3 | Gate #12 resolved with the strongest evidence produced this round: an independent recompute (not a re-read of the remediation report's claim) reproduced the committed report's `annual_return`/`annual_volatility`/`sharpe_ratio`/`max_drawdown` to 1e-9 AND the exact row count (1626=1626), plus a determinism re-run. Formula-layer checks (w^T Σw, symbol-order robustness, MCR/CR/%CR reconciliation) independently re-derived from scratch this round, not just re-confirmed from the old report. Ledoit-Wolf shrinkage and 4 schema-declared-but-never-computed risk fields remain open. |
| 6 | Portfolio Construction and Optimization | 9 | 10 | 12 | +1 | No major fixes landed here specifically since round 1; small credit for continued regression-test health (295/295 passing, including all 5 previously-fixed H1-H6 bugs) and general lineage/reproducibility improvements bleeding into this category's confidence. Transaction-cost split (0.15% vs 0.4%), dual sector-cap mechanisms, uncapped turnover, and unused tested-helper imports all remain open, unchanged. |
| 7 | Monte Carlo and Random Portfolio Search | 3 | 3 | 5 | +0 | No change found. `src/portfolio/monte_carlo.py` still has zero seed control (fresh grep this round). Notebook 14's best-random-sample-as-optimum pattern not independently re-verified as fixed (would require notebook execution, out of this round's scope). |
| 8 | Backtesting and Validation | 10 | 11 | 15 | +1 | Look-ahead guard now also covers the score-computation entry point (`src/alpha/scoring.py`), closing half of the original guard-coverage gap. Bootstrap CI now provides honest quantification of the 5-fold sample-size cap's real consequence (both `alpha_score` v2 intervals contain 0) — a disclosure improvement, not a fix to the underlying fold count. Board lot size, market-impact/participation-rate modeling, transaction-cost decomposition, and survivorship bias (Gate #3, cross-referenced) all remain open, unchanged. |
| 9 | Robustness, Overfitting, Statistical Validity | 4 | 7 | 8 | **+3 (second-largest gain)** | Went from "no formal overfitting correction anywhere despite 192 factors tested" to three of four named methods now implemented and independently confirmed present this round: DSR=0.0083 (M=560 trials, honestly low), BH-FDR on 214 combined tests (38 survive vs. 27 under the old informal threshold — an honestly-reported counter-intuitive result), and a block-bootstrap CI for the production factor's CAGR/Sharpe (both intervals honestly contain 0). `CLAUDE.md` rule 9 now makes FDR reporting mandatory for every future multi-factor table — a durable process change, not a one-off calculation. Portfolio-construction-parameter holdout separation remains the one item still open. |
| 10 | Engineering, Reproducibility, Production Readiness | 4 | 5 | 5 | +1 (full marks) | All four originally-open P1 items independently confirmed resolved this round: dependency pinning (exact versions, documented incompatibility notes), atomic writes (`_atomic_write` backing both `save_parquet` and a new `save_csv_atomic`), lunar-Tết holiday calendar (empirically derived from real no-trade days, not a hardcoded formula), and the one known test failure (now passing). A new operational gap is noted separately (daily automation blocked by macOS TCC) but is a platform-permissions issue requiring one-time user action, not a code defect, so it does not reduce this category's score. |
| | **TOTAL** | **58** | **78** | **100** | **+20** | |

## 2. Critical failure gates — Round 1 → Round 2

| # | Gate | Round 1 | Round 2 | Verification method this round |
|---|---|---|---|---|
| 1 | Look-ahead bias | Not triggered | Not triggered (unchanged) | Direct re-read of T-1 lines |
| 2 | Target leakage | Not triggered | Not triggered (unchanged) | Same guard as #1 |
| 3 | Severe survivorship bias | **TRIGGERED** | **STILL TRIGGERED** | Fresh grep: zero call sites for `check_survivorship_bias`; `trading_status.py` partial-mitigation table confirmed live but explicitly non-substitutive |
| 4 | Incorrect portfolio-risk formula | Not triggered | Not triggered, RE-VERIFIED | Independent w^T Σw recompute, 1e-9 match |
| 5 | Covariance/weight misalignment | Not triggered | Not triggered, RE-VERIFIED | Fresh reversed-order test, 1e-15 match |
| 6 | Stale/invalid data silently used | **TRIGGERED** | **RESOLVED** | `dataset_config.py` wiring confirmed by direct grep; `tests/test_dataset_config.py` (6 tests) re-run fresh, all pass |
| 7 | No out-of-sample validation | Partially mitigated | Partially mitigated (unchanged) | Still 5 folds |
| 8 | No transaction-cost model | Not triggered | Not triggered (unchanged) | Still under-decomposed, still inconsistent |
| 9 | Impossible execution assumptions | Not triggered | Not triggered (unchanged) | No change found |
| 10 | Solver failures ignored | Not triggered | Not triggered (unchanged) | Not re-verified; no regression evidence |
| 11 | Portfolio constraints violated | Not triggered | Not triggered, RE-VERIFIED | sum(weights)=1.0 confirmed fresh |
| 12 | Results cannot be reproduced | **TRIGGERED** | **RESOLVED** | Independent recompute: exact 1e-9 match on all 4 metrics + exact row count + determinism re-run |
| 13 | Corporate actions distort returns | Live residual risk | **Resolved** (same root as #6) | Same fix |
| 14 | Rejected symbols re-enter | Not triggered | Not triggered (unchanged) | Not re-verified; no regression evidence |
| 15 | Current constituents without disclosure | Not triggered (disclosed) | Not triggered (unchanged) | Bias remains disclosed |
| 16 | Outputs stale but reported current | Not triggered | Not triggered (unchanged) | Freshness mechanism re-read, unchanged |
| 17 | Reports model validated without evidence | **TRIGGERED** | **RESOLVED** | `alpha_rs_score` removal confirmed; 3 regression tests re-run fresh; live output artifact inspected directly (zero shadow columns) |

**Round 1: 4/17 triggered. Round 2: 1/17 triggered (#3 only).**

## 3. NEW findings this round (not in the original 75-row matrix), by severity

| Severity | Finding | Category | Detail |
|---|---|---|---|
| MEDIUM | Daily automation (`scripts/daily_run.sh` + LaunchAgent) is installed and loads correctly but is blocked by macOS TCC privacy protection on `~/Desktop` — confirmed via a documented controlled experiment (identical job succeeds pointed at `/tmp`, fails pointed at the project directory) | Engineering | Necessarily new: this automation did not exist at the time of the 2026-07-12 audit. Requires a one-time manual user action (Full Disk Access grant for `/bin/bash`); no code fix is possible. Until granted, the "automated" cycle silently does not run on schedule. |
| MEDIUM | `portfolio_return_series` silently treats a symbol's no-trade/gap day as a 0% return (`fillna(0.0)`) rather than excluding it from volatility/covariance calculation | Data Quality / Covariance-Risk | Surfaced during this round's independent Phase D math validation. For the current committed 10-symbol sample portfolio, 3/10 symbols (ABB, MSB, NAB) have 12-15% NaN days. Internally consistent (confirmed: the ex-ante formula reproduces the realized-series result exactly once the same convention is applied) and not a bug, but undocumented and could understate volatility for thinly-traded names. |
| LOW | `momentum_score` and `relative_strength_score` are mathematically identical (produce the same Newey-West statistic at every row) because subtracting a per-day benchmark-return constant does not change cross-sectional rank order | Signal/Alpha | Already documented in `docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md` (this project's own research finding) but had no row in the original 75-row audit gap matrix; added here for completeness. Moot under the current Nhánh C (no-ranking) state; relevant only if the composite is ever reactivated. |
| INFORMATIONAL | `PROJECT_STATE.md` (the project's own navigation entry point) does not reference `stock-decision-engine/` or `SDE_SCORING_REPORT.md` anywhere | Engineering (documentation completeness) | Minor — a future session reading only `PROJECT_STATE.md` would not learn that a second, now-unprotected sub-project with its own audit/prereg/report trail exists. Does not affect the main 100-point score (SDE is scored separately, see appendix). |

No CRITICAL or HIGH new findings this round.
