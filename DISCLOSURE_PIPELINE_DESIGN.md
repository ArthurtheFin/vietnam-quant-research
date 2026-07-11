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

## NV3 — source survey (read-only, no new signups)

### 1. SSI FCData (current client) — **no capability, confirmed**

Inspected the actual installed package (`ssi_fc_data` v2.2.2), not just
our wrapper: `MarketDataClient` exposes exactly 9 endpoints —
`access_token`, `backtest`, `daily_index`, `daily_ohlc`,
`daily_stock_price`, `index_components`, `index_list`, `intraday_ohlc`,
`securities`, `securities_details`. Nothing disclosure/event/ownership-
related exists anywhere in the package, confirming `DATA_AUDIT_REPORT.md`'s
original scope finding (this feed is price data only). **Ruled out.**

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
| `ingested_at` | timestamp | When *this pipeline* captured the row — the true point-in-time anchor for anything accumulated live |
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

**Rule for "what did we know as of date T"**:
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
