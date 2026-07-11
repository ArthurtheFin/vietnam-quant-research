# SCORE_FORENSIC_REPORT — tracing the 2026 failure to specific score components

**Dataset/code version**: `data/full_history_v2` (`DATA_BASELINE.md`),
code at commit `3b8c4a8` (post `CONCENTRATION_ANALYSIS_REPORT.md`'s
portfolio-config change, applied in this round's NV1 below). Follow-up to
`CONCENTRATION_ANALYSIS_REPORT.md`'s null test, which found the deployed
`alpha_score` (`src/alpha/scoring.py`) underperforms random stock-picking
on average (mean percentile 41.2/2000 across 5 folds) and that 2026
specifically (percentile 0.4) looked signal-driven, not concentration
noise. This round traces exactly which part of the signal.

**Terminology note**: the brief for this round mentions an
"accumulation/stealth score" component. That belongs to a *different*
scoring system (`src/screening/stealth_accumulation.py`), not
`alpha_score` — the actual composite tested in every null-test/fold-
autopsy round this session. `alpha_score` has six components:
`momentum_score` (25%), `rs_score` (25%), `trend_score` (20%),
`volume_score` (15%), `volatility_score` (10%), `liquidity_score` (5%).
Decomposed the real thing below; `momentum_score`/`rs_score` are used
where the brief's hypothesis calls for an "accumulation-style" (recent-
strength-rewarding) component, noted explicitly at each use.

---

## NV1 — approved portfolio configuration applied

