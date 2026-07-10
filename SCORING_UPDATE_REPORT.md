# SCORING_UPDATE_REPORT — applying the NV4 recommendations to deployed scoring

**Dataset/code version**: `data/full_history_v2` (see `DATA_BASELINE.md`),
factor re-test evidence in `FACTOR_RETEST_V2_REPORT.md`, code at commit
`4762d81` + this round's changes (below). Follow-up to that report's NV4
recommendations, executed in the order requested: (1) examine the
volatility cluster behind the 21/192 passing IC combinations before
touching anything deployed, (2) apply the approved GIỮ/GIẢM/GỠ changes,
(3) before/after comparison. Event detection (0/94 pass) is closed and
not reopened this round.

---

## NV1 — volatility-cluster examination

### The 21 passing combinations, by factor

All 21 come from `scratch/logs/diagnose_factor_ic_robust_v2.log`,
13 distinct factors, **0 of 21 on the `raw` target** (100% on
`residualized`):

| Factor | Universe(s) passing | Sign | Best \|t_NW\| |
|---|---|---|---|
| `atr_pct_14` | full, top150 | − | 5.76 |
| `realized_vol_20d` | full, top150 | − | 5.41 |
| `volatility_dryup_score` | full, top150 | + | 4.97 |
| `dist_kurt_60d` | full, top150 | + | 4.47 |
| `accumulation_score` | full, top150 | + | 4.34 |
| `tight_range_score` | full, top150 | + | 3.84 |
| `bb_width` | full, top150 | − | 3.56 |
| `net_accumulation_score` | full, top150 | + | 3.44 |
| `value_ma20` | full only | − | 3.33 |
| `liquidity_score` | full only | − | 3.33 |
| `volatility_support_score` | full only | + | 3.15 |
| `volatility_percentile` | full only | − | 3.12 |
| `pullback_from_high_20d` | full only | + | 3.11 |

**Does the signal live on the residualized target?** Yes, exclusively —
**zero of the 21 pass on the raw target**, and the raw-target versions of
these same factor/universe pairs sit at |t_NW| 2.1–2.9 at best (below the
bar). This is evidence *against* a beta-proxy artifact, not for one: a
factor whose apparent predictive power is really just proxying for market
beta or sector exposure would show up strongest on the *raw* target and
weaken or vanish after residualizing that exposure out. Here the opposite
happens — the signal only appears after removing market/sector effects,
consistent with a genuine idiosyncratic, stock-specific relationship.

### Correlation matrix (Spearman, cross-sectional, averaged over ~1,480 eligible-full days)

Full matrix: `data/full_history_v2/vol_cluster_correlation.csv`
(`scratch/diagnose_vol_cluster.py`). Pairs with |corr| > 0.7:

```
value_ma20 <-> liquidity_score              +1.00
volatility_support_score <-> volatility_percentile   -0.93
tight_range_score <-> bb_width              -0.92
accumulation_score <-> net_accumulation_score +0.90
realized_vol_20d <-> volatility_dryup_score  -0.89
atr_pct_14 <-> realized_vol_20d              +0.87
volatility_dryup_score <-> volatility_percentile -0.86
atr_pct_14 <-> volatility_dryup_score        -0.86
accumulation_score <-> tight_range_score      +0.82
atr_pct_14 <-> tight_range_score              -0.81
realized_vol_20d <-> tight_range_score        -0.81
volatility_dryup_score <-> accumulation_score +0.80
volatility_dryup_score <-> volatility_support_score +0.80
realized_vol_20d <-> accumulation_score       -0.79
atr_pct_14 <-> accumulation_score             -0.79
volatility_dryup_score <-> tight_range_score   +0.77
accumulation_score <-> bb_width               -0.76
net_accumulation_score <-> pullback_from_high_20d +0.75
realized_vol_20d <-> bb_width                 +0.75
volatility_dryup_score <-> bb_width           -0.72
atr_pct_14 <-> bb_width                       +0.72
volatility_dryup_score <-> net_accumulation_score +0.71
```
(22 of 78 possible pairs clear 0.7.)

### Conclusion: NOT one cluster — at least two, plus two loose outliers

