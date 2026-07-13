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

---

## Hợp nhất về main — 2026-07-13

**Từ hôm nay (2026-07-13): `main` tại thư mục gốc
(`/Users/jamesb/Desktop/vietnam-quant-research`) là nhánh làm việc duy
nhất.** Mọi session/commit từ nay chạy thẳng trên `main` tại thư mục
gốc, không tạo worktree/nhánh `claude/*` mới cho công việc thường xuyên.

Toàn bộ ~88 commit trên `claude/charming-bartik-d21dc1` (backfill dữ
liệu v2, retest 44 nhân tố, score v2, forensic 2026, disclosure
pipeline, audit 58/100) đã được **fast-forward thẳng vào `main`**
(`git merge --ff-only`, không rebase, không squash) — lịch sử commit
giữ nguyên. HEAD `main` sau hợp nhất: `6671db3`, sau đó có thêm 2 commit
dọn dẹp working-tree-bẩn tại gốc (`cb4d7c9`, `8d42be0` — xem chi tiết
bên dưới).

**Các nhánh/worktree sau đây đóng băng, chưa xoá, giữ làm hồ sơ tham
khảo, KHÔNG dùng cho việc mới:**
- `claude/charming-bartik-d21dc1` — nguồn của lần fast-forward này, nay
  trùng lịch sử với `main` tính đến `6671db3`.
- `claude/charming-bartik-d21dc1-8335fa`, `claude/infallible-mayer-ea5023`,
  `claude/youthful-franklin-62cac4`, `claude/audit-gates-17-6-12-049aeb`
  — đứng nguyên tại `d7c283e` (=tip cũ của `main` trước hợp nhất), chưa
  từng có commit riêng, rỗng.
- `backup/root-wip-20260713` — snapshot toàn bộ working-tree-bẩn ở thư
  mục gốc *trước khi* hợp nhất (101 mục: xem chi tiết bên dưới). Giữ
  làm bằng chứng, không merge tiếp.

**Cảnh báo artifact tiền-fix** (CẬP NHẬT 2026-07-13, xem mục
"Regenerate artifact sau fix gate #6/#12/#17" bên dưới cho phần đã
thu hẹp): mọi watchlist/report/research-note nằm trong
`backup/root-wip-20260713` (tức là mọi thứ đã được sinh ra tại
thư mục gốc *trước* khi hợp nhất — `reports/`, `data/signals/`,
16+7 file `research_notes/generated/*.md`, các notebook đã chạy,
`config/core_universe.csv` bản cũ) **đến từ code CHƯA có các fix của
88 commit vừa hợp nhất** (score v2, sửa raw/adjusted-close, sửa
momentum_score leak, v.v.). **Không dùng trực tiếp các file này** —
cần regenerate lại bằng pipeline hiện tại của `main` trước khi tin
tưởng bất kỳ số liệu nào trong đó. Các file này KHÔNG được khôi phục
vào `main` (trừ output `stock-decision-engine/` của người dùng, đã
khôi phục có chủ đích — xem dưới).

**Phạm vi cảnh báo còn hiệu lực sau 2026-07-13**: `research_notes/generated/*.md`
(23 file, KHÔNG regenerate hàng loạt — xem mục bên dưới), mọi notebook
đã chạy trong `backup/root-wip-20260713`, `config/core_universe.csv`
bản cũ. Cảnh báo đã được GỠ cho `reports/top_watchlist.csv`,
`reports/daily_alpha_ranking.csv`, `data/signals/final_watchlist.csv`
— các file này đã regenerate trên code post-fix, xem mục kế tiếp.

**Chi tiết quá trình dọn working-tree-bẩn tại gốc** (thực hiện trước
khi fast-forward, theo yêu cầu người dùng, không xoá/discard gì):
1. Snapshot toàn bộ 101 mục bẩn tại gốc vào `backup/root-wip-20260713`
   (commit `4b66766`), sau đó gốc mới sạch để fast-forward.
2. `git merge --ff-only claude/charming-bartik-d21dc1` → HEAD `6671db3`.
3. Khôi phục có chủ đích output phân tích của người dùng ở
   `stock-decision-engine/` (64 file: `*_metrics.csv`, `*_sub_scores.csv`,
   `*_decision_summary.txt`, biểu đồ `.png` cho GEX/HDB/POW/STB/VIX/VPB,
   và notebook `stock_buy_decision.ipynb`) từ snapshot vào `main`
   (commit `cb4d7c9`) — đây là thành quả chạy thật của người dùng, cần
   giữ lại, khác với các artifact tiền-fix ở trên.
