# SCORE_V2_DESIGN — pre-registered design, written before any v2 backtest is run

**This document is written and committed BEFORE any v2 comparison,
null test, or IC run.** Every design choice below is justified from
evidence already on record in `docs/reports/data/DATA_BASELINE.md`, `docs/reports/scoring/SCORING_UPDATE_REPORT.md`,
and `docs/reports/scoring/SCORE_FORENSIC_REPORT.md` — none of it is derived from, or will be
adjusted in response to, this round's confirmation run. If the
confirmation run (a separate step, after this file is committed) looks
bad, the response is to report honestly and hold, not to revise this
design and try again.

**Principle**: only factors with independently validated cross-sectional
IC evidence are eligible for a linear score weight. Simple weights,
chosen from relative evidence strength, not optimized. One confirmation
run. Accept the result as written.

---

## Components included

### 1. `realized_vol_20d` — core component, weight 70%

**Evidence**: `docs/reports/scoring/SCORE_FORENSIC_REPORT.md` NV3 — mean IC −0.0758 (full) /
−0.0734 (top150), t_NW **−5.41 in both universes**, residualized target.
Same-signed across all 3 time periods and *strengthening* over time
(t_NW −1.63 → −2.49 → −7.99, `docs/reports/scoring/SCORE_FORENSIC_REPORT.md`'s 3-period
table). This is the single most robust, longest-standing piece of
evidence in the whole factor-testing program this session — it is also
the one component `docs/reports/scoring/SCORE_FORENSIC_REPORT.md`'s forensic found actively
*helping* during the 2026 disaster fold (IC +0.1894 that period) while
everything else in the old composite was actively hurting.

**Direction**: reward LOW `realized_vol_20d` (matches the negative IC
sign — lower realized volatility predicts higher subsequent
market/sector-residualized return).

**Normalization**: daily cross-sectional percentile rank, inverted —
`(1.0 - rank(pct=True)) * 100.0` — same convention `alpha_score`'s
existing `volatility_score` component already uses
(`src/alpha/scoring.py`), for consistency and because it's robust to
outliers (a raw z-score would be more sensitive to the fat-tailed
`realized_vol_20d` distribution).

### 2. Liquidity cluster (`value_ma20`) — secondary component, weight 30%

**Evidence**: `docs/reports/scoring/SCORING_UPDATE_REPORT.md` NV1 — `value_ma20` and
`liquidity_score` both showed mean IC −0.0413, t_NW **−3.33**, but **full
universe only** (did not clear the bar in the top-150 subset) and
residualized target only. Weaker and narrower evidence than
`realized_vol_20d` — one universe, not two; t_NW 3.33 vs. 5.41 — which
is exactly why it gets the smaller weight below, not a tuned figure.
`value_ma20` and `liquidity_score` are the same signal in different
units (Spearman correlation +1.00 — the latter is a percentile-rank
transform of the former, `docs/reports/scoring/SCORING_UPDATE_REPORT.md` NV1) — only one is
needed; `value_ma20` (the raw, more legible quantity) is used directly.

**Direction**: reward LOW `value_ma20`, i.e. smaller/less-liquid names
*within the already-filtered eligible universe* (matches the negative
IC sign — a small/liquidity-premium-shaped effect, not a call to chase
illiquid names outright, since the eligibility gate's own
`min_value_ma20` floor still applies before this component ever sees a
candidate).

**Survivorship-bias caveat (carried forward, not resolved here)**: per
`docs/reports/data/DATA_BASELINE.md` caveat #2, this dataset excludes any company delisted,
merged away, or suspended since 2020. A small/less-liquid-name premium is
exactly the kind of effect survivorship bias is expected to inflate —
the small caps that didn't survive to be in today's universe are
invisible, so the measured premium on the ones that did survive is a
ceiling on the true effect, not a confirmed number. This is a known,
disclosed limitation of the weight below, not new information.

**Normalization**: same convention as component 1 —
`(1.0 - rank(pct=True)) * 100.0` on `value_ma20`.

### `distance_ma20` — kept as a gate only, NOT added to the v2 linear score

Already loosened to 0.23/0.33 (`docs/reports/scoring/SCORING_UPDATE_REPORT.md` NV2) in
`src/screening/final_watchlist.py`'s eligibility gate — **unchanged,
not touched by this round**. Not promoted into v2's weighted score
because its evidentiary basis is a different statistical framework
(event-detection lift, not cross-sectional IC) and, per
`docs/reports/scoring/SCORING_UPDATE_REPORT.md`, that lift result was explicitly flagged as
**"not yet statistically confirmed."** Mixing an unconfirmed lift-style
result into an IC-validated linear score would blur two different kinds
of evidence together under one weight — keeping it as a separate,
already-existing gate avoids that, and matches the instruction that its
role stays "gate/filter as currently."