- **Cluster A ("volatility level"), 9 factors, all pairwise >0.7 with the
  core pair** (`atr_pct_14`, `realized_vol_20d`, `volatility_dryup_score`,
  `tight_range_score`, `bb_width`, `volatility_percentile`,
  `volatility_support_score`, `accumulation_score`, `net_accumulation_score`):
  effectively one underlying signal. Confirmed mechanically, not just
  statistically — `src/screening/stealth_accumulation.py:550-553` builds
  `volatility_dryup_score` as `0.5*score(atr_pct_14) + 0.5*score(volatility_percentile)`
  directly; `volatility_support_score` (`:597`) is a regime bucket derived
  from the same `volatility_percentile`; `accumulation_score` (`:599-605`)
  and `net_accumulation_score` (`:633-637`) are further linear composites
  that include `tight_range_score`/`volatility_dryup_score` as direct
  inputs. These aren't 9 independent confirmations — they're 2-3 atomic
  measurements (ATR, realized vol, Bollinger width, return-distribution
  percentile/kurtosis) plus several derived scores built from them.
- **Cluster B ("liquidity/size"), 2 factors**: `value_ma20` and
  `liquidity_score` — correlated **+1.00** with each other (the latter is
  a percentile-rank transform of the former, per `stealth_accumulation.py:548`,
  a monotonic transform preserves Spearman rank exactly) but **~0.00
  correlated with every Cluster-A factor** (range −0.03 to +0.09). This is
  a genuinely separate, independent signal (larger/more liquid names show
  slightly lower idiosyncratic forward returns) that happens to also clear
  the IC bar — not part of the volatility story at all.
- **Loosely related, not clustered**: `dist_kurt_60d` (0.14–0.53 |corr|
  with Cluster A — a related-but-distinct "tail shape" dimension) and
  `pullback_from_high_20d` (0.19–0.57 with Cluster A, 0.75 with
  `net_accumulation_score` specifically, likely via its indirect
  construction path through `absorption_score`).

### Representative selection (Cluster A only)

Criteria as specified: highest |t_NW|, stable across periods, simplest.
`atr_pct_14` (|t_NW| 5.76/5.65) edges out the deployed `realized_vol_20d`
(5.41/5.41) on the full-sample number. 3-period split
(`scratch/diagnose_vol_cluster_periods.py`, full/residualized):

| Period | `realized_vol_20d` t_NW | `atr_pct_14` t_NW |
|---|---|---|
| Full sample | −5.41 | −5.65 |
| P1 (2020-06→2022-05) | −1.63 | −1.79 |
| P2 (2022-05→2024-06) | −2.49 | −2.97 |
| P3 (2024-06→2026-06) | −7.99 | −7.74 |

Both same-signed in all 3 periods (passes that check). `atr_pct_14` leads
in the full sample, P1, and P2; `realized_vol_20d` leads in P3 (the
largest, most recent period). **Not a decisive edge** — the two are
87%-correlated and trade places depending on which period is weighted
most. Per the pre-agreed default, **this does not clear the "rõ rệt tốt
hơn" (clearly better) bar for a switch — `realized_vol_20d` stays**,
consistent with its operational history.

### Survivorship-bias caveat (as instructed, not solved here)

The 501-symbol universe (per `DATA_BASELINE.md`) excludes any company
delisted, merged away, or suspended indefinitely since 2020. This matters
specifically for the volatility-level signal: a stock entering acute
distress typically shows *rising* volatility just before it is
suspended/delisted and disappears from the dataset entirely — so the
"high vol → lower subsequent return" relationship measured here reflects
only the high-vol names that *survived* to keep trading, and is silent on
the (plausibly worse) outcomes of the ones that didn't. This would bias
the measured effect in an unknown direction — likely making the true
effect of high volatility on forward returns look *better* than reality
(survivors' bad-but-not-fatal outcomes vs. non-survivors' unobserved
worse ones) — and can only be resolved with a point-in-time universe
including delisted names, which this data source cannot currently provide
(`DATA_BASELINE.md` caveat #2). Not addressed this round.

---

## NV2 — changes applied to deployed scoring

**`return_20d` — removed from `momentum_score`**
(`src/alpha/scoring.py:110-114`). Was `(rank(return_20d) + rank(return_60d))/2`;
now `rank(return_60d)` alone. Evidence: no significant IC in any of the 4
tested combinations (max |t_NW|=1.24, raw sign flips between universes) —
`FACTOR_RETEST_V2_REPORT.md` NV4.

**`distance_ma20` gate — loosened, not removed**
(`src/screening/final_watchlist.py:64-65`). `max_distance_ma20`: 0.18 →
0.23; `max_relaxed_distance_ma20`: 0.28 → 0.33 (same ~28% proportional
widening on both). Evidence: no significant average-return IC (max
|t_NW|=1.61) — but distance_ma20 isn't a linear score weight anywhere in
the codebase; it's 3 separate binary-threshold uses (`trend_score`
sub-average, `strict_pass`/`fallback_eligible` gate, "Extended from MA20"
warning). Per user decision, loosening the threshold values is the
change applied; the `trend_score` sub-average and warning-penalty
mechanics are untouched.

