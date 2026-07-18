# Test Execution Log — Round 2 (2026-07-18)

Every command executed during this round's audit, in order. All commands
were read-only against project state (test runs, greps, file reads, and
in-memory recomputation) except the creation of `audit/round2/` itself.
No pipeline step that writes to `data/output/`, `data/signals/`, or any
other tracked data path was executed. No external service (SSI API,
crawler) was called.

## Discovery (Phase A)

```
find src scripts -name "*.py" | wc -l                       -> 123
ls src/ ; ls scripts/ | head -40                             -> confirmed structure unchanged
find notebooks -name "*.ipynb" | wc -l                       -> 67
find tests -name "test_*.py" | wc -l                         -> 39
```

## Full test suite (run 3 times across the round, identical result each time)

```
python -m pytest tests/ -q
-> 295 passed, 3 warnings (0 failed) — up from 235 passed at the 2026-07-12 baseline
```

## Gate #6 verification (stale data / dataset_config wiring)

```
grep -n "stock_features.parquet|OFFICIAL_FEATURES_PATH|dataset_config" scripts/build_portfolio_stack.py
-> confirms line 18 imports OFFICIAL_FEATURES_PATH, line 233 reads PROJECT_ROOT/OFFICIAL_FEATURES_PATH

python -m pytest tests/test_dataset_config.py -v
-> 6 passed: test_no_hardcoded_derived_dataset_paths_outside_config,
   test_no_module_reads_legacy_raw_dir_outside_allowlist,
   test_no_module_reads_quarantine_dir,
   test_quarantined_files_are_absent_from_canonical_processed_paths[x3]
```

## Gate #17 verification (alpha_rs_score leak)

```
grep -n "alpha_rs_score|FORBIDDEN_V1_SHADOW_FIELDS" src/screening/final_watchlist.py src/analytics/meta_ranking.py
-> confirms alpha_rs_score removed from relative_strength_score's average (comment: "removed from this average (audit P0-4 / gate #17)")

python -m pytest tests/test_final_watchlist.py -k "shadow" tests/test_meta_ranking.py -k "shadow" -v
-> 3 passed: test_no_v1_shadow_alpha_fields_in_any_watchlist_output,
   test_merge_alpha_score_v2_only_merges_v2_not_v1_shadow_fields,
   test_meta_ranking_report_outputs_never_carry_v1_shadow_fields

python3 -c "import pandas as pd; df = pd.read_parquet('data/signals/final_watchlist.parquet'); ..."
-> live artifact inspection: 0 shadow columns found among 34 total columns
```

## Gate #12 verification (reproducibility) — see portfolio_math_validation.md for full output

```
python3 <<'PY'
# read committed portfolio_risk_report.json + portfolio_weights.parquet (read-only)
# rebuild return_matrix via scripts.build_portfolio_stack._build_return_matrix
# truncated to the report's own features_latest_date=2026-07-13
# call src.risk.management.build_portfolio_risk_report with committed risk_parity weights
# run twice for determinism
PY
-> row count: recompute=1626, committed track_record_days=1626 (exact)
-> annual_return/annual_volatility/sharpe_ratio/max_drawdown: exact match (1e-9) on all 4, both runs identical
```

## Phase D independent math validation (w^T Σw, symbol-order, risk contribution)

```
python3 <<'PY'
# w^T Sigma w with pandas default pairwise-deletion cov() -> did NOT match (0.2404 vs 0.2315)
# root-caused: portfolio_return_series uses fillna(0.0) before summing, not pairwise deletion
# re-ran with fillna(0.0)+ddof=0 matching the production convention exactly -> matched (1e-9)
# reversed symbol order -> variance matched to 1e-12
# MCR/CR/%CR -> sum(CR)=sigma_p (1e-9), sum(%CR)=100.00000000000002%
PY
```

## Spot-verification of PATH_TO_100.md's other "XONG" (done) claims

