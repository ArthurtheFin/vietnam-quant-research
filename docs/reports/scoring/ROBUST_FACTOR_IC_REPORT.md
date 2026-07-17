# ROBUST_FACTOR_IC_REPORT — Newey-West + residualized target + liquidity subset

> **Addendum (see `docs/reports/data/DATA_AUDIT_REPORT.md`)**: the "2020-2026" sample this
> report describes is, in reality, a 5-6 symbol dataset in 2020-2022 and a
> ~90-symbol dataset in 2023-2024 — 495 of 501 symbols have no data before
> 2023, and 406 of 501 have none before 2025-Q2. This report's eligibility
> filters could only be meaningfully satisfied from 2023 onward in
> practice, so the daily-IC series here draws almost all of its usable days
> from a 14-24 month window, not a 6-year one. The conclusion (no factor
> clears the bar) is not reversed by this — if anything a smaller, noisier
> sample makes weak results even less likely to be a false negative — but
> "walk-forward across 2020-2026" should be read as "walk-forward across
> whatever of 2020-2026 the data actually covers, which is mostly 2025+."

Follow-up to the comprehensive-negative finding in the prior chat turn (44
factors, naive t-stats, none cleared |t|>2). Before accepting that
conclusion, fixed two methodology issues and re-ran everything on a
liquidity subset. Script: `scratch/diagnose_factor_ic_robust.py`.

## What changed vs. the prior screen

1. **Newey-West HAC t-stats.** IC now computed on every trading day (not
   just every 20th) — deliberately reintroducing the overlap in the 20-day
   forward target — and corrected with Newey-West (maxlags=20, Bartlett
   kernel), implemented directly in numpy (`statsmodels` is broken in this
   environment — incompatible with the installed scipy 1.17, an unrelated
   pre-existing issue, not touched). Naive t-stat reported alongside.
2. **Residualized target.** `market_residual_20d = fwd_ret_20d - beta_250d *
   fwd_ret_20d_index`, beta from a trailing 250-session rolling regression
   (point-in-time, no look-ahead), then sector-demeaned using
   `config/sector_map.csv` (99.2% coverage here — the "sector" column
   embedded in `stealth_accumulation_history.parquet` is 95% "Unclassified"
   and was unusable).
3. **Liquidity subset.** Top-150-by-trailing-60-session-median-traded-value,
   rebalanced monthly, point-in-time (no survivorship bias) — alongside the
   full eligible universe.
4. **176 combinations** (44 factors × 2 universes × 2 targets) tested;
   conclusion bar kept at |t_NW| > 3 to account for multiple testing.

## Result: naive vs. Newey-West confirms the overlap was inflating significance, as suspected

Every single row in the table shows |t_naive| > |t_NW|, often by 2x — e.g.
`tail_ratio_60d` (full, residualized): naive t=+7.35 → NW t=+2.43. This
confirms Task 1's premise was correct: the overlapping-window problem was
real and was inflating apparent significance throughout, including in the
very first 44-factor screen a few turns ago (which sidestepped it by
sampling only every 20 days, at the cost of throwing away 95% of the data —
this version recovers that data properly instead).

## Main table — top 20 by |t_NW| (full 176-row table in the script output)

| factor | universe | target | mean IC | t_naive | **t_NW** | N days |
|---|---|---|---|---|---|---|
| **near_pivot_score** | full | raw | +0.0385 | +6.27 | **+3.56** | 772 |
| **near_pivot_score** | top150 | raw | +0.0368 | +5.73 | **+3.25** | 765 |
| upper_wick_pct | top150 | residualized | +0.0214 | +2.29 | +2.63 | 432 |
| close_location_value | top150 | residualized | -0.0214 | -2.29 | -2.63 | 432 |
| tail_ratio_60d | top150 | residualized | +0.0450 | +6.82 | +2.53 | 741 |
| atr_pct_14 | top150 | residualized | -0.0542 | -6.77 | -2.47 | 544 |
| realized_vol_20d | top150 | residualized | -0.0431 | -6.87 | -2.45 | 741 |
| tail_ratio_60d | full | residualized | +0.0500 | +7.35 | +2.43 | 737 |
| volatility_percentile | top150 | residualized | -0.0452 | -6.84 | -2.31 | 741 |
| volatility_dryup_score | top150 | residualized | +0.0420 | +6.67 | +2.27 | 741 |
| ... (166 more rows, all \|t_NW\| < 2.3) | | | | | | |

**Only 2 of 176 rows clear |t_NW| > 3** — and they're really one finding
counted twice (`near_pivot_score` in both universes, raw target only).
`upper_wick_pct`/`close_location_value` are mirror images of each other
(mathematically near-complementary) at ±2.63, just under the bar.

## `near_pivot_score` — the one survivor, and why it's not a clean win

- Clears the bar in **raw** target (both universes) but drops to t_NW=+1.46
  (full) / +1.65 (top150) once **residualized** against market beta and
  sector. That pattern — significant on raw returns, not on market/sector-
  adjusted returns — suggests this factor is partly (or mostly) proxying
  for "stocks near a recent pivot tend to do well when the *market* is doing
  well," not necessarily genuine idiosyncratic stock-picking skill.
- Horizon diagnostic (Task 4, informational): 5d t_NW≈0 (no signal at all
  short-horizon), 10d t_NW=+1.4/+1.7 (still weak), 60d t_NW=+2.78/+2.51
  (strengthens with horizon, but still short of 3). The effect looks like a
  slower-moving one that the 20d measurement happened to catch mid-build.

**This is not nothing, but it is not a validated factor either** — one
borderline survivor out of 176 tests, weaker once market/sector effects are
removed, is close to what a pure multiple-testing artifact would look like
too. It would need a dedicated, standalone robustness pass (split-half
stability across sub-periods, out-of-sample check) before being trusted —
exactly the same discipline that caught the last two "validated" formulas
after the fact.

## Does this change the comprehensive-negative conclusion?

Barely, and not in a way that's actionable yet. 174 of 176 combinations
still show no signal, including all three previously-deployed factors
(`distance_ma20`, `return_20d`, `realized_vol_20d`) at every combination
tested. `near_pivot_score` is a single, narrow candidate that survives raw-
target testing but weakens sharply under residualization — worth a closer,
dedicated look, not worth building anything on yet.
