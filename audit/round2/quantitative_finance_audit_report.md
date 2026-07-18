# Quantitative Finance Project Audit Report — Round 2

**Date**: 2026-07-18. **Framework**: identical to the 2026-07-12 audit
(`~/Downloads/claude_code_quantitative_finance_audit_prompt.md`, re-read
in full before this round began — same 100-point scorecard, same 17
critical failure gates, same severity/confidence taxonomy). **Baseline**:
58/100, Experimental, 4 critical failure gates triggered.

## 1. Executive summary

**Score: 78/100 (was 58/100), Strong foundation band (was Experimental).
3 of 4 original critical failure gates resolved and independently
re-verified this round; 1 remains open.**

This is not a fresh audit of an unchanged system — it is a re-audit
measuring genuine, verified remediation work performed across several
rounds since 2026-07-12 (a dedicated P0 remediation round on 2026-07-13,
incremental GĐ2-GĐ5.5 work through 2026-07-16, and this week's
`stock-decision-engine/` audit trail). Every claim of "resolved" in this
report was independently re-checked this round — fresh test-suite runs,
fresh greps against current source, and, for the three named critical
gates, fresh independent recomputation from first principles rather than
trusting the prior audit's or the remediation reports' own numbers. See
`delta_scorecard.md` for the row-by-row accounting and
`quantitative_finance_gap_matrix.csv`'s `verification_status` column for
exactly which of the 77 rows were freshly verified this round
(`RESOLVED_VERIFIED`, 51 rows) versus confirmed-still-open
(`KNOWN_OPEN`, 20 rows) versus newly discovered (`NEW`, 3 rows) versus
code-changed-but-outcome-not-re-run (`RESOLVED_UNVERIFIED`, 3 rows).

**The one remaining critical failure — severe survivorship bias (Gate
#3) — still blocks production-grade classification regardless of the
numeric score**, per the audit framework's own explicit rule. This is
unchanged from round 1's conclusion, for the same underlying reason: no
point-in-time universe exists anywhere in the codebase.

**Scope addition**: `stock-decision-engine/`, protected/excluded at
round 1, was explicitly unprotected by the user on 2026-07-17 and has
since been through its own 3-round audit/fix/prereg cycle. Per this
round's instruction, it is scored separately as an appendix (43/100,
Experimental, 1 open critical gate — inherited survivorship bias) and
does NOT contribute to the 78/100 headline score.

## 2. Repository overview

Structure unchanged from round 1: `src/` (16 module directories, 123
`.py` files across `src/`+`scripts/`), `scripts/` (CLI entrypoints,
orchestrated by `run_daily_pipeline.py`, now itself wrapped by a new
`scripts/daily_run.sh` one-command daily-cycle script), `tests/` (39
files, **295 tests** — up from 235), `notebooks/`, `config/`, `data/`
(not content-audited here). One structural change since round 1: the
~25 standalone `.md` reports previously loose at repo root were
reorganized into `docs/reports/<category>/` this week (cosmetic —
citations updated throughout the codebase, no functional change). See
`architecture_dependency_map.md` for the full module map and Mermaid
diagram.

## 3. Current system flow

Unchanged from round 1:

```
Raw data (data/full_history_v2)
→ Data validation (src/data/validators.py — EXPANDED this round)
→ Feature engineering (scripts/generate_features.py, via dataset_config.py — FIXED this round, Gate #6)
→ Signal generation (src/alpha/scoring.py — alpha_score v2, shadow only)
→ Candidate screening (src/screening/final_watchlist.py — NOW Nhánh C, no alpha ranking)
→ Eligibility filtering (apply_eligibility_gate)
→ Expected return estimation (NONE live — dead code, unchanged)
→ Covariance and correlation estimation (src/portfolio/construction.py)
→ Portfolio construction (src/portfolio/construction.py, optimization.py)
→ Risk calculation (src/risk/management.py — lineage FIXED this round, Gate #12)
→ Constraints (src/portfolio/constraints.py)
→ Backtesting (src/backtest/portfolio_backtest.py)
→ Validation (docs/reports/scoring/ROBUSTNESS_REPORT.md — DSR/FDR/bootstrap all NEW this round)
→ Reporting (scripts/build_portfolio_stack.py, generate_daily_report.py)
→ Daily production pipeline (scripts/daily_run.sh — NEW since round 1, blocked by macOS TCC pending user action)
```

