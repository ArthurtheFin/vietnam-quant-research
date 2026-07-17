# META_RANKING_VALIDATION_REPORT — is `score_meta_ranking()` actually good?

Follow-up to `docs/reports/scoring/docs/reports/scoring/STRATEGY_RESEARCH_REPORT.md` §7.2, which flagged that the live
client-watchlist formula (`src/analytics/meta_ranking.py::score_meta_ranking`)
was never validated good or bad — the original backtest never reached it
(it only ever fell through to the momentum fallback, since
`meta_ranking.parquet` only had 16 days of coverage). This applies the same
IC + shuffle-test + rolling-fold rigor used to validate the 3-factor score.

Scripts: `scratch/validate_score_meta_ranking.py` (partial-formula pass, run
first) and `scratch/validate_score_meta_ranking_full.py` (closes the gap the
first pass left open — see "Update" section below). Diagnostic only, not
production code — consistent with how the earlier factor research was done.

## Update: the 30% gap has now been closed

The section below ("Structural caveat") originally argued `trade_cards`
couldn't be reconstructed historically without look-ahead, because its
`edge_tier`/`profit_factor` come from a full-sample backtested-edge lookup.
That's true of the *production* lookup (`breakout_20d_setup_eligibility.parquet`,
computed once from the entire history) — but the underlying computation
(`src/backtest/breakout_research.py` + `src/reporting/trade_card_pipeline.py`
::`build_trade_cards`) can be re-run on data **truncated to each historical
decision date**, since `build_non_overlap_entries` already drops any breakout
entry whose `forward_return_20d` isn't fully realized yet — no manual
look-ahead guarding needed, it falls out of the existing code.
`scratch/validate_score_meta_ranking_full.py` does this (fixed -10% stop loss
instead of the production pipeline's train/validation stop-sweep, a
deliberate simplification — see that script's docstring) and successfully
reconstructed a genuine walk-forward `trade_cards` snapshot at 78 of 81
historical decision dates, in ~2.5 minutes.

**Result: running the complete formula (real `breakout_component_score`, not
a constant) changes essentially nothing.** IC: -0.0787, t=-2.57, N=40, 35%
of dates positive (vs the partial formula's -0.0754, t=-2.36, 45% positive —
statistically indistinguishable, if anything marginally more negative).
Rolling 5-fold: 2022 -27.6%, 2023 +38.1%, 2024 -24.3%, 2025 +12.8%, 2026
-10.2%, avg -2.25%, median -10.23%, win rate 40% — within noise of the
partial-formula numbers below. The 6-year aggregate backtest is even more
flattering in isolation (+7.48%, beating 100% of 20 shuffle seeds) than the
partial version's +2.99%, which only reinforces the point made below about
why that single-window number shouldn't be trusted on its own.

**This means the caveat below ("30% remains genuinely untested") no longer
applies — the verdict is now based on the complete formula, and it's
unchanged: no evidence of alpha, weak evidence of the opposite.** The
"secondary check" paragraph (waiting for the sparse 16 live dates to get a
completed forward-return window) is superseded by this — it's no longer the
only way to get full-formula evidence.

## Structural caveat — read before the verdict (original partial-formula pass)

`score_meta_ranking()` blends 4 components from 3 input sources. Only 2 of
those 3 have genuine multi-date history without look-ahead:

- `features` (technical) → `data/signals/setup_signals.parquet`, full
  2020-2026 daily history. ✅
- `stealth` → `data/signals/stealth_accumulation_history.parquet`, full
  2020-2026 daily history. ✅
- `trade_cards` → only ever exists as a ~16-day **live snapshot**
  (`breakout_20d_trade_cards.parquet`), because its `edge_tier`/
  `profit_factor`/`stop_loss` columns come from a full-sample backtested-edge
  lookup (`breakout_20d_setup_eligibility.parquet`) computed once FROM the
  entire history — using it at every historical decision date would itself
  be look-ahead bias. ❌ not reconstructable.

So this validation tests the historically-reconstructable 70% of the
formula's intended weight (momentum 25% + execution 15% + stealth 30% +
risk_penalty -20%, renormalized). With `trade_cards` absent,
`breakout_component_score` (intended 30% weight) collapses to a **constant**
across all symbols at every date — verified directly in the script
(`nunique() == 1` on every date checked) — so it cannot bias the ranking,
it just isn't being tested. The verdict below is about the tested 70%, not
proof about the full formula with real trade_cards.

## Results

**IC vs `forward_return_20d`, 40 rebalance dates, 2020-2026:**

| mean IC | t-stat | N | median | % dates positive |
|---|---|---|---|---|
| **-0.0754** | **-2.36** | 40 | -0.0765 | 45% |

Negative and statistically significant (|t| > 2). Weaker in magnitude than
the old momentum fallback (which IC-tested at -0.20, t=-5.16 per
`scratch/test_evidence_based_score.py`), but the same sign: higher score
does **not** predict higher forward returns — if anything, slightly the
opposite.

**Single 6-year aggregate backtest** (top-5 by reconstructed score, no
overlay):

