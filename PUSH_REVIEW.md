# PUSH_REVIEW — 50 local commits ahead of origin, for your review before pushing

Branch `claude/charming-bartik-d21dc1` is **50 commits ahead** of
`origin/claude/charming-bartik-d21dc1` (tip `e7e6728`), 0 behind — a
clean fast-forward push, nothing to reconcile. **Not pushed.** Grouped
oldest → newest below; each group's one-line summary states the overall
outcome, not just what was attempted. (Phases 0-4 below, 30 commits,
were the state as of this file's first version; Phases 5-9 were added
in later rounds, covering this file's own commits and the rounds that
followed it.)

---

## Phase 0 — pre-session audit & factor search (10 commits)

Work already on this branch before this session began.

| Hash | Message |
|---|---|
| `e5d2ee5` | docs: audit full pipeline re-run, surface critical data-staleness finding |
| `0611b80` | docs: confirm the weak-signal finding is not a G4-aggressiveness artifact |
| `3a2ee08` | docs: re-test 44 technical factors with Newey-West HAC, residualized target, liquidity subset |
| `0ca1384` | docs: reframe factor search from IC to tail-event detection (event/lift) |
| `cc697f2` | docs: data audit -- universe/coverage problem, not liquidity or units |
| `c01f473` | docs: add earlier quantile-spread and broad factor-IC scratch scripts |
| `936e513` | docs: design + pilot 20-symbol backfill; fix flawed statistical claim in audit |
| `685f269` | docs: root-cause HPG/TCB junction anomaly, finalize full-backfill design |
| `d12a6ac` | fix(data): use adjusted close in fetch_daily.py fallback, not raw closeprice |
| `2ebd2b0` | docs: add session handoff note to BACKFILL_DESIGN_REPORT.md |

**Summary**: found the data pipeline was stale/undersized (only ~6
symbols with full history) and 44 candidate technical factors showed no
reliable edge on that data; traced HPG/TCB's specific anomaly to a
raw-vs-adjusted-close bug in the fetch fallback path and fixed it,
setting up the full backfill this session executed.

## Phase 1 — backfill (this session, 5 commits)

| Hash | Message |
|---|---|
| `7f35c57` | test(data): verify Task-3 re-pilot against a bug-immune oracle |
| `ee248f2` | feat(data): full 501-symbol backfill to data/full_history_v2 |
| `d8ee06b` | test(data): quality suite for the full 501-symbol backfill |
| `1566f29` | docs: Round 3/4 write-up + DATA_BASELINE.md baseline documentation |
| `e9a815f` | feat(data): make full_history_v2 the official pipeline source |

**Summary**: re-fetched full 2020–2026 history for all 501 current
symbols via a fetch method proven immune to the raw/adjusted-close bug,
verified clean (0 unexplained coverage defects after investigation),
and made it the pipeline's official data source, quarantining the old
(partially corrupted) dataset rather than deleting it.

## Phase 2 — retest (this session, 5 commits)

| Hash | Message |
|---|---|
| `b182091` | test(alpha): lower eligibility threshold 10B->3B VND for factor re-tests |
| `4762d81` | docs: Round 5 write-up + first clean-data factor re-test report |
| `4aaf36e` | test(alpha): examine the volatility cluster before touching deployed scoring |
| `cff5f33` | fix(alpha): apply NV4 factor recommendations to deployed scoring |
| `6f452b2` | docs: before/after comparison for the scoring change + SCORING_UPDATE_REPORT.md |

**Summary**: re-ran the full 44-factor test on clean data for the first
time (21/192 combinations now significant, concentrated in a volatility
cluster); removed `return_20d` from deployed scoring for near-zero IC
and loosened the `distance_ma20` gate, confirmed via before/after
backtest that nothing broke.

## Phase 3 — forensic (this session, 6 commits)

| Hash | Message |
|---|---|
| `a67c792` | docs: fold autopsy for the walk-forward backtest's left tail |
| `bef0de6` | fix(backtest): remove silent benchmark fallback, raise a clear error instead |
| `7c791d7` | test(backtest): portfolio-construction sensitivity (size 5/10/20 + sector cap) |
| `88a97f7` | docs: concentration null test + CONCENTRATION_ANALYSIS_REPORT.md |
| `3b8c4a8` | fix(backtest): apply approved portfolio config -- size=10, sector cap=2 |
| `e61c65a` | docs: forensic 2026 fold + composite score tested directly for the first time |

**Summary**: traced the backtest's worst year (2026, −59.7% while
VNINDEX rose) to the deployed score itself, not bad luck or
concentration alone — a null test against 2,000 random portfolios found
the composite underperforms random stock-picking on average; fixed an
unrelated silently-wrong benchmark bug found along the way; applied a
diversification change (portfolio size 5→10, sector cap) that reduces
variance but doesn't fix the underlying signal problem.

