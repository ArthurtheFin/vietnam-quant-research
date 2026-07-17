# FOLD_AUTOPSY_REPORT — diagnosing the left tail in the walk-forward backtest

**Dataset/code version**: `data/full_history_v2` (`docs/reports/data/docs/reports/data/DATA_BASELINE.md`),
deployed scoring at commit `6f452b2` (post-`docs/reports/scoring/docs/reports/scoring/SCORING_UPDATE_REPORT.md`
changes — `return_20d` removed from `momentum_score`, `distance_ma20`
gate loosened, `realized_vol_20d` unchanged). **Diagnosis-only round**:
no scoring changes, no tuning, no new factor tests. Same 5 walk-forward
folds and cost/liquidity assumptions as `scratch/rolling_walk_forward.py`
/ `scratch/scoring_before_after.py` (`rebalance_period=20`,
`portfolio_size=5`, `transaction_cost_pct=0.0015`, `min_value_ma20=10B`,
`require_above_ma200=True`).

**Methodology note**: `run_portfolio_backtest`'s own returned
`benchmark_curve` silently falls back to the alphabetically-first symbol
in the features frame ("A32") whenever `"VNINDEX"` isn't a row in that
dataframe — which it never is, since VNINDEX lives in
`data/processed/benchmark_vnindex.parquet`, a separate file. Not fixed
this round (out of scope); worked around by pulling the real VNINDEX
series independently (`scratch/fold_autopsy.py`) for every excess-return
and regime computation below. Flagging this as a latent bug worth a
one-line fix in a future round regardless of what happens with any risk
overlay.

---

## NV1 — fold distribution autopsy

| Fold | Period | CAGR | Max DD | Avg names/rebalance | Turnover %/rebalance | VNINDEX CAGR | VNINDEX Max DD | Excess CAGR |
|---|---|---|---|---|---|---|---|---|
| 2026 | 2026-01-01..2026-07-06 | **−59.7%** | −43.7% | 5.0 | 143.1% | **+6.5%** | −16.4% | **−66.2%** |
| 2022 | 2022-01-01..2022-12-31 | **−51.7%** | −55.0% | 4.2 | 116.5% | −34.4% | −40.3% | −17.2% |
| 2024 | 2024-01-01..2024-12-31 | +9.6% | −27.3% | 4.6 | 206.8% | +12.1% | −8.9% | −2.5% |
| 2023 | 2023-01-01..2023-12-31 | +11.2% | −22.5% | 4.7 | 194.9% | +8.4% | −17.4% | +2.8% |
| 2025 | 2025-01-01..2025-12-31 | +37.8% | −18.6% | 4.2 | 199.8% | +41.3% | −18.1% | −3.6% |

**Disaster folds (CAGR < −30%): 2026 and 2022.** Both are stock-picking
losses, not pure beta-riding, but of very different character:

- **2022 — partly beta, partly selection.** VNINDEX itself fell 34.4%
  (a real bear market, matching the well-known 2022 VN market crash).
  Portfolio excess return vs. the index: **−17.2%** — meaningfully worse
  than the market, but the market crash explains roughly two-thirds of
  the portfolio's own loss.
- **2026 — almost entirely a selection failure.** VNINDEX was **up
  +6.5%** over the same period; the portfolio lost 59.7% CAGR anyway.
  Excess return: **−66.2%**. This is not "riding the market down" — the
  market went up while this portfolio fell apart.

### Root-cause check on the 2026 disaster (verified, not assumed)

Pulled every one of the 30 stock-holding-period combinations actually
held in 2026 (6 rebalances × 5 names) and checked for data artifacts
before accepting this as a genuine strategy failure:
- **Zero `suspect_corporate_action` flags** across all 30 holding
  windows.
- **No single-day move exceeds normal price-band limits** (worst daily
  moves range −0.6% to −10.0%, all within HOSE/HNX/UPCOM bands) — no
  adjustment-bug artifact, no halt/resume distortion.
- **24 of 30 holding-period combinations show a negative cumulative
  return**; the picks are concentrated in commodity/cyclical/small-bank
  names (OIL, MSR, KSV, DPM, DCM, PVT, PVP, PVC, KSF, ABB, BVB, NAB, VAB,
  etc.) that mostly ground down steadily, not via any single shock.

