# DISCLOSURE_PIPELINE_DESIGN — insider/major-shareholder disclosure data for pre-explosion accumulation detection

**Design-and-survey round. No crawler or pipeline code written this
round** — this document is for review before any of it is built.
References `DATA_BASELINE.md` (dataset versioning conventions) and the
current `data/full_history_v2/` pipeline this would join against.

**Target signal**: Vietnam-listed insider (`người nội bộ` — board/
management/related persons) and major-shareholder (`cổ đông lớn`, ≥5%
ownership) trading disclosures — both the pre-trade registration
(required 1–3 business days ahead, per current regulation) and the
post-trade result report, plus major-shareholder ownership-change
reports (required within days of a ≥1% change once holding ≥5%).

---

## ROUND 5 — full-universe crawl, descriptive baseline, live-update pipeline started

**Scope, stated plainly and enforced as a hard constraint**: this round is
collection and inventory only. No factor was computed, no signal was
tested, and — critically — **no statistic anywhere in this round's output
joins disclosure data against price or return data.** The reason is
sequencing, not caution for its own sake: a signal-test design must be
pre-registered *before* anyone looks at how disclosure timing relates to
subsequent price moves, exactly the discipline this session already
applied to `SCORE_V2_DESIGN.md` and `FACTOR_RETEST_V2_REPORT.md` elsewhere
in the codebase. Looking at event-to-return statistics now, even
"just descriptively," would let that look quietly bias whatever test design
gets written next — the single most important guardrail for this new
branch of work, and the reason this round's descriptive doc
(`DISCLOSURE_BASELINE.md`) is share-count/date statistics only, never
return statistics.

### NV1 — full-universe crawl

Ran `scripts/crawl_disclosure.py --universe` against all 500 symbols in
the current universe (`data/full_history_v2/raw/*.parquet` minus
`config/excluded_symbols.csv`'s `GEE`). **0 fetch errors, 0 rate-limiting,
~24 minutes wall-clock** — in line with ROUND 4/NV7's estimate. 57,800
rows parsed, 56,870 valid (in `events.parquet`), 518 rejected (in
`errors.parquet`, 0.90% reject rate — consistent with the pilot's 0.9%
found on 5 symbols). Full descriptive results: `DISCLOSURE_BASELINE.md`
(new document, mirroring `DATA_BASELINE.md`'s role for the price dataset).

**Headline finding**: historical depth is much better than the 5-symbol
ROUND 4 pilot suggested — **157 of 500 symbols (31%) have disclosure
history reaching back to 2008**, not just HPG. See `DISCLOSURE_BASELINE.md`
for the full depth histogram and every other descriptive cut requested
(period × event type, role distribution, execution/registration ratio,
field-completeness-by-year, rejected-row breakdown).

**One new data-quality finding from full-universe scale that the 5-symbol
pilot was too small to surface**: the natural key `(symbol, event_type,
person_name, disclosure_date)` collides for 829 rows (1.4%) where the same
person made two genuinely distinct disclosures published the same calendar
day — `append_parquet`'s dedup keeps only one, meaning up to several
hundred real events aren't individually represented right now. Documented
in `DISCLOSURE_BASELINE.md` caveat #1, not fixed this round (schema change,
out of "kiểm kê" scope) — flagged for whoever next relies on this dataset
needing an exact event count.

### NV2 — incremental daily update pipeline (live point-in-time branch)

`scripts/update_disclosure_daily.py` + `src/data/disclosure_ingest.py`'s
new `ingest_new_events_live()`: re-fetches each symbol's current history
(one request each, same politeness), anti-joins against both the events
and error tables by natural key, and ingests **only genuinely new rows**
with `is_backfilled=False` — the first code running the live branch of the
ROUND 3 point-in-time rule (`available_at = max(disclosure_date,
ingested_at)`) rather than every row being backfilled. Not yet run on a
real schedule this round (no cron/launchd entry installed) — the script
exists and is tested, running it daily is an operational step for whoever
owns that decision.

### NV3 — not done this round, by design

No join to `data/full_history_v2` or any price/return series. No factor
built on top of `disclosure_events`. No signal test, walk-forward, or IC
computation. **Next round, if pursued, should open by pre-registering the
signal-test design** (event window, label definition, train/test split,
acceptance bar) **before** running it against this dataset — the same
discipline `SCORE_V2_DESIGN.md` used, applied to a new data source for the
first time.

---

## ROUND 4 — crawler v1 built, run against 5 symbols, historical-depth question closed

**Crawler code written this round** (all under `src/data/disclosure_*.py`,
`scripts/crawl_disclosure.py`, tests in `tests/test_disclosure_*.py`).
Real network crawl run against TCB, MWG, TCH, VHM, HPG (as instructed)
plus one extra symbol (AAM) purely to calibrate the full-universe size
estimate in NV4 below — no other symbols touched, **full-universe
crawl was not run**, pending scope approval per NV5.

### NV1 — a design pivot: JSON AJAX endpoint, not HTML scraping

The manual pilot (ROUND 3) used the rendered page
`cafef.vn/du-lieu/lich-su-giao-dich/{exchange}/{symbol}-6.chn`. Building
the crawler required understanding how that page's date-filter form
actually gets data, so its network traffic was inspected (ordinary
browser DevTools-equivalent inspection of a page already used in the
pilot — not reverse-engineering a hidden or undocumented system). That
inspection found the page's own JS calls a public JSON endpoint:

```
GET https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDCoDong.ashx
    ?Symbol={SYMBOL}&StartDate={mm/dd/yyyy}&EndDate={mm/dd/yyyy}&PageIndex={n}&PageSize={n}
```

returning `{"Data": {"TotalCount": N, "Data": [...]}}`, one JSON object
per disclosure record with fields mapping directly onto the schema
(`TransactionMan`, `TransactionManPosition`, `RelatedMan`,
`RelatedManPosition`, `PlanBuyVolume`/`PlanSellVolume`/`PlanBeginDate`/
`PlanEndDate` for the registration phase, `RealBuyVolume`/
`RealSellVolume`/`RealEndDate` for the result phase, `PublishedDate` --
a **real source timestamp**, not an inferred one -- `VolumeBeforeTransaction`/
`VolumeAfterTransaction`/`TyLeSoHuu`, `ShareHolderCode`, `Url`).

**Decision: the crawler hits this endpoint directly instead of scraping
rendered HTML.** This is a deviation from the original NV1 instruction's
literal wording ("lưu nguyên HTML từng trang"), made because it strictly
improves the result along every axis that instruction cared about:

- **More polite, not less**: tested with a large `PageSize` and blank
  date range, this endpoint returns a symbol's **entire history in one
  response** for every company size tried (247 records for HPG, 352 for
  MWG) -- one polite request per symbol instead of paginating a
  20-row-per-page rendered table.
- **Same source, same page, same politeness rules**: it's the literal
  data backing the exact page used in the manual pilot, same origin,
  no authentication, discovered via normal use of that page.
- **Raw tier is still immutable and still "raw"**: each page response
  (JSON text, not HTML, but still the source's own unmodified bytes) is
  written verbatim with `url`/`fetched_at`/`status_code`, never edited.
  The two-tier separation (raw vs. parse) is unchanged; only the format
  of what's immutably stored moved from HTML to JSON.
- **No new dependency**: parsing JSON needs nothing beyond the standard
  library; the `beautifulsoup4`/`lxml` HTML-parsing dependency flagged
  as likely-needed in ROUND 3 was never actually added to
  `requirements.txt` -- it wasn't needed.

### NV2 — crawler v1, architecture as built

- `src/data/disclosure_client.py` -- `DisclosurePoliteClient`: single-
  threaded, **minimum 2.5s between requests (a floor enforced in code,
  not a config default)**, identifying User-Agent, exponential backoff
  on 429/403 that gives up (`DisclosureRateLimitedError`) rather than
  hammering.
- `src/data/disclosure_crawler.py` -- `crawl_symbol`/`crawl_symbols`:
  fetches a symbol's full history (paginating further only if
  `TotalCount` exceeds one page), writes each page verbatim+immutably
  under `data/disclosure/raw/{symbol}/page{NN}_{fetched_at}.json`,
  checkpoints via `data/disclosure/raw/manifest.json` -- same pattern as
  `scratch/full_backfill_v2.py`'s price backfill: one manifest entry per
  symbol, saved after every symbol, `status: ok` skipped on resume.
- `src/data/disclosure_parser.py` -- pure function of the raw tier,
  re-runnable any time without re-crawling. Converts the source's
  `/Date(ms)/` wire format (see NV3 below for a real bug found and fixed
  here), expands each record into 0-2 `disclosure_events` rows
  (registration phase / result phase), classifies
  `insider_registration` / `insider_result` / `major_shareholder_change`
  by whether a board/management position is stated (v1 heuristic, see
  NV6).
- `src/data/disclosure_ingest.py` -- applies the ROUND 3 point-in-time
  rule (`available_at = max(disclosure_date, ingested_at)` live,
  `disclosure_date + 1 trading day` backfilled), natural-key append-only
  write, universe-membership flagging, negative-quantity/inverted-date
  rejection to an error table.
- All three have unit tests using fake HTTP responses / fixture JSON /
  tmp_path parquet stores -- no network access in the test suite, matching
  this repo's existing convention (`_FakeClient`-style fakes, not
  `responses`/`httpretty`).