## Phase 4 — v2 (this session, 4 commits)

| Hash | Message |
|---|---|
| `6cf15a0` | docs: pre-register SCORE_V2_DESIGN.md before any v2 comparison is run |
| `066014e` | test(alpha): confirmation run for SCORE_V2_DESIGN.md -- all 3 criteria pass |
| `deed572` | feat(alpha): install v2 as the deployed score, v1 kept as live shadow |
| `327b8d4` | fix(screening): stop feeding alpha_score into final_watchlist's momentum_score |

**Summary**: redesigned the deployed score around only the two factors
with independently validated evidence (realized_vol_20d + value_ma20,
70/30, weights fixed before any test was run); confirmed it clears all
3 pre-registered acceptance bars and beats the old composite decisively;
installed it as the live score with the old composite kept running in
shadow for ongoing comparison, and cleaned up a downstream file
(`final_watchlist.py`) that was still averaging the old (now
repurposed) score into a "momentum" calculation.

---

## Phase 5 — push prep + next-branch design survey (this session, 2 commits)

| Hash | Message |
|---|---|
| `87691e7` | docs: PUSH_REVIEW.md -- 30 local commits ahead of origin, grouped for review |
| `683f611` | docs: survey disclosure data sources + point-in-time pipeline design |

**Summary**: this review document itself; and a read-only survey (no
crawler built, no new service signed up for) of Vietnamese insider/
major-shareholder trading disclosure sources for a possible future
accumulation-detection feature, concluding CafeF.vn is the best
candidate found but its historical depth is unverified at the row
level, with a design for point-in-time-safe storage ready for review
before any of it gets built.

## Phase 6 — SSI verified exhaustively, closed (this session, 1 commit)

| Hash | Message |
|---|---|
| `5f16120` | docs: verify SSI has no disclosure data via official docs, close definitively |

**Summary**: before committing to CafeF, cross-checked SSI's official
FastConnect documentation (not just the installed SDK) and its other
product (FastConnect Trading) for any disclosure capability at all —
found none, three independent sources (SDK code, English docs,
Vietnamese docs) agree exactly. CafeF.vn stays the plan.

## Phase 7 — point-in-time fix, momentum-score removal, CafeF pilot (this session, 4 commits)

| Hash | Message |
|---|---|
| `5f2ced4` | fix(docs): correct point-in-time rule in disclosure pipeline design (look-ahead bug) |
| `517a3d0` | fix(screening): remove v1 alpha_momentum_score from final_watchlist momentum |
| `a2e5933` | docs: CafeF pilot Step 0 (robots.txt/ToS check) + pre-registered event list |
| `d3bc803` | docs: CafeF pilot Steps 2-3 results + vnstock license review (Round 3) |

**Summary**: fixed a real look-ahead bug in the disclosure design's
point-in-time rule (it took `min(disclosure_date, ingested_at)` and
called that "stricter" — backwards; now `max()` for live rows, a
conservative `+1 trading day` placeholder for backfilled rows, flagged
`is_backfilled`); removed the v1 shadow's `momentum_score` from
`final_watchlist.py`'s live scoring (`SCORE_FORENSIC_REPORT.md` found
it IC ~0 over 2023-2025 and -0.1050 in 2026, the worst component in that
fold) — full test suite passes, one pre-existing unrelated failure
confirmed via `git stash` to predate this change; and ran a manual,
read-only CafeF verification pilot (robots.txt allows crawling, no ToS
found restricting it) against 15 pre-registered real disclosure events
— 10/10 found for 2024-2026 with exact field matches plus real
execution-vs-registration and multi-tranche findings press didn't
carry, 1/5 confirmed for 2020-2021 (VHM, exact, with a bonus finding of
real depth back to Nov 2018) with the other 4 blocked by browser-
automation tooling limits reaching deep pagination, not by evidence of
missing data. CafeF confirmed sufficient as primary source for live
accumulation; historical depth for high-turnover names stays an open
question. vnstock's non-commercial license clause quoted for the
record, no legal conclusion drawn.

## Phase 8 — disclosure crawler v1 built + run, historical-depth question closed (this session, 5 commits)

| Hash | Message |
|---|---|
| `2e17be7` | feat(data): polite crawler v1 for CafeF disclosure history (raw tier) |
| `5b96c44` | feat(data): parse tier for disclosure_events schema (raw JSON -> records) |
| `b02d419` | feat(data): ingest pipeline applying ROUND 3 point-in-time schema |
| `7e2c2de` | fix(data): correct ICT timezone offset in disclosure date parsing |
| `b56eeed` | docs+data: Round 4 -- crawler run, historical-depth question closed |