**This is a genuine, if narrow, market-breadth collapse.**
`data/processed/market_features.parquet`'s `pct_above_ma200` (the *median*
stock's own trend status, independent of the cap-weighted index) averaged
**36.8% during 2026** — comparable to 2022's 35.9% (the actual crash
year) — while the index itself rallied. In other words: a small number of
large/mega-cap names pulled VNINDEX up while most individual stocks,
including this portfolio's 5 equal-weighted holdings, kept declining.
`above_ma200` is a lagging filter (a 200-day average doesn't immediately
disqualify a name that's only recently rolled over), so names can remain
"eligible" for a while after the broad deterioration has already started.

---

## NV2 — regime hypothesis test

### Pre-registered labels (point-in-time, last known value strictly before each fold starts)

| Fold | Index above its own MA200? | Index 60d realized vol vs. its own history | CAGR | Max DD |
|---|---|---|---|---|
| 2026 | True | high (22.8% vs. 18.0% median-to-date) | −59.7% | −43.7% |
| 2022 | True | low (13.8% vs. 21.1% median-to-date) | −51.7% | −55.0% |
| 2024 | True | low (19.7% vs. 20.1% median-to-date) | +9.6% | −27.3% |
| 2023 | False | high (30.7% vs. 21.1% median-to-date) | +11.2% | −22.5% |
| 2025 | True | low (9.7% vs. 17.8% median-to-date) | +37.8% | −18.6% |

Cross-tab:

| Index-above-MA200 | Avg CAGR | % folds negative | n |
|---|---|---|---|
| True (4 folds) | −16.0% | 50% | 4 |
| False (1 fold) | +11.2% | 0% | 1 |

| Vol regime | Avg CAGR | % folds negative | n |
|---|---|---|---|
| High (2 folds: 2023, 2026) | −24.3% | 50% | 2 |
| Low (3 folds: 2022, 2024, 2025) | −1.4% | 33% | 3 |

**Neither label cleanly separates the disasters.** Both disaster folds
share `index above MA200 = True` — but so do 2 of the 3 fine folds
(2024, 2025). On vol regime, the two disasters split one high (2026) and
one low (2022) — the opposite of a clean signal. **With only 5 folds,
this cross-tab has essentially no statistical power regardless of what
it shows** — but even taken at face value, it does not point to a usable
pre-registered overlay trigger from either label.

### A third label tried, and correctly ruled out (not cherry-picked)

The `pct_above_ma200` breadth statistic looked promising in NV1 — but
only when averaged *during* the disaster folds themselves (an ex-post
description of what happened, not a usable predictor). Tested the
legitimate point-in-time version instead — breadth on the single last
day *before* each fold starts, vs. its own historical median to that
point:

| Fold start | Pre-fold breadth | Historical median-to-date | Label |
|---|---|---|---|
| 2022-01-01 | 89.2% | 78.3% | broad |
| 2023-01-01 | 12.0% | 71.3% | narrow |
| 2024-01-01 | 51.2% | 66.2% | narrow |
| 2025-01-01 | 46.7% | 60.6% | narrow |
| 2026-01-01 | 43.9% | 57.0% | narrow |

This does **not** hold up either: 2022 (disaster) starts from a *broad*
reading (89.2%, breadth hadn't rolled over yet the day before the crash
began), while 3 of the 3 non-disaster folds are *also* labeled "narrow"
by this same test. Recording this explicitly because it's a real,
honest negative result on a hypothesis that looked good on first glance
from the wrong (lookahead) angle — not something to quietly drop.

**Conclusion for NV2: disasters do not concentrate on any identifiable
pre-fold state tried here.** Per the instruction, this is reported
honestly rather than forced into a narrative — the problem is deeper
than a simple regime switch, or the sample (5 folds) is simply too small
to see one if it exists. Both are plausible; this round cannot
distinguish between them.

---

## NV3 — cost and execution sensitivity

| Transaction cost | Per-fold CAGR (2022, 2023, 2024, 2025, 2026) | Avg CAGR |
|---|---|---|
| 0x (0.0000) | −50.2%, +15.0%, +13.2%, +42.1%, −58.3% | **−7.7%** |
| 1x baseline (0.0015) | −51.7%, +11.2%, +9.6%, +37.8%, −59.7% | **−10.6%** |
| 2x (0.0030) | −53.1%, +7.6%, +6.0%, +33.6%, −61.1% | **−13.4%** |

Cost scales roughly linearly at ~2.9pp of average CAGR per unit
multiplier — real, but **not the primary driver**: even at *zero*
transaction cost, average CAGR is still deeply negative (−7.7%),
confirming the negative mean is not a cost/turnover artifact. It is
driven by the two disaster folds' magnitude (−51.7% and −59.7%), which
dwarfs anything cost sensitivity can explain. **Direction for any future
fix should target the disaster folds' stock selection/concentration, not
the cost model.**

---

## Conclusion

- The left tail (mean CAGR −10.6% vs. median +9.6%) is caused by exactly
  2 of 5 folds, not a broad-based problem across the backtest.
- 2022's disaster is mostly explained by a real, severe bear market
  (VNINDEX −34.4%) with a genuine but smaller (−17.2pp) selection
  shortfall on top.
- 2026's disaster is **not explained by a data defect** (verified,
  no anomalous flags or moves) and **not explained by transaction
  costs** (verified, cost sensitivity is small relative to the loss) —
  it reflects a real, narrow-breadth market phase (median stock in a
  downtrend while a handful of large caps carried the index up) landing
  on a concentrated, equal-weighted, 5-name portfolio built from
  commodity/cyclical/small-bank names.
- **No basis found for a simple, pre-registered regime-based risk
  overlay from this data** — three different point-in-time labels tried
  (index-vs-own-MA200, index vol regime, breadth-vs-own-history) all
  fail to cleanly separate the 2 disaster folds from the 3 healthy ones,
  and 5 folds is too small a sample to be confident this isn't simply a
  power problem rather than a true absence of a signal.
- **Per instruction, no overlay is designed or installed this round.**
  If a future round pursues one, the more promising direction based on
  this diagnosis is *portfolio construction* (concentration risk from
  only 5 equal-weighted names, sector clustering in the picks) rather
  than a market-timing regime switch — but that is a design decision for
  a future round with its own pre-registered criteria, not decided here.