## 4. Audit methodology

Same 6-phase procedure as round 1 (Discovery, Static Audit, Execution
Audit, Independent Mathematical Validation, Scoring/Gap Analysis,
Remediation Plan), plus a fourth verification-status dimension this
round explicitly requested: every gap-matrix row is tagged
`KNOWN_OPEN` / `RESOLVED_VERIFIED` / `RESOLVED_UNVERIFIED` / `NEW`,
distinguishing "I re-checked this myself this round" from "I am trusting
a prior report's claim." Full command log in `test_execution_log.md`.
Constraints honored throughout: inventory-only (no writes outside
`audit/round2/`, no pipeline execution that writes to `data/output/` or
calls an external service), the disclosure/price firewall (no new joins
or tests beyond already-closed preregs), and the research firewall
(no new IC/null-test/prereg run — existing conclusions read, not
regenerated).

## 5. Findings by category

See `quantitative_finance_scorecard.md` for the full 10-category table
and `delta_scorecard.md` for the "why" behind every point change. Summary
of the two largest deltas:

- **Signal and Alpha Quality: 4→9/12 (+5, largest gain).** The original
  #1 finding — "75/100 points of `final_watchlist`'s composite weight
  never validated at the composite level" — is now closed by a
  pre-registered IC/null-test that found the composite does NOT clear the
  validation bar, followed by an honest live-behavior change
  (`ranking_mode="no_alpha_liquidity_sort"`, every output row explicitly
  disclaiming alpha-ranking). Per this round's explicit scoring
  instruction, a validated-negative research conclusion honestly reflected
  in production is a credit, not a gap.
- **Robustness, Overfitting, Statistical Validity: 4→7/8 (+3).** Went
  from "no formal overfitting correction anywhere despite 192 factors
  tested" to three of four named methods (DSR, BH-FDR, bootstrap CI) now
  implemented and independently re-confirmed present this round, with
  FDR reporting now a standing `CLAUDE.md` rule for every future
  multi-factor table.

## 6. Mathematical validation

Independent recomputation this round (not a re-read of round 1's own
numbers) on the currently-committed 10-symbol sample portfolio:

