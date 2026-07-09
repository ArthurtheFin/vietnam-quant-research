# BACKFILL_DESIGN_REPORT — design + 20-symbol pilot for full 2020 backfill

Follow-up to `DATA_AUDIT_REPORT.md`. Decision already made: backfill full
history to 2020 (or earlier if the source allows). Round 1 (below, original
content): design + pilot on 20 symbols. Round 2 (this update, top section):
root-caused the HPG/TCB junction anomaly and finalized the full-backfill
plan. **Still no full backfill run. No existing data overwritten** — all
pilot output lives entirely under `data/pilot_backfill/raw/`.

---

## ROUND 2 — junction anomaly diagnosis (confirmed) + finalized full-backfill design

### Task 1 — "constant ratio" signature test: CONFIRMED scenario (b)

Computed `ratio = close_pilot / close_existing` per day over the pilot/
existing overlap.

**Control symbols** (VPB, SSI, STB — no known adjustment issue): ratio
**= 1.0000 exactly, every single day**, 328-1,622 overlapping rows each. No
noise, no drift. This is the clean baseline — confirms the pilot fetch
methodology itself introduces zero error where the existing data is already
correct.

**HPG and TCB: ratio is piecewise-constant, not noisy and not a single
one-time shift** — this is squarely scenario (b), not (c):
- HPG: only **5 distinct ratio values** across 871 overlapping days
  (0.6763, 1.0, 0.7439, 0.8927, 0.8928), stepping between them roughly
  every ~29 calendar days.
- TCB: only **4 distinct ratio values** (0.4724, 1.0, 0.4871, 0.9742), same
  ~29-day stepping cadence.

This node ruled out scenario (c) (pure noise) immediately — a genuinely
noisy/wrong series would not collapse to 4-5 exact repeating constants. But
it also **doesn't match a single real corporate-action date** as originally
guessed — the step dates alternate roughly monthly for **three years
straight** (2023-01-31, 03-02, 04-03, 05-04, 05-31, 06-30, ... every ~29
days through mid-2026), which no real dividend/split calendar does. That
ruled out "one specific event" and pointed at something systematic in how
the data was ingested, not a market event — investigated directly below.

### Task 2 — SSI FCData adjustment behavior: root cause found precisely

Read `src/data/ssi_client.py` and live-compared two endpoints for the same
HPG dates (2023-01-03 to 2023-01-10):

- **`get_daily_ohlc`**: its `close` field **is already back-adjusted** for
  all corporate actions (13,019 / 13,120 / 13,391 / ... for those dates) —
  this is what the pilot backfill uses exclusively, and it's why the pilot
  and control symbols agree perfectly with existing data wherever the
  existing data is correct.
- **`get_daily_stock_price`**: returns **both** `closeprice` (raw,
  unadjusted — 19,250 / 19,400 / 19,800 / ...) **and** `closepriceadjusted`
  (13,018.68 / 13,120.12 / 13,390.64 / ... — matches `get_daily_ohlc`
  almost exactly).

**The bug**: `src/data/fetch_daily.py::_fetch_chunk_with_fallback` (lines
256-317) tries `get_daily_ohlc` first, but falls back to
`get_daily_stock_price` whenever that chunk's `volume`/`value`/`high`/`low`
coverage is below 80% (`needs_fallback`, lines 287-291) — a reasonable
data-completeness safeguard on its own. The bug is in
`_normalize_daily_ohlc_response`'s shared `rename_map` (line 138):
`"closeprice": "close"` maps the **raw** field to `close` — `closepriceadjusted`
isn't in the rename map at all and is silently dropped. So any chunk where
the fallback triggers gets an **unadjusted** close silently substituted in
place of the adjusted one everywhere else, and `fetch_symbol_history`'s
default `chunk_days=29` lines up exactly with the ~29-day stepping cadence
observed in Task 1.

