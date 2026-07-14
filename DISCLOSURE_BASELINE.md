# DISCLOSURE_BASELINE — data/disclosure, the insider/major-shareholder disclosure dataset baseline

**Required citation**: any research note, factor design, or signal test built
from this point forward must cite `data/disclosure/events.parquet` (full
501-symbol-universe crawl minus `GEE`, completed 2026-07-12, code commit
range `2e17be7`..`7933e91`) as its disclosure data source. See
`DISCLOSURE_PIPELINE_DESIGN.md` (Rounds 3-5) for the full design and
verification history; this document is the operational/descriptive summary,
mirroring `DATA_BASELINE.md`'s role for the price dataset.

**This document is descriptive only.** Nothing below joins against price,
computes a return, or reports any statistic that mixes disclosure timing
with market outcomes. That boundary is deliberate — see
`DISCLOSURE_PIPELINE_DESIGN.md` Round 5/NV0 for why, and do not extend this
document with return-linked statistics; that belongs in a separately
pre-registered signal-test design, not appended here after the fact.

## Dataset identity

| | |
|---|---|
| Path | `data/disclosure/raw/{symbol}/page*.json` (immutable raw tier, 500 symbols) + `data/disclosure/events.parquet` + `data/disclosure/errors.parquet` + `data/disclosure/raw/manifest.json` |
| Fetch method | `GET cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDCoDong.ashx?Symbol={sym}&PageSize=2000` (blank date range = full history), one polite request per symbol at >=2.5s pacing |
| Fetch window | 2026-07-12 18:27 UTC → 2026-07-12 18:51 UTC (~24 min, 500 symbols) |
| Code commit range | `2e17be7` (client+crawler) .. `7933e91` (incremental ingest) |
| Symbols crawled | 500 of 501 (`GEE` excluded per `config/excluded_symbols.csv`, same exclusion as `DATA_BASELINE.md`) |
| Crawl errors | 0/500 (no rate-limiting encountered, no fetch failures) |
| Raw tier size | 29.3 MB |
| Parsed rows (pre-validation) | 57,800 |
| Valid events (post-validation, in `events.parquet`) | 57,282 (re-ingested 2026-07-14 with the widened `NATURAL_KEY` -- see caveat #1; was 56,870) |
| Rejected rows (in `errors.parquet`) | 518 (0.90%) |
| `events.parquet` size | 8.9 MB |
| `errors.parquet` size | 0.13 MB |
| Symbols with >=1 disclosure record (valid or rejected) | 497 of 500 |
| Symbols with zero disclosure records at all | 3 (very likely genuinely quiet/thin names, not investigated further) |

## Descriptive statistics (no price/return data anywhere below)

### Registration vs. result composition, match rate

Every raw CafeF record can carry a registration phase, a result phase, or
both; each phase becomes its own row (`insider_registration` /
`insider_result`), joined by `link_key` when both exist on the same record.

| | Count |
|---|---|
| `insider_registration` rows | 20,725 |
| `insider_result` rows | 20,702 |
| `major_shareholder_change` rows | 15,961 |
| Distinct insider `link_key`s | 21,787 |
| — matched (both registration **and** result present) | 19,065 (87.5%) |
| — registration only (no result recorded yet, or never executed) | 1,508 |
| — result only (no registration phase — e.g. some foreign-fund reports) | 1,214 |

### Distribution by period × event type

| Period | insider_registration | insider_result | major_shareholder_change |
|---|---|---|---|
| ≤2008 | 264 | 255 | 493 |
| 2009-2012 | 3,702 | 3,456 | 2,642 |
| 2013-2016 | 4,209 | 4,445 | 3,522 |
| 2017-2020 | 5,006 | 5,006 | 3,843 |
| 2021-2024 | 5,729 | 5,747 | 4,223 |
| 2025+ | 1,815 | 1,793 | 1,238 |

### Distribution by event type × direction

| event_type | buy | sell | (no direction) |
|---|---|---|---|
| `insider_registration` | 9,973 | 10,732 | 20 |
| `insider_result` | 9,213 | 9,253 | 2,236 |
| `major_shareholder_change` | 8,578 | 6,834 | 549 |

The ~2,236 direction-less `insider_result` rows and ~549 direction-less
`major_shareholder_change` rows are ownership changes with no matched
buy/sell volume field from the source (e.g. bonus-share/ESOP-driven
percentage shifts) — not a parser defect, the source itself doesn't
classify these as directional trades.

### Historical depth by symbol (earliest disclosure year, histogram)

| Earliest year bucket | # symbols |
|---|---|
| ≤2008 | 157 |
| 2009-2012 | 135 |
| 2013-2016 | 102 |
| 2017-2020 | 75 |
| 2021-2024 | 28 |
| 2025+ | 0 |

**157 of 500 symbols (31%) have disclosure history reaching all the way
back to 2008** — substantially deeper coverage than ROUND 4's 5-symbol
pilot sample suggested (which found only HPG reaching 2008 among 5 names).
This is real, not an artifact: every symbol was crawled the same way, with
the same one-request-returns-everything behavior confirmed in ROUND 4.

### Role distribution (person acting)

| Role category | Count | % |
|---|---|---|
| `insider` (stated board/management position) | 26,655 | 46.4% |
| `major_shareholder` (fund/holding co., no stated position) | 15,961 | 27.8% |
| `related_person` (related to an insider, e.g. spouse/sibling/child) | 14,772 | 25.7% |

### Execution / registration ratio (share-count ratio only — no price)

Computed only where a `link_key` has both a registration and a result row
with a known registered-share count; ratio = executed shares / registered
shares (capped at 2.0 for display; a handful of results exceed their stated
registration, likely multi-tranche executions against one registration).

| Percentile | Ratio |
|---|---|
| min | 0.00001 |
| 10% | 0.36 |
| 25% | 0.96 |
| 50% (median) | 1.00 |
| 75% | 1.00 |
| 90% | 1.00 |
| mean | 0.87 |

**Median execution matches registration exactly**; the left tail (10th
percentile at 0.36) is the economically-interesting part — a meaningful
minority of registrations are substantially under-executed. This is stated
purely as a share-count fact; no interpretation of *why* (price move,
change of mind, liquidity) is offered here, and none should be inferred
without the pre-registered signal-test design this round explicitly defers.

### Data quality: field completeness by year

`is_complete` = all of {symbol, event_type, person_name, direction,
disclosure_date} populated. Full year-by-year table generated by
`scratch/disclosure_baseline_stats.py`; summary:

| Era | Typical completeness |
|---|---|
| 2010-2012 (worst years) | 91.0%-92.8% |
| 2013-2020 | 94.5%-95.6% |
| 2021-2026 | 95.3%-97.4% |

**Older records are measurably dirtier**, as expected — confirms the
instruction's framing ("dữ liệu cũ thường bẩn hơn") with real numbers
rather than assumption. No year drops below 91%.

### Rejected-row breakdown (`errors.parquet`, 518 rows total)

| Reject reason | Count |
|---|---|
| `EXECUTION_BEFORE_REGISTRATION_START` | 402 |
| `INVERTED_REGISTRATION_WINDOW` | 91 |
| Both reasons on the same row | 25 |

All 518 are genuine source-data date inconsistencies (an execution date
1+ days before its own registration window's stated start, or a window
whose end predates its start) — the validation guardrail catching real
anomalies, not parser bugs; consistent with the 10/1,150 rate found in the
ROUND 4 five-symbol pilot, just at full-universe scale.

## Open caveats (do not treat as resolved)

1. **RESOLVED 2026-07-14 — natural-key collisions widened + re-ingested.**
   The schema's natural key was `(symbol, event_type, person_name,
   disclosure_date)`. 829 parsed rows (1.4% of the 57,800 parsed) shared a
   natural key with at least one other row — almost always a person who
   made two genuinely distinct disclosures (different registration window,
   different share count) published on the exact same calendar date.
   `append_parquet`'s dedup (`keep="last"`) kept only one of each colliding
   group. Confirmed the mechanism directly (see examples: Đào Văn Duy/AAA,
   Vương Ngọc Yến/ACE, both with two different real transactions same-day).
   Fix: `src/data/disclosure_ingest.py`'s `NATURAL_KEY` widened to add
   `direction` + `shares_registered_or_changed` (resolves 633/829, 76%, of
   the collisions) plus a `dedup_seq` row-order tiebreaker for the
   remaining 196 rows that still share symbol/event_type/person/date/
   direction/volume but differ only in registration window (e.g. the
   Vương Ngọc Yến/ACE case above) — **0 collisions remain** on the full
   widened key. Re-parsed from the immutable raw tier (no re-crawl) and
   fully re-ingested: `events.parquet` went from 56,870 to 57,282 rows
   (+412 net rows recovered; `errors.parquet` unaffected at 518, since
   none of the rescued rows were validation-rejected). Verified: parsed
   rows (57,800) = valid (57,282) + rejected (518) exactly, i.e. zero rows
   now lost to dedup collapse. Tests:
   `tests/test_disclosure_ingest.py::test_widened_key_keeps_two_distinct_same_day_disclosures`,
   `::test_dedup_seq_keeps_two_identical_looking_registrations_same_day`,
   `::test_reingest_of_identical_batch_still_dedupes_with_dedup_seq`.
2. **Panel is skewed toward large/long-listed symbols, same caveat as
   `DATA_BASELINE.md`'s survivorship-bias note, compounded here.** The 500
   symbols are "listed today"; disclosure history depth correlates with how
   long a company has been listed and how large/active its insider base
   is. Any later analysis must normalize by period × symbol-group (e.g.
   market-cap bucket, listing-age bucket) rather than pooling raw counts —
   pooling naively will make older/larger names dominate every statistic.
3. **Two rows have a sentinel `1900-01-01` disclosure date** (EVE/AFC VF
   Limited, PGD/Đinh Ngọc Huy) — the source's own `PublishedDate` and
   `PlanBeginDate` fields were apparently both null/placeholder for these
   two records specifically. Negligible in volume (2/57,388) but flagged
   for completeness; not fixed this round.
4. **3 of 500 symbols have zero disclosure records** (valid or rejected) —
   plausibly genuinely quiet/thin names with no insider or major-shareholder
   activity ever disclosed, not investigated further.
5. **Role classification (insider / major_shareholder / related_person) is
   the same v1 heuristic flagged in ROUND 4/NV6** — decided by presence of a
   stated board/management position string, not audited against a large
   diverse sample beyond the original 6-symbol pilot.
6. **No entity resolution beyond NFC-normalize + trim.** The same person
   can appear with spelling/spacing variants across records; "same person
   over time" queries need fuzzy matching not built here, per the original
   design's explicitly-deferred scope.
7. **This dataset has not been joined against price/return data, and this
   document deliberately contains no statistic that would require such a
   join.** Any signal-test design must be pre-registered (per
   `DISCLOSURE_PIPELINE_DESIGN.md` Round 5's hard constraint) before this
   dataset is looked at alongside price data for the first time.