- **Reproducibility (Gate #12)**: exact match to 1e-9 on
  `annual_return`/`annual_volatility`/`sharpe_ratio`/`max_drawdown`, plus
  an exact row-count match (1626=1626) and a determinism re-run.
- **Portfolio variance (`w^T Σw`)**: confirmed correct, but only after
  discovering and reconciling a real methodological detail — see NEW
  finding below.
- **Symbol-order robustness**: reversed-order recompute matches to 1e-15.
- **Risk-contribution reconciliation**: `sum(CR_i) = σp` and
  `sum(%CR_i) = 100%`, both to floating-point precision.

Full detail, including the script and every intermediate number, in
`portfolio_math_validation.md`.

## 7. Bias and leakage findings

Look-ahead bias, target leakage: **not triggered**, unchanged, re-verified
via direct re-read of the T-1 decision/execution convention. Survivorship
bias: **still triggered** — this remains the single largest open item in
the entire audit (see §9).

## 8. Portfolio and risk findings

Formula layer confirmed correct (again, independently, this round — see
§6). **NEW finding**: `src/risk/management.py::portfolio_return_series`
silently treats a symbol's no-trade day as a 0% return (`fillna(0.0)`)
rather than excluding it. Not a bug — the formula reconciles exactly once
this convention is matched — but undocumented, and for the current sample
portfolio 3/10 symbols have 12-15% NaN-day rates, which could understate
realized volatility for thinly-traded names. Schema-declared-but-never-
computed risk fields (`tracking_error`/`information_ratio`/`active_share`/
`r_squared`) remain open, confirmed unchanged this round.

## 9. Backtesting findings

Look-ahead guard now covers the score-computation entry point (closing
half the original coverage gap). Structural cap unchanged: still exactly
5 calendar-year folds, board lot size still unenforced, transaction-cost
model still split (0.15% vs. 0.4%) and undecomposed, no market-impact
modeling. Survivorship bias (Gate #3) is cross-referenced here as it
directly affects backtest validity: **every performance figure in every
backtest in this repository remains computed on a universe of symbols
listed today, backfilled to 2020, with historically delisted/suspended
names structurally invisible.**

## 10. Engineering findings

**Full marks this round (5/5).** All four originally-open P1 items
independently confirmed resolved: dependency pinning, atomic writes,
lunar-Tết holiday calendar (empirically derived from real no-trade
days), and the one known test failure (now passing). One genuinely NEW
finding — the daily-automation LaunchAgent is correctly installed and
loads, but is blocked by macOS TCC privacy protection on `~/Desktop`,
requiring a one-time manual user action; this is a platform-permissions
issue, not a code defect, and does not reduce the Engineering score.

## 11. Overall score

**78/100** (was 58/100). See §12 for why this is not the whole story.

## 12. Readiness classification

**78/100 lands in the "Strong foundation (70-79): important validation
gaps remain" band.** But per the audit framework's own explicit rule ("a
high total score must not override a critical failure"), **the system is
still not eligible for production-grade classification or a real-capital
pilot**, because Gate #3 (severe survivorship bias) remains triggered.
This is the same practical conclusion as round 1, for the same reason —
the score moved substantially, the blocking issue did not.

## 13. Critical failure gates

**1 of 17 triggered** (was 4/17): #3 only. Gates #6 (stale data), #12
(reproducibility), and #17 (unvalidated model reported as validated) are
now RESOLVED with direct, fresh evidence — see `critical_findings.md` for
the full writeup of each, and `quantitative_finance_scorecard.md`/
`delta_scorecard.md` for the complete 17-row before/after table.

## 14. Recommended next phase

Do not proceed to a real-capital pilot. The highest-leverage next phase
is unchanged from round 1's conclusion, now even more clearly the sole
remaining blocker: **acquire or construct a point-in-time
listing/delisting data source** (SSI/HOSE/HNX/UPCOM bulletins or a
third-party vendor) so backtests and factor-IC tests can include
historically delisted/suspended names. Everything else identified in this
round (Ledoit-Wolf shrinkage, transaction-cost decomposition, Monte Carlo
seeding, board-lot enforcement, portfolio-construction-parameter holdout
separation, the `fillna(0.0)` documentation gap) is real but secondary —
see `remediation_roadmap.md` for the full prioritized breakdown across 5
phases. Shadow/paper-trading operation (`alpha_score` v2,
`alpha_score_shadow_v1`) may reasonably continue in parallel, as before,
since it commits no capital and is already explicitly disclosed (DSR and
bootstrap CI both honestly show weak-to-absent multiple-testing-corrected
evidence of real skill).

---

## Appendix: stock-decision-engine/

Scored separately (43/100, Experimental, 1 open critical gate — see
`sde_appendix_scorecard.md` and `sde_appendix_report.md`), per this
round's explicit instruction. Not counted in §11's 78/100. Confirmed
protected-folder status: **not modified by this audit round** — the
user's 2026-07-17 unprotection decision and SDE's subsequent 3-round
audit/fix/prereg cycle both predate and are independent of this audit;
this round only reads and re-verifies what already exists there.