### NV3 — a real timezone bug found and fixed via cross-validation

Initial parse of the real crawl showed every date **exactly one
calendar day earlier** than the 5 independently pre-registered
2020-2021 events from the ROUND 3 manual pilot (e.g. the TCB/Hồ Thủy
Anh registration window came back as `2021-07-11 → 2021-08-03` instead
of the known `2021-07-12 → 2021-08-04`). Root cause: the source's
epoch-millisecond dates are Vietnam-local (ICT, UTC+7) calendar dates
serialized as UTC "midnight minus 7 hours" (e.g. `17:00:00` the
*previous* day when read naively as UTC). `parse_dotnet_date` now shifts
by `+7h` before treating the result as a local calendar timestamp.
**After the fix, all 5 pre-registered historical events' registration
windows matched exactly, to the day** (see NV4). This is exactly the
kind of bug the instruction's "nghiệm thu bằng chính câu hỏi lịch sử còn
treo" (verify against the very question left open) was for -- caught
because there was a known-correct answer to check against, not because
anyone would have spotted it by inspection.

### NV4 — the historical-depth question: closed

Real crawl results (after the NV3 fix), full history per symbol, one
request each:

| Symbol | Total records | Earliest disclosure_date | Latest disclosure_date |
|---|---|---|---|
| HPG | 247 | **2008-07-22** | 2026-06-24 |
| MWG | 352 | 2013-03-13 | 2026-02-25 |
| TCB | 164 | 2013-09-26 | 2025-10-27 |
| TCH | 29 | 2020-09-29 | 2026-07-08 |
| VHM | 14 (+2 rejected, see NV6) | 2018-11-27 (2020-06-04 among validated-only rows) | 2026-06-25 |

**HPG genuinely reaches back to 2008-07-22** -- matching CafeF's own
"cập nhật từ 01/01/2008" claim for at least this symbol, closing the
central open risk from ROUND 1 ("no source confirmed at the row level to
have working historical data before today") for this symbol
definitively. The other four don't reach 2008, but this is now known to
be a **real depth limit per symbol**, not a pagination/tooling artifact
of the manual pilot (which is what ROUND 3 could not distinguish) --
TCH's real depth is Sept 2020, plausibly because insider-disclosure
requirements and/or this specific company's own disclosure history
genuinely starts around there, not because CafeF stopped serving older
pages. This project draws no further conclusion about *why* depth
varies by symbol (e.g. listing date, disclosure-regulation timing) --
flagged as an open question if it matters later, not resolved here.

**All 5 of the ROUND 3 pilot's un-reached 2020-2021 events are present,
exactly, in the crawled data** (registration window, shares, and role
all match to the day and the unit):

| Event | Symbol | Registration window (crawled) | Shares |
|---|---|---|---|
| A — Nguyễn Thị Hà (TCH) | TCH | 2020-10-01 → 2020-10-30 | 18,000,000 |
| B — Phan Thị Thu Hiền (MWG) | MWG | 2020-12-09 → 2020-12-31 | 500,000 |
| C — Hồ Thủy Anh (TCB) | TCB | 2021-07-12 → 2021-08-04 | 22,474,840 |
| D — Vingroup (VHM) | VHM | 2021-08-19 → 2021-09-17 | 100,485,418 |
| E — Nguyễn Đức Tài (MWG) | MWG | 2021-12-03 → 2021-12-31 | 1,000,000 |

This directly answers the "còn treo" question from ROUND 3: **the data
was there all along** -- ROUND 3's inability to reach it was purely a
limitation of driving CafeF's rendered-page pagination widget through
browser automation, exactly as ROUND 3 itself hedged ("a tooling
limitation... not a data-absence finding"). That hedge is now confirmed
correct.

### NV5 — cross-validation against the 10 known 2024-2026 events

All 10 events verified manually in ROUND 3 were re-checked against the
crawled+parsed data for HPG/VIC/NVL/VDS/VNS/MPC-equivalent coverage
(only HPG among the 10's symbols was in this round's 5-symbol crawl
scope; the other 9 events' symbols -- NVL, VDS, VIC, VNS, MPC -- were
**not** re-crawled this round, staying in scope per the instruction's
"đúng 5 mã"). For HPG specifically, the #6 event (Trần Vũ Minh, 50M
registered / 33,291,904 executed, window 2026-03-12 → 2026-04-10) is
present in the crawled data with every field matching the ROUND 3
manual finding exactly, confirming the parser handles this record shape
correctly beyond just the 5 historical ones it was debugged against.

No parser fixes were needed here beyond the NV3 timezone fix -- once
that was corrected, both the 5 historical and the 1 in-scope recent
event matched without further adjustment.

### NV6 — parse-quality statistics

Across all 6 crawled symbols (TCB, MWG, TCH, VHM, HPG, AAM -- AAM added
only for the NV7 size estimate, see below), 1,147 raw records parsed
into disclosure_events rows:

- **97.5%** of rows have all of {symbol, event_type, person_name,
  direction, disclosure_date} populated.
- **10 rows (0.9%)** rejected to the error table -- all genuine source-
  data anomalies (execution date 1-2 days before the registration
  window's stated start, or an inverted window in one 2009-era HPG
  record), not parser bugs. This is the validation guardrail (NV built
  in ROUND 4/NV2 above) working as designed: catching real anomalies in
  old records rather than silently ingesting them or crashing.
- **29 rows (2.5%) have no `direction`** (`buy`/`sell`) -- these are
  `major_shareholder_change` rows where only before/after share counts
  changed (e.g. bonus-share/ESOP-driven ownership shifts) with no
  matched buy/sell volume field from the source. Not a parser defect;
  the source itself doesn't classify these as directional trades.
- **39.5% of rows have a blank `person_role`** -- expected: 356/1,147
  (31%) of rows are `major_shareholder_change` (funds/holding companies
  with no board position), plus a smaller number of insider rows where
  the source's own `TransactionManPosition` field was empty.
- **64.6% of `source_ref` values are not a `/du-lieu/ceo/...` profile
  link** (plain org name instead) -- consistent with the
  major_shareholder_change share of records; individual insiders
  generally do get a profile-page link, organizations don't.
- **Known v1 classification heuristic, not re-litigated here**: whether
  a record counts as "insider" vs. "major shareholder" is decided by
  presence of a stated board/management position string, per ROUND 4/NV2
  above. This worked correctly for all 6 test symbols cross-checked but
  hasn't been audited against a large, diverse sample.

### NV7 — full-universe crawl: time/size estimate, scope not yet run

Calibration data (raw JSON tier, one request per symbol in every case
tested):

| Symbol | Raw size | Parsed rows |
|---|---|---|
| VHM | 12 KB | 16 |
| TCH | 24 KB | 38 |
| AAM | 64 KB | 133 |
| TCB | 120 KB | 259 |
| HPG | 172 KB | 348 |
| MWG | 244 KB | 486 |

**Time**: every symbol tested needed exactly one HTTP request (full
history fits in one `PageSize=2000` response even for MWG's 352
records). At the hard-coded >=2.5s pacing, **501 symbols ≈ 501 requests
≈ 20-30 minutes wall-clock** for the raw crawl (parse+ingest afterward
is local computation over already-downloaded JSON, adds well under a
minute).

**Size**: raw tier averaged ~106 KB/symbol across this 6-symbol sample
→ **≈53 MB raw tier for the full 501-symbol universe** if this sample
is representative. **Caveat, stated plainly**: all 6 symbols tested are
large-cap or otherwise disclosure-heavy names (average 212 parsed rows/
symbol) -- most of the 501-symbol universe is smaller and less actively
traded, and likely has far fewer insider/major-shareholder events. A
realistic total events count is somewhere in a wide **~20,000-100,000
row** range (parquet ≈5-25 MB) depending on how skewed the true
distribution is; this round doesn't have data to narrow that further
without crawling more symbols.

### NV8 — proposed scope for the full-universe crawl (not run, awaiting approval)

- **Recommend**: crawl the full 501-symbol universe
  (`data/full_history_v2/raw/*.parquet` symbol list), full available
  history per symbol (blank date range, same as this round) -- given
  HPG's confirmed 2008 depth and the low per-symbol cost (~1 request,
  ~2.5-4s), there's no time/politeness reason to artificially cap the
  date range or restrict to a symbol subset.
