# BACKFILL_DESIGN_REPORT — design + 20-symbol pilot for full 2020 backfill

Follow-up to `DATA_AUDIT_REPORT.md`. Decision already made: backfill full
history to 2020 (or earlier if the source allows). This round: design +
pilot only, verifying quality on 20 symbols. **No full backfill run. No
existing data overwritten** — pilot output lives entirely under
`data/pilot_backfill/raw/`, untouched by anything else in the pipeline.

## Task 1 — data source inventory

Current pipeline fetches price/volume via `src/data/ssi_client.py`
(`SSIDataClient`), a thin wrapper around the `ssi_fc_data` package calling
SSI FCData's `daily_ohlc` / `daily_stock_price` endpoints
(`config/fcdata_config.py` reads credentials from `.env`; both were present
and valid in this environment).

**Tested directly** (live calls, read-only, no data source registration
needed):
- `get_daily_ohlc('HPG', '2020-01-01', '2026-07-06')` → **1,622 rows**, full
  2020-01-02 → 2026-07-06 coverage, in ~9.5 seconds (auto-paginated, 2 pages
  since page_size=1000 < 1622 rows).
- `get_daily_ohlc('HPG', '2010-01-04', '2010-01-15')` → data returned
  successfully. **The source supports history back to at least 2010** (HPG
  has been listed since 2007; did not test further back, no need to for
  this project's 2020-2026 scope).

**Conclusion: no source-capability limitation.** The existing SSI FCData
integration can fetch full 2020-2026 (and further back) history for any
symbol. The gap found in `DATA_AUDIT_REPORT.md` was purely that this fetch
was never run for ~495 of 501 symbols — not a provider/API constraint. **No
alternative data source is needed or was investigated further**, per
instruction not to register anything new.

**Rate/throughput characteristics** (measured, not estimated): client-side
throttle enforces >=1.0s between calls (`SSIDataClient._call`); a full
2020-2026 history for one symbol took **~9-10 seconds** end-to-end
(1-2 paginated calls + throttle + processing). See Task 3 for the
501-symbol extrapolation.

## Task 2 — point-in-time universe (survivorship bias) — reporting only, not solved

Checked whether the current source can enumerate the **historical**
listed universe (including symbols delisted/suspended since 2020), not
just today's:

- `get_securities(market)` → returns only `market, symbol, stockname,
  stockenname` for the market's **current** listing. No date parameter, no
  status/delisted field. Verified live (HOSE: 736 rows, columns confirmed).
- `get_securities_details(market, symbol)` → richer schema (`FirstTradingDate`,
  `LastTradingDate`, `MaturityDate`, etc. exist in the schema) but requires
  already knowing the symbol, and for an active name like HPG these date
  fields came back empty — no evidence this can be used to *enumerate*
  historically-delisted tickers, only to look up detail for a ticker you
  already have.

**Confirmed: no way to reconstruct historical point-in-time universe
membership from the currently-integrated source.** Documenting the
limitation as instructed, not resolving it this round:

**Universe = "symbols listed today, backfilled to 2020."** Any company
that was listed and traded in 2020-2026 but has since delisted, gone
bankrupt, merged away, or been suspended indefinitely will **not** appear
in this universe at all, no matter how much history we backfill for the
501 currently-active symbols.

**Consequence for event detection specifically**: this creates a real,
directional bias for exactly the kind of question `EVENT_DETECTION_REPORT.md`
asked. A stock that had an explosive +25% 60-day move and *then* later
deteriorated into delisting is invisible to this dataset — we only ever see
the survivors of any given pattern. This **inflates the apparent quality**
of the surviving population relative to reality: any factor found to
predict "explosive move" will look better than it really is, because the
denominator/comparison set silently excludes names that also had signal-
matching characteristics but ended badly enough to disappear from today's
listing. This does not invalidate everything already found — the
44-factor and event-detection results this session were comprehensively
negative anyway — but it is a real ceiling on how much confidence a
*future* positive finding could earn without addressing this.

## Task 3 — 20-symbol pilot backfill

**Selection** (fixed seed=42): 5 reference (`HPG, SSI, STB, TCB, VPB` — the
symbols confirmed missing from 2021 in `DATA_AUDIT_REPORT.md`) + 15 random,
5 from each of low/mid/high current-liquidity terciles of the full 495-symbol
universe (excluding the 5 references): `SVD, HAS, PTL, AG1, YBM, VNE, APG,
LIX, SRC, SJD, LCG, TVC, ITD, HHP, DGW`.

**Fetch result**: 20/20 succeeded, 207 seconds total (~10.4s/symbol). All 5
reference symbols returned the full 1,622 rows (2020-01-02 → 2026-07-06) —
directly confirming the "missing" 2020-2022 data was a backfill gap, not a
source problem. The 15 random symbols returned between 1,101 and 1,622
rows, with shorter spans consistently explained by later IPO/listing dates
(e.g. SVD starts 2021-02-02, AG1 starts 2020-04-10) — not fetch failures.

### (a) % of sessions present vs. trading calendar (VNINDEX proxy, per year)

18 of 20 symbols show >=95% coverage in most years they were listed. Two
patterns worth noting, neither a fetch defect:
- Genuine late-IPO symbols show 0% in pre-listing years (SVD: 0% in 2020),
  consistent with reality.
- A handful of small/micro caps show **sustained coverage drops in later
  years** — `HAS` (41-52% in 2025-2026), `SRC` (74-81% in 2023-2026), `TVC`
  (50.2% in 2023), `YBM` (67.6% in 2024). This looks like genuine
  extended trading halts/suspensions (common for smaller VN-listed names
  under administrative review or financial distress), not a fetch problem
  — the reference blue chips (HPG/SSI/STB/TCB/VPB) and larger names
  (APG/DGW/LCG/SJD) show 94-100% throughout.

### (b) junction continuity — 18 of 20 clean, 2 need dedicated follow-up before trusting a merge

Compared pilot's last pre-junction close to existing data's first close
(VPB has no gap — already full history, used instead as a same-series
sanity check: **0.0000% difference across all 1,622 overlapping rows**,
confirming the pilot fetch reproduces already-trusted data exactly where
both exist).

18 of 20 junctions show a small, plausible one-session move (-1.6% to
+7.0%). **Two do not**: `HPG` (+58.14%) and `TCB` (+124.80%), both at the
2023-01-03 junction (a 4-calendar-day gap over the New Year holiday, so
really one trading session). A jump this large is not a normal trading
session move under any circumstances — it needs to be either a genuine,
very large corporate action (bonus share issuance around year-end is
plausible for VN banks/steel companies) that the existing G4
flag-and-NaN mechanism would need to catch on the merged series, or a
genuine basis inconsistency between this pilot fetch and however the
already-existing 2023+ data was originally fetched. **Not resolved here —
flagged as a required check before merging backfilled history for these
two symbols** (and worth spot-checking more broadly once scaled to 501,
since these two were found in a sample of only 20).

### (c) magnitude sanity — clean pass, confirms no units bug

2021 average daily traded value (VND):

| Symbol | 2021 mean | 2021 median |
|---|---|---|
| HPG | 1,306.2B | 1,184.1B |
| SSI | 647.2B | 551.7B |
| STB | 687.9B | 577.3B |
| TCB | 741.2B | 632.6B |

All comfortably in the "hundreds of billions to >1000B VND/day" range
expected for these names in 2021 — directly confirms correct units/scale
in the fetched data.

### (d) 1-day return outliers > |20%| unadjusted

31 outlier observations across the 20 symbols (0 among the 5 reference
blue chips; concentrated in smaller-cap random picks: `STB`(2, actually
found in a different context — see note), `HAS`(4), `PTL`(2), `AG1`(1),
`YBM`(6), `VNE`(4), `SRC`(4), `SJD`(2), `ITD`(6)). **Almost all of these
are a verification-script artifact, not a real data problem**: most show
`close=0` on one day (immediately followed by `-100%` then `+inf%` on
resumption) — this is a **trading-halt/suspension representation** (a
recorded zero price on a non-trading/halted session), and the existing
production pipeline's `add_returns()` already guards against exactly this
(`valid_prices = close.where(close > 0)` in `src/features/returns.py`) —
so these would correctly become NaN in the real pipeline, not a fabricated
-100%/+inf% return. My verification script's naive `pct_change()` doesn't
have that guard, which is why they show up here. **One genuine outlier**
survives this caveat: `AG1` on 2020-10-22, close=7,408, return=**-30.9%**
with no zero-price involved — a real large single-session move, exactly
the kind of event the existing G4 corporate-action flag is designed to
catch once this data flows through the standard pipeline.

## Verdict on the 4 pilot checks

| Check | Result |
|---|---|
| (a) session coverage | Pass, with expected/explicable partial-year and suspension patterns |
| (b) junction continuity | **18/20 clean, 2/20 (HPG, TCB) need dedicated investigation before merge** |
| (c) magnitude sanity | Clean pass |
| (d) outlier scan | Pass once the close=0 halt artifact is accounted for; 1 genuine outlier (AG1), which the existing G4 mechanism already knows how to handle |

**Not a unanimous 4/4 pass** — (b) surfaced a real, unresolved question on
2 of 20 symbols. Per instruction, proceeding to the full-backfill time/
storage estimate below as requested, but recommending the HPG/TCB junction
anomaly be resolved (or at least understood) before actually running a full
backfill, since if it's systemic rather than symbol-specific it would
affect many more names at scale.

## Full-backfill estimate (proposal only, not run)

- **Time**: ~10.4s/symbol observed (throttled to ~1 call/sec, 1-2 pages per
  symbol for 6.5 years of history) → 501 symbols × ~10.4s ≈ **87 minutes**
  of continuous fetching, best case. Realistically **1.5-2.5 hours**
  accounting for retries, transient rate-limit backoff (the client already
  has exponential-backoff retry logic), and symbols needing more pages
  (none in this pilot needed more than 2, but a security with corporate
  action-driven extra rows or longer history could).
- **Storage**: 20 symbols' raw OHLCV = 1.4MB total (~70KB/symbol) →
  501 symbols ≈ **35MB** raw. Trivial; not a constraint.
- **Recommended execution shape** (not implemented): a resumable script
  (skip symbols already fetched, so a mid-run failure doesn't require
  restarting from scratch), run once outside normal pipeline hours, writing
  to a staging area first (mirroring this pilot's approach) — merge into
  `data/processed/` only after the same 4 checks pass at full scale, and
  after resolving the junction-anomaly question.

## Remaining risks (not resolved this round)

1. **Junction anomalies** (HPG +58%, TCB +124.8%) — root cause unknown;
   could recur for other symbols at full scale.
2. **Survivorship bias is untouched by this backfill** — it only deepens
   history for currently-listed names; delisted/suspended-since-2020
   companies remain permanently invisible with this data source. Directly
   relevant to any future event-detection or crash-risk work.
3. **Suspension/halt handling**: confirmed the existing `close>0` guard
   already handles the `close=0` halt pattern correctly, but this should be
   explicitly re-verified once the full 501-symbol backfill actually runs
   through `generate_features.py`, not just asserted from a 20-symbol
   sample.
4. **Rate-limit/provider stability over a ~2-hour unattended run** is
   untested at that duration — the pilot's 20-symbol, ~3.5-minute run
   completed with zero errors, which is reassuring but not conclusive for
   a run 25x longer.

## Next round (deferred, per instruction)

Decide: (a) resolve the HPG/TCB junction question first, (b) proceed to
full backfill and check for the same anomaly at scale, or (c) some
combination. Not decided or executed here.
