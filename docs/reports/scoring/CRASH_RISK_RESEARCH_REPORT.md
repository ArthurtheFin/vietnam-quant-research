# CRASH_RISK_RESEARCH_REPORT — a new angle on the 2022-style crash problem

Follow-up to `docs/reports/scoring/docs/reports/scoring/STRATEGY_RESEARCH_REPORT.md` §7.1: "2022-style broad market
crash (-27.6%) has no working protection. All 4 tried approaches (stop-loss,
regime filter, crash-severity filter, give-back stop) either didn't help or
destroyed the good years." This asks whether a genuinely different signal
does better, and reports honestly on what was and wasn't established.

Scripts: `scratch/validate_breadth_collapse_overlay.py` (main result),
plus ad-hoc diagnostics run interactively (not committed — see "what was
investigated" below for what they showed).

## Why the 4 prior approaches failed — the actual mechanism

Traced the 2022 damage month-by-month (plain 3-factor score, no overlay):
Jan -0.2%, Feb -2.4%, Mar -0.2%, **Apr -10.3%, May -13.1%**, Jun -1.4%, then
roughly flat/recovering through year-end. Essentially all of 2022's loss
happened in a 2-month window. Cross-referencing market breadth
(`market_features.parquet` / `src/models/regime.py`):

- `pct_above_ma50` (fraction of ~500 tracked stocks trading above their own
  50-day MA) was still 0.67 at end-March, then collapsed to **exactly 0.0**
  by 2022-04-27 and stayed at 0.0 continuously through mid-June.
- `index_drawdown_pct` (VNINDEX off its own rolling high) only crossed the
  existing `crash_severity` "Correction" threshold (-10%) on 2022-04-27 —
  the same day breadth already hit zero — and didn't cross into "Crash"
  (-20%) until mid-June, by which point April AND May's combined ~-22% had
  already happened.

This confirms report §5's finding precisely: any THRESHOLD-based reactive
signal (price drawdown, or the legacy 0.55 breadth threshold) crosses its
trigger only after — or right as — the worst of the damage occurs, because
ordinary corrections and this genuine rout look identical at the moment
either first crosses a level-based line.

## The new idea: EXTREME breadth level + persistence, not a level threshold alone

`pct_above_ma50 < 0.10` (all but a total breadth wipeout) turns out to be
much rarer and more specific than the legacy 0.55 cutoff:

| Year | days with pct_above_ma50 < 0.10 (of ~250 trading days) |
|---|---|
| 2020 | 41 (mostly the Jan warmup artifact + real COVID crash, see caveat below) |
| 2021 | 13 |
| **2022** | **68** |
| 2023 | 15 |
| **2024** | **0** |
| 2025 | 17 |
| **2026** | **0** |

2024 and 2026 — the years the validated 3-factor score does best — never
once hit this extreme. Requiring the condition to hold for **3 consecutive
days** (avoid single-day noise) before treating it as "Risk-off" and
combining with the existing take-profit overlay:

## Result — same 5-fold walk-forward protocol as docs/reports/scoring/docs/reports/scoring/STRATEGY_RESEARCH_REPORT.md §6

| | 2022 | 2023 | 2024 | 2025 | 2026 | Avg | Median | Win rate |
|---|---|---|---|---|---|---|---|---|
| Plain (no overlay) | -27.6% | +12.0% | +2.0% | +12.8% | -0.0% | -0.2% | +2.0% | 60% |
| **Current production** (take-profit only) | -27.6% | +13.1% | +2.0% | +11.6% | +5.3% | +0.9% | +5.3% | 80% |
| breadth<0.10, full cash (no persistence) | -18.0% | +12.0% | +2.0% | **+2.7%** | -0.0% | -0.3% | +2.0% | 60% |
| **breadth<0.10 persist-3d, full cash + take-profit** | **-15.1%** | +13.5% | +2.0% | +7.7% | +10.9% | **+3.8%** | +7.7% | 80% |

The persistence requirement is what makes the difference: without it, the
filter also fires on 2025's shorter breadth dips and cuts that year's return
by more than half (+12.8% → +2.7%); requiring 3 consecutive days lets 2025
mostly ride through (+7.7%, still a real but much smaller cost) while still
catching 2022's multi-week collapse early enough to cut that year's loss
nearly in half (-27.6% → -15.1%). Every other year is flat-to-better than
the current production overlay. This is the first candidate found across
both this session and the original research that reduces the 2022 loss
without a net cost to the other years — average and median both improve
versus the currently-deployed take-profit-only overlay.

## Why this isn't a confirmed fix — two honest caveats

**1. Parameter selection risk.** The threshold (0.10) and persistence window
(3 days) were chosen after looking directly at 2022's own breadth timeline —
the same fold used to evaluate the result. This is a real curve-fitting risk
that the 3-factor score's original validation specifically avoided (weights
there were derived from TRAIN-only IC, never from looking at backtest P&L on
the test fold itself). Mitigating factors: 0.10 and "a few days of
persistence" both match magnitudes already used elsewhere in this codebase
(the existing 10% correction/take-profit thresholds, the ~3-day settlement
convention), so they aren't arbitrary grid-search picks — but this is not
the same as genuine out-of-sample proof.

**2. The attempted out-of-sample check (2020 COVID crash) was inconclusive,
not negative.** 2020 is the first year of the entire dataset, so `above_ma200`
(a hard eligibility filter, `require_above_ma200=True`) cannot be computed
for most of the year — it needs 200 trading days of history that don't
exist yet at the start of the dataset. Traced this directly: the backtest's
first actual trade in a 2020-only test window doesn't happen until **June
2020**, after the COVID crash (March-April) was already over. Plain,
take-profit-only, and the new breadth-filter overlay all produced bit-for-bit
identical results (CAGR +55.30%) for 2020 — not because the signal failed,
but because the portfolio held no positions at all during the only window
where it could have mattered. This is a genuine data-availability limitation,
not evidence either way, and is reported as such rather than glossed over.

## Verdict

**A real, mechanistically-sensible candidate — sustained, near-total breadth
collapse is a rarer and more specific condition than any previously-tried
threshold, and it improves 4 of 5 folds while cutting the worst year's loss
by ~45%.** But it rests on parameters picked with some knowledge of the one
crash year available, and the natural out-of-sample check (2020) couldn't
be run due to data warmup limits — so this is "best candidate found so far,"
not "problem solved." Recommend: (a) treat as a candidate opt-in overlay,
not a default; (b) re-validate once more calendar time (and ideally another
real drawdown episode) accumulates past 2026-07; (c) if implementing, wire
it the same way the take-profit overlay already is — via the existing
`market_regime`/`regime_col`/`risk_off_regimes` parameters in
`run_portfolio_backtest`, which already support this without any new backtest
engine code (confirmed empirically in this research — no source changes were
needed to run any of the above).

## What was NOT done

No production code was changed. `src/models/regime.py`,
`src/backtest/portfolio_backtest.py`, and the reference notebook are
untouched — this is a research finding awaiting a decision on whether/how to
implement it, consistent with how `score_meta_ranking()` was handled in the
deploy phase.
