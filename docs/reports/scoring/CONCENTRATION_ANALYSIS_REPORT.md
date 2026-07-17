# CONCENTRATION_ANALYSIS_REPORT — is the tail concentration risk, or the signal?

**Dataset/code version**: `data/full_history_v2` (`docs/reports/data/docs/reports/data/DATA_BASELINE.md`),
deployed scoring at commit `7c791d7` (post-`docs/reports/scoring/docs/reports/scoring/SCORING_UPDATE_REPORT.md` and
`docs/reports/scoring/docs/reports/scoring/FOLD_AUTOPSY_REPORT.md` changes). Follow-up to `docs/reports/scoring/docs/reports/scoring/FOLD_AUTOPSY_REPORT.md`,
which ruled out simple regime labels and transaction costs and named
portfolio structure (5 equal-weighted names, idiosyncratic/sector variance)
as the next suspect. **Seed = 42** for every random draw below (same
convention as `scratch/pilot_backfill.py` earlier this session), one
continuous RNG stream across all 10,000 null-test iterations, not reset
per fold.

**Critical caveat, upfront and throughout**: this whole analysis rests on
**5 folds**. Every mean/average figure below has a large, unquantified
standard error — a 6th fold could move any of these numbers substantially.
Treat directional evidence as suggestive, not confirmatory.

---

## NV1 — concentration null test

For each fold, 2,000 random 5-stock portfolios were drawn from the exact
same eligible universe the real system uses at each rebalance (same
20-day rebalance schedule, same 0.15% transaction cost, same equal-weight
allocation, same `above_ma200`/`value_ma20>=10B` filters) — implemented by
feeding `run_portfolio_backtest` a uniform-random score column per
iteration and letting its own top-N-by-score selection do the sampling,
so no selection logic was reimplemented. The real (deployed) `alpha_score`
portfolio's CAGR was then located as a percentile within each fold's
2,000-portfolio null distribution.

| Fold | Real CAGR | Null p1 | p5 | p25 | p50 (median) | p75 | p95 | p99 | **Real's percentile** |
|---|---|---|---|---|---|---|---|---|---|
| 2022 | −51.7% | −62.5% | −58.8% | −50.6% | −44.7% | −37.7% | −27.2% | −18.1% | **21.5** |
| 2023 | +11.2% | −12.6% | −5.4% | +4.1% | +11.8% | +20.4% | +34.0% | +44.5% | **48.4** |
| 2024 | +9.6% | −15.0% | −8.4% | +2.5% | +11.6% | +21.5% | +37.3% | +49.0% | **42.5** |
| 2025 | +37.8% | −24.0% | −15.5% | −2.5% | +8.9% | +21.1% | +42.9% | +58.0% | **93.0** |
| 2026 | −59.7% | −56.1% | −50.0% | −37.4% | −27.2% | −14.8% | +9.2% | +28.5% | **0.4** |

**Average real-portfolio percentile across 5 folds: 41.2** — below the
50th percentile. Read plainly: across these 5 folds, picking 5 random
eligible names on average did *better* than the deployed scoring system.
This is the cleaner, apples-to-apples measure the null test was designed
to produce, and it is a more serious finding than the raw mean-CAGR
comparison in `docs/reports/scoring/docs/reports/scoring/SCORING_UPDATE_REPORT.md`/`docs/reports/scoring/docs/reports/scoring/FOLD_AUTOPSY_REPORT.md` surfaced
on its own.

### Per-fold, against the pre-registered interpretation

- **2022** (percentile 21.5, disaster fold): falls in the 5–25 bucket —
  **"mainly concentration variance, not active harm."** The real portfolio
  underperformed most random draws (worse than ~78% of them) during the
  broad 2022 bear market, but not at the extreme low end that would
  indicate the signal was actively pointing the wrong way.
- **2023** (48.4) and **2024** (42.5): both land close to the median,
  matching neither the ">50 in a good fold" nor any disaster bucket —
  **statistically indistinguishable from random stock-picking** in both
  of these profitable-but-unremarkable years.
- **2025** (93.0, the best fold, CAGR +37.8%): **clear positive evidence
  the signal added real value** — top 7% of all random portfolios drawn
  from the same eligible universe.
