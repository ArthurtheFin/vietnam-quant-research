# stock-decision-engine/ — Appendix Audit Report (Round 2, 2026-07-18)

This is a summary; SDE already has its own extensive, independently-dated
documentation trail from this same week, produced across 3 dedicated
rounds before this audit began. This appendix does not repeat that
detail — it cross-references it and adds the fresh spot-checks performed
specifically for this audit round.

## 1. Why this is an appendix, not part of the main score

`stock-decision-engine/` was protected/read-only at the 2026-07-12 audit
and excluded entirely. The user lifted that protection on 2026-07-17
(`CLAUDE.md` rule 10) — a decision made independently of, and prior to,
this audit round. Per this round's explicit instruction (constraint B),
SDE is now audited under the identical framework but kept as a separate
appendix so the main 100-point score remains directly comparable to the
58/100 baseline, which never included SDE.

## 2. What SDE is

A single-ticker "should I buy/wait/watch/avoid" research notebook,
architecturally and organizationally independent of the main project's
`alpha_score`/`final_watchlist` pipeline (own `src/`, own `config.yaml`,
own notebook). Before this week, it had never been tested, audited, or
validated in any form — a research artifact the user was actively using
(64→172 output files across 16 tickers) without ever having checked
whether its scores meant anything.

## 3. This week's 3-round history (source documents, not repeated here)

1. **Audit-only round** (`stock-decision-engine/AUDIT_SDE_REPORT.md`) —
   architecture map, full scoring-formula inventory, a direct ladder-test
   confirming 5/16 tickers' historical prices were corrupted by the same
   raw/adjusted-close mixing bug the main project had already fixed for
   itself (Gate #6-equivalent), and a strong indirect finding: 50% of
   `final_score`'s weight sits on the exact factor family
   (`trend`/`momentum`/`relative_strength`) the main project's own
   forensic work had already found IC-inverted.
2. **Data-fix + prereg round** — wired SDE to the main project's
   `dataset_config.py` single source of truth (fixing the Gate #6/#12/#17
   equivalents), regenerated all 20 historical outputs on clean data, and
   locked a prereg (`SDE_SCORING_PREREG.md`) for a formal IC/null-test —
   reusing the main project's exact methodology (Newey-West, BH-FDR,
   2000-portfolio null test), not inventing a new one.
3. **Scoring-verdict round** (`SDE_SCORING_REPORT.md`) — ran the locked
   prereg once. `final_score` failed both legs of the validation bar
   (`t_NW(full,residualized)=+1.28`, null-test percentile=31.2 with one
   fold at 0.75). No sub-score cleared the bar either (the one
   FDR-surviving positive result, `risk`, could not be confirmed stable
   across 3 periods because the sample was too small — only 43 usable
   cross-sections). Per the pre-registered decision tree's own
   conservative tie-break rule, this resolved to **Nhánh C**: `scoring.py`
   had its composite/decision logic **removed from the codebase entirely**
   (not deprecated, not hidden) and replaced with a plain facts table.

## 4. Fresh verification performed specifically for this audit round

- Re-ran `tests/test_dataset_config.py` (6 tests, main-project file whose
  scan scope was extended to `stock-decision-engine/src/` this week) —
  passes, confirming SDE has no hardcoded copy of the canonical dataset
  path outside the shared single source of truth.
- Confirmed via direct source read that `stock-decision-engine/src/scoring.py`
  no longer defines `WEIGHTS`, `score_decision`, `_hard_filters`,
  `_decision_label`, or `_confidence` — `build_facts_table()` is the only
  public entry point, and it returns no composite/decision field.
- Confirmed `stock-decision-engine/src/report.py`'s lineage helper reuses
  `src/utils/pipeline_io.py::build_lineage_metadata` (the main project's
  own function) rather than a local reimplementation — the same standard
  the main project holds itself to.
- Spot-checked the CAPM/risk formulas in `stock-decision-engine/src/risk.py`
  (`beta = cov/var`, `alpha = excess_return - beta*bench_excess`) —
  standard, correctly implemented.

## 5. Key differences from the main project's own Signal/Alpha and

## Backtesting/Validation findings, worth noting explicitly

SDE's Round 3 validation, while methodologically rigorous (identical
apparatus to `WATCHLIST_VALIDATION_REPORT.md`), was structurally
underpowered in a way the main project's tests are not: SDE's own
`lookback_days=756` design, combined with the main project's backfill
only completing 2026-07-10, caps SDE's currently-testable history at
~3.5 years / 43 cross-sections — too short to compute the standard
3-period robustness split at all (each period needs ≥30 observations for
Newey-West; SDE's periods have ~15). `SDE_SCORING_REPORT.md` mục 5
("Giới hạn phiên tòa") is explicit about this: most of the confidence in
the Nhánh C verdict comes from the DIRECTIONAL match with the main
project's own much-more-powerful prior evidence (same factor family,
independently found IC-inverted with N in the thousands), not from
SDE's own test's statistical power alone.

## 6. Score and gates

See `sde_appendix_scorecard.md` for the full 10-category breakdown
(43/100, Experimental) and 17-gate table (1 gate currently triggered:
inherited survivorship bias; 3 gates — stale data, reproducibility,
unvalidated-model-reported-as-validated — resolved this week with direct
evidence, arguably more thoroughly than the main project's own
equivalent fixes since the invalid composite was removed rather than
patched).

## 7. What this appendix does NOT do

Per this round's constraints, this appendix does not re-run SDE's
Round 3 prereg, does not propose a Round 4, and does not modify any file
under `stock-decision-engine/`. It scores what already exists, using
fresh spot-checks where cheap and citing SDE's own dated reports where a
full re-derivation would duplicate work already done rigorously this
same week.
