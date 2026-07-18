# Quantitative Finance Scorecard — Round 2 (2026-07-18)

Re-audit against the identical framework as the 2026-07-12 audit
(`claude_code_quantitative_finance_audit_prompt.md`, same 100-point
scorecard, same 17 critical failure gates, same severity/confidence
levels). Baseline: 58/100, Experimental. See `delta_scorecard.md` for the
row-by-row reasoning behind every point change.

## Category scores

| Category | Score | Max | % | Δ vs. 58/100 baseline | Notes |
|---|---:|---:|---:|---:|---|
| 1. Data Quality and Governance | 13 | 15 | 87% | +4 | Gate #6 RESOLVED_VERIFIED (dominant fix); OHLC/calendar-gap/dtype-drift validation fully expanded with a new test file; git-hash+config lineage added; disclosure NATURAL_KEY widened; GEE exclusion unified. Survivorship bias (Gate #3) remains open and caps the ceiling. |
| 2. Universe and Eligibility | 7 | 8 | 88% | +1 | Zero-volume coverage-ratio gate and sector-mapping decision both closed. Point-in-time universe reconstruction (Gate #3) remains fully MISSING — the one structural gap in this category. |
| 3. Signal and Alpha Quality | 9 | 12 | 75% | **+5** | Largest single-category improvement. The full `final_watchlist` composite (75/100 of its own weight, previously never tested) has now been IC/null-tested end to end and honestly demoted to a liquidity sort with no alpha claim (Nhánh C) — a validated research conclusion, not a gap, per this round's scoring instruction. liquidity_score removed from ranking entirely; weight citations and look-ahead-guard coverage both closed. |
| 4. Expected Return Model | 2 | 8 | 25% | +1 | No live expected-return model still exists (unchanged), but the system's de-facto "no alpha ranking / risk-based" position is now much more explicit across research reports (not yet in README/DEPLOY_REPORT specifically, which is why this is +1, not more). |
| 5. Covariance, Correlation, Portfolio Risk | 11 | 12 | 92% | +3 | Gate #12 RESOLVED_VERIFIED with the strongest evidence of this round: independent recompute matched the committed report to 1e-9 on all 4 headline metrics plus exact row count. Ledoit-Wolf shrinkage and 4 schema-only risk fields remain open. |
| 6. Portfolio Construction and Optimization | 10 | 12 | 83% | +1 | Stable — all previously-fixed HIGH bugs still hold (295/295 tests pass). Transaction-cost split, sector-cap duplication, and turnover-uncapped remain open, unchanged. |
| 7. Monte Carlo and Random Portfolio Search | 3 | 5 | 60% | +0 | No change — portfolio-level MC remains unseeded; best-random-sample-as-optimum anti-pattern in notebook 14 not re-verified as fixed. |
| 8. Backtesting and Validation | 11 | 15 | 73% | +1 | Look-ahead guard now also covers the score-computation entry point. 5-fold sample-size cap, board lot size, market-impact modeling, and survivorship bias (Gate #3, cross-referenced) all remain open. |
| 9. Robustness, Overfitting, Statistical Validity | 7 | 8 | 88% | **+3** | Second-largest improvement. DSR (0.0083), BH-FDR (214 tests, now a standing CLAUDE.md rule), and bootstrap CI (both intervals honestly contain 0) all newly implemented and independently confirmed present this round. Portfolio-construction-parameter holdout remains the one open item. |
| 10. Engineering, Reproducibility, Production Readiness | 5 | 5 | 100% | +1 | Full marks — dependency pinning, atomic writes, lunar-Tết holiday calendar, and the one known test failure all independently confirmed resolved. A new (necessarily new — the automation didn't exist before) operational gap is noted: the daily-run LaunchAgent is blocked by macOS TCC pending a one-time user action, not a code defect. |
| **TOTAL** | **78** | **100** | **78%** | **+20** | |

## Rating

**78/100 → Strong foundation (70-79 band): "Important validation gaps
remain."** Up from 58/100 (Experimental, 40-59 band) at the 2026-07-12
baseline.

**This is a large, genuinely-verified jump — not a re-read of the prior
remediation reports' own claims.** Every RESOLVED_VERIFIED row in
`quantitative_finance_gap_matrix.csv` was independently re-checked this
round: fresh test-suite runs, fresh greps against current source, and
(for the three named critical gates) fresh independent recomputation from
first principles rather than trusting the prior audit's or the
remediation reports' own numbers.

**The critical-failure override still applies, and still matters more
than the numeric score.** Per the audit framework's own rule ("a high
total score must not override a critical failure"): **1 of the original
4 triggered critical gates remains open (Gate #3, survivorship bias)**.
This alone means the system cannot be classified as production-grade or
eligible for a real-capital pilot, regardless of the 78/100 score — the
same conclusion as the original audit, for the same underlying reason,
even though 3 of the 4 original gates are now closed.

## Critical failure gates — status (17 gates, same framework)

| # | Gate | Round 1 (2026-07-12) | Round 2 (2026-07-18) | Verification this round |
|---|---|---|---|---|
| 1 | Look-ahead bias | Not triggered | **Not triggered** (unchanged) | Re-read T-1 convention lines directly; no change since round 1 |
| 2 | Target leakage | Not triggered | **Not triggered** (unchanged) | Same guard coverage as #1 |
| 3 | **Severe survivorship bias** | **TRIGGERED** | **STILL TRIGGERED** | Fresh grep: `check_survivorship_bias` has zero call sites. `trading_status.py`'s partial mitigation confirmed live (462 ACTIVE / 19 STALE_SHORT / 20 INACTIVE_LONG) but explicitly not point-in-time |
| 4 | Incorrect portfolio-risk formula | Not triggered | **Not triggered**, RE-VERIFIED | Independent w^T Σw recompute matched the committed report to 1e-9 this round (see `portfolio_math_validation.md`) |
| 5 | Covariance/weight misalignment | Not triggered | **Not triggered**, RE-VERIFIED | Fresh reversed-symbol-order test, exact match to 1e-15 |
| 6 | **Stale or invalid data silently used** | **TRIGGERED** | **RESOLVED** | `build_portfolio_stack.py` now reads via `dataset_config.OFFICIAL_FEATURES_PATH`; `tests/test_dataset_config.py` (6 tests) run fresh, all pass |
| 7 | No out-of-sample validation | Partially mitigated | **Partially mitigated** (unchanged) | Still 5 folds; construction-hyperparameter holdout still not separated |
| 8 | No transaction-cost model | Not triggered | **Not triggered** (unchanged) | Cost model exists, still under-decomposed and inconsistent (0.15% vs 0.4%) |
| 9 | Impossible execution assumptions | Not triggered | **Not triggered** (unchanged) | No change found |
| 10 | Solver failures ignored | Not triggered | **Not triggered** (unchanged) | Not re-verified this round; no evidence of regression |
| 11 | Portfolio constraints violated | Not triggered | **Not triggered**, RE-VERIFIED | sum(weights)=1.0 exactly on a fresh independent check this round |
| 12 | **Results cannot be reproduced** | **TRIGGERED** | **RESOLVED** | Independent recompute reproduced all 4 headline metrics to 1e-9 AND the exact row count (1626=1626), plus a determinism re-run; strongest evidence of this round |
| 13 | Corporate actions materially distort returns | Live residual risk | **Resolved** (same root as #6) | Same fix as gate #6 |
| 14 | Rejected symbols can re-enter | Not triggered | **Not triggered** (unchanged) | Not re-verified this round; no evidence of regression |
| 15 | Current constituents without disclosure | Not triggered (disclosed) | **Not triggered** (unchanged) | Bias (#3) remains disclosed in multiple reports |
| 16 | Outputs stale but reported current | Not triggered | **Not triggered** (unchanged) | `pipeline_metadata.json` freshness mechanism re-read this round, unchanged |
| 17 | **Reports a model validated without evidence** | **TRIGGERED** | **RESOLVED** | `alpha_rs_score` confirmed removed from `relative_strength_score`; 3 regression tests re-run fresh, pass; live `final_watchlist.parquet` inspected directly — zero shadow-field columns. Additionally, the broader pattern is now structurally prevented: `final_watchlist` no longer claims to rank by alpha at all (Nhánh C) |

**3 of 17 critical failure gates are triggered → resolved this round: #6,
#12, #17. 1 gate remains triggered: #3.** (Round 1: 4 triggered.)

## Distinguishing code-exists from code-is-validated (per audit brief)

| Claim | Round 1 | Round 2 |
|---|---|---|
| Code exists | True | True |
| Code is executed | True (235 tests) | True (**295 tests**, fresh run this round) |
| Code produces output | True | True |
| Output is consumed | True | True |
| **Output is mathematically correct** | True for the formula layer only | **True for the formula layer, AND now independently re-confirmed for the realized-return layer too** (Gate #12 resolved — a report can now be reproduced from its own recorded lineage) |
| **Output is statistically validated** | True only for `alpha_score` v2's two factors | **Now also true for the full `final_watchlist` composite** — tested, found NOT to have validated alpha (Nhánh C), and the live system's behavior honestly matches that conclusion. `alpha_score` v2 itself now carries an honestly-disclosed DSR=0.0083 and a bootstrap CI containing 0 — "validated" for IC purposes does not mean "known profitable after correction," and the repo now says so explicitly. |

## Recommended next phase

Do not proceed to a real-capital pilot — Gate #3 (survivorship bias)
remains the blocking critical failure, unchanged from round 1. The
highest-leverage next phase is acquiring or constructing a point-in-time
delisting/suspension data source (the single largest remaining item in
this entire audit); `src/validation/trading_status.py`'s 3-state table is
a genuine first step but explicitly not a substitute. Everything else
scored in this round (Expected Return model, Ledoit-Wolf shrinkage,
transaction-cost decomposition, Monte Carlo seeding, board-lot
enforcement) is real but secondary to Gate #3 in terms of blocking
production readiness. Shadow/paper-trading operation (`alpha_score`
v2, `alpha_score_shadow_v1`) may reasonably continue in parallel, as
before, since it commits no capital.
