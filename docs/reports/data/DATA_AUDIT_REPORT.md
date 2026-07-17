# DATA_AUDIT_REPORT — the "501-symbol, 2020-2026" universe is real only from ~2025-Q2

Pure diagnosis, no fixes, no re-runs, no threshold changes. Triggered by
`docs/reports/scoring/EVENT_DETECTION_REPORT.md`'s finding of only 2-5 eligible names/day in
2020-2022 — which is inconsistent with 2021 being a record-liquidity year
for VN equities, so the suspect was a data problem, not a real liquidity
constraint. **Confirmed: it's a universe/coverage problem, not liquidity and
not a units bug — and it is far larger in consequence than originally
suspected.**

## Task 1 — coverage inventory by year

Symbols with `close`/`value` non-null on >=80% of that year's sessions, vs.
symbols clearing three `value_ma20` liquidity thresholds (last available
reading each year, `data/processed/stock_features.parquet`):

| Year | N with >=80% session coverage | N with value_ma20 >= 10B | >= 3B | >= 1B |
|---|---|---|---|---|
| 2020 | **5** | 5 | 5 | 5 |
| 2021 | **5** | 6 | 6 | 6 |
| 2022 | **6** | 6 | 6 | 6 |
| 2023 | 15 | 86 | 91 | 93 |
| 2024 | 15 | 87 | 94 | 94 |
| 2025 | 15 | 151 | 214 | 282 |
| 2026 (partial, ~123 sessions) | 323 | 128 | 198 | 261 |

**2020-2022: only 5-6 symbols have sustained data, out of a claimed
501-symbol universe.** This alone explains `docs/reports/scoring/EVENT_DETECTION_REPORT.md`'s
"2-5 eligible names/day" finding — it was never a liquidity-threshold
problem, there was almost nothing in the data to filter in the first place.

## Task 2 — unit/correctness check on 5 known-liquid 2021 blue chips

Checked HPG, SSI, STB, TCB, VPB — all definitely large, liquid, actively
traded throughout 2021 in reality — in both `stock_features.parquet` and
`stealth_accumulation_history.parquet`:

| Symbol | Rows found in 2021 | Verdict |
|---|---|---|
| HPG | 0 | **Missing entirely** |
| SSI | 0 | **Missing entirely** |
| STB | 0 | **Missing entirely** |
| TCB | 0 | **Missing entirely** |
| VPB | 250 (full year) | Present |

VPB's own monthly average traded value in 2021 (the one symbol with data):
Jan 207.8B, Feb 260.1B, Mar 198.1B, Apr 562.9B, ..., Sep 449.1B, Oct 404.7B,
Nov 555.2B, Dec 584.2B VND/day — **the right order of magnitude** for a
large-cap VN bank in 2021. **This rules out a units/scaling bug.** Where
data exists, it's correctly scaled. The problem is that for 4 of 5 obviously
important names, there is no data at all for 2021 — not wrong data, absent
rows.

## Task 3 — universe origin and per-symbol start-date distribution

`scripts/update_daily_data.py::get_full_universe_symbols()` reads the union
of `data/raw/securities/{HOSE,HNX,UPCOM}.parquet` (the real exchange-listed
universe, added per commit `f1c6a40 fix(B1): scope=full reads the real
listed universe from exchange securities lists`). `config/strategy_config.yaml`'s
hand-picked "core" watchlist has only **30 symbols** (includes HPG, SSI,
STB, TCB, CTG, ...).

First-available-date distribution across all 501 symbols in
`stock_features.parquet`:

| First date | N symbols |
|---|---|
| 2020-Q1 | **5** |
| 2021-Q1 | 1 |
| 2023-Q1 | 88 |
| 2025-Q2 | **406** |
| 2026-Q1 | 1 |