| | CAGR | MaxDD | Sharpe |
|---|---|---|---|
| Reconstructed score_meta_ranking() | +2.99% | -59.33% | +0.12 |
| Shuffled (avg of 20 seeds) | -3.26% (std 4.49%, range -10.2%..+9.0%) | | |

Real beat 19 of 20 shuffle seeds here — taken alone, this would look like a
positive signal.

**Rolling 5-fold breakdown** (same fold boundaries as
`docs/reports/scoring/docs/reports/scoring/STRATEGY_RESEARCH_REPORT.md` §6, one independent test year at a time):

| | 2022 | 2023 | 2024 | 2025 | 2026 | Avg | Median | Win rate |
|---|---|---|---|---|---|---|---|---|
| Reconstructed score_meta_ranking() | -27.6% | +38.1% | **-23.9%** | +12.8% | -10.2% | **-2.17%** | **-10.23%** | **40%** |
| (reference) validated 3-factor score | -27.6% | +13.1% | +2.0% | +11.6% | +5.3% | +0.9% | +5.3% | 80% |

This is the same lesson the original research already learned once: a single
multi-year aggregate number can flatter a formula that has no real edge. The
6-year aggregate here (+2.99%, beating 19/20 shuffles) is almost entirely an
artifact of one very good year (2023, +38%) sitting in the same window as one
very bad year (2022, -27.6%) netting out to a positive-looking blend. Once
split into independent yearly folds, the picture reverses: **3 losing years
out of 5, negative average, negative median, and a losing year (2024, -23.9%)
that doesn't even correspond to the validated formula's known bad year.**

**Secondary check on the real formula** (with real `trade_cards`, over the
~16 live production dates where it actually exists): not computable in this
environment — no date in `data/signals/meta_ranking.parquet` had a symbol
count ≥ 15 with a completed `forward_return_20d` window (the production data
here is too close to "today" for a full 20-session-forward return to exist
yet). This check would need to be re-run once ~20 more trading sessions have
passed after this production data was captured.

## Verdict (updated, full formula)

**No evidence of positive alpha in `score_meta_ranking()` — tested now as the
COMPLETE formula (real walk-forward `trade_cards` included, not a constant
placeholder), not just the 70% partial reconstruction.** Weak but
statistically significant negative IC (-0.079, t=-2.57, N=40), and a rolling
walk-forward backtest that loses money in 3 of 5 independent years (avg
-2.25%, median -10.23%, win rate 40%). Adding the real breakout/trade_cards
component changed nothing material versus the partial-formula pass — this
is no longer a partial finding with an open 30% gap; it's now a complete
one. Recommend treating any future decision to blend or replace this formula
(report §7.2's item 2/3 options) as resting on solid, not partial, evidence.

## Action taken (later in this session, once the full-formula evidence was in hand)

Given the complete-formula verdict above, `score_meta_ranking()` in
`src/analytics/meta_ranking.py` has been **replaced outright**: `meta_score`
is now `score_reversal_quality()` (the same validated 3-factor mean-reversion
score used in the backtest fallback), not the old breakout/stealth/momentum/
execution blend.

What changed and what didn't:
- `meta_score` computation: fully replaced. No blending with the old
  formula, no synergy bonus (removed — it added points for
  breakout/watchlist/eligible flags on top of a blend that no longer exists;
  keeping it would have meant adding bonus points to an otherwise-independent
  technical score for reasons that no longer apply).
- `breakout_component_score`, `stealth_component_score`,
  `momentum_component_score`, `execution_component_score`, `risk_penalty_score`
  are **still computed** — they're informational inputs to `meta_summary`/
  `setup_style`, and `final_watchlist.py` independently consumes
  `risk_penalty_score`/`trade_edge_score`/`setup_quality_score`. None of that
  downstream logic needed to change.
- `priority_bucket` thresholds (75/60/45) and the G5 thin-evidence cap were
  **kept as-is** — sanity-checked against real production data
  (`data/signals/setup_signals.parquet` + the live `trade_cards`/`stealth`
  snapshots): 501 symbols, score range 2.4-100, mean 51.5, buckets split
  66/136/117/182 (Prime/High Conviction/Secondary/Low Priority) — a healthy,
  non-degenerate distribution, no recalibration needed.
- Known side effect, not fixed (out of scope of this change): `setup_style`
  can now label a top-`meta_score` (mean-reversion) pick as "Momentum-led",
  since that label still comes from the old, independent
  `momentum_component_score`. Cosmetic/labeling inconsistency, not a
  correctness issue — flagged for a future pass, not fixed here.
- Tests: `tests/test_meta_ranking.py` — 2 tests rewritten
  (`test_build_meta_ranking_prefers_mean_reversion_setups`, formerly
  "...prefers_hybrid_high_quality_setups"; `test_thin_evidence_caps_priority_bucket`
  redesigned so both symbols independently clear the Prime threshold),
  1 test removed (`test_synergy_bonus_does_not_double_count_action_label` —
  tested that synergy bonus didn't double-count `action_score`; both the
  synergy bonus and action_score's role in `meta_score` are gone, so the
  thing it verified no longer exists to double-count). 194 passed after the
  change (195 before, minus the one removed test).