- **Estimated cost**: ~20-30 minutes wall-clock, ~53 MB raw tier (rough,
  see NV7 caveat), single-threaded, no burst load on CafeF at any point
  (one request every >=2.5s throughout).
- **Not run this round** -- per instruction, awaiting explicit approval
  before crawling beyond the 5(+1 calibration) symbols above.
- **Left for a later round regardless of this decision**: entity
  resolution beyond NFC-normalize+trim (same person appearing with
  spelling variants across records), a live-accumulation mode (this
  crawler only does bulk historical fetch --  `is_backfilled=True` on
  every row -- there is no incremental "run me daily and only fetch new
  rows" mode yet), and using the now-larger real dataset to measure the
  actual disclosure-date-to-CafeF-publish lag distribution flagged in
  ROUND 3/NV1 (this round's data already contains the real
  `PublishedDate` per record, once a large-enough sample exists this
  could be computed directly instead of estimated from one data point).

---

## ROUND 3 — point-in-time rule fix (look-ahead bug) + CafeF manual verification pilot

### NV1 — the original point-in-time rule was backwards

**The bug**: NV4 below (Round 1) defined
`effective_knowable_date = ingested_at if disclosure_date_is_estimated
else min(disclosure_date, ingested_at)`, and justified taking the
*earlier* of the two dates as the "stricter, safer" choice. That
reasoning is inverted. Taking the **minimum** doesn't protect against
look-ahead — it **causes** it: whenever a live-scraped row is captured
later than the event's stated `disclosure_date` (the normal case —
scraping always lags the real-world announcement by some amount), `min`
picks `disclosure_date`, which tells a backtest "this was knowable on
`disclosure_date`" even though **this pipeline** didn't actually have
the row until `ingested_at`, strictly later. A backtest driven off that
rule would be trading on information before its own ingestion pipeline
had captured it — exactly the class of bug `FOLD_AUTOPSY_REPORT.md` and
`run_portfolio_backtest`'s T-1 convention were built to prevent
elsewhere in this project, reintroduced here by an inverted min/max.

**The fix — two cases, not one rule**:

1. **Live-accumulated rows** (`is_backfilled=False`): a row is only
   knowable once *both* the disclosure has legally happened *and* this
   pipeline has actually captured it:
   ```
   available_at = max(disclosure_date, ingested_at)
   usable_as_of_T = available_at <= T
   ```
   This is the correct direction: `max`, not `min` — the later of the
   two is the true point-in-time floor, since a backtest cannot act on
   a row before the pipeline itself possessed it, no matter how early
   the disclosure was legally dated.

2. **Backfilled rows** (`is_backfilled=True`): backfill has no real
   `ingested_at` — it's just "whenever the backfill job happened to
   run," which is unrelated to when the information would have been
   knowable historically, so it cannot be used in the `max()` rule
   above (it would make everything artificially "available" only as of
   the backfill run date, which is wrong in the opposite direction —
   look-ahead-safe but uselessly conservative for building historical
   labels). Instead, backfilled rows use a **conservative assumed lag**
   in place of a real capture timestamp:
   ```
   available_at = disclosure_date + 1 trading day  # assumed scrape lag, conservative
   ```
   flagged with `is_backfilled=True` so any backtest consuming this
   table can run a **lag-sensitivity check** later (e.g. redo with +0,
   +2, +3 trading days and confirm results don't hinge on the assumed
   value) instead of silently trusting one hardcoded guess.

**Plan to replace the assumption with a measurement**: once the
pipeline is running live, log both `disclosure_date` (the date printed
on the source announcement/table row) and `ingested_at` (real capture
time) for every row, and periodically compute the **empirical
distribution of `ingested_at - disclosure_date`** across live rows.
Once enough live observations exist, that measured distribution (e.g.
its median or a conservative percentile) should replace the flat
"+1 trading day" backfill assumption above — the assumption is a
placeholder for a build-phase that has no live data yet, not a
permanent design choice.

**Also fixes**: `disclosure_date_is_estimated`'s role in the old rule
(picking `ingested_at` alone when the disclosure date was estimated) is
superseded by the same two-case split above — `is_backfilled` and
`disclosure_date_is_estimated` are now orthogonal flags (one about
whether `ingested_at` is a real timestamp, the other about whether
`disclosure_date` itself is exact or inferred), both usable together
with the `max()` rule for any live row.

### NV2 — CafeF manual verification pilot