**495 of 501 symbols (98.8%) have no data before 2023. 406 of 501 (81%)
have no data before 2025-Q2** — roughly the last 14 months before "today"
(2026-07-09). Even the config's own 30-symbol "core" watchlist isn't
spared: of HPG/SSI/STB/TCB/CTG, only **CTG** has data from 2020-Q1; the
other four fall in the 2023-Q1 cohort despite being flagship, long-listed
names that should have full history if the universe were genuinely
point-in-time since 2020.

Git history is consistent with a real-world timeline: `02b87e3 expand
candidate pool and enforce exclusive watchlist tiers` → `d7c283e add
universe update scope and per-symbol freshness policy` → `f1c6a40 fix(B1):
scope=full reads the real listed universe from exchange securities lists`.
**Most likely mechanism** (circumstantial, not confirmed from fetch logs):
the tracked universe was expanded from a small core list to the full
~501-symbol exchange list relatively recently, and the historical backfill
for most newly-added symbols was never completed back to 2020 — plausibly
because backfilling 6+ years of daily history for ~500 symbols via the SSI
FCData provider is a large, rate-limited fetch job that only finished (or
was only run) starting around 2025-Q2, populating data forward from that
point without retroactively filling 2020-2025 history for those symbols.

## Diagnosis

**Universe/coverage problem. Not a liquidity threshold problem (Event
Detection Task's original suspect). Not a units/scaling bug (Task 2 rules
this out directly).** The "2020-2026, 501-symbol" dataset this entire
research effort has been built on on is, in reality:
- 2020-2022: a 5-6 symbol dataset
- 2023-2024: a ~90-symbol dataset
- 2025-Q2 onward: something close to the claimed ~500-symbol universe

## Consequences for prior conclusions — this is the important part

**Every walk-forward result in this session (and the prior session's
`docs/reports/scoring/STRATEGY_RESEARCH_REPORT.md`) that included a pre-2025 period was computed
on a universe far smaller than believed:**

- The "2022 crash fold" (-27.6%, repeated identically across every re-test
  in this session — `docs/reports/scoring/STRATEGY_RESEARCH_REPORT.md`, `docs/reports/deploy/DEPLOY_REPORT.md`,
  `docs/reports/scoring/CRASH_RISK_RESEARCH_REPORT.md`, `docs/reports/codebase_audit/PIPELINE_AUDIT_REPORT.md`) is the return
  of a **5-6 symbol portfolio**, not a cross-sectional stock-picking result
  over hundreds of names. With `portfolio_size=5`, the backtest's "top-5 by
  score" selection had essentially no universe to select FROM in 2020-2022
  — it was holding close to the entire available dataset regardless of
  which factor or formula was used. This is almost certainly why that
  fold's return was so consistent and unaffected by every formula change
  tested (old momentum fallback, 3-factor score, breadth-collapse overlay,
  zero-fill variants) — there was barely a choice being made.
- The "2023 fold" (~90-93 symbols) is thin but at least somewhat
  cross-sectional; still far from the claimed universe size.
- `docs/reports/scoring/META_RANKING_VALIDATION_REPORT.md`'s 40-date IC reconstruction,
  `docs/reports/scoring/ROBUST_FACTOR_IC_REPORT.md`'s 176-combination Newey-West re-test, and
  `docs/reports/scoring/EVENT_DETECTION_REPORT.md`'s 88-combination lift test all applied
  eligibility filters (liquidity + `above_ma200`) that, per Task 1's table,
  could only be meaningfully satisfied from **2023 onward, and mostly only
  from 2025-Q2 onward** — meaning every one of those "walk-forward 2020-2026"
  or "rolling 5-fold" analyses was, in the years that actually contributed
  usable days, testing something much closer to **a 14-24 month sample**,
  not 6 years. Both reports already contain a version of this caveat for
  the specific period-1 gap found in `docs/reports/scoring/EVENT_DETECTION_REPORT.md`; this
  report generalizes it to essentially all prior "multi-year" work.
