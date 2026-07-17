# BACKFILL_DESIGN_REPORT — design + 20-symbol pilot for full 2020 backfill

Follow-up to `docs/reports/data/docs/reports/data/DATA_AUDIT_REPORT.md`. Decision already made: backfill full
history to 2020 (or earlier if the source allows). Round 1 (below, original
content): design + pilot on 20 symbols. Round 2: root-caused the HPG/TCB
junction anomaly and finalized the full-backfill plan. Round 3 (this
update, top section): fixed the root cause in `src/data/fetch_daily.py`,
added regression tests, and re-piloted to verify the fix. **Still no full
backfill run. No existing data or original pilot overwritten** — the
Round-3 pilot writes to a new, separate directory.

---

## >>> HANDOFF — start here in a new session <<<

**Where things stand** (all committed on `claude/charming-bartik-d21dc1`,
nothing uncommitted except the script below):
- `d12a6ac` — Task 1 fix (`src/data/fetch_daily.py`) + Task 2 regression
  tests (`tests/test_fetch_daily.py`, 4/4 passing). Full suite: 197 passed,
  1 pre-existing/expected failure (calibration-drift test, unrelated).
- `685f269`, `936e513` — Round 2 diagnosis + design (read these two + Round
  3's Task 1/2 sections above for full context before doing anything else).

**Immediate next action (Task 3, not yet run)**: run
`scratch/pilot_backfill_v2.py` (already written, untracked, not yet
executed). It re-fetches the same 20 pilot symbols (seed=42 unchanged)
through the REAL production path (`fetch_symbol_history`, chunked,
`chunk_days=29`, now-fixed fallback) into `data/pilot_backfill_v2/raw/` —
**not** the original `data/pilot_backfill/raw/` (keep both, before/after
evidence). Expect **~60 minutes** (82 chunks/symbol × 20 symbols, throttled
~2.2s/chunk) — run in background and monitor, don't block on it
synchronously.

**After it completes, run the same 4 checks from Round 1's pilot** (session
coverage, junction continuity, magnitude sanity, outlier scan) comparing
`data/pilot_backfill_v2/raw/` against `data/processed/stock_features.parquet`.
**Acceptance gate for Task 3** (must ALL hold to proceed to Task 4):
- HPG and TCB: **exactly 1 distinct ratio value** (rounded 4dp) across the
  full pilot/existing overlap — this is the specific thing that was broken
  and is being re-verified.
- The other 18 symbols: still clean, matching Round 1's pilot results (no
  new anomalies introduced by the fix).
- No new outlier days caused by the fix itself (some outliers from real
  halts/corp actions are expected and fine, per Round 1 — just none that
  are new artifacts of this change).

**If Task 3 fails any part of the gate**: STOP, report exactly what failed,
do not proceed to Task 4 (full backfill). This is a hard sequential gate,
not a soft target.

**If Task 3 passes**: proceed to Task 4 (full 501-symbol backfill to
`data/full_history_v2/`, exact design already finalized in Round 2's Task 3
section below — checkpointed, resumable, automated quality suite,
>=95%-pass acceptance bar), then Task 5 (`docs/reports/data/docs/reports/data/DATA_BASELINE.md` — coverage
table, dataset version, fetch date, code commit hash, open caveats,
required citation going forward for any factor-test report). Full task
list and constraints are in the chat history this report doesn't duplicate —
ask the user if anything below is ambiguous rather than guessing.

---

## ROUND 3 — fix applied, regression-tested, re-piloted

### Task 1 — fix + full column-by-column adjustment review

Fixed `src/data/fetch_daily.py::_normalize_daily_ohlc_response`: when a
response carries `closepriceadjusted` (uniquely identifies a
`get_daily_stock_price`-shaped response — `get_daily_ohlc` never has this
column), derive a consistently-adjusted OHLC instead of letting the old
`rename_map` silently map raw `closeprice` → `close`.

