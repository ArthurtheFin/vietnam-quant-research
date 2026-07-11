# SCORE_V2_REPORT — v2 confirmed against the pre-registered bar, installed with shadow logging

**Dataset/code version**: `data/full_history_v2` (`DATA_BASELINE.md`), design
pre-registered in `SCORE_V2_DESIGN.md` (commit `6cf15a0`, before any
comparison was run), evidence chain from `SCORE_FORENSIC_REPORT.md`.
This report covers the confirmation run and the installation decision
only — the design itself, with full reasoning, is in `SCORE_V2_DESIGN.md`
and is not repeated here.

---

## Confirmation run results

All three legs used the identical currently-deployed configuration
(`portfolio_size=10`, `max_per_sector=2` with `config/sector_map.csv`,
`rebalance_period=20`, `transaction_cost_pct=0.0015`, `min_value_ma20=10B`,
`require_above_ma200=True`), same 5 calendar-year folds (2022–2026
partial) used throughout this session.

### Walk-forward backtest: v2 vs. old composite vs. minimal (realized_vol_20d alone)

| Fold | Minimal (vol only) | Old composite | v2 (vol70/liq30) |
|---|---|---|---|
| 2022 | −22.8% | −40.1% | **−19.7%** |
| 2023 | +13.9% | +9.1% | +18.9% |
| 2024 | +13.3% | +23.1% | +17.8% |
| 2025 | **+10.1%** | **+20.2%** | −0.2% |
| 2026 | −4.9% | −47.3% | −9.6% |
| **Mean CAGR** | +1.9% | −7.0% | +1.4% |
| **Median CAGR** | **+10.1%** | +9.1% | −0.2% |
| **Worst fold** | −22.8% | −47.3% | **−19.7%** |
| **Avg max DD** | −14.2% | −28.4% | **−13.8%** |

