# Eligibility gate mass-STALE_DATA rejection — diagnosis (2026-07-13)

Blocker raised after NV1-NV5 (gate #6/#12/#17 remediation, commits
`b966aa2`/`28b9f60`/`72be363`/`ccad49f`/`550910f`): running the full
pipeline on the regenerated dataset produced 0 eligible candidates
(500/500 landed in `data_review_watchlist`). This document is the
diagnosis only — **no code was changed as a result** (user decision:
report only, do not fix the gate or re-fetch data this round).

## 1. Which pipeline, which gate

`scripts/run_daily_pipeline.py` → `run_meta_ranking.py` →
`build_watchlist_tiers` / `apply_eligibility_gate`
([final_watchlist.py:982](../src/screening/final_watchlist.py#L982)).

The gate measures freshness as a plain date gap, not a row-count or
coverage-ratio:

```python
# final_watchlist.py:326 (_latest_feature_snapshot)
out["analysis_as_of"] = pd.Timestamp(as_of_date)   # = universe's max(date)
out["data_age_days"] = (out["analysis_as_of"] - out["date"]).dt.days

# final_watchlist.py:982 (apply_eligibility_gate)
if not pd.isna(data_age) and data_age > 1:
    reasons.append("STALE_DATA")
```

**Two inconsistent paths through eligibility, confirmed by grep**:
`final_watchlist`/`client_ready_watchlist`/`trading_watchlist`/
`research_candidates` go through this gate. `reports/daily_alpha_ranking.csv`/
`reports/top_watchlist.csv` (`scripts/run_alpha_scoring.py`) do **not** —
`grep -n "eligib\|STALE_DATA" scripts/run_alpha_scoring.py` returns nothing.
Noted as a real inconsistency (two artifacts both called "watchlist" with
different eligibility standards), not fixed this round.

## 2. Five-symbol sample (2 blue-chip, 2 mid, 1 low-liquidity)

Raw `data/full_history_v2/raw/{symbol}.parquet` rows vs. an idealized
trading calendar (business days minus `config/vn_market_holidays.csv`):

| Symbol | Rows | First–last | Coverage vs. calendar | `data_age_days` | `eligibility_reason` |
|---|---|---|---|---|---|
| VIC (blue-chip) | 1622 | 2020-01-02 → 2026-07-06 | 95.7% | 3 | STALE_DATA |
| FPT (blue-chip) | 1622 | 2020-01-02 → 2026-07-06 | 95.7% | 3 | STALE_DATA |
| DHA (mid) | 1613 | 2020-01-02 → 2026-07-06 | 95.2% | 3 | LOW_LIQUIDITY; STALE_DATA |
| VTO (mid) | 1618 | 2020-01-02 → 2026-07-06 | 95.5% | 3 | STALE_DATA |
| APL (low-liquidity) | 160 | 2020-07-16 → 2026-06-24 | **10.3%** | 15 | LOW_LIQUIDITY; STALE_DATA |

## 3. Hypothesis test: "gate hasn't adapted to the volume=0-day-omission convention"

**Rejected as the cause of mass rejection.** Direct inspection of the raw
parquet for VIC/FPT/VCB/HPG/VNM/MWG shows **no rows at all** (not
volume=0 placeholder rows) after 2026-07-06 — this is an absence of
fetched data, not an omitted-but-valid trading session. The
volume=0/no-trade-day convention documented in `DATA_BASELINE.md`
caveat #3 is real, but it explains interior gaps for thin names (like
APL's genuine 10.3% coverage) — not this systemic, universe-wide
tail-end cutoff.

## 4. Actual root cause: two un-reconciled fetch batches, confirmed in `DATA_BASELINE.md`

`DATA_BASELINE.md:20-21`:
> Fetch window: 2026-07-09 main run, **+ supplementary re-fetch pass same
> day for 48 symbols**. Requested date range: 2020-01-01 → 2026-07-06
> (**2026-07-10 for the 48 supplemented symbols**).

This was already documented before this session — it is a known,
deliberate scope boundary of the one-time historical backfill, not a
newly-introduced bug. It has simply never been reconciled by a
subsequent synchronized incremental update across the full 501-symbol
universe.

Full per-symbol gap-vs-universe-max distribution (`data/processed/stock_features.parquet`,
regenerated in gate-6 commit `28b9f60`):

```
gap_days  n_symbols
0          28   <- freshest (subset of the 48-symbol supplement, reached 07-09)
1           8   <- rest of the supplement batch, reached 07-08
2           3   <- reached 07-07
3         411   <- main-batch cohort, capped at the requested 07-06 cutoff
6-20       35   <- moderately stale, ordinary lagging updates
71-499      8   <- long-tail, likely trading suspensions
1219+       3   <- AMD, ARM, ART (etc.) -- effectively delisted/suspended,
                   correctly flagged stale on their own merits
```

`gap_days > 100` symbols: AMD, ARM, ART, ASA, ATB, BBC, BCG, KPF, PSH,
SVI, TCD — `ART` is one of the three tickers (`FLC`/`ROS`/`ART`) named
in `audit/critical_findings.md` P0-1 as an example of a name that should
appear in a point-in-time survivorship check; consistent with this being
a real long-suspended/near-delisted name, not a fetch artifact.

## 5. Conclusion / disposition

The mass rejection is **not** a data-corruption or gate-measurement-convention
bug (the two hypotheses the round intended to fix or reject). It is a
reference-date selection issue: `analysis_as_of` anchors to the
universe's single freshest date (driven by a 28-symbol outlier subset),
so the 411-symbol main cohort — whose own data is 95%+ complete and
internally consistent through 2026-07-06 — gets misclassified as stale
relative to that outlier reference point.

**User decision (2026-07-13, asked via AskUserQuestion after this
diagnosis): stop and report only.** No gate logic change
(`analysis_as_of` reference-date selection), no online re-fetch, and no
regeneration of the NV4 consumer artifacts this round. The three real
remediation options identified, left for a future round to choose
among with full context:
1. Change `analysis_as_of` to the universe's *modal* (most common)
   latest date instead of the max, so a small outlier-fresh subset
   doesn't misclassify the majority cohort. (Gate/policy design change.)
2. Run a synchronized incremental update (`scripts/update_daily_data.py`)
   across the full 501-symbol universe to bring everyone to a common,
   current date. (Data-engineering/online action, needs explicit
   authorization — calls the SSI FCData API.)
3. Leave as-is and treat `client_ready_watchlist`/`trading_watchlist`/
   `research_candidates` as unusable until one of the above happens,
   relying on `reports/top_watchlist.csv`/`daily_alpha_ranking.csv`
   (which bypass this gate) in the interim — while separately deciding
   whether that bypass inconsistency should itself be closed.

This is Gate #3/eligibility-gate-adjacent territory and was intentionally
not touched, per this round's explicit scope boundary.