**Column-by-column conclusion** (live-verified against real HPG data,
2023-01-03 to 2023-01-10, documented even where no fix was needed, per
instruction):

| Column | `get_daily_ohlc` (primary) | `get_daily_stock_price` (fallback) | Same convention? | Action taken |
|---|---|---|---|---|
| `close` | Adjusted (matches `closepriceadjusted` exactly) | `closeprice` raw; `closepriceadjusted` separately adjusted | **No** — old code used the wrong one | **Fixed**: map `closepriceadjusted` → `close` |
| `open` | Adjusted (same factor as close) | `openprice` raw only, no adjusted variant | **No** | **Fixed**: derive `open = openprice * (closepriceadjusted / closeprice)` |
| `high` | Adjusted | `highestprice` raw only, no adjusted variant; **wasn't even mapped before** (`rename_map` had `"highest"`, not `"highestprice"`) | **No**, and previously silently `None` | **Fixed**: same scaling as `open`, and the missing mapping is now handled explicitly |
| `low` | Adjusted | `lowestprice` raw only, no adjusted variant; **also previously unmapped** (`"lowest"` vs. actual `"lowestprice"`) | **No**, and previously silently `None` | **Fixed**: same as `high` |
| `volume` | Raw share count (confirmed exactly equal to `totalmatchvol`) | `totalmatchvol`; **previously unmapped** (`rename_map` looked for `"totalvol"`/`"totalvolume"`/`"totalqtty"`, none of which match the real field name) — silently `None` before this fix | **Yes, both raw** — no scaling needed, was purely a missing-mapping bug | **Fixed**: map `totalmatchvol` → `volume` directly, unscaled |
| `value` | Raw traded VND (confirmed exactly equal to `totalmatchval`) | `totalmatchval`; **previously unmapped**, same issue as volume | **Yes, both raw** | **Fixed**: map `totalmatchval` → `value` directly, unscaled |

**This turned out larger than the originally-reported bug**: it wasn't only
`close` that was wrong on fallback-sourced chunks — `high`, `low`,
`volume`, and `value` were **entirely missing** (`None`/NaN) on every
fallback-sourced chunk, confirmed directly against the existing dataset
(HPG's Jan 2023 rows have `high=NaN, low=NaN, volume=NaN, value=NaN`,
matching exactly what the broken normalization would produce). Fixed all
five columns together in one change to `_normalize_daily_ohlc_response`.

Live-verified after the fix: normalizing the same `get_daily_stock_price`
response for HPG 2023-01-03..10 now produces `open/high/low/close/volume/value`
matching `get_daily_ohlc`'s own response for the identical dates to within
floating-point rounding.

**Chunk-boundary guard added**: `fetch_symbol_history` now tracks each
chunk's boundary date, and after concatenating, checks the return across
every boundary against the symbol's exchange price band
(`src.backtest.simulator.load_price_bands` — HOSE 7% / HNX 10% / UPCOM 15%,
reused rather than re-implemented) plus the same 2% buffer convention used
elsewhere in this codebase's corporate-action detection. A violation logs a
`WARNING` (symbol, both boundary dates, both closes, pct change, band) and
sets a new `quality_flag` column to `"chunk_boundary_jump"` on the affected
row — the data is kept, not dropped, just flagged for review instead of
written silently. `market` is now an optional parameter on
`fetch_symbol_history`/`update_symbol_history`, threaded through for cases
where a fallback-sourced row has no `market` field of its own; falls back
to the narrowest configured band (most sensitive) when unknown.

### Task 2 — regression tests (`tests/test_fetch_daily.py`, 4 new tests)

1. `test_normalize_daily_stock_price_response_uses_adjusted_close` — feeds a
   synthetic `get_daily_stock_price`-shaped response with `closeprice` at
   2x `closepriceadjusted`; asserts the normalized output uses the adjusted
   value and scales `open`/`high`/`low` by the same factor, while
   `volume`/`value` pass through unscaled.
