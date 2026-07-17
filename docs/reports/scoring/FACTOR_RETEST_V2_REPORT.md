# FACTOR_RETEST_V2_REPORT — first clean-data re-test after the full backfill

**Required citation**: this report's IC and event-detection results are
computed on `data/full_history_v2` (see `docs/reports/data/docs/reports/data/DATA_BASELINE.md` for dataset
identity, coverage, and caveats), rebuilt through `scripts/generate_features.py`
at commit `1566f29` (+ this round's changes: raw-source swap, GEE exclusion,
3B VND eligibility threshold — see `docs/reports/data/docs/reports/data/BACKFILL_DESIGN_REPORT.md` Round 5).
**This is the first time any factor test in this repo has run on a real,
uncorrupted 2020+ cross-section** — every prior IC/event-detection report
(`docs/reports/scoring/docs/reports/scoring/ROBUST_FACTOR_IC_REPORT.md`, `docs/reports/scoring/docs/reports/scoring/EVENT_DETECTION_REPORT.md`) drew almost all
of its usable days from 2023+ only, because 495/501 symbols had no
pre-2023 data at all (per `docs/reports/data/docs/reports/data/DATA_AUDIT_REPORT.md`) and, separately, the
10B VND eligibility filter was "too strict for 2020-2022" even where data
existed (`docs/reports/scoring/docs/reports/scoring/ROBUST_FACTOR_IC_REPORT.md` addendum, `docs/reports/scoring/docs/reports/scoring/EVENT_DETECTION_REPORT.md`
open question #1).

**What changed vs. those prior runs, mechanically**:
1. Raw price source: `data/full_history_v2/raw/` (bug-immune fetch method,
   verified in `docs/reports/data/docs/reports/data/BACKFILL_DESIGN_REPORT.md` Rounds 3-4) instead of the
   pre-fix `data/raw/daily_ohlcv/` (now in `data/quarantine_existing_v1/`).
2. Eligibility threshold lowered 10B → **3B VND** (`MIN_VALUE_MA20` in both
   `scratch/diagnose_factor_ic_robust.py` and `scratch/diagnose_event_detection.py`)
   — resolves the open question from both prior reports now that 2020-2022
   coverage is clean and complete. The event definition's own liquidity
   condition (1B VND/day, part of what defines a "hit") is unchanged.
3. GEE excluded (`config/excluded_symbols.csv`) — unresolved 9-day gap, see
   `docs/reports/data/docs/reports/data/DATA_BASELINE.md`.
4. No other change: same 44+3 candidate list, same Newey-West maxlags=20,
   same market-residual + sector-demean target construction, same
   event definition, same 3-period split, same `|t_NW|>3` and
   `lift CI_lo>1.5 AND lift>1-in-all-3-periods` pass bars. Nothing tuned,
   no factor added or removed from the test list.

**Result of the fix, mechanically confirmed**: base rate check (Task 1 of
event detection) now shows real 2020/2021 event rates (10.13%/15.59%) for
the first time — previously these years were essentially unobserved. IC
test now draws ~1,480-1,520 usable days per combination (vs. a 14-24 month
window before).

---

## NV4 (priority) — the 3 currently-deployed factors

`distance_ma20` (extension/eligibility gate, `src/screening/final_watchlist.py`),
`return_20d` (drives the momentum component, `src/alpha/scoring.py:111`),
`realized_vol_20d` (drives the volatility-contraction component,
`src/alpha/scoring.py:130`).

| Factor | IC (best \|t_NW\|) | IC verdict | Event lift (best direction) | Event verdict |
|---|---|---|---|---|
| **realized_vol_20d** | **-5.41** (full & top150, residualized; consistent -4.4 to -6.2 across 5d/10d/60d horizons too) | **Strong, robust, real** | high: lift=1.20, CI_lo=1.01, period-2 lift=0.97 (fails) | Does not pass; noisy/inconsistent for tail-capture |
| `return_20d` | -1.24 (max \|t_NW\| across all 4 combos; raw sign flips full-vs-top150) | **Not significant, no real average-return signal** | high: lift=1.32, CI_lo=1.19, holds >1 in all 3 periods | Close but does not clear CI_lo>1.5 bar |
| `distance_ma20` | -0.29 (max \|t_NW\|=1.61, weakest of the 3) | **Not significant, no real average-return signal** | high: lift=1.35, CI_lo=1.25, holds >1 in all 3 periods — **2nd-highest raw lift of all 47 candidates** | Close but does not clear CI_lo>1.5 bar |

### Recommendation

**`realized_vol_20d` — GIỮ (keep).** The only one of the 3 with a
statistically robust signal on clean data: |t_NW| = 5.41 in both the full
and top-150 universes on the residualized target, and the sign/magnitude
holds consistently from 5d out to 60d horizons (t_NW -5.95 to -4.29 across
that range). This is real, validated evidence that high realized volatility
predicts lower idiosyncratic forward returns — its role driving the
volatility-contraction component of the alpha score is empirically
supported. It does *not*, however, help detect the specific tail-event
this repo's event-detection framework targets (explosive +25% 60d moves)
— its lift is inconsistent across sub-periods (period-2 lift = 0.97, i.e.
slightly *worse* than base rate) — so it should be understood as an
average-return factor, not an event-detector, and not asked to do that job.

**`return_20d` — GỠ (remove) from the momentum-score weighting.** Zero
significant IC in all 4 tested combinations (full/top150 × raw/residualized),
with the raw sign even flipping between universes — this is definitionally
what "no signal" looks like under this test. `return_60d`, the other input
to the momentum component, independently shows the same null result
(max |t_NW|=1.43, not significant). The event-detection angle shows a
directionally positive, 3-of-3-periods-consistent lift (1.32) — but it
does not clear the pre-registered CI_lo>1.5 bar, and per this session's
explicit constraint (no new test variants, no re-tuning the pass criteria
to fit a result), a near-miss on a stricter test cannot be used to rescue
a factor that fails the test it's actually deployed against (average
forward-return prediction via the momentum score). Recommend removing it
from that role; if event-detection is later formalized as its own scoring
path, `return_20d`'s near-miss lift would be worth reopening as a fresh,
separate question — not a justification to keep it where it is now.