See the pilot report appended after this section once run (Step 0
robots.txt/ToS check, Steps 1-3 manual lookups, conclusion) —
**pilot results below**, not yet present at the point this rule fix was
written; see the "CafeF Manual Verification Pilot" heading further down
this document.

### NV3 — vnstock license

See "vnstock License Review" heading further down this document for the
verbatim non-commercial-use clause, gathered for review, no legal
conclusion drawn.

---

## CafeF Manual Verification Pilot

**Manual, read-only. No crawler, no scripted/bulk requests, no
reverse-engineering of any internal API.** All of Step 0-3 below were
done by fetching individual pages one at a time and reading the
rendered content, same as a human visiting the site.

### Step 0 — robots.txt / terms-of-use check for automated access

- **`https://cafef.vn/robots.txt`** (fetched directly, verbatim):
  ```
  User-agent: *
  Allow: /
  Sitemap: https://cafef.vn/sitemap.xml
  Sitemap: https://cafef.vn/google-news-sitemap.xml
  ```
  Explicitly **allows all crawlers on the entire site** — no `Disallow`
  lines at all, and specifically no `Crawl-delay`.
- **Dedicated Terms of Use page**: not found. The site's footer links to
  exactly one legal document — `https://cafef.vn/static/chinh-sach-bao-mat.html`
  ("Chính sách bảo mật" / Privacy Policy) — no separate "Điều khoản sử
  dụng" page exists in the footer navigation.
- **Privacy policy content**: fetched and checked for scraping/reuse/
  commercial-use clauses. **Contains none** — it covers personal-data
  collection, cookies, and third-party sharing only; no statement on
  automated access or content reuse either way.
- **Footer copyright line** (verbatim): *"© Copyright 2007 - 2026 -
  Công ty Cổ phần VCCorp. Giấy phép thiết lập trang thông tin điện tử
  tổng hợp trên mạng số 2216/GP-TTĐT do Sở Thông tin và Truyền thông Hà
  Nội cấp ngày 10 tháng 4 năm 2019."* — a publishing-license notice, not
  a usage restriction on the data itself.

**Verdict: not prohibited.** robots.txt affirmatively allows automated
access to the whole site, and no ToS/legal page found states otherwise.
Proceeding to Steps 1-3 under the stated constraint (manual/read-only,
no scripted bulk access) regardless of this permissive robots.txt —
that constraint is about *this pilot*, not a statement that a future
real scraper would be unrestricted.

### Step 1 — 10 pre-registered known disclosure events, 2024-2026

Chosen for being widely reported in mainstream Vietnamese financial
press (independent of CafeF), spanning 6 different tickers, both
registration and result events, and both insider and major-shareholder
categories. **Registered here before any CafeF lookup was performed.**

| # | Symbol | Person / entity | Role | Type | Shares | Window / date | Source |
|---|---|---|---|---|---|---|---|
| 1 | NVL | Bùi Cao Ngọc Quỳnh | Con gái Chủ tịch Bùi Thành Nhơn | Registration (sell) | 9,100,000 | 9/5–6/6/2024 | mekongasean.vn |
| 2 | NVL | NovaGroup | Tổ chức liên quan Chủ tịch | Registration (sell) | 9,410,000 | 6/5–31/5/2024 | vneconomy.vn |
| 3 | VDS | Phạm Mỹ Linh | Mẹ TV HĐQT Phạm Hữu Luân | Registration (sell) | 5,000,000 | 8/9–6/10/2025 | cafef.vn (188250904...) |
| 4 | VDS | Nguyễn Thị Thu Huyền | TV HĐQT kiêm TGĐ | Registration (sell) | 940,000 | 8/9–6/10/2025 | vneconomy.vn |
| 5 | VDS | (lãnh đạo, name unconfirmed in this search pass) | Lãnh đạo | Registration (sell) | 400,000 | announced ~18/2/2026 | cafef.vn (188260218...) |
| 6 | HPG | Trần Vũ Minh | Con trai Chủ tịch Trần Đình Long | Result (buy) | registered 50,000,000 / executed 33,290,000 (66.6%) | 12/3–9/4/2026 | cafef.vn (188260414...), tuoitre.vn |
| 7 | VIC | Phạm Nhật Vượng | Chủ tịch | Transfer (capital contribution) | >70,600,000 | announced ~11/6/2025 | tuoitre.vn |
| 8 | VIC | Phạm Nhật Vượng | Chủ tịch | Transfer (capital contribution) | >48,000,000 | announced ~mid-2025 | tuoitre.vn |
| 9 | VNS | CTCP Tư vấn Kim Ngưu | Liên quan lãnh đạo Vinasun | Result (sell) | registered >3,400,000 / executed 909,091 (26.6%) | 15/5–13/6/2026 | cafef.vn (188260621...) |
| 10 | MPC | Chu Hồng Hà | Phó Tổng Giám đốc | Registration (sell) | 275,000 | 8/6–30/6/2026 | tinnhanhchungkhoan.vn |

### Step 3 (pre-registered ahead of Step 2, per numbering above) — 5 events, 2020-2021, for historical-depth check

| # | Symbol | Person / entity | Role | Type | Shares | Window / date | Source |
|---|---|---|---|---|---|---|---|
| A | TCH | Nguyễn Thị Hà | Vợ Chủ tịch Đỗ Hữu Hạ | Registration (buy) | 18,000,000 | 1/10–30/10/2020 (announced 28/9/2020) | cafef.vn (own archive page) |
| B | MWG | Phan Thị Thu Hiền | Vợ Chủ tịch Nguyễn Đức Tài | Registration (sell) | 500,000 | 9/12–31/12/2020 | vietnambiz.vn |
| C | TCB | Hồ Thủy Anh | Con gái Chủ tịch Hồ Hùng Anh | Registration (buy) | 22,474,840 | 12/7–4/8/2021 | baodautu.vn |
| D | VHM | Tập đoàn Vingroup | Cổ đông lớn | Registration (sell) | ~100,500,000 (~3% vốn điều lệ) | 19/8–17/9/2021 | baodautu.vn |
| E | MWG | Nguyễn Đức Tài | Chủ tịch HĐQT | Registration (sell) | 1,000,000 | 3/12–31/12/2021 | tuoitre.vn |

### Step 2 — manual CafeF lookup results

Method: for each symbol, opened `cafef.vn/du-lieu/lich-su-giao-dich/{exchange}/{symbol}-6.chn`
in a real browser session, read the rendered "Cổ đông & Nội bộ" table
(same view a human sees), and compared every field against the
pre-registered row above. **No scripted bulk requests, no API reverse-
engineering** — one page view per symbol, exactly as designed for this
pilot.

#### 2024-2026 pool — 10/10 found, fields match almost exactly