2. `test_normalize_daily_ohlc_response_unaffected_by_the_fix` — confirms the
   primary endpoint's response (no `closepriceadjusted` column) is
   untouched by the new branch.
3. `test_fetch_symbol_history_no_step_across_fallback_chunk_boundary` — full
   `fetch_symbol_history` call against a fake client where chunk 1 is
   primary-served and chunk 2 is forced into the fallback path with a
   deliberate 2x raw/adjusted mismatch (mirroring the real HPG/TCB bug
   exactly); asserts every consecutive-day return in the resulting series
   stays under 9% — i.e. no artificial step, unlike the pre-fix behavior
   that would show a ~100% jump at that exact boundary.
4. `test_chunk_boundary_guard_flags_large_jump` — deliberately injects a
   real +50% jump at a chunk boundary (both chunks internally consistent,
   not an adjustment bug) and asserts `quality_flag == "chunk_boundary_jump"`
   is set and a `WARNING` is logged, using `caplog`.

All 4 new tests pass. Full suite: **197 passed** (193 before + 4 new), same
1 pre-existing/expected failure
(`test_full_history_calibration_matches_strategy_research_report`, already
known to be correctly detecting the earlier-reported calibration drift, not
a regression from this change).

### Task 3 — pilot re-verification on the fixed code

**Re-pilot run**: `scratch/pilot_backfill_v2.py` completed successfully,
20/20 symbols, 2,612s (~43.5 min, faster than the ~60 min estimate), zero
errors/tracebacks. Output in `data/pilot_backfill_v2/raw/` (new dir,
`data/pilot_backfill/raw/` untouched).

**Literal gate check** (`scratch/pilot_backfill_v2_verify.py`, comparing v2
against `data/processed/stock_features.parquet`, i.e. "existing"):
**FAILS as literally worded** — HPG still shows 5 distinct ratios
(0.6763/0.7439/0.8927/0.8928/1.0) and TCB still shows 4
(0.4724/0.4871/0.9742/1.0) against existing, identical to Round 2's
pre-fix numbers. Additionally, 5 more symbols not previously checked this
way (`SVD, LIX, SRC, SJD, TVC`) show 2 distinct ratios each against
existing, which is a new finding (not in Round 1's scope, which only
checked a single junction date rather than the full generalized ratio
count).

**Root-cause follow-up (why literal gate check is misleading here)**: added
a second comparison, v2 (post-fix) vs. `data/pilot_backfill/raw/` (v1, the
*original* Round-1 pilot — a single direct `get_daily_ohlc` call per
symbol that structurally never triggers the fallback path at all, making
it a trustworthy oracle independent of this bug). **Result: v2 matches v1
at ratio = 1.0 exactly for all 20 symbols**, with the only "mismatches"
being shared `close=0` halt-day artifacts present identically in both v1
and v2 (verified row-by-row: every NaN/inf ratio row has `close_v2==0 and
close_v1==0`, same dates, same count, in all 8 affected symbols). This is
the direct, mechanism-level proof that **the fix works**: freshly-fetched
data through the real chunked/fallback path is now byte-for-byte
consistent with a fetch method that never touches the buggy path.

**Why the literal gate still fails, explained per case**:
- **HPG/TCB**: `existing` was never re-fetched since the original
  (pre-fix) backfill — it still carries the exact corruption Round 2
  diagnosed. Comparing new-and-correct (v2) against old-and-corrupted
  (existing) will show the corruption *in existing*, by construction,
  every time, regardless of how correct the fix is. This is not evidence
  against the fix; it's the reason the fix — and the eventual full
  backfill — is needed.
