# Critical Findings — P0 and P1 only

4 distinct root-cause issues generate the 7 P0 rows in the gap matrix
(several root causes surface in more than one scorecard section — cross-
referenced below rather than repeated). 14 P1 rows follow, grouped by
theme. Full detail, evidence, and acceptance criteria for every row are
in `quantitative_finance_gap_matrix.csv`; this document extracts only
what's needed to act.

---

## P0-1 — No point-in-time universe; every backtest and factor test has severe, unaddressed survivorship bias

**STATUS (2026-07-13): OPEN.** Explicitly out of scope for the NV1-NV5
remediation round that closed P0-2/P0-3/P0-4 below ("KHÔNG đụng Gate #3
(survivorship)"). Not touched, not investigated further, no code changed.
Still the single largest unresolved issue in this repository — see the
Impact paragraph below, which continues to apply in full.

**Severity**: CRITICAL. **Confidence**: CONFIRMED (independently verified by two audit passes).

**Exact location**: structural — no file constructs a point-in-time
listing/delisting table anywhere in `src/` or `scripts/`.
`src/validation/bias_checks.py::check_survivorship_bias` exists but is
never called against real data. `BACKFILL_DESIGN_REPORT.md` Task 2
documents that the available SSI endpoints (`get_securities`,
`get_securities_details`) cannot enumerate historically-delisted
symbols.

**Evidence**: the 500-symbol universe (`data/full_history_v2/raw/*.parquet`
minus `GEE`) is "symbols listed today, backfilled to 2020." Any company
delisted, merged away, or suspended indefinitely since 2020 is invisible
to every backtest run against this universe (`src/backtest/portfolio_backtest.py`,
`src/backtest/breakout_research.py`) and every factor-IC test
(`FACTOR_RETEST_V2_REPORT.md`, `ROBUST_FACTOR_IC_REPORT.md`). A prior
notebook cell that mocked a survivorship check with a hardcoded
`["FLC","ROS","ART"]` list was replaced with an honest "no data
available" state — an improvement in honesty, but the underlying gap
remains unfilled.

**Impact**: every CAGR, Sharpe, drawdown, and IC figure in every report
in this repository is computed on a survivorship-biased sample. This is
the single largest, most consequential unresolved issue in the whole
system — it does not just weaken one component, it caps how much any
other finding in this audit can be trusted, since a factor or portfolio
method that looks validated on this universe could be validated on a
biased sample.

**Recommended fix**: acquire or construct a point-in-time listing table
(historical exchange membership snapshots, delisting dates) before this
system is used for any live-capital decision. In the interim, prominently
disclose the bias in every client-facing output, not just internal
reports.

**Required validation test**: re-run the walk-forward backtest and the
44-factor retest including delisted/suspended names from a point-in-time
universe; compare resulting CAGR/Sharpe/IC figures against the current
(survivorship-biased) results to quantify the actual bias magnitude.

**Cross-referenced gap-matrix rows**: Data Quality/"Survivorship bias /
point-in-time universe", Universe-Eligibility/"Point-in-time universe
reconstruction", Backtesting-Validation/"Survivorship bias in every
backtest".

---

## P0-2 — Production portfolio pipeline reads the known-corrupted, superseded dataset instead of the fixed one

**STATUS (2026-07-13): RESOLVED — commit `28b9f60`** (gate #6). Root cause
was broader than the exact line cited below: `scripts/generate_features.py`
already read from `data/full_history_v2/raw` in code, but the on-disk
`data/processed/stock_features.parquet` (and siblings) predated the final
backfill and had never been regenerated. Fix: added
`src/data/dataset_config.py` as the single source of truth for all official
dataset paths, migrated all ~17 consumer files (`build_portfolio_stack.py`
included) to import from it, physically quarantined the stale files into
`data/quarantine_existing_v1/`, and regenerated clean
`stock_features.parquet`/`clean_daily_ohlcv.parquet`/`market_features.parquet`
from `full_history_v2/raw`. Verified via a 0%-mismatch re-check on the
same 9-symbol sample (previously up to 100% mismatch) plus a new AST-based
regression test (`tests/test_dataset_config.py`) guarding against any future
hardcoded path outside `dataset_config.py`.

**Severity**: CRITICAL. **Confidence**: CONFIRMED (direct code citation).

**Exact location**: `scripts/build_portfolio_stack.py`, line 222:
```python
features = read_parquet(PROJECT_ROOT / "data/processed/stock_features.parquet")
```

**Evidence**: `DATA_BASELINE.md` (this repo's own official price-dataset
baseline) explicitly states: *"data/full_history_v2 is not yet merged
into data/processed/ — any code still reading data/processed/stock_features.parquet
directly is reading data known to be wrong for a large, uncatalogued
subset of symbols until that merge happens."* `build_portfolio_stack.py`
is exactly such a code path, and it is the script that produces the
committed `data/output/portfolio_weights.parquet` and
`portfolio_risk_report.json` — the actual client-facing portfolio
construction and risk-reporting output. (This audit's Phase D spot-check
on the 10-symbol sample portfolio did not find a price discrepancy for
the one symbol checked (VIC) between the two datasets — meaning this
specific committed report may not currently be affected — but the risk
is universe-wide and uncatalogued; the next portfolio built from a
different symbol mix could hit an affected name with no warning.)

**Impact**: portfolio weights and risk metrics for any affected symbol
could silently be computed from the wrong (raw-vs-adjusted-close-mixed)
price series, corrupting downstream vol/return/risk-contribution
figures without any error or warning surfacing.

**Recommended fix**: either merge `data/full_history_v2` into
`data/processed/` (the fix `DATA_BASELINE.md` itself already
recommends), or repoint `build_portfolio_stack.py` at
`data/full_history_v2` directly.

**Required validation test**: after repointing, re-run
`build_portfolio_stack.py` and confirm `data/output/portfolio_weights.parquet`
is byte-identical (for symbols present in both datasets) whether sourced
from `data/full_history_v2` or a freshly-merged `data/processed/`.

**Cross-referenced gap-matrix row**: Data Quality/"Corporate actions /
stale dataset still in use".

---

## P0-3 — The committed portfolio risk report cannot be reproduced from currently-available data

**STATUS (2026-07-13): RESOLVED — commit `72be363`** (gate #12). Added
`build_lineage_metadata()`/`validate_lineage_metadata()` (`src/utils/pipeline_io.py`):
every `portfolio_risk_report.json` now embeds `dataset_version`,
`features_sha256`, `features_row_count`, `config_hash`, `git_commit_hash`,
and `lineage_generated_at`, with `validate_lineage_metadata` raising before
write if any field is missing/empty ("no lineage, no commit" convention
enforced as a runtime guard, not just documentation). Verified: two
back-to-back runs of `build_portfolio_stack.py` produced bit-identical output
(diffed programmatically, excluding timestamps); re-ran this finding's own
three-attempt independent recompute methodology against the now-regenerated,
hash-pinned `stock_features.parquet` and all four metrics
(`annual_return`, `annual_volatility`, `sharpe_ratio`, `max_drawdown`) plus
`track_record_days` matched the committed report to 1e-9 (previously: 0/3
attempts matched).

**Severity**: HIGH-to-CRITICAL (scored HIGH in the gap matrix; elevated to
P0 priority because it is empirically confirmed, not theoretical, and
directly triggers critical failure gate #12). **Confidence**: CONFIRMED
via three independent recomputation attempts (see
`audit/portfolio_math_validation.md`).

**Exact location**: `data/output/portfolio_risk_report.json` /
`data/output/portfolio_stack_metadata.json` (`return_matrix_rows: 1317`).

**Evidence**: independently rebuilding the return matrix using the exact
documented method (`scripts/build_portfolio_stack.py::_build_return_matrix`),
the exact same source file, the exact same 10 symbols/weights, and the
report's own stated `features_latest_date` cutoff produces **1621 rows**,
not the reported 1317 — and consequently different `annual_return`
(0.235 vs. 0.187), `annual_volatility` (0.195 vs. 0.127), `sharpe_ratio`
(1.18 vs. 1.42), and `max_drawdown` (-0.391 vs. -0.163). Weight-derived
metrics (max_weight, effective_n, herfindahl_index) reproduced exactly —
isolating the problem specifically to the mutable historical return
window, not the weights or the formulas.

**Impact**: no committed risk report in this repository can currently be
audited or reproduced after the fact. This is a direct instance of the
audit brief's critical failure gate #12 ("Results cannot be reproduced").

**Recommended fix**: freeze or content-hash the exact
`data/processed/stock_features.parquet` (or whatever source file is used
after P0-2 is fixed) state alongside every `portfolio_risk_report.json`,
so a committed report can always be traced back to and reconstructed
from a specific, retrievable data snapshot.

**Required validation test**: generate a new report, freeze its input
snapshot, then — after further data updates occur — reproduce the exact
same report from the frozen snapshot and confirm bit-for-bit match.

**Cross-referenced gap-matrix rows**: Data Quality/"Data lineage /
reproducibility (empirical)", Covariance-Risk/"Realized-return risk
metrics reproducibility".

---

## P0-4 — `final_watchlist.py`'s live scoring still includes the exact factor this repo's own forensic work found actively harmful

**STATUS (2026-07-13): RESOLVED — commit `b966aa2`** (gate #17). Fixed the
exact `alpha_rs_score` leak cited below, and a broader sweep found the same
class of bug independently reintroduced in `scripts/run_meta_ranking.py`
(which had re-leaked the already-fixed `momentum_score`, plus all other v1
shadow components, into the saved meta-ranking outputs via its own inline
merge). Removed all v1 shadow `alpha_*` component merges from every
non-shadow-log consumer; `alpha_score_shadow_v1` and its per-component
fields remain available only in `data/signals/alpha_scores.parquet` and
`alpha_score_shadow_log.parquet` for out-of-sample comparison. Added
`tests/test_final_watchlist.py::test_no_v1_shadow_alpha_fields_in_any_watchlist_output`
and `tests/test_meta_ranking.py::test_meta_ranking_report_outputs_never_carry_v1_shadow_fields`
as regressions against every field in `FORBIDDEN_V1_SHADOW_FIELDS`
reappearing in any output.

**Severity**: CRITICAL. **Confidence**: CONFIRMED (direct code citation,
cross-referenced against `SCORE_FORENSIC_REPORT.md`).

**Exact location**: `src/screening/final_watchlist.py`, `relative_strength_score`
computation (`rs_raw`, ~line 459), which includes `_rank(out.get("alpha_rs_score", ...))`.
`alpha_rs_score` is merged in from `alpha_scores.parquet`'s `rs_score`
column (`_merge_latest_alpha`, ~line 386).

**Evidence**: `SCORE_FORENSIC_REPORT.md` found this exact `rs_score`
component's IC flipped from +0.0141 (2023-2025) to **-0.1060 in 2026** —
"the single largest negative IC of any component in that fold" and one of
"the primary culprits" of a real backtest fold that lost -59.7% while
VNINDEX rose. This session already fixed the *sibling* leak
(`momentum_score`, commits `517a3d0`/`327b8d4`, verified still holding in
this audit) but the same class of bug in `rs_score` was not caught and
remains live in `relative_strength_score` (portfolio weight 20/100 in
`final_watchlist`'s composite).

**Impact**: the Client Ready / Trading Watchlist tiers that reach actual
users are still partly driven by a factor this repository's own
forensic analysis identified as having actively destroyed value in a
real historical fold.

**Recommended fix**: remove `alpha_rs_score` from
`relative_strength_score`'s inputs, mirroring the momentum_score fix
exactly (stop merging `rs_score` from the v1 shadow into
`final_watchlist.py`, keep it available only for shadow comparison).

**Required validation test**: add a regression test mirroring
`test_momentum_score_ignores_alpha_score` — vary `alpha_score`/shadow
`rs_score` inputs while holding everything else fixed, and assert
`relative_strength_score` doesn't move.

**Cross-referenced gap-matrix row**: Signal-Alpha/"final_watchlist
relative_strength_score component".

---

## P1 findings (14 rows, grouped by theme)

**Data validation depth** — `validate_ohlcv` (`src/data/validators.py`)
checks duplicates/missing-close/negative-volume but not the full OHLC
relationship, calendar gaps, extreme returns, or schema drift; no
dedicated test file. **Data lineage** — pipeline metadata lacks a git
commit hash and config-version field entirely, compounding P0-3's
reproducibility gap.

**Signal composite validation** — `final_watchlist`'s two largest
weights (trend 25, momentum 20 = 45/100 points) are never IC-tested as
this specific composite and are individually non-significant on clean
data. The look-ahead guard (`assert_no_forward_columns`) is not called
in `src/alpha/scoring.py`, `scripts/run_alpha_scoring.py`, or
`src/backtest/portfolio_backtest.py` — only at two output/save points.

**Execution realism** — `config/vn_market_rules.yaml`'s `lot_size: 100`
is declared but enforced nowhere (grep-confirmed zero usages); the flat
0.15%/0.4% transaction-cost assumption (two different, unreconciled
values across two backtest engines) has no VN-specific tax/commission/
spread decomposition and needs external verification against actual
brokerage schedules.

**Statistical rigor** — the walk-forward validation rests on only 5
calendar-year folds, which structurally caps the confidence of every
mean-based statistic in every report in this repository (explicitly
disclosed by the reports themselves, independently confirmed here as a
genuine statistical constraint, not just a caveat to note in passing).
No Deflated Sharpe Ratio, PBO, or formal multiple-testing correction
(Bonferroni/FDR) is applied anywhere, despite 192 factor combinations
having been tested — only an informal fixed `|t_NW|>3` threshold stands
in for a real correction. Bootstrap resampling tooling exists
(`src/simulation/bootstrap.py`) but is used only for client-facing path
visualization, not to compute a confidence interval on the backtest's
own headline CAGR/Sharpe.

**Operational** — `config/vn_market_holidays.csv` covers only 4
fixed-date solar holidays; lunar Tết dates are absent (self-disclosed in
code comments), meaning the freshness/staleness check will likely
misfire during and immediately after Tết each year.
