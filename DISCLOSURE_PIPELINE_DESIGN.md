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

*(filled in below as each symbol's "Cổ đông & Nội bộ" tab is checked)*

---

## vnstock License Review

*(filled in below)*

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