- This also affects the ORIGINAL audit + strategy research
  (`docs/reports/scoring/STRATEGY_RESEARCH_REPORT.md`, `docs/reports/codebase_audit/AUDIT_REPORT.md`) from the session before
  this one — every one of its "2020-2023 train / 2024-2026 test" splits and
  "6-year backtest" claims rests on the same thin early-period universe.

**Addenda added to `docs/reports/scoring/ROBUST_FACTOR_IC_REPORT.md` and `docs/reports/scoring/EVENT_DETECTION_REPORT.md`**
pointing back to this report, per instruction.

## Correction (statistical error in the original version of this section)

The original text here claimed a smaller sample makes the negative findings
"MORE likely to hold." **That is wrong and has been corrected**: a smaller
sample does not strengthen a null result — it just means the test had **no
statistical power in either direction**. The 2020-2022 portion of every
prior walk-forward/IC/lift analysis (a 5-6 symbol universe) is not weak
evidence *for* "no alpha" — it is **not evidence at all**, in either
direction. It cannot be cited as support for a negative conclusion, and it
equally could not have been cited as support for a positive one.

**Correct scope of what remains valid**: the negative findings in
`docs/reports/scoring/META_RANKING_VALIDATION_REPORT.md`, `docs/reports/scoring/ROBUST_FACTOR_IC_REPORT.md`, and
`docs/reports/scoring/EVENT_DETECTION_REPORT.md` retain whatever validity they had **only for
the sub-period where the universe was actually thick enough to test
anything** — in practice, ~2025-Q2 onward with something close to the full
universe, and 2023-2024 only weakly (~90-93 symbols, thin but non-trivial).
The 2020-2022 portion of those analyses should be read as **uninformative,
not confirmatory** — neither for nor against the factors tested.

**This means the "validated" status of the 3 factors already deployed to
production (`src/analytics/reversal_quality_score.py`, replacing both the
backtest fallback and `score_meta_ranking()`) rests on a much thinner
evidence base than recorded at deploy time.** The original walk-forward
validation (`docs/reports/scoring/STRATEGY_RESEARCH_REPORT.md`) presented 2022 as a real,
informative crash-year test fold; it was not — it was a 5-6 symbol result
with no cross-sectional power. Whatever confidence that fold contributed to
the original "validated" decision should be discounted entirely, and the
deploy decision (already made and reported as based on a full 2020-2026
walk-forward) should be treated as an open item pending re-assessment
against only the periods that actually carried statistical weight. This is
not something resolved in this report — flagging it for an explicit
decision, since it affects code already sitting in an unmerged PR.

## What this does NOT mean

- It does not mean 2025-Q2-onward results are unreliable — that's the one
  window where the data appears to genuinely match the claimed universe
  size (406 of 501 symbols have data from exactly there).

## Proposed remediation options (not executed this round — your call)

1. **Backfill history for the ~495 symbols missing pre-2023 data** via
   `scripts/update_daily_data.py --scope full` (or `batch`), if the SSI
   FCData provider supports requesting data that far back per symbol. This
   is the only option that would let future walk-forward work genuinely
   cover 2020-2026 for the full universe. Likely a long-running,
   rate-limited job (~500 symbols x 6 years).
2. **Rescope all historical claims to what the data actually supports**:
   treat 2023-2026 as the only evaluable window (and note the 2023-2024
   portion is still a thin ~90-symbol sample), rather than "2020-2026."
   Cheapest option, no new fetching, but permanently narrows the backtest
   horizon and loses the 2022 crash year as a real cross-sectional test.
3. **Explicitly flag and exclude the 2020-2022 window** from any future
   walk-forward/IC work using this dataset until (1) is done, rather than
   silently including dates that contribute near-zero real information (as
   happened throughout this session).

No threshold was loosened, no data was modified, and no test was re-run in
this round, per instruction. Decision on which remediation path (if any) to
take is deferred to the next round.