I could not re-trigger the fallback live for the exact historical chunks
today (`get_daily_ohlc` currently returns 100% volume/high/low coverage for
Jan 2023 HPG, so the bug doesn't reproduce on a fresh call for that window)
— SSI's backend completeness for a given historical window may have
improved since the original ingestion ran, or an older code path/threshold
was in effect at the time. **The mechanism is proven by the two-field
match** (raw vs. adjusted values line up exactly with the two observed
ratio levels); the exact historical trigger moment can't be replayed, but
doesn't need to be to fix this going forward.

This also reconciles with your original hypothesis, not against it: HPG's
and TCB's real adjustment factors (0.68-0.89 for HPG, 0.47-0.97 for TCB,
consistent with TCB's known 1:1 bonus issue) **are genuine**, reflecting
real historical corporate actions — that part of your hypothesis was right.
What's *inconsistent* is that the existing data applies that real
adjustment on some ~29-day chunks and not others, because of which endpoint
happened to answer for each chunk.

**Consequence beyond this pilot**: `update_symbol_history` (the function
used for ongoing daily updates, not just this backfill) calls the same
`_fetch_chunk_with_fallback`. **This bug will keep corrupting future
incremental updates**, for HPG/TCB and potentially any other symbol whose
historical `get_daily_ohlc` coverage dips below 80% for some chunk — a
backfill alone does not prevent recurrence.

### Task 3 — finalized full-backfill design

**Principle confirmed: no splicing.** Refetch the entire 2020 → present
history for all 501 symbols in one pass, `get_daily_ohlc` only (adjusted,
consistent basis — exactly what the pilot already used and what the clean
control symbols validated), written to a **new** dataset
(`data/full_history_v2/raw/`), old data left untouched for side-by-side
comparison.

**Recommended companion fix (not applied this round, flagging for a
decision)**: before or alongside the backfill, `_fetch_chunk_with_fallback`'s
fallback path should map `closepriceadjusted` → `close` (not `closeprice`),
or the fallback should be disabled for the `close` field specifically (still
allowed to fill in `volume`/`value`/`high`/`low` gaps from the raw endpoint,
just not `close`). Without this, a freshly-backfilled `data/full_history_v2/`
would start drifting the same way the first time a normal incremental
update hits a low-coverage chunk.

**Plan**:

1. **Fetch order**: process symbols by descending current liquidity tier
   (mirrors the pilot's tiering) so the most-used names for any current
   research land first and partial-progress runs are maximally useful even
   if interrupted early. Within a symbol, single `get_daily_ohlc` call for
   the full 2020-01-01 → today range (page_size=1000; the pilot showed this
   auto-paginates to 2 pages per symbol without issue for 6.5 years).
2. **Rate limit / retry**: reuse `SSIDataClient`'s existing throttle
   (>=1.0s/call) and retry-with-backoff (3 attempts) unchanged — both
   already proven in the pilot (zero errors across 20 symbols, 207s).
3. **Checkpointing / resume**: write one parquet file per symbol to
   `data/full_history_v2/raw/{symbol}.parquet` as each completes (matching
   the pilot's approach) and maintain a `data/full_history_v2/manifest.json`
   recording `{symbol: status, row_count, fetched_at}` after each write. A
   restarted run skips any symbol already `status: ok` in the manifest —
   safe to interrupt and resume at any point, no partial-symbol corruption
   risk since each symbol's file is only written after its fetch completes.
4. **Automated post-fetch quality suite** (extends the pilot's 4 checks to
   all 501 symbols automatically, no manual review needed to start):
   - (a) % sessions vs. the VNINDEX trading calendar, per symbol per year.
   - (b) **junction check generalized**: for every symbol, compare
     `data/full_history_v2` against the existing `data/processed/stock_features.parquet`
     over their full overlap (not just a single junction date) — compute
     `ratio = close_v2 / close_existing` for every overlapping day and count
     **distinct rounded ratio values**. `1` distinct value at `1.0` = clean;
     `>1` distinct value = flag for manual review (this is precisely the
     test that caught HPG/TCB in the pilot, now automated and run
     unconditionally over all 501 symbols instead of by hand).
   - (c) magnitude sanity: flag any symbol whose average traded value in
     any full year is <10x or >1000x its own all-time median (catches
     gross unit/scale errors without needing a hand-picked reference list).
   - (d) outlier scan: count `|return_1d| > 20%` days with `close > 0` on
     both sides (excluding the halt/`close=0` artifact identified in the
     pilot) per symbol; no hard fail threshold, just surfaced in the output
     table for review (large real corporate actions are expected and will
     be caught downstream by the existing G4 mechanism).
5. **Output**: a single table, one row per symbol, columns
   `[symbol, rows, date_range, check_a_pass, check_b_distinct_ratios, check_c_pass, check_d_outlier_count]`,
   sorted to put failures first.

**Acceptance criterion for `data/full_history_v2` to replace the current
dataset**: **>=95% of symbols pass checks (a) and (b) cleanly** (single
ratio value at (b), >=95% session coverage for years the symbol was
actually listed at (a)); symbols failing either are listed individually
with the specific reason, not silently included or silently dropped. (c)
and (d) are informational/review-only, not hard gates, since large real
corporate actions and genuine outliers are expected and already handled
downstream. **This criterion, the companion code fix, and the actual
full-backfill run are all still pending your decision — nothing beyond
this design has been executed.**

---

## ROUND 1 (original) — data source inventory, pilot backfill, initial findings

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

## Next round (deferred, per instruction) — superseded by Round 2 above

Round 2 (top of this document) resolved the HPG/TCB junction question: root
cause identified precisely (raw-vs-adjusted field mixing in
`src/data/fetch_daily.py`'s fallback path), and the full-backfill design is
finalized there. **Still not decided or executed**: whether to apply the
companion code fix, and whether/when to run the actual full backfill.
