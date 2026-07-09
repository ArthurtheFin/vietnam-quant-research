# DEPLOY REPORT — validated 3-factor score → production

Follows `IMPLEMENTATION_PLAN_DEPLOY.md` (approved). Scope: items 1-3 only
(§4 was resolved as "leave `score_meta_ranking()` untouched").

## What was done

**Commit `b18a34b`** — `feat(analytics): add reusable reversal-quality factor scoring module`
- New [src/analytics/reversal_quality_score.py](src/analytics/reversal_quality_score.py):
  `compute_factor_ic` (train-window Spearman IC, lag-1 decision convention),
  `derive_factor_weights` (|IC|-proportional weights + sign), `score_reversal_quality`
  (cross-sectional composite, missing values → neutral 50th percentile).
  `DEFAULT_WEIGHTS`/`DEFAULT_SIGNS` hold the full-history calibration as a
  default, not a hardcoded permanent constant — recalibrate by calling the
  two functions on a fresh TRAIN window.
- Re-exported from `src/analytics/__init__.py`.

**Commit `77b0848`** — `fix(backtest): replace no-alpha dynamic fallback with validated 3-factor score`
- [src/backtest/portfolio_backtest.py](src/backtest/portfolio_backtest.py) — the dynamic
  fallback (fired whenever a decision date has no `meta_ranking` coverage) no
  longer computes the old momentum(0.4)/trend(0.4)/liquidity(0.2) blend; it
  calls `score_reversal_quality` instead. No new kwarg — straight swap of a
  proven-bad formula for the validated one, as agreed (item a, unambiguous).

**Commit `31b1710`** — `chore(notebook): enable take-profit trend-break overlay in reference backtest run`
- [notebooks/04_watchlist_portfolio/20_portfolio_backtester.ipynb](notebooks/04_watchlist_portfolio/20_portfolio_backtester.ipynb)
  cell 4 now passes `take_profit_pct=0.10, trend_break_col="above_ma20"` to
  `run_portfolio_backtest`. No stop-loss / regime filter / give-back stop —
  per report §5, all three were tested and made results worse or didn't help.
  Notebook was re-executed end-to-end against real data (`jupyter nbconvert
  --execute`); it completed with no errors.

## Tests proving the numbers match the research

- `tests/test_reversal_quality_score.py` (7 tests): synthetic-fixture unit
  tests for weight/sign derivation, IC recovery on a known monotonic
  relationship, and mean-reversion ranking direction — plus
  `test_full_history_calibration_matches_strategy_research_report`, which
  runs `compute_factor_ic` + `derive_factor_weights` on the real
  `data/processed/stock_features.parquet` and asserts the result matches
  `DEFAULT_WEIGHTS`/`DEFAULT_SIGNS` (0.39/0.32/0.29, all negative) within
  0.01. This test is skipped (not failed) if that parquet file is absent —
  it was present in this environment, so the check ran and passed.
- `tests/test_portfolio_backtest.py::test_fallback_score_uses_reversal_quality_when_ranking_missing`
  (new): confirms the fallback now picks the best **mean-reversion** candidate
  (lowest distance_ma20/return_20d/realized_vol_20d), not the momentum leader
  the old formula would have picked.
- Full suite: **195 passed**, 0 failed (was 187 before this work; +8 new tests).

## Real-data reproduction (Phase 4 requirement)

Re-ran the exact research scripts against current code + data, unchanged:

- `PYTHONPATH=. python3 scratch/rolling_walk_forward.py` → the "take-profit
  trend-break" row reproduces **exactly**: 2022 -27.6%, 2023 +13.1%, 2024
  +2.0%, 2025 +11.6%, 2026 +5.3%, avg +0.9%, median +5.3%, win rate 80% —
  identical to `STRATEGY_RESEARCH_REPORT.md` §6, and identical to the run
  performed during Phase 0 before any code changed (confirms no regression
  from the fallback swap or notebook edit).
- `PYTHONPATH=. python3 scratch/walk_forward_validation.py` → single-split
  result reproduces exactly: CAGR +6.82%, Sharpe +0.27, matching report §4.
- The notebook's own full-history run (`20_portfolio_backtester.ipynb`, using
  the real `data/signals/meta_ranking.parquet` wherever it has coverage, and
  falling back to the new 3-factor score elsewhere, now with the take-profit
  overlay on) produced CAGR +17.17%, Sharpe +0.66, MaxDD -38.35%. **This
  number is not directly comparable to the report §6 table** — the rolling
  walk-forward table uses the pure 3-factor score for the entire test
  period, while the notebook blends whatever `score_meta_ranking()` output
  exists in `meta_ranking.parquet` with the new fallback only on dates it
  doesn't cover. Both are legitimate, they just answer different questions;
  documenting this explicitly so the two numbers aren't mistaken for a
  discrepancy.

## What remains open (not touched by this deploy, by design)

1. ~~`score_meta_ranking()` in `src/analytics/meta_ranking.py` is untouched.~~
   **Superseded in a later session**: the formula was subsequently validated
   (`META_RANKING_VALIDATION_REPORT.md` — negative IC, loses in 3 of 5
   rolling-fold years, confirmed on the complete formula including real
   walk-forward `trade_cards`) and then replaced outright with the same
   validated 3-factor score used elsewhere, once that evidence was in hand.
   `scripts/run_meta_ranking.py` → the client-ready watchlist path now uses
   the validated formula.
2. **2022-style crash risk (report §7.1) is unresolved** — no new stop-loss/
   regime/give-back logic was added; out of scope per your instructions.
3. **D3 survivorship bias** — still open, untouched.
4. **AUDIT_REPORT.md G1/G5/G6** (relative-rank scoring, default-50 filler,
   duplicate bonus stacking) — all describe `score_meta_ranking()`, not
   anything touched here; still open.
5. The 0.39/0.32/0.29 weights are a point-in-time calibration on 2020-2026
   history. `compute_factor_ic`/`derive_factor_weights` are reusable, but no
   recurring recalibration job was built (not asked for, would be new scope).
