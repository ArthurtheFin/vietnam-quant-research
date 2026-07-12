# Remediation Roadmap

Organized into the 5 phases the audit brief requests. Where a task is
already planned in an existing report, this roadmap cross-references it
rather than restating it — see the "Already planned in" column/note.
Complexity: S/M/L/XL, no calendar-time estimates per instruction.

---

## Phase 1 — Data and mathematical correctness

### 1.1 Repoint (or merge) the production portfolio pipeline off the stale dataset
- **Reason**: `scripts/build_portfolio_stack.py` reads `data/processed/stock_features.parquet`, which `DATA_BASELINE.md` documents as still containing the raw/adjusted-close corruption for an uncatalogued subset of symbols. (P0-2)
- **Affected files**: `scripts/build_portfolio_stack.py`; or, if merging instead, whatever script performs the `data/full_history_v2` → `data/processed/` merge (does not yet exist).
- **Already planned in**: `DATA_BASELINE.md` caveat 1 explicitly recommends this merge — this roadmap item executes that existing recommendation, not a new idea.
- **Proposed implementation**: either (a) repoint `build_portfolio_stack.py`'s `read_parquet` call at `data/full_history_v2`, adapting the return-matrix builder to that schema, or (b) build the documented merge script and repoint `data/processed/` generation to source from `data/full_history_v2`.
- **Acceptance criteria**: `build_portfolio_stack.py` produces identical output whether run against `data/full_history_v2` directly or the freshly-merged `data/processed/`, for every symbol present in both.
- **Required tests**: a new test comparing weights/risk-report output for a known symbol set against both data sources, asserting equality within floating-point tolerance.
- **Dependencies**: none — can start immediately.
- **Complexity**: M.

### 1.2 Acquire or construct a point-in-time listing/delisting universe
- **Reason**: severe, structural survivorship bias affects every backtest and factor test in the repository. (P0-1)
- **Affected files**: new data source + a new `src/data/` loader; `src/validation/bias_checks.py::check_survivorship_bias` (currently unused, would become the consumer).
- **Already planned in**: `BACKFILL_DESIGN_REPORT.md` Task 2 and `DATA_AUDIT_REPORT.md` both flag this as unresolved; no existing report proposes a concrete data source, so this is a genuinely new task, not a duplicate.
- **Proposed implementation**: investigate whether SSI, HOSE/HNX/UPCOM historical listing bulletins, or a third-party VN market-data vendor can supply historical exchange-membership/delisting dates; failing that, manually curate a delisting list from public disclosure records for the highest-impact period (2020-2026).
- **Acceptance criteria**: a point-in-time universe function exists that, given a historical date, returns the symbols actually listed/tradable on that date, including subsequently-delisted names.
- **Required tests**: `check_survivorship_bias` (already exists) run against real data for the first time, with a passing assertion.
- **Dependencies**: external data-source research; may require a paid vendor.
- **Complexity**: XL.

### 1.3 Freeze/hash input data snapshots alongside every committed output
- **Reason**: `portfolio_risk_report.json` cannot currently be reproduced from available data — confirmed empirically (P0-3), and the same root gap (no commit-hash/config-version in lineage) was independently flagged by two audit passes.
- **Affected files**: `src/utils/pipeline_io.py` (`dataframe_metadata`, `write_run_snapshot`, `validate_pipeline_metadata`), `scripts/build_portfolio_stack.py`.
- **Already planned in**: none — new finding this audit.
- **Proposed implementation**: add a `git rev-parse HEAD` commit hash and a content-hash (e.g. SHA-256 of the relevant input parquet) to every pipeline metadata output; optionally snapshot-copy the exact input slice used for a report.
- **Acceptance criteria**: given a committed `portfolio_risk_report.json` and its accompanying metadata, the exact input data state can be retrieved or verified via hash, and the report can be regenerated to match.
- **Required tests**: a reproducibility test that generates a report, records its hash, and confirms re-generation from the same frozen input matches exactly.
- **Dependencies**: none.
- **Complexity**: M.