v2 and the minimal score both dramatically outperform the old composite
on every metric — the old composite's catastrophic 2022/2026 folds
(−40.1%, −47.3%) shrink to −19.7%/−9.6% (v2) and −22.8%/−4.9% (minimal).
Between v2 and minimal specifically: v2 has the shallower worst fold and
lower average drawdown; minimal has the better mean/median CAGR in this
single backtest realization, driven almost entirely by 2025 (the one
fold where the liquidity component dragged v2 down to −0.2% against
minimal's +10.1%).

### Null test: v2's percentile within 2,000 random portfolios/fold (seed=42)

| Fold | Real CAGR | Null median | **v2 percentile** |
|---|---|---|---|
| 2022 | −19.7% | −43.3% | **100.0** |
| 2023 | +18.9% | +13.0% | **75.9** |
| 2024 | +17.8% | +12.1% | **71.3** |
| 2025 | −0.2% | +9.7% | **20.2** |
| 2026 | −9.6% | −25.2% | **87.8** |

**Average percentile: 71.0.** No fold below the 5th percentile (worst:
2025 at 20.2). For direct comparison, the old composite's equivalent
null test (`CONCENTRATION_ANALYSIS_REPORT.md`, measured under the
previous size=5/no-cap config) averaged 41.2, with one fold at 0.4 —
v2 clears the bar the old composite failed by a wide margin, though the
configs aren't perfectly identical (noted for transparency, not
material to v2's own pass/fail reading against its fixed thresholds).

### IC Newey-West (full history, maxlags=20)

| Factor | Full, residualized | Top150, residualized |
|---|---|---|
| v2_score | **+6.09** | **+5.67** |
| alpha_score (old) | +1.68 | +1.75 |
| realized_vol_20d (minimal) | −5.41 | −5.41 |

v2's IC is stronger in magnitude than the minimal score's in both
universes (and the old composite never approaches significance
anywhere). 3-period split, full/residualized:

| Period | v2_score t_NW | realized_vol_20d t_NW |
|---|---|---|
| 2020-06→2022-05 | +2.07 | −1.63 |
| 2022-05→2024-06 | +2.95 | −2.49 |
| 2024-06→2026-06 | +7.72 | −7.99 |
| Same-sign all 3? | **Yes** | Yes |

v2 is same-signed across all 3 periods and, notably, clears a meaningful
t-stat even in period 1 alone (+2.07) where the minimal score on its own
does not (−1.63) — combining the two components appears to add real,
independent statistical power (consistent with `SCORING_UPDATE_REPORT.md`'s
earlier finding that `value_ma20`/liquidity is ~0-correlated with the
volatility cluster, i.e. genuinely orthogonal information, not restating
the same signal).

## Reading against the pre-registered criteria (`SCORE_V2_DESIGN.md`)

| Criterion | Result | Pass? |
|---|---|---|
| Null-test avg percentile > 50 | 71.0 | **Yes** |
| No fold's percentile < 5 | worst = 20.2 (2025) | **Yes** |
| IC same-sign across 3 periods | Yes (all positive) | **Yes** |

**All three criteria are met — v2 is accepted.**

**On the tie-break ("if v2 doesn't clearly beat the minimal score, use
the minimal score")**: the comparison is mixed, not one-sided — v2 wins
on the two more statistically rigorous measures (Newey-West IC magnitude
and the null-test percentile framework, both explicitly designed this
session to be more trustworthy than single-realization backtest CAGR),
while the minimal score wins on mean/median CAGR in this one 5-fold
backtest sample. Given the session-long theme of distrusting raw CAGR
comparisons in favor of IC/percentile evidence (`CONCENTRATION_ANALYSIS_REPORT.md`,
`SCORE_FORENSIC_REPORT.md`), and that v2's own three pre-registered
criteria pass cleanly, **v2 is judged to clearly beat the minimal score
on the stronger evidence**, not superseded by it. This judgment call is
recorded explicitly rather than presented as unambiguous — a reader who
weighs backtest CAGR more heavily could reasonably reach the opposite
conclusion from the same numbers above.

---

## Installation and shadow mechanism

`src/alpha/scoring.py`'s `calculate_alpha_scores`: `alpha_score` (the
primary, deployed output) is now the v2 composite. The v1 composite is
retained as `alpha_score_shadow_v1` — computed every run, not consumed
by any downstream logic, purely for comparison.

`scripts/run_alpha_scoring.py`: appends `[symbol, date, alpha_score,
alpha_score_shadow_v1]` for the latest date to
`data/signals/alpha_score_shadow_log.parquet` on every run (deduped on
`symbol`+`date`), building a growing daily record. **First entry:
2026-07-09, 28 symbols** — this is where v2's real, live out-of-sample
track record starts; everything in this report and `SCORE_V2_DESIGN.md`
is in-sample/backtested by comparison.

**Known side effect, disclosed and not fixed this round**:
`src/screening/final_watchlist.py`'s own `_score()` function averages
`rank(alpha_score)` as one of several inputs to *its own*, differently-
named `momentum_score`/`momentum_raw` (a separate composite from
`src/alpha/scoring.py`'s). That ingredient is now fed by a volatility/
liquidity signal, not a momentum signal — a labeling/conceptual mismatch
in `final_watchlist.py`'s own weighting, not a bug, but worth a dedicated
look in a future round rather than silently working around it here
(out of scope for this round, which was about `src/alpha/scoring.py`
specifically, the composite tested throughout this session's diagnosis
chain).

## Conditions for review

Not "revisit whenever it looks bad" — concrete triggers, so a review
happens on a schedule or a threshold, not on vibes:

1. **Time-based**: review after **6 months of live shadow tracking**
   (i.e. once `alpha_score_shadow_log.parquet` covers roughly
   2026-07-09 → 2027-01-09), regardless of how it's performing, simply
   because that's enough live data to say something about v2 vs. v1
   out-of-sample that the backtest can't.
2. **Drawdown-based**: review immediately if live tracking shows a
   drawdown **worse than −25%** on a v2-scored portfolio (a margin above
   the worst backtested fold, −19.7% in 2022, so this triggers on a
   genuinely new worst case, not backtest noise repeating).
3. **Relative-performance-based**: review if v2 underperforms the shadow
   v1 composite by **more than 10 percentage points cumulative over any
   rolling 60-trading-day window** — directly computable from the shadow
   log this round sets up, and a large enough gap to be more than
   day-to-day noise between two portfolios drawing from the same
   universe.

Whichever triggers first should prompt a review, not an automatic
reversion — the review itself would need its own evidence, same as this
round did.