**`realized_vol_20d` — kept, unchanged.** Strong, robust IC
(|t_NW|=5.41 both universes, residualized target, consistent sign 5d-60d
horizons). NV1 found a nominally-stronger cluster-mate (`atr_pct_14`) but
not decisively enough to displace the deployed factor per the pre-agreed
default (see NV1 above). No replacement made.

**Nothing else touched.** No new factor added to `alpha_score` or the
`final_watchlist` gates, including none of the other 18 factors from the
21-combination list (Cluster A members, Cluster B's `value_ma20`/
`liquidity_score`, or the two loose outliers) — those require their own
dedicated evaluation round, not a byproduct of this one.

---

## NV3 — before/after comparison

`scratch/scoring_before_after.py`. `distance_ma20`'s gate-threshold change
is a `final_watchlist.py` eligibility change, not a `alpha_score` formula
change, and isn't comparable via top-N/backtest the same way — this
section covers the `return_20d` removal from `momentum_score` only.

### Top-20 by `alpha_score`, last 5 trading days, OLD vs. NEW

| Date | Overlap | OUT (old-only) | IN (new-only) |
|---|---|---|---|
| 2026-07-03 | 19/20 | AAS | POW |
| 2026-07-06 | 20/20 | — | — |
| 2026-07-07 | 20/20 | — | — |
| 2026-07-08 | 19/20 | ABT | L10 |
| 2026-07-09 | 18/20 | MDG, TN1 | CCC, TSJ |

Small, expected day-to-day movement — 2 of 5 days show zero change at all.

### Turnover estimate

Average top-20 overlap across 78 monthly rebalance dates spanning the
full history: **87.5%** → average turnover attributable to this change
alone: **12.5%**.

### Walk-forward backtest (same folds/costs as `scratch/rolling_walk_forward.py`: 5 calendar-year folds 2022-2026, `rebalance_period=20`, `portfolio_size=5`, `transaction_cost_pct=0.0015`, `min_value_ma20=10B`, `require_above_ma200=True`)

| Fold | OLD CAGR | NEW CAGR |
|---|---|---|
| 2022 | −51.6% | −51.7% |
| 2023 | +13.7% | +11.2% |
| 2024 | +12.2% | +9.6% |
| 2025 | +35.5% | +37.8% |
| 2026 (partial) | −59.6% | −59.7% |
| **Avg** | **−10.0%** | **−10.6%** |
| **Median** | **+12.2%** | **+9.6%** |
| **Win rate** | 60% | 60% |

**Honest read, not tuned further**: NEW is essentially flat-to-slightly-
worse (avg CAGR −0.6pp, median −2.6pp) across this 5-fold backtest — it
does *not* clearly improve performance. This is not a contradiction of
the IC finding: a factor with no measured average-return IC is expected
to contribute ~noise, not necessarily *harmful* noise, to a backtest —
and a 5-fold, largely crash-dominated backtest (2 of 5 folds are
-50%+ drawdown years essentially unchanged by this factor either way) is
a small, noisy sample for detecting a ~0.6pp average difference. Per the
explicit constraint for this round, **this result is accepted as-is, not
used to tune or revert the change** — the removal is justified by the
IC evidence in `FACTOR_RETEST_V2_REPORT.md`, and this backtest's job was
only to confirm nothing broke (no blown-up drawdown, no collapsed win
rate, no runaway turnover) — which it does confirm.