4. `src/validation/freshness_check.py` có 2 bản sửa không xung đột
   logic nhưng nằm cạnh nhau trong file (bản chưa commit ở gốc: tự suy
   core universe từ dữ liệu OHLCV thô cục bộ khi
   `config/core_universe.csv` chưa tồn tại; bản trên nhánh vừa hợp
   nhất: so khớp với lịch giao dịch thật, đã được audit xác nhận
   `IMPLEMENTED_AND_VALID`). Hợp nhất thủ công, giữ cả hai (commit
   `8d42be0`), xác nhận bằng `tests/test_freshness_check.py` (19/19
   pass).
5. Không phát hiện cron/LaunchAgent/tiến trình nào đang chạy tạo ra các
   file bẩn tại gốc (`crontab -l`, `~/Library/LaunchAgents/`, `ps aux`
   đều không có kết quả liên quan) — nguồn gốc nhiều khả năng là chạy
   tay ở phiên trước, không phải tiến trình định kỳ đang hoạt động.

## Đóng 3 critical gate (#6, #12, #17) + regenerate artifact — 2026-07-13

Vòng remediation trên `audit/critical_findings.md`'s P0-2/P0-3/P0-4 (=
gate #6/#12/#17). Gate #3 (P0-1, survivorship) **giữ nguyên OPEN**, không
đụng theo đúng ràng buộc của vòng này. 5 nhiệm vụ, mỗi nhiệm vụ 1 commit
riêng trên `main`, không push:

