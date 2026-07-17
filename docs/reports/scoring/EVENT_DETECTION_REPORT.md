# EVENT_DETECTION_REPORT — reframed from IC to tail-event lift

> **Addendum (see `docs/reports/data/docs/reports/data/DATA_AUDIT_REPORT.md`, written as a direct follow-up to
> this report's Period-1 finding)**: the root cause of Period 1's
> structural NaN is now confirmed as a universe/coverage problem, not the
> 10B VND liquidity threshold. Only 5-6 symbols (of 501) have sustained
> data in 2020-2022 at all — 495 of 501 symbols have no data before 2023,
> 406 of 501 have none before 2025-Q2. HPG/SSI/STB/TCB (definitely liquid,
> actively-traded 2021 blue chips) are entirely absent from the dataset in
> 2021, while VPB (the one 2021-covered name checked) shows correctly-scaled
> traded value — ruling out a units bug. This is a much larger issue than
> "the threshold happened to be too strict for 2020-2022" as this report
> originally framed it: there was barely a universe to apply any threshold
> to in that period. Not fixed or re-run this round; see `docs/reports/data/docs/reports/data/DATA_AUDIT_REPORT.md`
> for remediation options.

Reframes the question from "average monotonic relationship" (IC) to "can a
factor flag names ahead of an explosive move" (event detection + lift).
Event definition and evaluation protocol were pre-registered in chat before
running; not adjusted after seeing results. Script:
`scratch/diagnose_event_detection.py`.

## Task 1 — event definition and base rate (fixed, not tuned)

```
Event(symbol, t) = 1  if  excess_return_60d(t) >= +25%
                    AND  median_value_20d(t) >= 1B VND/day
```
`excess_return_60d` = symbol's forward 60-day return (zero-fill corporate-
action handling, consistent with prior work) minus VNINDEX's own forward
60-day return over the same window — simple difference, no beta adjustment
(beta-adjustment was Task 2's job in the prior IC re-test, not asked for
here). The 1B VND/day liquidity threshold was picked by checking the actual
`median_value_20d` distribution before running anything (keeps 56.7% of all
(symbol,date) rows) — not re-picked after seeing the event rate.

**Base rate: 4.20% overall** (N=91,931 defined symbol-days) — within the
required [1%, 15%] band, so Task 2 proceeded automatically per instruction.

| Year | Base rate |
|---|---|
| 2020 | 7.26% |
| 2021 | 10.22% |
| 2022 | 3.95% |
| 2023 | 8.16% |
| 2024 | 5.22% |
| 2025 | 4.01% |
| 2026 | 1.58% |

## Data-coverage gap found during Task 2 — flagging before the results, not after

Task 2's eligibility filter (`above_ma200` AND `value_ma20 >= 10B VND/day` —
inherited unchanged from the earlier IC screens, a *different* threshold
than the 1B used in the event definition itself) turned out to be far too
strict for 2020-2022 in this dataset: median eligible-name count per day was
**2 (2022), 4 (2020), 5 (2021)** — nowhere near the 15-name minimum. Only
from 2023 onward does the eligible count regularly clear 15 (median
32-49/day). Concretely: **all 722 "usable" days for Task 2 fall in
2023-2026; Period 1 (2020-01 to 2022-03) and part of Period 2 have zero
usable days.**

Consequence: `lift_p1` is NaN for every single factor-direction (not a
computation bug — verified directly, see below) — which means the
literal pass criterion ("lift > 1 in all 3 periods") **cannot be satisfied
by any factor, structurally**, regardless of whether a real effect exists.
This is a genuine methodological gap in this run, not something I adjusted
after seeing factor results — the 10B threshold was carried over from prior
scripts without re-checking it against 2020-2022 liquidity levels first.
**I did not loosen it to make the check "work" — reporting it as found, and
flagging that revisiting this threshold (or evaluating only the
2023-2026 window, where the data actually supports it) is your call.**

## Task 2 — main table (top 20 of 88 factor-direction rows, sorted by lift@10%; full 88 in script output)

Both ranking directions ("high" = top decile by highest raw value, "low" =
top decile by lowest raw value) were pre-registered and tested for every
factor — not picked after seeing which direction looked better.

