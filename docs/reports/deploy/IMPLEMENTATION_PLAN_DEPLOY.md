# IMPLEMENTATION PLAN — Deploy validated 3-factor score to production

Status: **DRAFT — awaiting "APPROVED"**. No production code touched yet.

## 0. Pre-checks done

- `pytest tests/ -q` → **187 passed**, baseline green. Safe to build on.
- `data/processed/stock_features.parquet` and `benchmark_vnindex.parquet` **are present** in this
  worktree (45MB / 355KB) — real-data verification is possible, no fixture-only fallback needed.
  Required factor columns (`distance_ma20`, `return_20d`, `realized_vol_20d`) all exist.
- Re-ran `PYTHONPATH=. python3 scratch/rolling_walk_forward.py` against current code+data. The
  `take-profit trend-break` row reproduces **exactly** the table in
  `docs/reports/scoring/STRATEGY_RESEARCH_REPORT.md` §6: 2022 -27.6%, 2023 +13.1%, 2024 +2.0%, 2025 +11.6%, 2026 +5.3%,
  avg +0.9%, median +5.3%, win rate 80%. The formula/report is not stale.
- Read `src/analytics/meta_ranking.py::score_meta_ranking()` in full. It is a **different, more
  elaborate formula** (breakout/stealth/momentum/execution component blend with synergy bonuses)
  than what this research touched — confirms report §7 point 2: this function was never exercised
  by the walk-forward backtest (which only ever fell through to the *dynamic fallback inside
  `run_portfolio_backtest`*, not to `score_meta_ranking`). It has not changed since the report was
  written.
- Checked `docs/reports/codebase_audit/AUDIT_REPORT.md` G1 (0-100 is relative rank, not absolute), G5 (missing data → default
  50), G6 (duplicate bonus stacking) — all describe `score_meta_ranking()`, not the backtest
  fallback. Still open, out of scope here per your instructions (no drive-by fixes).
- Traced production wiring:
  - **Live scoring path** (daily pipeline): `scripts/run_meta_ranking.py` → `build_meta_ranking()` →
    `score_meta_ranking()` → feeds `data/signals/meta_ranking.parquet` →
    `build_watchlist_tiers()` → client-ready watchlist. `scripts/build_portfolio_stack.py` consumes
    watchlist candidates for capital allocation; it **never calls `run_portfolio_backtest`**, so the
    take-profit/no-stop-loss overlay has no live-execution counterpart to wire — it is a backtest
    simulation setting only.
  - **Backtest path**: `notebooks/04_watchlist_portfolio/20_portfolio_backtester.ipynb` cell 3 loads
    `data/signals/meta_ranking.parquet` (built by `score_meta_ranking`) and cell 4 calls
    `run_portfolio_backtest(...)` with **no** `stop_loss_pct`/`take_profit_pct`/`market_regime`
    kwargs today (all defaulted off). This is the one place a "production backtest report" is
    generated from the notebook.
  - Confirmed no test currently locks in the old fallback's specific behavior
    (0.4 mom + 0.4 trend + 0.2 liquidity) — grepped `tests/test_portfolio_backtest.py`, nothing
    asserts on it by name/ranking. Safe to replace outright.

## 1. New reusable module: `src/analytics/reversal_quality_score.py`

Rationale for a new module vs. extending `src/alpha/scoring.py`: `alpha/scoring.py`'s
`calculate_alpha_scores` is a momentum-**chasing** model (rewards high `return_20d`/`return_60d`) —
the opposite sign convention from what this research validated. Bolting a mean-reversion score onto
a momentum-chasing module under the same namespace invites someone later averaging the two together
without realizing they cancel out. A dedicated module keeps the two conceptually and namespace-
separated; both remain importable independently by the backtest/notebook.

Contents (pure functions, no hardcoded weights baked in beyond a documented `DEFAULT_*` calibration
for convenience callers):

```python
FACTORS = ["distance_ma20", "return_20d", "realized_vol_20d"]

def compute_factor_ic(features: pd.DataFrame, factors=FACTORS,
                       target_col="forward_return_20d", rebalance_period=20,
                       min_value_ma20=10_000_000_000.0, require_above_ma200=True,
                       min_eligible=15) -> dict[str, float]:
    """Mean Spearman IC per factor, sampled every `rebalance_period` sessions,
    decision lagged 1 session (same convention as scratch/*.py). TRAIN-only by
    construction: caller passes an already-date-filtered `features` slice."""

def derive_factor_weights(mean_ic: dict[str, float]) -> tuple[dict[str, float], dict[str, int]]:
    """weights = |IC| / sum(|IC|); signs = sign(IC). Returns (weights, signs)."""

# Full-history calibration reproduced in this session (matches report §6 exactly);
# used as the built-in default for callers that don't recalibrate explicitly
# (e.g. the backtest's live fallback, which has no train/test split notion).
DEFAULT_WEIGHTS = {"distance_ma20": 0.39, "return_20d": 0.32, "realized_vol_20d": 0.29}
DEFAULT_SIGNS = {"distance_ma20": -1, "return_20d": -1, "realized_vol_20d": -1}

def score_reversal_quality(features: pd.DataFrame, weights=DEFAULT_WEIGHTS,
                            signs=DEFAULT_SIGNS, factors=FACTORS,
                            score_col="reversal_quality_score") -> pd.DataFrame:
    """Per-date cross-sectional percentile rank of `sign * raw_value`, weighted
    sum * 100, output column `score_col` (NOT named `meta_score` — avoids
    colliding with the unrelated official meta_score from meta_ranking.py).
    Missing factor values rank at the 50th percentile (fillna(0.5)), matching
    scratch/rolling_walk_forward.py::build_score exactly."""
```