**Summary**: built the disclosure crawler design approved in Round 3
into working code -- `src/data/disclosure_client.py` (polite HTTP:
single-threaded, >=2.5s floor between requests, backs off then gives up
on 429/403), `disclosure_crawler.py` (checkpoint/resume manifest, same
pattern as the price backfill), `disclosure_parser.py` (raw JSON ->
`disclosure_events` schema, pure function of the immutable raw tier),
`disclosure_ingest.py` (Round 3's point-in-time rule, natural-key
append-only, validation/rejection). During investigation, discovered
the manual pilot's page is backed by a public JSON AJAX endpoint that
returns a symbol's *entire* history in one response -- pivoted the
crawler to hit that directly instead of scraping rendered HTML (more
polite, same source, no new dependency; documented as a deliberate
deviation from the literal "store raw HTML" instruction, not a
shortcut).

Ran the real crawler against TCB/MWG/TCH/VHM/HPG (as instructed) plus
one extra symbol for a size estimate. Found and fixed a real timezone
bug (dates were one calendar day off) by cross-validating against the 5
historical events ROUND 3 couldn't reach -- after the fix, all 5 match
exactly, closing the historical-depth question: HPG genuinely reaches
back to 2008 (matching CafeF's own claim), others to 2013-2020
per-symbol, confirmed by real data rather than pagination-limited
inference. Full-universe crawl (501 symbols) NOT run -- estimated
~20-30 min / ~53MB, proposed for approval in Round 4/NV8.

## Phase 9 — full-universe disclosure crawl, descriptive baseline, live-update pipeline (this session, 4 commits)

| Hash | Message |
|---|---|
| `7933e91` | feat(data): incremental daily disclosure update (live point-in-time branch) |
| `bc56f50` | data(disclosure): full-universe crawl -- 500 symbols, 0 errors, 0 rate limits |
| `40e928e` | docs(disclosure): DISCLOSURE_BASELINE.md -- descriptive stats only, Round 5 |

(3 commits shown; a 4th, the PUSH_REVIEW.md update itself, follows this one.)

**Summary**: with the crawler nghiệm thu'd in Round 4, ran it against the
full 500-symbol universe (`data/full_history_v2/raw/*.parquet` minus
`GEE`) -- 0 fetch errors, 0 rate-limiting, ~24 minutes wall-clock,
matching the Round 4 estimate exactly. 56,870 valid events + 518 rejected
(0.90%, same rate as the pilot, all genuine source-data anomalies).
Historical depth turned out much better than the 5-symbol pilot
suggested: **157/500 symbols (31%) reach back to 2008**, not just HPG.

Built the incremental daily-update pipeline
(`scripts/update_disclosure_daily.py` + `ingest_new_events_live()`) --
the first code path where the *live* branch of the point-in-time rule
(`available_at = max(disclosure_date, ingested_at)`) actually runs,
anti-joining against existing events+errors so already-known rows are
never silently reflagged. Not yet scheduled/run for real (script exists
and is tested; installing a cron/launchd entry is a separate decision).

Wrote `DISCLOSURE_BASELINE.md` (descriptive stats only -- composition,
period distribution, role distribution, historical depth, execution/
registration ratio, field completeness, rejected-row breakdown).
**Deliberately contains zero price/return statistics anywhere** -- the
hard constraint for this round, protecting whatever signal-test design
comes next from being biased by an early look at event-to-return
patterns. One new full-universe-scale finding: 829 rows (1.4%) collide
on the natural key and get silently collapsed by dedup -- flagged as an
open caveat, not fixed (schema change, out of this round's "kiểm kê"
scope).

---

## Not included in these commits (pre-existing, untouched)

`git status` also shows modified/untracked files this session did not
create or touch: `data/signals/final_watchlist.csv`, `reports/daily_alpha_ranking.csv`,
`reports/top_watchlist.csv`, `reports/final_watchlist.xlsx`, and several
`research_notes/generated/*.md` files. These were already
modified/untracked before this session began (from an unrelated process)
and are left alone — not staged, not part of any commit above.

**Note**: running `scripts/run_alpha_scoring.py` in Phase 4 (to seed the
new shadow log) did regenerate `reports/daily_alpha_ranking.csv` and
`reports/top_watchlist.csv` with live v2 scores as a side effect of that
script's normal behavior — they're still sitting as uncommitted local
changes, not part of any commit, exactly like the rest of this group.
If you want that refreshed ranking data pushed too, it would need to be
staged separately; it wasn't bundled into any commit above to keep this
session's commits scoped to what was actually asked.