| factor | direction | lift@10% | lift@5% | CI 95% | period 2 | period 3 | passes (strict) |
|---|---|---|---|---|---|---|---|
| distance_ma200 | high | +1.76 | +1.75 | [1.36, 2.32] | +0.86 | +2.27 | **False** |
| bb_width | high | +1.68 | +2.06 | [1.05, 2.60] | +0.62 | +2.28 | False |
| distance_ma50 | high | +1.66 | +2.13 | [1.24, 2.27] | +0.69 | +2.21 | False |
| higher_low_ratio | high | +1.59 | +1.65 | [1.06, 2.22] | +0.97 | +1.93 | False |
| **absorption_score** | **high** | +1.58 | +1.66 | [1.13, 2.26] | **+1.04** | **+1.90** | False |
| **return_10d** | **high** | +1.58 | +1.66 | [1.00, 2.17] | **+1.17** | **+1.78** | False |
| market_down_alpha_20d | high | +1.56 | +1.82 | [1.17, 2.31] | +0.85 | +1.97 | False |
| **up_down_value_ratio_10d** | **high** | +1.44 | +1.56 | [1.11, 1.86] | **+1.06** | **+1.66** | False |
| near_pivot_score | low | +1.37 | +1.09 | [0.86, 2.04] | +1.22 | +1.36 | False |

**0 of 88 factor-directions pass the literal criterion** (mechanically
impossible given the Period 1 gap above — every row has period_p1=NaN).

**Relaxed reading** (evaluating only the two periods the data actually
supports, 2022-03→2024-05 and 2024-05→2026-07 — informal, not a
pre-registered fallback, reported for transparency): **still 0
factor-directions reach CI_lo > 1.5.** The closest are `distance_ma200`
(CI_lo=1.36), `distance_ma50` (1.24), `market_down_alpha_20d` (1.17). Of
those with lift > 1 in *both* evaluable periods — `absorption_score`,
`return_10d`, `up_down_value_ratio_10d` — none has CI_lo above 1.13.

Notable pattern: `distance_ma200`, `distance_ma50`, `bb_width`,
`market_down_alpha_20d` all show period 2 **below 1** (i.e. anti-predictive
or flat in 2022-2024) and period 3 **strongly above 1.7-2.3** (2024-2026).
That looks like regime-specific behavior tied to the recent recovery
window, not a stable, always-on tail-detection signal.

## Task 3 — sanity check on the best-ranked factor (`distance_ma200`, high)

Distribution of `median_value_20d` among the 395 top-decile hits that
actually had an event:

| | value |
|---|---|
| min | 3.1B VND |
| median | 76.6B VND |
| mean | 162.8B VND |
| 90th pct | 481.9B VND |
| **% of hits within 3x the liquidity threshold (< 3B VND)** | **0.0%** |

No caveat needed here specifically — hits are not clustered near the
minimum-liquidity edge, they're comfortably liquid, genuinely tradeable
names. (Moot in the sense that this factor doesn't clear the significance
bar anyway, but worth confirming the *type* of failure isn't "only found
thin, untradeable names.")

## Conclusion

**Still no factor-direction passes**, under either the literal 3-period
criterion (structurally unattainable this run due to the Period 1 data gap)
or a relaxed 2-period reading (0 of 88 reach CI_lo > 1.5). Reframing from
average-relationship (IC) to tail-event lift did not surface a validated
early-warning factor among these 44 technical candidates. The one pattern
worth a mental note, not action: `distance_ma200`/`distance_ma50`/
`bb_width`/`market_down_alpha_20d` cluster tail-event hits specifically in
the 2024-2026 window and are flat-to-negative in 2022-2024 — a regime
dependency, not a general factor.

## What to decide next

1. Whether to revisit the 10B VND eligibility threshold so 2020-2022 can
   actually be evaluated (currently contributes zero information to this
   analysis) — or explicitly scope this event-detection question to
   2023-2026 only, where the data supports it.
2. Whether the period2-fails/period3-strong pattern in a few factors is
   worth a dedicated regime-conditional follow-up, or is better left alone
   given it didn't clear the bar even ignoring Period 1.
3. No code committed to production; this is a research finding only.
