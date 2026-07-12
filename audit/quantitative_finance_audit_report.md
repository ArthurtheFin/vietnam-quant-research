# Quantitative Finance Project Audit Report

**Repository**: `vietnam-quant-research` · **Audited at**: HEAD `01d4079`, branch `claude/charming-bartik-d21dc1` · **Audit type**: read-only, inventory-only (Phases A-F per the audit brief) · **Protected path**: `stock-decision-engine/` — confirmed untouched throughout.

---

## 1. Executive Summary

**Overall score: 58/100 — Experimental** ("high bias, robustness, or
implementation risk"). **4 of 17 critical failure gates are confirmed
triggered**: severe survivorship bias (#3), stale/corrupted data still
used in the production portfolio path (#6), an empirically-confirmed
reproducibility failure on the committed risk report (#12), and a
composite score presented as production-ready that still includes a
component this repository's own forensic work identified as actively
harmful (#17). Per the audit brief's rule, a high total score must not
override a critical failure — and in this case the score itself already
lands in the same band the critical failures would force regardless.

The system is **not ready for a real-capital pilot**. It is,
however, a genuinely more mature and better-engineered codebase than a
first read of "Experimental" might suggest: this repository has already
been through at least one full internal self-audit
(`AUDIT_REPORT.md`/`REMEDIATION_REPORT.md`), and the large majority of
that audit's own findings — same-bar look-ahead bias, a silent
benchmark-substitution bug, fabricated volatility inputs, a mislabeled
Kelly-sizing bug, hardcoded NAV, mock survivorship data — are confirmed
**fixed** in current code, independently re-verified by this audit
rather than taken on faith. The core portfolio-risk mathematics (`w^T
Sigma w`, marginal/component/percentage risk contribution, symbol-order
alignment) is confirmed correct via independent recomputation. The
weaknesses that remain are concentrated in exactly the areas the audit
brief warns are hardest to get right and easiest to overlook:
survivorship bias, statistical significance at scale (192 factors
tested, no formal correction), and the gap between "this specific
sub-signal is validated" and "the composite score actually shipped to
users is validated."

## 2. Repository Overview

See `architecture_dependency_map.md` for the full module map, prior-report
inventory, and duplicated/dead-code findings. In brief: a `src/` package
organized by concern (data, features, alpha, screening, portfolio, risk,
backtest, validation, disclosure), a `scripts/` layer of CLI entrypoints
orchestrated by `scripts/run_daily_pipeline.py`, 19 notebooks (inventoried,
none containing hidden production logic), 32 test files / 235 tests, and
~25 standing markdown reports documenting this project's own iterative
audit-and-fix history. A separate, protected nested project
(`stock-decision-engine/`) exists and was not inspected beyond confirming
its presence and non-modification.

## 3. Current System Flow

```
Raw data (SSI FCData + CafeF disclosure feed)
  -> data/full_history_v2 (price, backfilled+fixed) / data/disclosure (events)
  -> data/processed/stock_features.parquet (features -- NOTE: not yet merged from full_history_v2, see finding P0-2)
  -> src/alpha/scoring.py (alpha_score v2, validated; alpha_score_shadow_v1, shadow-only)
  -> src/screening/final_watchlist.py (composite score, eligibility gate, tiering)
  -> scripts/build_portfolio_stack.py (equal/inverse-vol/risk-parity/HRP allocation, risk report)
  -> data/output/ (client-facing watchlists, portfolio weights, risk report)

separately: src/backtest/portfolio_backtest.py (walk-forward validation, 5 folds)
```

## 4. Audit Methodology

Four parallel, independently-instructed static-audit passes (one per
scorecard-category cluster) plus this orchestrator's own Phase A
discovery, Phase C test execution, and Phase D independent mathematical
recomputation. Every prior report listed in the brief's addendum was read
first; every claim from those reports that this audit touched was
re-verified against current code rather than restated on faith — see the
`[KNOWN_DOCUMENTED]` vs. `[NEW]` tagging throughout `quantitative_finance_gap_matrix.csv`.
No production code, config, or data file was modified. `git status`
confirms `stock-decision-engine/` untouched.

## 5. Findings by Category

Full detail for all 75 gap-matrix rows is in
`quantitative_finance_gap_matrix.csv`; category-level narrative and point
justification is in `quantitative_finance_scorecard.md`. Highlights:

- **Data Quality (9/15)**: freshness checking is unusually rigorous and
  demonstrably fired on real data; the production portfolio path reads a
  documented-stale dataset (P0-2); survivorship bias is real and
  unaddressed (P0-1); a reproducibility gap was empirically confirmed
  (P0-3).
- **Universe/Eligibility (6/8)**: the eligibility gate and exclusive tier
  construction are strong, verified-fixed mechanisms; point-in-time
  universe reconstruction doesn't exist.
- **Signal/Alpha (4/12)**: one rigorously validated signal
  (`alpha_score` v2) is real; the composite that actually reaches users
  (`final_watchlist`) is majority-weighted toward unvalidated or
  contradicted factors, including a confirmed-still-live forensically-bad
  component (P0-4).
- **Expected Return (1/8)**: no expected-return model operates in
  production; the one implementation is dead code.
- **Covariance/Risk (8/12)**: formulas confirmed correct and
  symbol-order-robust by independent recomputation; realized-return-based
  risk metrics are not reproducible (shared root cause with P0-3).
- **Portfolio Construction (9/12)**: wide, mostly-correct method
  coverage; 5 previously-documented HIGH-severity bugs all confirmed
  fixed.
- **Monte Carlo (3/5)**: sound mechanics; unseeded portfolio-level RNG and
  an unresolved (but production-isolated) noise-mining pattern.
- **Backtesting/Validation (10/15)**: genuinely strong anti-look-ahead
  architecture and an unusually good self-remediation track record,
  capped by survivorship bias and a 5-fold sample size.
- **Robustness/Overfitting (4/8)**: a real, well-designed random-portfolio
  null test; no formal overfitting correction (DSR/PBO/FDR) despite 192
  factors tested.
- **Engineering (4/5)**: clean, deterministic, well-logged pipeline;
  unpinned dependencies, incomplete holiday calendar.

## 6. Mathematical Validation

Full detail in `portfolio_math_validation.md`. Summary: weight-derived
statistics (max weight, effective N, HHI) reproduce **exactly**.
Portfolio variance (`w^T Sigma w`) and risk-contribution formulas
(MCR/CR/%CR) are confirmed correct, and — critically — confirmed **robust
to symbol reordering** via a direct reversed-order test, ruling out the
single most severe common bug class the audit brief warns about.
Realized-return-based metrics (annual return, annual volatility, Sharpe,
max drawdown) in the committed `portfolio_risk_report.json` could **not**
be reproduced across three independent attempts using the documented
method, the same weights, and the report's own stated date cutoff —
this is the evidentiary basis for critical failure gate #12.

## 7. Bias and Leakage Findings

- **Look-ahead bias**: the primary backtest engine's T-1
  decision/T-execution convention is confirmed correctly implemented and
  enforced (a genuine strength — this exact bug class was the subject of
  a prior CRITICAL finding, now fixed and re-verified). Guard coverage
  (`assert_no_forward_columns`) has real gaps at the scoring/backtest
  entry points, not just output points — not currently exploited, but a
  live risk.
- **Survivorship bias**: severe and structural, triggers critical gate
  #3. See P0-1.
- **Target/overlapping-label leakage**: no exploitation found within
  this audit's scope.
- **Data snooping / multiple testing**: 192 factor combinations tested
  with no formal correction — see Robustness findings.

## 8. Portfolio and Risk Findings

Core math confirmed correct (Section 6 above). Constraint enforcement
(weight sum, non-negativity, position/sector/liquidity limits) confirmed
solid. Turnover is tracked but not enforced. Two unreconciled
transaction-cost models and two structurally different sector-cap
mechanisms coexist without being unified — maintainability risk, not a
live numerical bug. Covariance shrinkage is a fixed-intensity blend, not
a genuine Ledoit-Wolf/OAS estimator (already known-deferred per
`REMEDIATION_REPORT.md` H5).

## 9. Backtesting Findings

T-1 timing, price-band limit-up rejection, T+2.5 settlement, and honest
benchmark-fallback handling are all confirmed correctly implemented.
Board-lot enforcement is missing entirely despite being configured.
Transaction costs are flat-rate and under-decomposed. No market-impact
modeling exists beyond the eligibility liquidity filter. The one known
failing test (`test_full_history_calibration_matches_strategy_research_report`)
is confirmed to be exactly what's documented — a stale hardcoded
expectation, not a new regression, and consistent with this repository's
own later factor-retest findings.

## 10. Engineering Findings

Strong: one-command pipeline, deterministic seeding (with one noted
exception), real retry/backoff, run-history snapshots, metadata
validation that actively rejects absolute paths, clean notebooks. Gaps:
unpinned dependencies (no lockfile), no atomic writes, an
incomplete lunar-holiday calendar (self-disclosed in code comments), and
one previously-flagged notebook-runner reliability concern
(`run_all_notebooks.sh`) not re-verified this round (execution was out of
scope for a read-only audit).

## 11. Overall Score

**58/100.** See `quantitative_finance_scorecard.md` for the full
per-category breakdown and justification.

## 12. Readiness Classification

**Experimental (40-59 band)**: "High bias, robustness, or implementation
risk." This is the natural score-band classification independent of the
critical-failure override, and the critical-failure override (4 gates
triggered) would not permit a higher classification regardless.

## 13. Critical Failure Gates

**4 of 17 triggered and confirmed**: #3 (severe survivorship bias), #6
(stale/invalid data silently used), #12 (results cannot be reproduced),
#17 (a component presented as production-ready is not statistically
validated, and in fact contradicts the repository's own forensic
evidence). Full gate-by-gate status table in
`quantitative_finance_scorecard.md`. Full narrative, evidence, and
required fixes for each in `critical_findings.md`.

## 14. Recommended Next Phase

**Phase 1 of the remediation roadmap** (data and mathematical
correctness): repoint the production portfolio pipeline off the stale
dataset (P0-2), remove the confirmed-harmful `alpha_rs_score` component
from `final_watchlist` (P0-4), add data-lineage hashing to make outputs
reproducible (P0-3), and begin the point-in-time universe effort (P0-1,
the largest and longest-running item). Shadow/paper-trading mode may
continue in parallel — it commits no capital and is already explicitly
disclosed as statistically immature at this stage. **Do not proceed to a
real-capital pilot** until at minimum P0-1 through P0-4 are resolved and
this audit's Phase D validation is re-run and passes.