This makes the 0.39/0.32/0.29 weights **recalibratable**: a future quarterly job can call
`compute_factor_ic` on a fresh TRAIN window + `derive_factor_weights`, instead of the constants
being frozen forever. Nothing in this plan builds that quarterly job (out of scope — not asked for
by the research report or your prompt); only the reusable primitives are being introduced now.

**Test**: `tests/test_reversal_quality_score.py`
- Synthetic-fixture unit tests (no real data dependency, runs in CI): weight/sign derivation from a
  hand-built IC dict; `score_reversal_quality` ranking direction on a tiny synthetic frame (verifies
  low `return_20d`/`distance_ma20`/`realized_vol_20d` → highest score, per the mean-reversion sign
  flip).
- Real-data reproduction test (skipped if `data/processed/stock_features.parquet` absent): runs
  `compute_factor_ic` + `derive_factor_weights` on full history, asserts weights match
  0.39/0.32/0.29 within a small tolerance — this is the "proves it matches the research" check
  your prompt requires.

## 2. Replace the dynamic fallback in `src/backtest/portfolio_backtest.py`

Location: lines 285-323 (`if scores_today.empty and not features_today.empty:` block).

**Before**: inline momentum(0.4)/trend(0.4)/liquidity(0.2) rank blend (proven no-alpha by the
shuffle test in the report).

**After**:
```python
if scores_today.empty and not features_today.empty:
    from src.analytics.reversal_quality_score import score_reversal_quality
    scored = score_reversal_quality(features_today.reset_index())
    scores_today = scored.set_index("symbol")[["reversal_quality_score"]].rename(
        columns={"reversal_quality_score": "meta_score"}
    )
```
No new kwarg/toggle — this is a straight swap of a proven-bad formula for the validated one inside
an existing code path, per your instruction that item (a) is unambiguous and doesn't need to be
opt-in. Docstring of `run_portfolio_backtest` gets one line noting the fallback formula changed.

**Test**: extend `tests/test_portfolio_backtest.py` with
`test_fallback_score_uses_reversal_quality_when_ranking_missing()` — build a small synthetic
`features` frame with no matching `meta_ranking` rows, run the backtest, assert the symbol picked
at the first rebalance is the one with the lowest synthetic `return_20d`/`distance_ma20`/
`realized_vol_20d` (i.e., confirms mean-reversion direction, not momentum-chasing).

## 3. Wire the take-profit overlay into the backtest notebook

File: `notebooks/04_watchlist_portfolio/20_portfolio_backtester.ipynb`, cell 4.

Add `take_profit_pct=0.10, trend_break_col="above_ma20"` to the existing `run_portfolio_backtest(...)`
call (both params already exist and default to off — this just turns them on for the reference
production backtest run). No stop-loss, no `market_regime`, no `giveback_arm_gain` — per report §5,
all three were tested and made things worse or didn't help.

This is a notebook-only change (no `.py` test coverage possible for notebook cells in this repo's
test setup); verification is the Phase 4 manual re-run described below.

## 4. DECISION — `score_meta_ranking()` in `meta_ranking.py`: RESOLVED

**Decided: (i) Leave it untouched.** Ship only items 1-3 below (backtest fallback + notebook
overlay). The live client watchlist keeps using the existing breakout/stealth/momentum/execution
blend exactly as today — it is untouched by this deploy, and remains flagged in `docs/reports/deploy/DEPLOY_REPORT.md`
(Phase 4) as an open item, per report §7.2.

## 5. Commits (one per cluster, after approval)

1. `feat(analytics): add reusable reversal-quality factor scoring module`
2. `fix(backtest): replace no-alpha dynamic fallback with validated 3-factor score`
3. `chore(notebook): enable take-profit trend-break overlay in reference backtest run`

## 6. Out of scope (confirmed, not touching)

- 2022-style crash risk (report §7.1) — no new stop-loss/regime/give-back logic.
- D3 survivorship bias.
- Any change to `src/alpha/scoring.py`'s existing momentum-chasing `calculate_alpha_scores`.
- Any "while I'm in there" cleanup of G1/G5/G6 in `meta_ranking.py` unless you pick option (ii) or (iii) above.

---

**Waiting for "APPROVED"** before writing any production code (items 1-3 only; §4 resolved as "leave untouched").