---

## Components excluded, with reasons

| Component | Reason for exclusion |
|---|---|
| `momentum_score` | `docs/reports/scoring/SCORE_FORENSIC_REPORT.md` NV2: IC flips from +0.0158 (2023-2025) to **−0.1050** (2026) — a momentum-crash/reversal pattern. Never independently validated (its own inputs, `return_20d`, already removed from the score in `docs/reports/scoring/SCORING_UPDATE_REPORT.md` for near-zero IC across all 4 tested combinations). |
| `rs_score` | Same forensic pattern: IC flips from +0.0141 to **−0.1060** in 2026. No independent validated-IC evidence of its own either. |
| `trend_score` | `docs/reports/scoring/SCORE_FORENSIC_REPORT.md` NV2: pinned at exactly 100.0 for all 30 stocks selected in the 2026 forensic sample — saturated by the `above_ma200` eligibility gate that already runs before scoring, so it has no discriminating power left to contribute to a ranking. |
| `volume_score` | Never appeared in the 21/192 passing IC combinations (`docs/reports/scoring/SCORING_UPDATE_REPORT.md` NV1) and was never independently validated elsewhere in this session's factor-testing program. No positive evidence to include it on the "only validated factors" principle. |

---

## Weighting: 70% `realized_vol_20d` / 30% `value_ma20`

**Not tuned, not grid-searched.** Chosen purely from the *relative*
strength/breadth of each component's pre-existing evidence, established
in earlier reports before this design was written:
- `realized_vol_20d`: significant in **both** universes tested, **3/3
  periods** same-signed and strengthening, t_NW 5.41.
- `value_ma20`: significant in **one** universe only, t_NW 3.33, plus
  a disclosed survivorship-bias ceiling on how much of the effect is real.

70/30 reflects "clearly stronger evidence gets clearly more weight,"
nothing more precise than that ordinal judgment. An equal 50/50 split
was the only other scheme considered and rejected only because it would
imply parity between two components with visibly different evidence
strength — not because 70/30 was tested against it.

## v2 score formula

```
v2_score = 0.70 * (1 - rank_pct(realized_vol_20d)) * 100
         + 0.30 * (1 - rank_pct(value_ma20)) * 100
```
(ranks computed cross-sectionally, within-day, over the same eligible
universe the rest of the pipeline already uses.)

---

## Confirmation run — methodology and acceptance criteria, locked before running

**Configuration** (identical to the currently-deployed setup, not a new
choice for this test): `rebalance_period=20`, `portfolio_size=10`,
`max_per_sector=2` with `sector_map` from `config/sector_map.csv`,
`transaction_cost_pct=0.0015`, `min_value_ma20=10B`,
`require_above_ma200=True` — same 5 calendar-year folds used throughout
this session (2022-2026 partial).

**Three variants backtested**:
1. **v2** (this design).
2. **Old composite** (current deployed `alpha_score`, all 6 components,
   post-`docs/reports/scoring/SCORING_UPDATE_REPORT.md` edits).
3. **Minimal score** (`realized_vol_20d` alone, 100% weight, same
   inverted-rank normalization) — the benchmark v2 must clearly beat to
   justify its extra complexity.

**Tests, same methodology as established this session, no new methodology invented**:
- Walk-forward backtest, 5 folds: CAGR, max DD, worst fold.
- Null test: 2,000 random portfolios/fold, **seed=42**, same eligible
  universe/rebalance/cost, for v2 (the old composite's null-test result,
  average percentile 41.2, and the minimal score's, are both already on
  record from `docs/reports/scoring/CONCENTRATION_ANALYSIS_REPORT.md`/`docs/reports/scoring/SCORE_FORENSIC_REPORT.md`
  and are reused as the comparison baseline, not rerun).
- IC Newey-West, maxlags=20, full+top150 universe, raw+residualized
  target, 3-period split — same pipeline as
  `scratch/diagnose_factor_ic_robust.py`.

**Acceptance criteria for v2 (fixed now, not adjusted after seeing results)**:
v2 is **accepted** only if **all three** hold:
1. Null-test average percentile **> 50** across the 5 folds.
2. **No single fold's percentile < 5** (the disaster-signature threshold
   `docs/reports/scoring/CONCENTRATION_ANALYSIS_REPORT.md` pre-registered).
3. IC **same-sign across all 3 periods** (full universe, residualized
   target).

If v2 does not clearly beat the minimal single-factor score on this
evidence, **the minimal score is used instead** — simplicity wins on a
tie or an ambiguous result, per instruction. If v2 fails the acceptance
criteria outright, the current deployed composite's fate is a separate
decision **not** pre-committed here (this design only pre-commits v2's
own accept/reject bar, not what replaces it if rejected) — that would be
reported honestly and held for discussion, not patched with another
untested configuration in the same round.