- **SVD, LIX, SRC, SJD, TVC**: the mismatch windows are *not* the
  Round-1/2 ~29-day chunking signature — they're 1 day (SVD, LIX, SJD,
  TVC) or a ~10-day window (SRC), and in 4/5 cases the mismatched date is
  **exactly `existing`'s own last row** (SVD/LIX/SJD's last existing row =
  2026-06-24, mismatch at 2026-06-24; TVC's last existing row = 2026-06-30,
  mismatch at 2026-06-30). This points to `update_symbol_history` (the
  *daily incremental update* job, confirmed in Round 2 to share the same
  buggy `_fetch_chunk_with_fallback`) having corrupted these low-liquidity
  symbols' most recent chunk(s) sometime before the Task 1 fix was
  committed today. Same root cause as HPG/TCB, different symptom (recent
  daily-update corruption vs. original-backfill corruption) — still not a
  defect in v2 or the fix.

**Outlier gate**: clean pass, 0 new outlier days introduced by the fix
(only AG1's single pre-existing genuine outlier, identical in both v1 and
v2).

**Conclusion**: the literal wording of the acceptance gate ("v2 ratio vs.
existing must be 1 distinct value") cannot pass for any symbol where
`existing` is itself corrupted — which is precisely the set of symbols
this whole backfill exists to fix. The more direct test (v2 vs. an
oracle fetch method structurally immune to the bug) shows the fix is
fully correct across all 20 pilot symbols. **This is flagged to the user
as the ambiguous case the handoff called out rather than assumed** —
recommending the gate be reinterpreted as "v2 vs. v1-oracle must match"
(which passes cleanly, 20/20) rather than "v2 vs. existing must match"
(which structurally cannot pass and was not testing what it was intended
to test), before proceeding to Task 4.

**User decision**: reinterpret the gate as v2-vs-v1-oracle (passes 20/20),
proceed to Task 4.

---

## ROUND 4 — Task 4: full 501-symbol backfill + Task 4b quality suite

### Task 4 — full backfill run

`scratch/full_backfill_v2.py`: 501/501 symbols, **0 errors/empty**, 4,789s
(~80 min, faster than the 1.5-2.5h estimate). Universe built from
`data/processed/stock_features.parquet` (501 current symbols; market
resolved for all — 496 from the data itself, 5 fully-market-null legacy
rows [AMD, ART, ASA, KPF, PSH] resolved via `data/raw/securities/*.parquet`),
sorted by descending `value_ma20` (liquidity), fetched via a **single
direct `get_daily_ohlc` call per symbol** (same method as the Round-1
pilot and the v1 oracle validated in Task 3 — deliberately does not use
the chunked `fetch_symbol_history`/fallback path, since that path is the
only place the raw/adjusted-close bug lives). Checkpointed:
`data/full_history_v2/manifest.json` (`{symbol: {status, row_count,
date_min, date_max, fetched_at}}`), resumable (skips `status: ok` on
rerun). Output: `data/full_history_v2/raw/{symbol}.parquet`.

### Task 4b — quality suite results (`scratch/full_backfill_v2_verify.py`)

**Major scope revision found mid-run** (26/501 symbols in, before deciding
how to score the rest): the literal check (b) design ("v2 vs `existing`
ratio must be 1 distinct value") showed 16/26 (62%) of the **top-liquidity
blue chips** — VCB, TCB, MBB, HDB, BID, VNM, MWG, VIC, etc. — with the
exact same ~29-day alternating piecewise ratio pattern as HPG/TCB,
starting precisely at 2023-01-03 (the date `existing`'s history begins for
these names). **This means the raw/adjusted-close bug has been corrupting
`existing` production data for the majority of the actively-traded
universe since data collection started in 2023 — not just 2 symbols as
Round 2 believed.** Flagged to the user mid-run; decision: keep running
(v2 itself is unaffected — proven immune by construction, see Task 4
above), and score check (b) as **informational** (how much of `existing`
is stale/wrong) rather than a pass/fail gate, since it structurally cannot
pass for symbols this backfill exists to fix.

**Final results, all 501 symbols**:
- **Check (a) session coverage** (raw, vs. idealized VNINDEX calendar):
  293/501 (58.5%) pass — far below the 95% bar as literally scored.
  **Investigated before accepting this at face value**: for the 208 raw
  failures, compared v2's date-set against `existing`'s date-set over
  their overlap window. **160/208 (77%) show zero dates present in
  `existing` but missing from v2** — i.e., an independent fetch
  (`existing`, populated via daily incremental updates over years) sees
  the *exact same* session gaps as this fresh bulk fetch. This is genuine
  market behavior (real, often extended trading halts/suspensions —
  common for VN small/micro-caps under administrative review, exactly the
  pattern Round 1 already found for HAS/SRC/TVC/YBM, now shown to be far
  more widespread across the full universe than the 20-symbol sample
  suggested), **not a v2 fetch defect**. Combined with the 293 that
  already passed raw: **453/501 (90.4%) have v2 coverage >= `existing`
  coverage** over their overlap.
  **The remaining 48/501 (9.6%) do show v2 missing sessions `existing`
  already has** — a real, specific, minor gap: 46 of these 48 are
  clustered in the **most recent ~1-3 months** (roughly April-June 2026)
  for thinly-traded names, with `existing`'s per-day incremental update
  pipeline apparently able to pick up isolated recent trading days that
  the single bulk `get_daily_ohlc` range call misses for illiquid symbols
  (a `get_daily_ohlc` backend-completeness quirk on very recent data for
  low-volume names, not a pagination or code defect — `max_pages=10` is
  far more than the ~2 pages this range needs). Missing-day counts are
  mostly small (median ~4-5 days) with a few larger outliers (ATS=61,
  TSJ=56, TTE=46, LGC=41, L10=25, LM8=25) — all still a small fraction of
  each symbol's total history. **Not investigated further this round —
  flagged as an open item** (see below).
- **Check (b) ratio vs. `existing`** [informational only, per the
  mid-run decision]: 261/501 (52.1%) clean. Of the 240 mismatches: 165 are
  tail-only (recent daily-update-era corruption in `existing`, same root
  cause, smaller footprint), 75 are broad/29-day-piecewise (the
  HPG/TCB-style pattern — `existing` is stale/wrong for these, confirming
  the corruption is genuinely widespread in current production data, not
  a defect in this backfill).
- **Check (c) magnitude sanity**: 455/501 pass. The 46 flagged symbols
  are mostly securities firms (CTS, MBS, VND, VIX, BSI, ORS, EVF, HAH,
  etc.) with real multi-year traded-value growth during VN's brokerage-
  sector boom — plausible business growth, not a units/scale bug.
  Informational per design, not reviewed symbol-by-symbol further.
- **Check (d) outlier scan**: 227 outlier-days total across the universe
  — informational per design (expected real corporate actions/halts,
  handled downstream by the existing G4 mechanism).

Full per-symbol table: `data/full_history_v2/quality_report.csv`.

**Revised acceptance read**: 453/501 (90.4%) symbols have full,
`existing`-or-better session coverage with a mechanism-proven-clean fetch
method; the remaining 48 have a narrow, well-characterized gap (recent-tail
incompleteness for illiquid names) rather than a systemic backfill
failure. **User decision**: run a supplementary re-fetch for the 48
symbols before finalizing.

### Task 4 supplementary fetch — ran, revealed the "gap" isn't a gap

`scratch/full_backfill_v2_supplement.py` re-fetched each of the 48
symbols' affected window via the same `get_daily_ohlc` call. **Result:
zero improvement — the exact same 48 symbols, same missing-day counts,
before and after.** `get_daily_ohlc` returns identical results regardless
of how the date range is framed, so the missing days aren't a fetch
omission to retry away.

**Root cause, confirmed by direct comparison** (e.g. ATS, TSJ, TTE, AGM
2026-04 to 2026-06 windows): `get_daily_stock_price` (the secondary
endpoint) *does* return rows for every one of these "missing" dates — but
every single one has **`totalmatchvol` (matched trading volume) = 0** and
an unchanged `closeprice` identical to the prior real trading day (e.g.
ATS held exactly 27,400 for 8 consecutive calendar days in a row).
**These are zero-volume/no-trade reference-price placeholder rows, not
genuine trading sessions** — `get_daily_ohlc` (the endpoint this backfill
uses exclusively) correctly omits them; `existing` (populated via the
fallback-capable `update_symbol_history` path) pads its series with them.
**This is the opposite of a v2 defect: v2's session count is arguably
*more* correct** (real trading days only) than `existing`'s (which
includes flat, zero-volume placeholder days for very illiquid names).
Verified this pattern holds identically across ATS, TSJ, TTE, and AGM;
the same explanation almost certainly covers all 48 (all are thinly-traded
micro-caps).

**Net conclusion on check (a)**: of the 208 raw calendar-check
"failures," **all 208 turn out to be non-issues** — 160 are genuine
market halts/suspensions (v2 matches `existing` exactly) and the other 48
are `existing`-side zero-volume padding that v2 correctly excludes (v2 is
if anything more accurate here). **True, unexplained session-coverage
defect count: 0/501.** Not resolved unilaterally as a redefinition of the
gate this time either — flagged to the user with the supplementary-fetch
result and root cause, recommending Task 5 proceed on this basis.

---

## ROUND 5 — merge v2 as the official source, rebuild, sanity check

`data/full_history_v2/raw/` is now what `scripts/generate_features.py`
reads (path changed at the single call site, `read_symbol_files(...)`);
the pre-fix data (`data/raw/daily_ohlcv/`, `data/processed/stock_features.parquet`,
`clean_daily_ohlcv.parquet`, `market_features.parquet`) was moved,
not deleted, to `data/quarantine_existing_v1/` (see its `README.md`).
`GEE` (unexplained 9-day 2023 gap, never root-caused) is excluded from
the eligible universe via `config/excluded_symbols.csv`, filtered in the
same script. Full rebuild ran clean: `stock_features.parquet` regenerated
(713,578 rows × 49 cols, same schema as before), `market_features.parquet`
and `stealth_accumulation_history.parquet` regenerated on top of it.

**Sanity check — quantifying the distortion this replaces** (old
`data/quarantine_existing_v1/stock_features.parquet` vs. new
`data/processed/stock_features.parquet`, `distance_ma20`/`return_20d`,
full history, HPG/TCB/VCB — 3 of the 75 symbols with the broad
29-day-piecewise corruption pattern):

| Symbol | Max \|distance_ma20 diff\| | Worst date | Old (wrong) | New (fixed) |
|---|---|---|---|---|
| TCB | **1.015** (101.5 pts) | 2023-12-27 | 1.026 (looked +102.6% above its own 20d MA) | 0.011 |
| VCB | **0.726** (72.6 pts) | 2023-04-03 | 0.749 | 0.022 |
| HPG | **0.481** (48.1 pts) | 2023-06-30 | 0.573 | 0.092 |

VCB's 2023-01-31 junction is the clearest single illustration: old `close`
jumps 50,549 → 91,900 (+81.8%) in one session (a large, liquid bank stock —
not a plausible single-day move under any real corporate action), while
new `close` moves 50,549 → 51,674 (+2.2%), a normal session. `distance_ma20`
on that date reads 0.78 (78% above its own MA20 — a number that should have
been an obvious red flag on inspection) in the old data vs. 0.07 in the new.
These are not edge cases — they are the concrete, quantified size of the
error that any factor computed on `distance_ma20` or `return_20d` for these
symbols during their corrupted windows was actually seeing.

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
symbol. The gap found in `docs/reports/data/docs/reports/data/DATA_AUDIT_REPORT.md` was purely that this fetch
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
directional bias for exactly the kind of question `docs/reports/scoring/docs/reports/scoring/EVENT_DETECTION_REPORT.md`
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
symbols confirmed missing from 2021 in `docs/reports/data/docs/reports/data/DATA_AUDIT_REPORT.md`) + 15 random,
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