```
head -10 requirements.txt                          -> pinned exact versions, confirmed
cat config/vn_market_holidays.csv | head -10        -> lunar Tet dates present, empirically sourced
grep -rn "lot_size" src/ scripts/                   -> 0 matches (still not enforced, confirmed still open)
python3 -c "... pipeline_metadata.json lineage..."  -> git_commit_hash present and populated

grep -n "transaction_cost_pct.*0\.|0.0015|0.004" src/backtest/portfolio_backtest.py src/backtest/simulator.py
-> confirms still split (0.0015 vs 0.004), still open

grep -n "def _atomic_write|def save_parquet|def save_csv_atomic|atomic" src/data/loaders.py
-> confirms atomic-write helper present and used by both save functions

grep -n "NATURAL_KEY" src/data/disclosure_ingest.py
-> confirms widened key (6 fields + dedup_seq)

grep -n "DSR|Deflated Sharpe|Benjamini-Hochberg|bootstrap" docs/reports/scoring/ROBUSTNESS_REPORT.md
-> confirms DSR=0.0083, BH-FDR q=0.05/214 tests, bootstrap CI all present as claimed

grep -n "LedoitWolf|shrink_covariance" src/portfolio/construction.py
-> confirms still fixed-intensity (shrinkage=0.1 default), no LedoitWolf import found -- still open

grep -n "turnover" src/backtest/portfolio_backtest.py
-> confirms turnover computed/costed but not capped -- still open

grep -n "def.*sector.*cap|max_per_sector" src/backtest/portfolio_backtest.py src/portfolio/constraints.py
-> confirms count-based mechanism unchanged, still dual/unreconciled with weight-based mechanism

grep -n "FOLDS = \[" -A6 scratch/concentration_null_test.py
-> confirms still exactly 5 calendar-year folds (2022-2026)

grep -n "random_state|default_rng|np.random.seed" src/portfolio/monte_carlo.py
-> 0 matches -- still unseeded, confirmed still open

grep -rn "check_survivorship_bias" src/ scripts/
-> only the definition + __init__.py re-export; zero call sites -- Gate #3 confirmed still open

python3 -c "from src.validation.trading_status import latest_trading_status; ..."
-> live status split: ACTIVE 462 / STALE_SHORT 19 / INACTIVE_LONG 20

grep -n "^def load_universe_symbols" -A8 src/data/disclosure_ingest.py
-> confirms delegation to src.data.universe.tracked_universe_symbols (exclusion-sync fix)

python -m pytest tests/test_validators.py -q
-> 10 passed (new test file, confirmed OHLCV validation expansion)

python -m pytest tests/test_reversal_quality_score.py -v
-> 7 passed, including test_full_history_calibration_matches_strategy_research_report
   (previously the one known-failing test; now passing)

grep -rn "tracking_error|information_ratio|active_share|r_squared" scripts/build_portfolio_stack.py src/risk/*.py src/portfolio/*.py
-> confirms these 4 fields exist ONLY in the empty-candidates placeholder branch, never
   actually computed in the live (non-empty) path -- still open
```

## Documentary re-reads (no execution, evidence citation only)

- `audit/audit_summary.json`, `audit/quantitative_finance_scorecard.md`,
  `audit/critical_findings.md`, `audit/quantitative_finance_gap_matrix.csv`
  (75 rows), `audit/PATH_TO_100.md`, `audit/architecture_dependency_map.md`
  — full read, used as the Round 1 baseline for every delta claim.
- `PROJECT_STATE.md`, `PUSH_REVIEW.md` (tail), `docs/reports/scoring/ROBUSTNESS_REPORT.md`,
  `docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md`, `audit/SECTOR_MAPPING_COVERAGE_REPORT.md` — read
  in full or in relevant part this session.

## Explicitly NOT executed this round (scope constraints)

- No pipeline script that writes to `data/output/`, `data/signals/`, or
  any tracked path (`build_portfolio_stack.py`, `run_daily_pipeline.py`,
  `update_prices_daily.py`, `update_disclosure_daily.py`, etc.) was run
  in its normal write mode.
- No new IC/null-test/prereg was run (firewall constraint F — this round
  reads existing research-report conclusions, does not generate new ones).
- No notebook was executed (`run_all_notebooks.sh` success-reporting
  claim and notebook 14's Monte Carlo cell were not re-verified by
  execution this round; both remain RESOLVED_UNVERIFIED / KNOWN_OPEN
  respectively per the gap matrix).
- `check_survivorship_bias` was not run against real data this round
  (would be new research output, not a verification of an existing
  claim — out of scope per the inventory-only + firewall constraints).
- The 829-row NATURAL_KEY collision "0 collisions after widening" claim
  was not independently re-counted against the full 57,800-row disclosure
  dataset (would require a fresh anti-join scan) — marked
  RESOLVED_UNVERIFIED accordingly.