- **2026** (0.4, the worst fold, CAGR −59.7%): **percentile < 5 in a
  disaster fold — the pre-registered signature of "active signal actively
  hurt this period," not concentration noise.** 99.6% of random 5-stock
  portfolios from the same eligible universe did *better* than the
  deployed score's actual picks. This sharpens `docs/reports/scoring/docs/reports/scoring/FOLD_AUTOPSY_REPORT.md`'s
  2026 finding: it isn't just an unlucky concentrated draw during a
  narrow-breadth market — the scoring formula itself steered toward
  names that underperformed even a random draw from the same
  (already trend/liquidity-filtered) universe.

---

## NV2 — portfolio-construction sensitivity

One run per configuration (`scratch/concentration_size_sensitivity.py`),
same folds/costs, config not chosen based on which result looked best.

| Config | Mean CAGR | Median CAGR | Worst fold | Avg Max DD | Avg turnover |
|---|---|---|---|---|---|
| size=5 (current) | −10.6% | +9.6% | **−59.7%** | −33.4% | 172.2% |
| size=10 | −12.9% | −2.0% | −55.2% | −31.2% | 157.3% |
| size=20 | −8.4% | +8.4% | −45.3% | −29.1% | 143.5% |
| size=10 + sector cap 2 | **−7.0%** | +9.1% | −47.3% | **−28.4%** | 164.3% |

**Against the pre-registered theoretical expectation** ("more names →
shallower worst fold, mean/median converge"):
- **Worst-fold CAGR shallows monotonically with size**, as predicted:
  −59.7% → −55.2% → −45.3% for 5/10/20 names. **Confirmed.**
- **Mean-median gap narrows** (−20.1pp → −16.8pp for size 5 → 20) but only
  modestly, not dramatically. **Weakly confirmed.**
- **Mean CAGR itself is *not* monotonic** — it gets *worse* at size=10
  (−12.9%) before improving at size=20 (−8.4%). **Does not match the
  simple theoretical expectation** — with 5 folds this dip could be
  small-sample noise, but it means "just add more names" is not a clean,
  guaranteed fix on this evidence.
- **Sector cap helps independently of raw name count**: size=10 + cap-2
  beats plain size=10 on every single metric (mean CAGR, worst fold, max
  DD), and even edges out size=20 on mean CAGR and max DD despite holding
  half as many names. This points at *sector* diversification specifically,
  not just headcount, as the more effective lever.

---

## Final diagnosis: both, but not evenly split across folds

Putting NV1 and NV2 together:

- **2022**: structure/variance-flavored (percentile 21.5, not <5) — a real
  bear market where average stock-picking, including random, struggled;
  more names/sector diversification would plausibly have helped (NV2's
  worst-fold-shallowing pattern is consistent with this).
- **2023, 2024**: indistinguishable from random either way — no strong
  signal, no strong harm. Structure changes wouldn't obviously move
  these.
- **2025**: genuine signal value (percentile 93) — not a structure
  question at all.
- **2026**: **a signal problem, not (primarily) a structure problem.**
  The null test's percentile-0.4 result means more names or better sector
  spreading would have diversified the *same wrong picks* across a wider
  base — likely softening the drawdown somewhat (consistent with NV2's
  worst-fold pattern generally) but not addressing why the ranking
  favored underperforming names in a narrow-breadth market in the first
  place. That is a scoring-methodology question, out of scope for a
  portfolio-construction round.

**This round's overall conclusion**: portfolio construction (concentration
in 5 equal-weighted, sector-unconstrained names) is a real, evidenced
contributor to tail depth — but is not suffient on its own to explain the
worst fold, where the evidence points at the signal itself. A structure
change alone would be expected to blunt future disasters somewhat, not
prevent a repeat of 2026's specific failure mode.

## Proposed configuration (not applied — decision for a future round)

Based on the evidence above, **`portfolio_size=10` with a sector cap of 2**
is the best-evidenced candidate among the 4 tested: it wins on mean CAGR,
avg max drawdown, and improves substantially on plain size=10's worst
fold, at a turnover cost roughly comparable to the current size=5 setup
(164.3% vs. 172.2%). This is a proposal only — **not installed this
round**. Any adoption decision should weigh: (a) the 5-fold sample size
caveat above, (b) that this does not fix the 2026-style signal-driven
failure mode NV1 identified, and (c) whether a dedicated scoring-quality
round (out of scope here — this round touched no scoring, no factors, no
overlay) should be sequenced first.