### 1.4 Remove `alpha_rs_score` from `final_watchlist`'s `relative_strength_score`
- **Reason**: still includes the exact factor `SCORE_FORENSIC_REPORT.md` found actively harmful (-0.1060 IC in 2026). (P0-4)
- **Affected files**: `src/screening/final_watchlist.py` (`_merge_latest_alpha`, `_score`'s `rs_raw` computation).
- **Already planned in**: none directly, but this is the same class of fix already applied to `momentum_score` (commits `517a3d0`/`327b8d4`) — this task generalizes that fix to its sibling.
- **Proposed implementation**: stop merging `rs_score` from `alpha_scores.parquet` into `final_watchlist`, mirroring exactly how `momentum_score` was removed.
- **Acceptance criteria**: `relative_strength_score` computed with no reference to any v1 shadow component.
- **Required tests**: new test mirroring `test_momentum_score_ignores_alpha_score`.
- **Dependencies**: none — can be done immediately, small and isolated.
- **Complexity**: S.

### 1.5 Extend OHLCV validation depth
- **Reason**: `validate_ohlcv` misses several requested checks (full OHLC relationship, calendar gaps, extreme returns, schema/dtype drift).
- **Affected files**: `src/data/validators.py`; new `tests/test_validators.py`.
- **Already planned in**: none.
- **Proposed implementation**: add `high >= max(open, close)`, `low <= min(open, close)`, extreme-return flagging, and dtype consistency checks.
- **Acceptance criteria**: each new check has a corresponding unit test with a synthetic violating row.
- **Required tests**: new `tests/test_validators.py`.
- **Dependencies**: none.
- **Complexity**: M.

---

## Phase 2 — Portfolio and risk engine

### 2.1 Wire tested allocation helpers into the production backtest engine
- **Reason**: `run_portfolio_backtest` imports but doesn't call `equal_weight_allocation`/`inverse_volatility_allocation`, hand-rolling duplicate logic instead — a drift risk.
- **Affected files**: `src/backtest/portfolio_backtest.py`.
- **Already planned in**: none.
- **Proposed implementation**: replace the inline equal-weight/inverse-vol math with calls to the imported, tested helpers.
- **Acceptance criteria**: no duplicated allocation logic remains; existing backtest outputs unchanged (regression-tested).
- **Required tests**: existing portfolio_backtest tests must still pass unchanged.
- **Dependencies**: none.
- **Complexity**: S.

### 2.2 Reconcile the two transaction-cost models
- **Reason**: `portfolio_backtest.py` (0.15%) and `simulator.py` (0.4%) disagree, unreconciled since `REMEDIATION_REPORT.md`'s D6 (still DEFERRED).
- **Affected files**: `src/backtest/portfolio_backtest.py`, `src/backtest/simulator.py`, `config/vn_market_rules.yaml`.
- **Already planned in**: `REMEDIATION_REPORT.md` item D6 — this executes that existing, already-identified deferral.
- **Proposed implementation**: research actual VN brokerage commission + 0.1% sell-side tax + typical spread/slippage; encode as one config-driven, decomposed cost model both engines reference.
- **Acceptance criteria**: both engines cite the same documented cost assumption; the assumption is itemized (commission/tax/spread), not a single flat blend.
- **Required tests**: cost-model unit tests for each component.
- **Dependencies**: external verification of current VN brokerage/tax schedules.
- **Complexity**: M.

### 2.3 Add Ledoit-Wolf (or OAS) covariance shrinkage as an option
- **Reason**: current `shrink_covariance` is a fixed-intensity diagonal blend, not a data-driven optimal shrinkage estimator; already flagged DEFERRED as `REMEDIATION_REPORT.md` H5.
- **Affected files**: `src/portfolio/construction.py`, `src/portfolio/risk.py`.
- **Already planned in**: `REMEDIATION_REPORT.md` H5.
- **Proposed implementation**: add `sklearn.covariance.LedoitWolf`-backed shrinkage as an alternative to `shrink_covariance`, defaulting risk-parity/HRP to it.
- **Acceptance criteria**: Ledoit-Wolf shrinkage available and used by at least one production allocator; existing fixed-shrinkage path remains available for comparison.
- **Required tests**: unit test comparing shrinkage output against a known-answer synthetic covariance.
- **Dependencies**: `scikit-learn` already in `requirements.txt`.
- **Complexity**: M.

### 2.4 Add tracking error / information ratio; complete the risk-report schema
- **Reason**: `tracking_error`/`information_ratio`/`active_share`/`alpha`/`r_squared` are templated in `build_portfolio_stack.py`'s empty-state output but never actually computed in the normal-state branch.
- **Affected files**: `src/risk/management.py`, `scripts/build_portfolio_stack.py`.
- **Already planned in**: none.
- **Proposed implementation**: implement each metric properly (tracking error = std of active returns; IR = active return / tracking error; alpha/beta via regression against benchmark), or remove unused fields from the schema.
- **Acceptance criteria**: every field present in the empty-state template is also computed in the normal-state branch, or removed from both.
- **Required tests**: unit tests for each new metric against a known synthetic case.
- **Dependencies**: none.
- **Complexity**: M.

### 2.5 Add a random seed to portfolio-level Monte Carlo; reframe "best sample" as a range
- **Reason**: `src/portfolio/monte_carlo.py::generate_random_weights` has no seed control (unlike its sibling module); `select_best_portfolio` still presents a single in-sample-maximized "optimal" portfolio, a documented noise-mining anti-pattern (`AUDIT_REPORT.md` H5, still DEFERRED).
- **Affected files**: `src/portfolio/monte_carlo.py`, `notebooks/04_watchlist_portfolio/14_portfolio_construction.ipynb`.
- **Already planned in**: `AUDIT_REPORT.md` H5 / `REMEDIATION_REPORT.md` (DEFERRED).
- **Proposed implementation**: add `random_state` parameter matching `src/models/monte_carlo.py`'s pattern; change notebook 14's reporting to show a percentile range (e.g. 10th-90th) rather than a single "best" portfolio, or add an explicit caveat next to the number.
- **Acceptance criteria**: two runs with the same `random_state` produce identical results; notebook output either shows a range or an explicit noise-mining caveat.
- **Required tests**: `tests/test_portfolio_monte_carlo.py` extended to assert determinism given a fixed seed.
- **Dependencies**: none.
- **Complexity**: S (seed) + M (reframing notebook output).

---

## Phase 3 — Backtesting and validation

### 3.1 Enforce board lot size in position sizing
- **Reason**: `lot_size: 100` declared in config, enforced nowhere (grep-confirmed).
- **Affected files**: `src/backtest/portfolio_backtest.py`, `src/backtest/simulator.py`.
- **Already planned in**: none.
- **Proposed implementation**: round computed position sizes to the nearest `lot_size` before applying to NAV.
- **Acceptance criteria**: all backtest-generated position sizes are multiples of `lot_size`.
- **Required tests**: unit test asserting rounded sizes.
- **Dependencies**: none.
- **Complexity**: S.

### 3.2 Extend look-ahead guard coverage to the backtest and scoring entry points
- **Reason**: `assert_no_forward_columns` is only called at two output/save points, not in `src/alpha/scoring.py`, `scripts/run_alpha_scoring.py`, or `src/backtest/portfolio_backtest.py`.
- **Affected files**: `src/alpha/scoring.py`, `scripts/run_alpha_scoring.py`, `src/backtest/portfolio_backtest.py`.
- **Already planned in**: none — extends the existing D5 guard pattern to new call sites.
- **Proposed implementation**: add raise-mode guard calls at each entry point identified.
- **Acceptance criteria**: a forward_return_ column injected into a test fixture causes each of these paths to raise, not silently proceed.
- **Required tests**: new unit tests per entry point, mirroring existing `test_*_drops_forward_columns` patterns.
- **Dependencies**: none.
- **Complexity**: S.

### 3.3 Decompose the transaction-cost model with VN-specific tax/commission/spread
- Same as Phase 2.2 — cross-referenced here since it is also a Section 9 (Backtesting) finding.

### 3.4 Add market-impact / participation-rate limits to position sizing
- **Reason**: no cap on trade size relative to average daily volume beyond the existing eligibility liquidity filter.
- **Affected files**: `src/backtest/portfolio_backtest.py`, `src/portfolio/constraints.py`.
- **Already planned in**: none.
- **Proposed implementation**: add a participation-rate cap (e.g. max X% of `value_ma20`/`volume_ma20` per trade) to position sizing.
- **Acceptance criteria**: a synthetic large-NAV scenario is capped by the participation limit rather than sizing at full theoretical weight.
- **Required tests**: unit test with a deliberately oversized NAV/position scenario.
- **Dependencies**: none.
- **Complexity**: M.

### 3.5 Increase walk-forward fold count or add explicit confidence intervals to every mean-based statistic
- **Reason**: only 5 calendar-year folds exist; every mean-based statistic in every report has a large, unquantified standard error as a structural consequence.
- **Affected files**: `scratch/rolling_walk_forward.py` and any report that states a mean-based statistic without a confidence interval.
- **Already planned in**: the caveat itself is already disclosed in `CONCENTRATION_ANALYSIS_REPORT.md`/`FOLD_AUTOPSY_REPORT.md`; the remediation (more folds or explicit CIs) is new.
- **Proposed implementation**: switch to rolling monthly/quarterly walk-forward windows instead of annual to generate more folds; alternatively, report standard errors/confidence intervals alongside every mean statistic going forward.
- **Acceptance criteria**: either fold count materially increases, or every future report states a CI/SE next to every mean-based figure.
- **Required tests**: N/A (methodology change, not a code correctness test).
- **Dependencies**: more granular historical data already exists (`data/full_history_v2` is daily), so this is primarily a re-run of existing backtest code with a different fold schedule.
- **Complexity**: L.

---

## Phase 4 — Robustness and statistical testing

### 4.1 Implement Deflated Sharpe Ratio for the production score
- **Reason**: no formal overfitting-correction statistic exists anywhere in the repo.
- **Affected files**: new module, likely `src/validation/robustness.py` or a new `src/validation/overfitting.py`.
- **Already planned in**: none.
- **Proposed implementation**: implement DSR (Bailey & López de Prado) accounting for the number of trials (44 factors × configs) and non-normal returns.
- **Acceptance criteria**: a Deflated Sharpe Ratio is computed and reported for `alpha_score` v2's confirmation backtest.
- **Required tests**: unit test against a known-answer DSR calculation (e.g. from the original paper's worked example).
- **Dependencies**: none additional (`scipy`/`numpy` sufficient).
- **Complexity**: M.

### 4.2 Apply formal multiple-testing correction to the 192-combination factor retest
- **Reason**: only an informal fixed `|t_NW|>3` threshold stands in for a real correction; no Bonferroni/FDR procedure exists anywhere.
- **Affected files**: `FACTOR_RETEST_V2_REPORT.md`'s underlying analysis script (in `scratch/`), re-run to produce updated q-values.
- **Already planned in**: none — `ROBUST_FACTOR_IC_REPORT.md` only acknowledges the problem informally.
- **Proposed implementation**: apply Benjamini-Hochberg FDR control (or Bonferroni) across the 192 tested combinations; re-state which factors survive at a controlled false-discovery rate.
- **Acceptance criteria**: `FACTOR_RETEST_V2_REPORT.md` (or a successor document) reports FDR-adjusted q-values alongside existing t-statistics.
- **Required tests**: N/A (statistical re-analysis, not code).
- **Dependencies**: none (`statsmodels` or a simple manual BH implementation suffices).
- **Complexity**: S.

### 4.3 Use bootstrap resampling to compute a confidence interval on backtest CAGR/Sharpe
- **Reason**: `src/simulation/bootstrap.py` exists and is correctly seeded, but is only used for client-facing path visualization, not to quantify statistical significance of the backtest's own headline numbers.
- **Affected files**: `src/simulation/bootstrap.py` (consumer), whichever report/script produces headline CAGR/Sharpe figures.
- **Already planned in**: none.
- **Proposed implementation**: apply `block_bootstrap_returns` to the walk-forward return series to produce a bootstrap confidence interval around CAGR/Sharpe.
- **Acceptance criteria**: a bootstrap CI is reported alongside every headline CAGR/Sharpe figure going forward.
- **Required tests**: unit test on a synthetic return series with a known CI.
- **Dependencies**: none.
- **Complexity**: M.

### 4.4 Separate holdout for portfolio-construction hyperparameter selection
- **Reason**: size=10/sector-cap=2 were chosen by evaluating against the same 5 folds used to report performance.
- **Affected files**: `CONCENTRATION_ANALYSIS_REPORT.md`'s underlying analysis script.
- **Already planned in**: none — `CONCENTRATION_ANALYSIS_REPORT.md` itself discloses this as a judgment call, not a fix.
- **Proposed implementation**: once fold count increases (4.5/3.5 above), reserve a subset of folds purely for construction-parameter selection, distinct from the folds used to report final performance.
- **Acceptance criteria**: portfolio-construction parameter selection uses a fold/period never used in the reported performance numbers.
- **Required tests**: N/A (methodology change).
- **Dependencies**: Phase 3.5 (more folds) makes this practical.
- **Complexity**: M.

---

## Phase 5 — Production hardening

### 5.1 Pin dependencies / add a lockfile
- **Reason**: `requirements.txt` uses `>=` only; no lockfile exists.
- **Affected files**: `requirements.txt`, new lockfile.
- **Proposed implementation**: generate a lockfile via `pip-compile`, `poetry`, or `uv`.
- **Acceptance criteria**: exact versions pinned; a fresh environment installs identically every time.
- **Required tests**: N/A (environment change).
- **Dependencies**: none.
- **Complexity**: S.

### 5.2 Add lunar Tết dates to the holiday calendar
- **Reason**: `config/vn_market_holidays.csv` self-discloses this gap; freshness checks will misfire around Tết.
- **Affected files**: `config/vn_market_holidays.csv`, ideally a programmatic lunar-calendar source rather than hand-maintenance.
- **Proposed implementation**: source Tết and other lunar holiday dates for the relevant years; consider a small lunar-calendar library or an annually-maintained reference table.
- **Acceptance criteria**: freshness check correctly identifies Tết week as a holiday period without manual intervention that year.
- **Required tests**: unit test with a Tết-week date confirming it's excluded from expected-trading-date calculations.
- **Dependencies**: none.
- **Complexity**: S.

### 5.3 Atomic writes for output files
- **Reason**: `write_json`/`to_parquet` write directly with no temp-file+rename pattern; a crash mid-write could corrupt output.
- **Affected files**: `src/utils/pipeline_io.py`, `src/data/loaders.py`.
- **Proposed implementation**: wrap writes in a temp-file + `os.replace` pattern.
- **Acceptance criteria**: a simulated interrupted write leaves the previous good file intact.
- **Required tests**: test that kills the write mid-way (or mocks the failure) and confirms the prior file is untouched.
- **Dependencies**: none.
- **Complexity**: S.

### 5.4 Verify `run_all_notebooks.sh`'s failure-reporting accuracy
- **Reason**: `AUDIT_REPORT.md` J1 previously flagged this as always printing success even on failure; not re-verified by execution in this (read-only) audit.
- **Affected files**: whatever `run_all_notebooks.sh` script exists.
- **Already planned in**: `AUDIT_REPORT.md` J1.
- **Proposed implementation**: run the script against a deliberately-broken notebook and confirm it now reports failure correctly (or fix it if it doesn't).
- **Acceptance criteria**: a deliberately-failing notebook causes the script to report failure, not success.
- **Required tests**: the verification run itself serves as the test.
- **Dependencies**: none.
- **Complexity**: S.

### 5.5 Widen the disclosure natural key
- **Reason**: 829 rows (1.4%) collide on `(symbol, event_type, person_name, disclosure_date)` and get silently collapsed by dedup.
- **Affected files**: `src/data/disclosure_ingest.py`.
- **Already planned in**: `DISCLOSURE_BASELINE.md` caveat 1 already recommends this exact fix.
- **Proposed implementation**: widen `NATURAL_KEY` to include `link_key` or `registration_window_start`.
- **Acceptance criteria**: re-ingesting the full raw tier with the widened key produces zero collision-driven row loss (verified against the known 829-row collision count).
- **Required tests**: regression test using the specific colliding examples already identified (Đào Văn Duy/AAA, Vương Ngọc Yến/ACE).
- **Dependencies**: none.
- **Complexity**: S.

### 5.6 Add git commit hash and config version to pipeline metadata
- Same as Phase 1.3 — cross-referenced here since it is also a Section 11 (Engineering) concern.