`run_portfolio_backtest` defaults changed: `portfolio_size` 5→10,
`max_per_sector` None→2 (cap only activates when a caller also supplies
`sector_map`; without one it's a no-op, unchanged from before). Full
rationale and caveat are in the function's own docstring now, citing
`CONCENTRATION_ANALYSIS_REPORT.md`: this is a diversification decision
made because a pre-registered theoretical prediction was tested and
partially confirmed (worst-fold CAGR shallowed monotonically with size),
**not** because this configuration won the sensitivity table outright —
and it explicitly does not address signal quality, which is what the
rest of this report is about.

---

## NV2 — forensic on fold 2026

### Every stock selected, per rebalance, with decision-date score decomposition

(`portfolio_size=5` used explicitly here — matching the exact
configuration diagnosed in `FOLD_AUTOPSY_REPORT.md`/
`CONCENTRATION_ANALYSIS_REPORT.md`, not this round's new size=10 default,
since the point is explaining *that* diagnosed result.)

30 picks across 6 rebalances (`data/full_history_v2/score_forensic_2026_decomposition.csv`
has the full table: symbol, holding-period return, `alpha_score`, and
every component). Two things stand out immediately:
- **`trend_score` is pinned at exactly 100.0 for all 30 picks** — not
  discriminating anything; it's saturated because the eligibility filter
  already requires `above_ma200`, and candidates ranking near the top on
  momentum/RS are almost always also above MA20/MA50. It looks like the
  "top component" for every single pick only because it hits the ceiling,
  not because it's doing real selection work.
- **`momentum_score` and `rs_score` are both in the 82–99 range for every
  single pick** — the actual discriminating engine behind these
  selections was chasing recent price strength, hard.

### Cross-sectional Spearman IC, 2026 vs. 2023-2025, alpha_score and each component

| Factor | IC 2026 | IC 2023-2025 | Sign flipped? |
|---|---|---|---|
| `rs_score` | **−0.1060** | +0.0141 | **yes** |
| `momentum_score` | **−0.1050** | +0.0158 | **yes** |
| `liquidity_score` | −0.0941 | +0.0447 | **yes** |
| `alpha_score` (composite) | −0.0768 | +0.0246 | **yes** |
| `trend_score` | −0.0623 | +0.0169 | **yes** |
| `volume_score` | −0.0358 | −0.0089 | no (weak both periods) |
| `volatility_score` | **+0.1894** | +0.0507 | no — strengthened |

**`momentum_score` and `rs_score` (50% combined weight of `alpha_score`)
are the primary culprits**: both were mildly positive in 2023-2025 and
flipped to strongly negative in 2026 — a classic momentum-crash/reversal
pattern (chasing recent winners, which then reversed hard in the
narrow-breadth 2026 market documented in `FOLD_AUTOPSY_REPORT.md`).
`volatility_score` (the component built on `realized_vol_20d`, the one
factor with independently validated IC) did the opposite: it got
*stronger* in 2026, but its 10% weight in the composite was nowhere near
enough to offset the other 50%.

### Direct hypothesis test: high-momentum cohort vs. low-momentum cohort, 2026

| Factor | Top decile fwd 20d return | Bottom decile fwd 20d return |
|---|---|---|
| `momentum_score` | **−3.42%** | +0.16% |
| `rs_score` | −1.72% | −0.22% |

Confirms the IC finding directly and starkly: in 2026, stocks the score
ranked *highest* on momentum went on to underperform stocks it ranked
*lowest*, by 3.6 percentage points over the next 20 trading days. The
component designed to chase strength was, in this specific fold, an
active contrarian indicator.

---

## NV3 — the composite score tested directly as a factor (first time)

Ran `alpha_score` itself through the canonical Newey-West IC pipeline
(`scratch/diagnose_factor_ic_robust.py`'s exact methodology — maxlags=20,
raw + residualized target, full + top-150 universe, eligibility
`value_ma20>=3B` per the locked threshold), alongside a "minimal score" =
`realized_vol_20d` alone, the one component with independently validated
IC (`FACTOR_RETEST_V2_REPORT.md`).

| Factor | Universe | Target | mean IC | t_NW |
|---|---|---|---|---|
| alpha_score | full | raw | +0.0025 | +0.73 |
| **realized_vol_20d** | full | raw | −0.0602 | **−2.69** |
| alpha_score | full | residualized | +0.0055 | +1.68 |
| **realized_vol_20d** | full | residualized | −0.0758 | **−5.41** |
| alpha_score | top150 | raw | +0.0021 | +0.57 |
| **realized_vol_20d** | top150 | raw | −0.0504 | **−2.14** |
| alpha_score | top150 | residualized | +0.0061 | +1.75 |
| **realized_vol_20d** | top150 | residualized | −0.0734 | **−5.41** |

**The full 6-component composite never clears |t_NW|>3 anywhere — best
case +1.75.** The single-factor minimal score clears the bar in both
residualized combinations (−5.41 both universes) and is directionally
strong even on the raw target. **The minimal score beats the composite
outright, everywhere it was tested.**

### 3-period stability, full universe, residualized target

| Period | alpha_score IC (t_NW) | realized_vol_20d IC (t_NW) |
|---|---|---|
| 2020-06→2022-05 | −0.0005 (−0.11) | −0.0478 (−1.63) |
| 2022-05→2024-06 | +0.0091 (+1.31) | −0.0587 (−2.49) |
| 2024-06→2026-06 | +0.0075 (+1.47) | −0.1206 (−7.99) |
| Same-sign all 3 periods? | **No** | **Yes** |

`alpha_score` isn't even consistently signed across periods and is never
significant in any of them — indistinguishable from noise on this
evidence. `realized_vol_20d` is consistently signed and getting
*stronger* over time.

---

## Recommendation

Of the three directions on offer:

- (i) *Remove the identified harmful component*: `momentum_score` and
  `rs_score` are the clearest culprits in the fold-level forensic, but
  this only patches the symptom found in one disaster fold — it doesn't
  change that the composite as a whole has never shown significant IC in
  any full-history test.
- **(ii) Rebuild the score around evidenced factors — recommended.**
  The evidence converges from two independent angles: the fold-level
  forensic (NV2) shows momentum/RS actively drove the worst fold via a
  reversal, and the full-history factor test (NV3) shows the composite
  has *no* significant standalone predictive power anywhere it was
  tested, while its single volatility-based ingredient does, robustly,
  and is getting stronger over time. Rebuilding the score to weight
  primarily on `realized_vol_20d` (and, per `SCORING_UPDATE_REPORT.md`'s
  earlier volatility-cluster work, potentially its closely-related
  cluster-mates if a future round wants to explore that) rather than the
  current 50%-momentum/RS design is the change the evidence points at.
- (iii) *Needs more investigation*: not selected — the evidence here is
  unusually convergent (fold forensic + full-history factor test agree)
  for a 5-fold-backtest research program; further stalling doesn't seem
  justified by what's missing so much as by not wanting to touch
  deployed scoring without a dedicated round.

**Not implemented this round** — per instruction, no change to
`scoring.py` beyond NV1's portfolio-config application. A future round
should design the rebuilt score's exact weighting with its own
pre-registered criteria (this report does not prescribe one), then run
the same before/after comparison discipline `SCORING_UPDATE_REPORT.md`
established.
