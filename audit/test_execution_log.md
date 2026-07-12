# Test Execution Log — Phase C

All commands below were run read-only against the working tree at HEAD
`01d4079` (branch `claude/charming-bartik-d21dc1`). No pipeline that writes
production state was run (no crawler, no daily update script, no scoring
run that appends to shadow logs). Full pytest transcript saved at
`/tmp/audit_pytest_full.log` (outside the repo, not committed).

## Command 1 — full test suite

```
$ cd /Users/jamesb/Desktop/vietnam-quant-research/.claude/worktrees/charming-bartik-d21dc1
$ python -m pytest -v
```

**Result**: `1 failed, 234 passed, 3 warnings in 7.10s`

**Failing test**: `tests/test_reversal_quality_score.py::test_full_history_calibration_matches_strategy_research_report`

```
AssertionError: assert {'distance_ma...eturn_20d': 1} == {'distance_ma...turn_20d': -1}
Differing items:
{'distance_ma20': 1} != {'distance_ma20': -1}
{'return_20d': 1} != {'return_20d': -1}
```

This test was independently re-run and confirmed by a second audit
subagent (backtesting/robustness/engineering) with an identical result,
so the finding is corroborated by two independent executions.

**Assessment**: this is the single known pre-existing failure documented
in the project-context addendum, confirmed still accurate. Root cause:
`derive_factor_weights` recomputes factor *signs* from live IC on the
current `data/processed/stock_features.parquet`, and the test's hardcoded
`DEFAULT_SIGNS` expectation for `distance_ma20`/`return_20d` no longer
matches — consistent with `FACTOR_RETEST_V2_REPORT.md`'s own finding that
neither factor clears the significance bar on the refreshed dataset (and
`return_20d`'s raw sign is reported there as unstable across universes).
Not a new regression; not fixed in this audit (per the read-only
restriction).

The three warnings are expected `UserWarning`s from
`assert_no_forward_columns(mode="drop")` firing correctly in
`test_final_watchlist.py` and `test_meta_ranking.py` — intentional,
asserted-on behavior.

## Command 2 — test collection count

```
$ python -m pytest --collect-only -q
```

**Result**: `235 tests collected in 1.85s` across 32 files in `tests/`.
234 passed + 1 failed = 235 — consistent with Command 1.

## Command 3 — random-seed audit (read-only grep)

```
$ grep -rn "np.random.seed\|random.seed\|default_rng" src/ scripts/
```

**Result**:
```
src/simulation/bootstrap.py:22:    rng = np.random.default_rng(random_state)
src/simulation/bootstrap.py:43:    rng = np.random.default_rng(random_state)
src/models/monte_carlo.py:57:    rng = np.random.default_rng(random_state)
```
No bare global `np.random.seed()`/`random.seed()` calls found in `src/`
or `scripts/` (only in `scratch/` and `tests/`, which is appropriate).
Note (surfaced by the covariance/portfolio-construction audit subagent):
`src/portfolio/monte_carlo.py::generate_random_weights` uses the global
numpy RNG (`np.random.exponential`) with **no** `random_state`/seed
parameter at all — inconsistent with the two modules above. See gap
matrix for this as a standalone finding.

## Command 4 — dependency pinning check (read-only read)

```
$ head -20 requirements.txt
```

**Result**: every dependency uses `>=` only (e.g. `pandas>=2.0`,
`numpy>=1.24`) — no exact `==` pins, no lockfile found in the repo
(`requirements.lock`/`poetry.lock`/`uv.lock` all absent).

## Command 5 — Phase D independent recomputation scripts

Three scripts, all read-only, all writing only to `/tmp/audit_phase_d/`:

```
$ python3 /tmp/audit_phase_d/independent_check.py
$ python3 /tmp/audit_phase_d/independent_check2.py
$ python3 /tmp/audit_phase_d/independent_check3.py
```

Results and interpretation: see `audit/portfolio_math_validation.md`.
Summary: weight-derived metrics (max_weight, effective_n,
herfindahl_index) reproduced exactly; portfolio-variance formula
confirmed correct and symbol-order-robust; risk-contribution
reconciliation confirmed exact; realized-return-based metrics
(annual_return, annual_volatility, sharpe_ratio, max_drawdown) could
**not** be reproduced in any of the three attempts.

## Command 6 — quarantine/firewall grep checks (read-only)

```
$ grep -rn "quarantine_existing_v1" src/ scripts/
```
**Result**: zero hits — confirms no live production code path reads the
quarantined v1 data.

```
$ grep -rn "bonferroni\|fdr\|holm\|benjamini\|deflated\|pbo\b" src/ scripts/ *.md
```
**Result**: zero hits for any formal multiple-testing correction
procedure anywhere in the codebase or reports.

## What was deliberately NOT run this audit (per the read-only restriction)

- `scripts/crawl_disclosure.py` / `scripts/update_disclosure_daily.py` —
  would make external network calls and mutate `data/disclosure/`.
- `scripts/run_alpha_scoring.py` — appends to
  `data/signals/alpha_score_shadow_log.parquet` (a shadow-comparison log
  that must only grow via its own scheduled process, not an audit run).
- `scripts/run_daily_pipeline.py` (any mode) — writes to `data/output/`,
  `data/signals/`, `data/processed/` in ways this audit must not disturb.
- `scripts/build_portfolio_stack.py` — would regenerate
  `data/output/portfolio_risk_report.json`/`portfolio_weights.parquet`,
  the exact artifact Phase D needed to check *as committed*; running it
  would have overwritten the evidence being validated.
- All 19 notebooks — not executed top-to-bottom this round (would be
  needed to fully verify `AUDIT_REPORT.md`'s `run_all_notebooks.sh`
  claim; flagged NOT_VERIFIABLE in the gap matrix instead of run).