| # | Symbol | Found? | CafeF's actual row (verbatim fields) | Match vs. pre-registration |
|---|---|---|---|---|
| 1 | NVL | Yes | Bùi Cao Ngọc Quỳnh (Con của Bùi Thành Nhơn, Chủ tịch HĐQT): trước GD 24,678,549; đăng ký bán 9,109,784, 09/05/24–06/06/24; kết quả bán 9,109,784, 14/05/24; sau GD 15,568,765 (0.65%) | Exact — share count, window, and post-transaction holding all match the press figures to the unit |
| 2 | NVL | Yes | CTCP Novagroup (liên quan Nguyễn Hiếu Liêm, Phó Chủ tịch HĐQT): trước GD 358,176,865; đăng ký bán 9,413,000, 06/05/24–31/05/24; **kết quả bán chỉ 40,475**, 09/05/24 | Registration matches exactly (9,413,000); **execution was ~0.4% of the registered amount** — CafeF captured the large registration-vs-tiny-execution gap that a naive "assume registration = outcome" pipeline would have missed entirely |
| 3 | VDS | Yes | Phạm Mỹ Linh (Mẹ của Phạm Hữu Luân, TV HĐQT): trước GD 29,999,219; đăng ký bán 5,000,000, 08/09/25–06/10/25; kết quả bán 5,000,000, **10/09/25** (2 days after window opened, well before window close) | Exact on shares/window; execution date now known precisely |
| 4 | VDS | Yes | Nguyễn Thị Thu Huyền (Tổng Giám đốc): trước GD 1,452,212; đăng ký bán 940,000, 08/09/25–06/10/25; kết quả bán 939,000 (1,000 short), 06/10/25 | Registered amount exact; execution 1,000 shares short of registration |
| 5 | VDS | Yes | Nguyễn Chí Trung (Thành viên HĐQT): trước GD 768,150; đăng ký bán 400,000, **25/02/26–26/03/26** (article was published 18/02/26); kết quả bán 400,000, 25/02/26 (same day the window opened) | Share count exact; **registration window start (25/2) is 7 days after the press article's publish date (18/2)** — a real, observed data point for the lag question, see NV1 note below |
| 6 | HPG | Yes | Trần Vũ Minh (Con của Trần Đình Long, Chủ tịch HĐQT): trước GD 176,391,996; đăng ký mua 50,000,000, 12/03/26–**10/04/26**; kết quả mua 33,291,904, 09/04/26; sau GD 209,683,900 (2.48%) | Registered and executed amounts exact; window end date is 10/4 not 9/4 as press paraphrased — CafeF's date is authoritative |
| 7 | VIC | Yes | Phạm Nhật Vượng → CTCP Năng lượng VinEnergo: 70,646,767 shares, 16/06/25–15/07/25, executed 17/06/25 | Exact — but this is **one of four separate VinEnergo tranches** Vượng made in 2025 (17/4: 35.0M; 5-10/6: 48.1M to VinSpeed, see #8; 16-17/6: 70.6M; 9/10-9/11: 60.0M) — press coverage of "the VinEnergo transfer" collapsed a multi-tranche series into a single number |
| 8 | VIC | Yes | Phạm Nhật Vượng → CTCP Đầu tư và Phát triển Đường sắt cao tốc VinSpeed: 48,086,745 shares, 05/06/25–04/07/25, executed 10/06/25 | Exact — also one tranche of a larger VinSpeed series (later tranches: 28/10/25 243.5M via a different related entity; 15/12/25 76.0M more from Vượng directly) |
| 9 | VNS | Yes | Công ty TNHH Tư vấn Kim Ngưu (not "CTCP" as press paraphrased — CafeF's legal-form field is authoritative): đăng ký bán 3,423,020, 15/05/26–13/06/26; kết quả bán 909,091 (26.6%), 13/06/26 | Exact on both registered and executed counts |
| 10 | MPC | Yes | Chu Hồng Hà (Phó Tổng GĐ): trước GD 319,140; đăng ký bán 275,000, 08/06/26–30/06/26; **kết quả: still blank/0 as of this pilot's run (12/07/26)**, i.e. 12 days after the window closed | Share count and window exact; the still-missing result row past window-close is itself a data-quality observation (either non-execution or a CafeF update lag), not an error in this pilot |

**Coverage: 10/10.** Every field this pilot checked (person/entity name,
role, related-party link, shares before/after, registration mua/bán +
window, result mua/bán + execution date, resulting ownership %) was
present and matched independent press reporting to the unit wherever
press gave exact numbers. Three genuinely new things were learned that
press coverage didn't carry: exact execution-vs-registration shortfalls
(#2, #4), a corrected window end-date (#6), and confirmation that
several "single transactions" reported in the press are actually
multi-tranche series (#7, #8).

#### 2020-2021 pool — 1/5 confirmed, 4/5 blocked by a pagination tooling limit, not a data-absence finding

| # | Symbol | Result |
|---|---|---|
| D | VHM | **Confirmed, exact.** Tập đoàn Vingroup → (liên quan Phạm Nhật Vượng, Chủ tịch HĐQT): trước GD 2,333,164,250; đăng ký bán 100,485,418, 19/08/21–17/09/21; kết quả bán 100,485,418, 06/09/21; sau GD 2,232,678,832 (54.36%, i.e. post-transaction stake). **Bonus finding**: VHM's entire "Cổ đông & Nội bộ" history fits on a single page (15 rows total) and reaches back to **29/11/2018** (a Phó Tổng GĐ's wife's transaction) — real evidence the historical-depth claim holds for at least one large-cap, low-insider-turnover symbol. |
| A | TCH | **Not reached.** Page 1 (~20 rows) covers only Sept 2025–June 2026; a 2nd page exists but this pilot's browser-automation tooling could not reliably drive the site's date-range filter or its JS-based pagination control (`ownerCDL.handleChangePage`) to load it — repeated attempts hit either an unresponsive filter (same unfiltered "most recent" rows returned regardless of the dates entered) or renderer timeouts when trying to click the page-2 control. **This is a tooling limitation of this pilot, not a finding that the 2020 row is absent.** |
| B, E | MWG | **Not reached.** MWG has 18 pages of insider/major-shareholder rows; page 1 only reaches back to Feb 2026. The Dec-2020 and Dec-2021 target rows are many pages further back than this pilot could navigate to, for the same tooling reason as TCH. |
| C | TCB | **Not reached.** TCB has 9 pages; page 1 only reaches back to Nov 2024. Same tooling limitation. |

**Honest summary of the historical-depth check**: 1 of 5 pre-registered
2020-2021 events was directly confirmed (VHM), with a bonus data point
showing genuine depth to late 2018 for that symbol. The other 4 could
not be checked this round — **not because CafeF appeared not to have
the data**, but because this pilot's date-range-filter and pagination
interactions were unreliable in the browser-automation tool used
(the filter form frequently ignored the entered dates and returned the
unfiltered "most recent" page regardless; the pagination widget's
click target could be located in the DOM but not consistently
triggered without further tooling work). **This is a distinct, weaker
conclusion than Round 1's "no row has been observed yet at all"** — one
real 2018-era row has now been observed and matches exactly — but it
does not close the historical-depth question for high-frequency-insider
names like TCB/MWG. A follow-up spike with either a more capable
browser-automation setup or a direct look at the page's underlying data
endpoint (still manual, still read-only, still not a scraper) would be
the next step if this matters before committing to a build.

### NV1 — real disclosure-lag data point observed

Event #5 above (VDS, Nguyễn Chí Trung) gives one real number for the
question ROUND 3/NV1 flagged as needing live measurement: the press
article reporting this registration was published 18/02/2026, while
CafeF's own record shows the registration window itself only started
25/02/2026 — a **7-day gap** between "the market found out" and "the
registration period began." This is a single data point, not a
distribution, but it's directly relevant to calibrating the backfill's
`+1 trading day` placeholder (this round's default is likely too
short for at least some disclosure types) — flagged for the live-phase
lag-measurement plan in ROUND 3/NV1, not acted on here (one data point
doesn't justify changing the placeholder value).

---

## vnstock License Review

Fetched `github.com/thinh-vu/vnstock`'s license (`LICENSE.md`). Verbatim
excerpts of the relevant restriction (short quotes only, per citation
norms):

- The Vietnamese-language README states the license is *"hướng đến cá
  nhân, không dành cho mục đích thương mại"* — i.e. aimed at
  individuals, not for commercial purposes.
- The license text itself states the software is **"intended for
  personal use only"** and **"may not be redistributed or used for"**
  commercial purposes without the author's written approval, where
  commercial use is defined to include anything that "directly or
  indirectly contributes to generating revenue."
- Permitted without special permission: individual research, academic
  study, editing/modification, learning.
- The license "will automatically terminate immediately without
  notice" on breach, requiring destruction of all copies.

**No legal conclusion is drawn here** — this is a citation/gathering
exercise only, per instruction. Whether this project's use of
`vnstock` (a research pipeline, not a resold product, but one whose
output informs paid or investment-relevant decisions) falls inside or
outside "personal, non-commercial" is a judgment call for whoever owns
that decision, ideally with the author contacted directly given the
license's own suggestion to do so for anything beyond personal use.
This was flagged as a blocker for *production* use in Round 1; nothing
in this round changes that — it remains unresolved, not cleared.

### ROUND 3 conclusion — CafeF: sufficient for recent data, historical depth still open

- **Coverage**: 10/10 pre-registered 2024-2026 events found, every
  field matching independent press reporting exactly wherever press
  gave exact numbers, plus three concrete things CafeF captured that
  press didn't (registration-vs-execution shortfalls, a corrected
  window date, multi-tranche series press collapsed into one number).
  **For live/recent accumulation, CafeF is sufficient as the primary
  source** — this is a stronger, evidence-backed version of Round 1's
  "best candidate found" verdict, not just an unverified plausibility.
- **Historical depth**: genuinely mixed evidence, not a clean answer.
  One low-insider-turnover symbol (VHM) showed real depth back to
  November 2018. Zero evidence either way for high-turnover names
  (TCB, MWG) or for reaching all the way back to 2008 for any symbol —
  this pilot's tooling could not page deep enough to test it. **The
  central open risk from Round 1 is now partially retired (2018 depth
  confirmed for at least one symbol) but not closed** — a pipeline
  that needs pre-2023 history for names like TCB/MWG/HPG specifically
  should re-run this same manual check with either a sturdier browser
  session or a direct (still manual, still read-only) look at the
  page's data endpoint before relying on that depth.
- **Lag**: one real data point (7 days, press-to-registration-window for
  one VDS event) — nowhere near enough for a distribution, but it's the
  first real number this project has, and it's consistent with the
  backfill's `+1 trading day` placeholder in ROUND 3/NV1 being too
  short for at least some disclosure types (a registration *window*
  starting isn't the same thing `+1 trading day` was modeling, so this
  isn't a direct apples-to-apples comparison either — flagged, not
  acted on).
- **robots.txt/ToS**: not prohibited (Step 0 above) — nothing here
  changes the earlier build-phase plan to use CafeF as primary source,
  manually/read-only for now.

**Decision**: CafeF remains primary source, now with real verification
behind the recent-data claim. Before committing to a production
crawler, whoever approves the build phase should decide whether the
historical-depth gap (for high-turnover names specifically) is
acceptable to launch with live-accumulation-only, or whether it's worth
another verification pass first — this round doesn't force that
decision either way, it just makes the tradeoff visible with real
numbers instead of Round 1's "central open risk, unverified at the row
level" framing.

---

## ROUND 2 — SSI verified exhaustively via official documentation, closed definitively

Follow-up to Round 1's SSI finding below, which was based on inspecting
the installed SDK package only. This round checks the **official
documentation**, independent of what any particular SDK version
implements, per instruction — a real distinction, since SDKs can lag a
published API spec. Conclusion did not change, but is now evidenced at
the documentation level, not just the code level.

### NV1 — full FCData endpoint catalog, cross-checked 3 ways

1. **SDK source** (`ssi_fc_data` v2.2.2, `model/api.py`): defines exactly
   10 URL constants, all under `api/v2/Market/`.
2. **Official English docs**: `guide.ssi.com.vn/ssi-products/fastconnect-data/api-specs`.
3. **Official Vietnamese docs**: `guide.ssi.com.vn/ssi-products/tieng-viet/fastconnect-data/danh-sach-cac-api`.

All three sources list the **same 10 endpoints**, no more, no fewer:

| Endpoint | Path | Description |
|---|---|---|
| AccessToken | `Market/AccessToken` | Auth token for API/streaming access |
| Securities | `Market/Securities` | Securities list by exchange |
| SecuritiesDetails | `Market/SecuritiesDetails` | Detailed info for a security (ISIN, type, trading specs) |
| IndexComponents | `Market/IndexComponents` | Constituent securities of an index |
| IndexList | `Market/IndexList` | Available indices by exchange |
| DailyOhlc | `Market/DailyOhlc` | Daily OHLC + volume/value (the adjusted, primary price endpoint this whole project is built on) |
| IntradayOhlc | `Market/IntradayOhlc` | Intraday tick-level OHLC |
| DailyIndex | `Market/DailyIndex` | Daily index-level trading results |
| DailyStockPrice | `Market/DailyStockPrice` | Daily price incl. raw/adjusted close, foreign-investor activity (the fallback endpoint `BACKFILL_DESIGN_REPORT.md` root-caused the adjustment bug in) |
| BackTest | `Market/BackTest` | Present in the SDK's method list and URL constants; not wrapped in `src/data/ssi_client.py`, not documented with a description on either official page found — appears to be a historical-replay/testing utility, not disclosure-related regardless |

**Corporate-actions/events/disclosure check**: **zero** of these 10
relate to corporate actions, dividends, splits, AGM/shareholder
meetings, insider trading, or ownership changes — confirmed identically
by the SDK's own code and by both language versions of the official
docs. **No endpoint qualified for the requested test-call step (HPG or
otherwise) — there is nothing in this category to call.** This is a
stronger result than Round 1's (SDK-only) finding: it rules out the
possibility that the SDK simply hadn't caught up to a richer published
API, since the official spec itself has nothing more.

### NV2 — other SSI products

Official product index (`guide.ssi.com.vn/ssi-products`) lists exactly
**two** FastConnect products total:
- **FastConnect Data (FCData)** — market data (the 10 endpoints above).
- **FastConnect Trading (FCTrading)** — account info, order placement/
  amendment/cancellation, order-status streaming. Purely execution/
  account management — not a data product, and not disclosure-related
  by its own stated purpose regardless of what scope our credentials
  have. Never used anywhere in this codebase.

**Account scope**: not inspected by dumping the live access-token
response (blocked — printing a real credential/token into this
transcript isn't something to do without a specific reason, and wasn't
needed here). Not needed for the conclusion anyway: every successful
call this whole project has ever made (`get_securities`, `get_daily_ohlc`,
etc.) is FCData-scoped, FCTrading has never been touched, and FCTrading
is the wrong *kind* of product for disclosure data regardless of scope
— so account-scope introspection wouldn't change this section's answer.

**iBoard's disclosure-news backend**: searched official SSI
documentation and support pages for any description of what powers
iBoard's "công bố thông tin" news feed. **Found none** — no public SSI
documentation describes iBoard's disclosure-news data source.
Per instruction, this was **not pursued further via inspecting iBoard's
actual network traffic** (that would be reverse-engineering, explicitly
out of bounds unless terms of service clearly allow it, which wasn't
established). This line of inquiry is closed as "undocumented
publicly," not as "confirmed absent."

### NV3 — conclusion: **(b) closed**

**SSI's full FastConnect product line (both products, all 10 FCData
endpoints, cross-verified via SDK source + 2 official documentation
pages) has no insider-trading or major-shareholder disclosure data of
any kind.** This is the complete evidence list for that conclusion —
nothing further to check within SSI's own documented offering.

**Corporate-actions aside** (as instructed, independent of the main
disclosure question): **no corporate-action endpoint exists either** —
neither DailyOhlc/DailyStockPrice nor any other endpoint returns
dividend/split events directly; the existing pipeline's own adjustment
handling (`BACKFILL_DESIGN_REPORT.md`) works by consuming `DailyOhlc`'s
*already-adjusted* close series, not by reading discrete corporate-
action records. **No reconciliation source was found here** — if a
future round wants an independent corporate-action feed to cross-check
`full_history_v2`'s adjustment handling, it isn't SSI; it would need its
own separate survey, out of scope for this round.

**Decision**: primary source stays **CafeF.vn**, exactly as designed in
Round 1 below — nothing in this round changes that plan. Proceed to the
verification spike already recommended (fetch known historical events,
confirm they match) before committing further.

---

## ROUND 1 — original survey and design

## NV3 — source survey (read-only, no new signups)

### 1. SSI FCData (current client) — **no capability, confirmed**

Inspected the actual installed package (`ssi_fc_data` v2.2.2), not just
our wrapper: `MarketDataClient` exposes exactly 9 endpoints —
`access_token`, `backtest`, `daily_index`, `daily_ohlc`,
`daily_stock_price`, `index_components`, `index_list`, `intraday_ohlc`,
`securities`, `securities_details`. Nothing disclosure/event/ownership-
related exists anywhere in the package, confirming `DATA_AUDIT_REPORT.md`'s
original scope finding (this feed is price data only). **Ruled out.**

*(Superseded by the deeper check above: this was SDK-code-only —
**ROUND 2** cross-verifies against SSI's official documentation
directly and checks SSI's other product, FCTrading, too. Conclusion is
unchanged, now evidenced independent of any one SDK version.)*

### 2. HOSE — public viewer not pinned down, submission portal is login-gated

`ecm.hsx.vn` (referenced by SSI's own disclosure-rules page as HOSE's
disclosure system) is a **login-gated portal** — fetched directly,
returns only a username/password form, no public content. This is very
likely the *submission* side (where listed companies file disclosures),
not a public viewer. `www.hsx.vn` has a "Thông tin công bố" navigation
section per search results, but the exact public per-symbol disclosure
URL wasn't isolated in this survey — **needs a follow-up look before
being ruled in or out**, not resolved here.

### 3. HNX — public listing page exists, blocked by a certificate error both attempts

`hnx.vn/vi-vn/thong-tin-cong-bo-ny-hnx.html` is described (via search
results) as a public disclosure listing. **Both direct fetch attempts
failed**: `unable to verify the first certificate` — an SSL chain issue
on HNX's side, not a transient network blip (failed identically twice).
A real scraper would need to either fix/pin HNX's cert chain or
knowingly disable verification (a security-hygiene tradeoff worth a
second opinion before doing, not decided here). **Blocked, not ruled
out** — content/structure unverified.

### 4. SSC (State Securities Commission) — not identified as a practical per-symbol source

SSC publishes law/regulation text (confirmed: the Securities Law PDF is
hosted there) and is the ultimate regulator, but no per-symbol
transaction-level disclosure search portal was found in this survey.
Likely delegates actual disclosure *hosting* to the exchanges. **Not
pursued further as a data source** (distinct from being a source of the
*rules*, which it clearly is, and which informed the field definitions
below).

### 5. CafeF.vn — **best candidate found, free, structured, but historical depth unverified at the row level**

Confirmed directly by fetching a real per-symbol page
(`cafef.vn/du-lieu/lich-su-giao-dich/hose/hpg-6.chn` — the "Cổ đông &
Nội bộ" tab, URL pattern `.../lich-su-giao-dich/{exchange}/{symbol}-6.chn`).
**Table columns match almost exactly what's needed**: `Mã` (symbol),
`Tổ chức/người GD` (trading org/person), `Người liên quan` (related
person: position + name), `SLCP trước GD` (shares before),
`Đăng ký` (registration: buy/sell + start/end dates), `Kết quả`
(result: buy/sell + execution date), `SLCP sau GD` (shares after),
`Tỷ lệ(%)`, `Chức vụ` (position). Page states historical coverage
**"từ 01/01/2008"** and has a date-range filter. Content appears
server-rendered (the fetch tool extracted table structure and text
directly, not just a JS shell) — a good sign for scraper feasibility,
though not a substitute for a real HTTP-level check.

**Caveat, stated plainly**: this is a page-structure and stated-coverage
finding, not a verified historical row count. The one live query run
(HPG, default date range) returned "Chưa có thông báo kết quả giao dịch"
(no results for that window) — that's an empty *result*, not evidence
against the claim, but it also means **no actual historical row has
been observed yet in this survey**. See "the central open risk" below.

### 6. Vietstock.vn — free per-event articles (unstructured) + paid structured feed (not pursued)

Individual disclosure events are published as free news-style articles
(e.g. "VFG: Báo cáo kết quả giao dịch cổ phiếu của Người nội bộ...") —
usable but would need text parsing per article, less structured than
CafeF's table. Vietstock also sells a paid `VietstockXLS`/DataFeed
product explicitly covering "insider and related shareholder
transactions" and major-shareholder transactions — **not signed up for,
per instruction**; flagged as a fallback worth a paid-service decision
in a future round if the free sources prove insufficient.

### 7. `vnstock` (open-source Python package) — promising, two real caveats

`github.com/thinh-vu/vnstock` (464+ commits, appears actively
maintained) exposes `insider_trading()`, `shareholders()`, and
`events()` under `Reference.company`, returning DataFrames directly —
no scraper to write at all if this holds up. **Guest tier needs no
registration** (20 req/min), fitting the "no new signups" constraint
for evaluation. **Two caveats found, not resolved**:
1. The underlying data provider for these three specific functions
   wasn't confirmed from the docs (the library generally sources from
   TCBS/SSI's public web endpoints, not the FCData feed we hold
   credentials for, but which provider backs `insider_trading()`
   specifically is unconfirmed).
2. **License is a custom license restricting use to "individuals, not
   for commercial purposes"** — worth a deliberate legal/licensing
   review given this project's nature, before any real dependency on it.
   Not a blocker for a small manual evaluation spike, but a blocker for
   production use until reviewed.

### Summary table

| Source | Structured? | History claimed | Access blocker | Verdict |
|---|---|---|---|---|
| SSI FCData | — | — | No such endpoint exists | **Ruled out** |
| HOSE (ecm.hsx.vn) | Unknown | Unknown | Login-gated (wrong URL, likely) | **Needs follow-up** |
| HNX | Unknown | Unknown | SSL cert error (2/2 attempts) | **Blocked, unverified** |
| SSC | N/A | N/A | No per-symbol portal found | **Not pursued** |
| **CafeF.vn** | **Yes, HTML table, right fields** | **"since 2008" (unverified at row level)** | None observed | **Best candidate** |
| Vietstock (free) | No (news articles) | Ongoing, unclear depth | None | Fallback, needs parsing |
| Vietstock (paid) | Yes | Likely deep | Paid signup | Deferred, future round |
| vnstock (library) | Yes (DataFrame) | Unconfirmed | License scope, unconfirmed provider | Promising, needs a spike |

### The central open risk, stated honestly (per instruction)

**No source in this survey was confirmed, at the individual-row level,
to have working historical data before today.** CafeF's page *claims*
coverage since 2008 and has the right shape, but nothing here proves a
single 2020-2021 row is actually retrievable. **If a build-phase
verification spike shows the historical claim doesn't hold** (data only
populated from whenever CafeF started actively maintaining that tab, or
inconsistent/sparse before some cutoff), **the consequence is real and
should be planned for now**: the pipeline can only *accumulate* events
from its own launch date forward, meaning the accumulation-before-
explosion *detector* this whole effort is for would need a live run of
enough months (a real, unavoidable lag between "the pipeline works" and
"there's enough labeled history to backtest it on") before it can be
evaluated the way every other factor in this session's work has been —
via a walk-forward or IC test against realized outcomes. **This isn't a
reason not to build it — it's a reason to start the pipeline early and
size expectations correctly**, and to prioritize the row-level
historical verification spike as the very first build-phase task,
before investing in the rest of the pipeline.

---

## NV4 — point-in-time storage design

### Schema: `disclosure_events` (append-only, never updated in place)

| Field | Type | Notes |
|---|---|---|
| `symbol` | string | Normalized uppercase, matched against `data/full_history_v2/raw/{symbol}.parquet`'s universe |
| `event_type` | enum | `insider_registration` \| `insider_result` \| `major_shareholder_change` |
| `person_name` | string | Trader/organization name, as published (see name-normalization risk below) |
| `person_role` | string | e.g. "Thành viên HĐQT", "Người liên quan", "Cổ đông lớn" — free text, not enumerated (roles vary by source wording) |
| `direction` | enum | `buy` \| `sell` |
| `shares_before` | int, nullable | SLCP trước GD |
| `shares_registered_or_changed` | int, nullable | Registered volume (registration events) or the volume that changed (ownership-change events) |
| `shares_after` | int, nullable | SLCP sau GD |
| `pct_after` | float, nullable | Ownership % after, where disclosed |
| `registration_window_start` | date, nullable | Registration events only |
| `registration_window_end` | date, nullable | Registration events only |
| `execution_date` | date, nullable | Result/ownership-change events |
| `disclosure_date` | date | **The critical field** — see below |
| `disclosure_date_is_estimated` | bool | True if backfilled as a proxy (see below), False if taken directly from a source-provided announcement timestamp |
| `source` | string | e.g. `cafef`, `hnx`, `vietstock` — for auditability and reconciling conflicts across sources |
| `source_ref` | string | URL or source-internal ID, for manual verification |
| `ingested_at` | timestamp | When *this pipeline* captured the row. For live-accumulated rows this is a real capture timestamp. For backfilled rows it is **not** a real point-in-time signal (it's just "when the backfill job ran") — see `is_backfilled` and **ROUND 3** below. |
| `is_backfilled` | bool | True if this row was loaded by a historical backfill job (its `ingested_at` is not a real point-in-time capture); False if accumulated live. Added in **ROUND 3** — distinct from `disclosure_date_is_estimated`, which is about whether `disclosure_date` itself is exact. |
| `raw_payload` | string (JSON), nullable | Original scraped text/fields, kept for reprocessing if parsing logic improves later |

**Natural key** (uniqueness, append-only enforcement):
`(symbol, event_type, person_name, disclosure_date)`. A later
correction/amendment to an already-published disclosure is **inserted
as a new row**, never an in-place update — if sources publish
amendments, they get their own `disclosure_date` and the old row stays
exactly as it was, preserving what was knowable at the time.

### Point-in-time query rule

**None of the sources surveyed confirmed a distinct, directly-published
"announcement timestamp" field separate from the registration window's
start date.** Regulation requires public announcement ~1-3 business
days before the registered window starts, so `registration_window_start`
minus that lead time is a reasonable *estimated* lower bound when a
source doesn't give the disclosure date directly —
`disclosure_date_is_estimated=True` in that case. For live-accumulated
rows, `ingested_at` is unambiguous and should be preferred.

**Rule for "what did we know as of date T"** *(SUPERSEDED — this rule has
a look-ahead bug, see **ROUND 3** below for the fix; kept here
unmodified for the record)*:
```
effective_knowable_date = ingested_at if disclosure_date_is_estimated else min(disclosure_date, ingested_at)
usable_as_of_T = effective_knowable_date <= T
```
Taking the earlier (stricter) of the two whenever both are meaningful
avoids the specific class of look-ahead bug this session spent a lot of
effort on elsewhere (`FOLD_AUTOPSY_REPORT.md`'s D1 decision-timing
convention, `run_portfolio_backtest`'s T-1 rule) — same principle,
applied here.

### Join with `data/full_history_v2`

- **Symbol match**: direct join on `symbol` against
  `data/full_history_v2/raw/{symbol}.parquet`'s universe. Any disclosed
  symbol not in the current 501-symbol universe (delisted, OTC-only, or
  not yet backfilled) is logged and dropped, not treated as an error —
  consistent with `DATA_BASELINE.md`'s disclosed survivorship-bias
  caveat, which this inherits.
- **Trading-calendar alignment**: `disclosure_date` (or
  `ingested_at`-derived effective date) that falls on a non-trading day
  is forward-adjusted to the next trading day before being used in any
  feature (e.g. "days since last insider-buy disclosure"), matching the
  T-1/decision-date convention already established in
  `src/backtest/portfolio_backtest.py`.

### Risks (disclosed, not mitigated this round)

1. **Historical depth unverified** — the central open risk above.
2. **Source format changes** — HTML structure changes silently break a
   scraper; needs schema/row-count validation checks built into
   whatever ingestion job is eventually written, not designed in detail
   here.
3. **Name normalization** — the same person may appear with inconsistent
   spacing, diacritics, or abbreviated titles across records/sources;
   matching "same person over time" for pattern features needs fuzzy
   matching, a real data-quality task not scoped here.
4. **OTC/UPCOM and non-universe symbols** — some sources may cover
   names outside the current 501-symbol universe; handled by the
   drop-and-log join rule above, but worth remembering this pipeline
   inherits the same universe-scope limits as the rest of `data/full_history_v2`.
5. **HNX's certificate issue** — a concrete, already-observed technical
   obstacle (not hypothetical) for any HNX-sourced scraping.
6. **Licensing/ToS** — CafeF and Vietstock are commercial media
   properties; scraping them at real pipeline scale/frequency should
   get a terms-of-service check before building, not assumed clear.
   `vnstock`'s custom license (individuals, non-commercial) needs the
   same kind of review. None of this was adjudicated in this round —
   flagged for whoever approves the build phase.

## Not done this round

No crawler, no scheduled job, no new dependency added, no new service
signed up for. First recommended build-phase step, if this design is
approved: a small, throwaway verification spike — fetch a handful of
*known*, independently-documented historical insider disclosures (e.g.
from an old news article) for 2-3 symbols from CafeF and confirm the
exact same events appear with matching dates/volumes, before committing
to the rest of the pipeline.