**`distance_ma20` — GIẢM TRỌNG SỐ (reduce weight), not full removal.**
Same null result on average-return IC (max |t_NW|=1.61) as `return_20d` —
if it were being used as a ranked alpha factor, the same GỠ logic would
apply. But its actual deployed role is different: an *extension gate*
(a threshold filter against over-extension from the 20d MA), not an alpha
ranker, and no test run here specifically evaluates a gate's job (does it
reduce downside/entry risk?) — only average-IC and explosive-upside-event
lift were tested, and neither is what a defensive gate is for. What *is*
notable: `distance_ma20` posts the **2nd-highest raw event-detection lift
of all 47 candidates tested** (1.35, behind only `distance_ma50` at 1.37),
consistent across all 3 sub-periods (1.32/1.15/1.82) — it just falls short
of the strict CI bar (1.25 vs. required 1.5), plausibly a power/sample-size
issue rather than a true-zero effect. Recommend de-emphasizing it (reduce
its weight/strictness as a gate) rather than removing it outright, and
flagging the event-detection angle as a promising, not-yet-conclusive lead
worth a dedicated, pre-registered follow-up test — not something to fold
into this session's already-run analysis after the fact.

---

## NV5 — full 44-candidate re-test (informational, same run as above)

Both scripts ran once each over the complete candidate list (no separate
reduced-candidate run — the 3-factor table above is a subset view of the
exact same computation, not a re-tuned or differently-scoped test).

### IC Newey-West (`scratch/diagnose_factor_ic_robust.py`, full output: `scratch/logs/diagnose_factor_ic_robust_v2.log`)

**21 of 192 factor×universe×target combinations clear |t_NW|>3** (vs. 0
in the pre-backfill `docs/reports/scoring/docs/reports/scoring/ROBUST_FACTOR_IC_REPORT.md` run). Top combinations:

| Factor | Universe | Target | mean IC | t_NW |
|---|---|---|---|---|
| `atr_pct_14` | top150 | residualized | -0.0755 | -5.76 |
| `atr_pct_14` | full | residualized | -0.0785 | -5.65 |
| `realized_vol_20d` | full | residualized | -0.0758 | -5.41 |
| `realized_vol_20d` | top150 | residualized | -0.0734 | -5.41 |
| `volatility_dryup_score` | full | residualized | +0.0622 | +4.97 |
| `volatility_dryup_score` | top150 | residualized | +0.0598 | +4.95 |
| `dist_kurt_60d` | full | residualized | +0.0582 | +4.47 |
| `accumulation_score` | top150 | residualized | +0.0551 | +4.34 |
| `tight_range_score` | full | residualized | +0.0485 | +3.84 |

Pattern: every one of the top strong-and-robust signals is a
**volatility-family** factor (`atr_pct_14`, `realized_vol_20d`,
`volatility_dryup_score`, `dist_kurt_60d`, `tight_range_score`) or a
composite score built substantially from volatility inputs
(`accumulation_score`, `net_accumulation_score`). Pure return/momentum
factors (`return_5d/10d/20d/60d`, `relative_strength_20d`,
`sector_relative_strength_20d`) and static price-location factors
(`distance_ma20/50/200`) show **no** combination clearing the bar for
average-return prediction. Full per-row table in the log file; 3
NaN factors (`up_down_volume_ratio`, `breadth_support_score`,
`market_support_score`) have zero eligible non-null days and could not be
evaluated — pre-existing, not introduced by this backfill.

### Event detection (`scratch/diagnose_event_detection.py`, full output: `scratch/logs/diagnose_event_detection_v2.log`)

Base rate 6.72% (N=579,193 defined symbol-days; by year 2020=10.1%,
2021=15.6%, 2022=4.1%, 2023=5.7%, 2024=3.4%, 2025=4.0%, 2026=1.9%) — passes
the [1%,15%] gate, proceeds to Task 2.

**0 of 94 factor-direction combinations pass** (`CI_lo>1.5` AND
`lift>1` in all 3 periods) — same comprehensively-negative conclusion as
the pre-backfill `docs/reports/scoring/docs/reports/scoring/EVENT_DETECTION_REPORT.md`, now confirmed on a real,
clean, full 2020+ cross-section rather than a mostly-2023+ one. The
ranking of near-misses is topped by static price-location factors
(`distance_ma50` high: lift=1.37, `distance_ma20` high: lift=1.35,
`higher_low_ratio` high: lift=1.33, `return_20d` high: lift=1.32) — the
opposite pattern from the IC table, where these same factors were flat.
Sanity check on the single best factor-direction (`distance_ma50`, high):
94.6% of captured hits have `median_value_20d` comfortably above 3x the
liquidity threshold — the lift is not an artifact of a thin, illiquid tail.

**Conclusion for NV5**: the comprehensively-negative event-detection
finding survives the data cleanup — this was not a data-quality artifact.
The IC picture changed materially (0/176 → 21/192 clearing the bar), but
the newly-significant factors are concentrated in one family
(volatility/quiet-accumulation), not spread across the candidate list.