1. **NV1 (gate #17, commit `b966aa2`)** — gỡ toàn bộ họ `alpha_*` v1
   shadow khỏi mọi consumer không phải shadow-log. Không chỉ sửa
   `alpha_rs_score` trong `final_watchlist.py` như finding gốc mô tả —
   rà soát phát hiện thêm một leak độc lập trong
   `scripts/run_meta_ranking.py` (đã tái phát chính leak `momentum_score`
   từng fix trước đó, cộng toàn bộ 5 v1-shadow component khác). 2 test
   regression mới chặn mọi field trong `FORBIDDEN_V1_SHADOW_FIELDS`
   tái xuất hiện ở bất kỳ output nào.
2. **NV2 (gate #6, commit `28b9f60`)** — `src/data/dataset_config.py`
   là điểm cấu hình duy nhất cho mọi đường dẫn dataset chính thức; sửa
   ~17 file consumer (`build_portfolio_stack.py` và toàn bộ script/module
   khác) để import từ đó thay vì hard-code. Quarantine vật lý
   `data/processed/{clean_daily_ohlcv,stock_features,market_features}.parquet`
   bản nhiễm vào `data/quarantine_existing_v1/`, regenerate bản sạch từ
   `data/full_history_v2/raw`. Xác nhận 0% mismatch (trước đó tới 100%)
   trên mẫu 9 mã. Test AST-scan mới (`tests/test_dataset_config.py`)
   chặn hard-code đường dẫn ngoài `dataset_config.py`.
3. **NV3 (gate #12, commit `72be363`)** — mọi `portfolio_risk_report.json`
   giờ nhúng `lineage` (dataset_version, features SHA-256, số dòng,
   config hash, git commit hash, ngày sinh); `validate_lineage_metadata`
   raise nếu thiếu — quy ước "không lineage thì không commit" được thực
   thi bằng code, không chỉ ghi chú. Xác nhận: chạy `build_portfolio_stack.py`
   2 lần cho kết quả giống hệt (trừ timestamp); recompute độc lập theo
   đúng phương pháp 3-attempt của `audit/portfolio_math_validation.md`
   khớp report đã commit đến 1e-9 (trước đó 0/3 attempt khớp).
4. **NV4 (regenerate artifact, commit `ccad49f`)** — chạy lại
   `final_watchlist`/`daily_alpha_ranking`/`top_watchlist` trên pipeline
   đã fix + dataset v2, nhúng lineage. So sánh top-20 với bản tiền-fix
   trong `backup/root-wip-20260713`: `top_watchlist.csv` (không qua
   eligibility gate) đổi hoàn toàn 0/20 mã trùng — đúng như kỳ vọng vì
   `alpha_score` phụ thuộc trực tiếp `close`, vốn bị fix khỏi lỗi 2x
   raw/adjusted-close. `client_ready_watchlist` KHÔNG so sánh được vòng
   này — pipeline post-fix hiện cho ra 0 candidate hợp lệ (500/500 vào
   `data_review`), truy nguyên do `full_history_v2` có độ phủ ngày
   không đều theo từng mã (411/500 mã dừng ở 2026-07-06, 28 mã lẻ tới
   2026-07-09), khiến eligibility gate's `data_age_days>1` rule đánh
   `STALE_DATA` hàng loạt — đây là vấn đề Gate #3/eligibility-gate,
   ngoài phạm vi vòng này, chỉ ghi nhận + tạo task riêng, KHÔNG sửa.
   Chi tiết đầy đủ: `audit/NV4_ARTIFACT_REGENERATION_COMPARISON.md`.
   `research_notes/generated/*.md` (23 file) **không** regenerate hàng
   loạt theo đúng phạm vi yêu cầu — xem cảnh báo artifact tiền-fix ở
   mục trên.
5. **NV5 (nghiệm thu, commit này)** — full test suite: 256 passed, 1
   fail đã biết trước và ngoài phạm vi
   (`test_reversal_quality_score.py::test_full_history_calibration_matches_strategy_research_report`
   — hằng số hiệu chỉnh `DEFAULT_SIGNS`/`DEFAULT_WEIGHTS` tính trên dữ
   liệu cũ bị nhiễm, giờ lệch dấu so với dữ liệu sạch; đây là việc tune
   scoring, ngoài phạm vi vòng này, đã tạo task riêng theo dõi). Cập
   nhật `audit/critical_findings.md` (P0-2/3/4 → RESOLVED kèm commit
   hash, P0-1 → giữ OPEN) và `audit/audit_summary.json` (thêm
   `remediation_log`, không đụng điểm số gốc).

Trong lúc rà soát, phát hiện thêm 2 vấn đề ngoài phạm vi, đã tạo task
riêng để theo dõi (không sửa trong vòng này):
- `reversal_quality_score`'s hằng số hiệu chỉnh cần tính lại trên dữ
  liệu sạch (xem NV5 ở trên).
- `full_history_v2` có độ phủ ngày không đều theo từng mã, khiến
  eligibility gate hiện tại loại toàn bộ candidate — cần quyết định
  data-engineering (backfill bổ sung) và/hoặc policy (đổi ngày tham
  chiếu freshness) trước khi động vào Gate #3.

## Chẩn đoán blocker eligibility gate + fix reversal_quality_score — 2026-07-13 (vòng 2)

Sau vòng đóng gate #6/#12/#17, phát hiện eligibility gate loại 100%
candidate (0/500 hợp lệ). Vòng này: chẩn đoán trước, sửa gốc chỉ khi
đúng giả thuyết.

1. **Chẩn đoán (commit `801d3b0`)** — kiểm tra giả thuyết "gate chưa
   thích ứng quy ước bỏ dòng volume=0" nêu trong `DATA_BASELINE.md`
   caveat #3: **BÁC BỎ** cho vấn đề mass-rejection này. Kiểm tra trực
   tiếp raw parquet của VIC/FPT/VCB/HPG/VNM/MWG: không có dòng nào
   (kể cả volume=0) sau 2026-07-06 — tức thiếu dữ liệu thật, không
   phải "dòng hợp lệ bị lược". Nguyên nhân thật, đã ghi sẵn trong
   `DATA_BASELINE.md:20-21` từ trước: `full_history_v2` được fetch 2
   đợt — đợt chính đến 2026-07-06 (411/500 mã), đợt bổ sung 48 mã đến
   2026-07-10 (28 mã trong số đó chạm 07-09) — chưa từng đồng bộ lại.
   5 mã mẫu (VIC, FPT, DHA, VTO, APL) xác nhận: 4/5 mã có coverage
   95-96% so với lịch giao dịch thật, hoàn toàn sạch đến 07-06; chỉ bị
   gắn STALE_DATA vì `analysis_as_of` neo vào mốc mới nhất của nhóm 28
   mã ngoại lệ. Chi tiết đầy đủ:
   `audit/ELIGIBILITY_GATE_STALE_DATA_DIAGNOSIS.md`.
   Sau chẩn đoán, hỏi người dùng hướng đi tiếp — **chọn "dừng lại, chỉ
   báo cáo"** — không sửa gate, không chạy update dữ liệu online,
   không regenerate lại artifact NV4 trong vòng này. 3 phương án sửa
   thật đã liệt kê cho vòng sau.
2. **Fix `reversal_quality_score` (commit `e7c305c`)** — xác nhận đây
   là tính toán xác định (không phải tune): `derive_factor_weights` là
   hàm thuần của `compute_factor_ic`'s output, docstring module tự ghi
   rõ đây là quy trình hiệu chỉnh định kỳ. Chạy lại đúng quy trình đó
   trên dữ liệu sạch: `DEFAULT_WEIGHTS`/`DEFAULT_SIGNS` đổi từ
   `{0.39,0.32,0.29 / -1,-1,-1}` (tính trên dữ liệu cũ bị nhiễm) sang
   `{0.22,0.20,0.58 / +1,+1,-1}`. Phát hiện đáng chú ý (chỉ báo cáo,
   không quyết định thêm): IC của `distance_ma20`/`return_20d` gần như
   biến mất và đổi dấu trên dữ liệu sạch — tín hiệu mean-reversion cũ
   không sống sót qua fix dữ liệu; `realized_vol_20d` vẫn giữ IC âm và
   giờ chiếm ưu thế trong tổ hợp. Rà nhanh (chỉ liệt kê, chưa sửa) các
   hằng số hard-code khác có ghi nguồn gốc từ IC/dữ liệu:
   `src/alpha/scoring.py`'s tổ hợp `alpha_score` v2 (70%
   realized_vol_20d / 30% value_ma20, trích t-stat từ
   `SCORE_FORENSIC_REPORT.md`/`SCORE_V2_REPORT.md`) là ứng viên rõ
   ràng duy nhất khác — chưa xác minh được tính trên dữ liệu cũ hay
   mới, để vòng sau kiểm tra riêng.
3. **Nghiệm thu** — full suite: 257 passed (không còn fail nào). Commit
   riêng từng nhiệm vụ vào `main`, không push.

## Đồng bộ full_history_v2 + cơ chế cập nhật giá hằng ngày — 2026-07-13 (vòng 3)

Xác nhận với `task_42360495` (đã dừng, đã đối chiếu, không đụng code) trước
khi bắt đầu. Đóng nguyên nhân gốc đã chẩn đoán ở vòng 2: `full_history_v2`
có 2 đợt fetch chưa từng đồng bộ, không có cơ chế cập nhật hằng ngày.

1. **NV1 — Đồng bộ về một mốc (commit `296a2f4`)** — chạy fetch trực tiếp
   (`get_daily_ohlc`, single-call, KHÔNG bao giờ dùng đường chunked/fallback
   — đúng cơ chế đã miễn nhiễm với bug raw/adjusted-close) cho toàn bộ 501
   mã, từ mốc hiện có của từng mã đến ngày giao dịch gần nhất phát hiện qua
   VNINDEX (`get_daily_index`, không phải `get_daily_ohlc` — endpoint chỉ số
   khác endpoint cổ phiếu). Kết quả: 441/501 mã (88%) chung mốc 2026-07-13;
   42 mã lệch 3-10 ngày (thanh khoản thấp, có thật); 18 mã lệch 12-1634
   ngày (ASA/ART/AMD/KPF/PSH/ATB/TCD/BCG/BBC/SVI/ARM/LGC/APL/SSC/ACS/ATS/
   ADC/TTE) — xác nhận qua chính lần fetch trực tiếp hôm nay (không phải suy
   từ snapshot cũ) là không còn phiên khớp lệnh nào kể từ ngày cuối, khả
   năng ngừng giao dịch thật. Cập nhật `DATA_BASELINE.md`.
2. **NV2 — `scripts/update_prices_daily.py` (commit tiếp theo)** — đối
   xứng `update_disclosure_daily.py`: fetch incremental từ max(date) từng
   mã, checkpoint qua `manifest.json`, quality-flag (|return|>20%, toàn
   volume=0) không chặn append, log JSONL. Chạy 2 lần liên tiếp để kiểm
   chứng idempotent: lần 2 ban đầu vẫn báo "UPDATED" cho 60 mã ít giao dịch
   (vì fetch lại thành công nhưng không có phiên mới) — sửa để phân biệt
   trạng thái `NO_NEW_DATA` (không đổi file/manifest) khỏi `UPDATED` (có
   dữ liệu mới thật); chạy lại lần 3: `n_updated: 0, total_new_rows: 0` —
   no-op sạch.
   **Quy trình vận hành** (bổ sung vào quy ước repo): chạy
   `scripts/update_prices_daily.py --universe` và
   `scripts/update_disclosure_daily.py --universe` **trước** khi sinh
   watchlist (`scripts/run_daily_pipeline.py`). Gate STALE_DATA trong
   `final_watchlist.py` là chốt chặn cuối nếu quên chạy update — không phải
   cơ chế cập nhật, không dựa vào nó để tự động lấy dữ liệu mới.
