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
3. **NV3 — Rebuild features + regenerate artifact (commit `a184047`)** —
   `data/raw/index_ohlcv` (nguồn VNINDEX/benchmark) là dữ liệu tách biệt
   khỏi `full_history_v2`, vẫn dừng ở 2026-07-06 sau khi đồng bộ giá cổ
   phiếu — chạy thêm `scripts/update_index_data.py` (cơ chế đã có sẵn,
   không phải viết mới) trước khi `generate_features.py` để tránh
   benchmark/stock_features lệch mốc nhau. Sau đó chạy
   `run_daily_pipeline.py --offline`: gate giờ cho qua
   `client_ready=10, trading=20, research=174, data_review=296`
   (`freshness_status: OK`, trước đó `ERROR` với 500/500 bị loại). Lý do
   loại trong 296 mã còn lại giờ chủ yếu là tiêu chí kinh doanh thật
   (`LOW_LIQUIDITY`, `SEVERE_DISTRIBUTION_RISK`), `STALE_DATA` chỉ còn
   đúng 60 mã đã xác định ở NV1 — không còn là lỗi hàng loạt.
   `client_ready_watchlist` so với bản tiền-fix: 5/10 mã trùng (MSB, CTS,
   NAB, BMP, VIC) — hợp lý, phản ánh đúng các fix điểm số + dữ liệu, không
   phải xáo trộn toàn bộ. Chi tiết đầy đủ:
   `audit/NV4_ARTIFACT_REGENERATION_COMPARISON.md` (mục cập nhật
   2026-07-13).
4. **NV4 — Nghiệm thu** — full suite: 263 passed. Không có mục nào trong
   `audit/critical_findings.md` nhắc tới eligibility-gate/coverage-gap này
   (vấn đề mới phát sinh và đã đóng trong chính vòng này, không phải P0/P1
   đang mở) nên không cần cập nhật thêm ở đó. Commit riêng từng nhiệm vụ
   vào `main`, không push.

## GĐ2 — Vệ sinh dữ liệu nhỏ theo PATH_TO_100.md mục 1-2 (8 nhiệm vụ)

1. **NV1 (commit `fbdd4b0`)** — mở rộng `NATURAL_KEY` disclosure thêm
   `direction` + `shares_registered_or_changed` (cứu 76% trong 829 dòng
   trùng khóa), thêm `dedup_seq` (tiebreaker theo thứ tự dòng) cho 196 dòng
   còn lại — 0 va chạm còn sót trên parse thật. Parse lại từ tầng thô
   (không crawl lại), ingest lại toàn bộ: `events.parquet` 56.870 → 57.282
   dòng (+412). `DISCLOSURE_BASELINE.md` cập nhật caveat #1 → RESOLVED.
2. **NV2 (commit `2f53cda`)** — lịch nghỉ Tết âm lịch 2020-2027 vào
   `config/vn_market_holidays.csv`, suy ra TRỰC TIẾP từ dữ liệu thật (ngày
   nào cả 501 mã đều không giao dịch = ngày nghỉ), đối chiếu 2 chiều với
   `full_history_v2` khớp 100% (0 lệch). 2027 (Tết + ngày bù 1/5) chưa có
   dữ liệu thật, đánh dấu ƯỚC TÍNH kèm nguồn (web search, cột `source`
   riêng). Rà toàn bộ nơi đếm ngày giao dịch (`next_trading_day`,
   `expected_latest_trading_date`, `trading_sessions_behind`) — xác nhận
   tất cả đã dùng chung `load_market_holidays()`, không sửa gì thêm.
3. **NV3 (commit `edf79af`)** — bảng `trading_status` point-in-time
   (append-only, chỉ ghi dòng mới khi trạng thái đổi), phân loại
   ACTIVE/STALE_SHORT/INACTIVE_LONG theo gap-to-latest. Gate loại 18 mã
   INACTIVE_LONG qua cơ chế trạng thái sống (không hard-code danh sách).
   Sửa một lỗi rò rỉ dữ liệu test thật (test ghi đè file thật của dự án do
   thiếu tham số `status_path` cô lập) trong lúc nối dây.
4. **NV4 (commit `c318df0`)** — hợp nhất `load_universe_symbols`
   (disclosure) và `get_universe_symbols` (giá) về một hàm duy nhất
   (`src/data/universe.py::tracked_universe_symbols`) — xác nhận đúng lỗi:
   GEE bị loại khỏi crawl nhưng KHÔNG bị loại khỏi validate disclosure
   trước khi sửa.
5. **NV5 (commit `3c66f36`)** — `validate_ohlcv` thêm 4 nhóm check (OHLC
   đầy đủ high/low vs open/close, khoảng trống lịch giao dịch bất thường
   — dùng đúng lịch Tết ở NV2, return vượt biên độ sàn dùng đúng cơ chế G4
   sẵn có, dtype/schema drift). Nhúng git commit hash + config version vào
   6 file metadata còn thiếu (sector_board, cashflow_board, research_notes,
   sector_map_coverage, portfolio_stack — 2 chỗ, pipeline_metadata).
6. **NV6 (commit `f46b2cc`)** — tỷ lệ ngày-vắng-dòng trong 60 phiên gần
   nhất làm proxy đình chỉ. Kiểm tra thực tế trước khi nối dây: dải tỷ lệ
   của STALE_SHORT và INACTIVE_LONG CHỒNG LẤN nhau (0.12-0.95 vs 0.0-0.40)
   — không thể tách rạch ròi bằng tỷ lệ này — nên gộp vào đúng lý do
   `LOW_LIQUIDITY` sẵn có, không tạo trạng thái cạnh tranh mới (đúng yêu
   cầu "một logic, không hai"). Phát hiện + sửa một vấn đề hiệu năng thật:
   tính tỷ lệ ngay trong gate làm chậm test suite 3 lần (8s→27s) vì phải
   quét 500 file mỗi lần gọi — chuyển sang snapshot tính trước 1 lần/ngày.
7. **NV7 (commit `23607d4`)** — báo cáo sector mapping (chỉ báo cáo, không
   sửa code): 96.4% phủ (482/500), tác động thật hiện tại chỉ 4 mã (đều ở
   research_candidates, không mã nào ở client_ready/trading). Xác nhận
   sector mapping hiện là báo-cáo-thuần trên đường sản xuất thật —
   `check_sector_constraints` (cap 35%) đã có sẵn nhưng chỉ nối vào module
   Monte Carlo không dùng trong production, không nối vào
   `build_portfolio_stack.py`. 2 phương án + hệ quả để người dùng quyết
   vòng sau.
8. **NV8 — Nghiệm thu (commit này)** — full suite: 295 passed. Commit
   riêng từng nhiệm vụ vào `main`, không push.

## GĐ3 — Prereg + event study disclosure×giá (kết quả: âm tính, H2 bị thách thức)

Session mới sinh ra tại một worktree (`.claude/worktrees/vietnam-quant-setup-5304a5`)
thay vì thư mục gốc — đúng theo `CLAUDE.md` mục 1, đã DỪNG lại xin xác nhận trước
khi làm gì, người dùng chọn "chuyển về gốc" — mọi commit dưới đây thực hiện tại
`/Users/jamesb/Desktop/vietnam-quant-research`, branch `main` (dùng `git -C`/đường
dẫn tuyệt đối do shell cwd tự kéo về worktree giữa các lệnh). Bổ sung một dòng làm
rõ quy ước này vào `CLAUDE.md` mục 1 (commit `0673cea`).

1. **NV0a (commit `86643ce`)** — đối soát 20/196 dòng disclosure còn phụ thuộc
   `dedup_seq` (tiebreaker theo thứ tự dòng, phần còn lại sau khi mở rộng
   `NATURAL_KEY` ở GĐ2 NV1) đối chiếu trực tiếp `raw_payload` (JSON nguồn, không
   chỉ cột đã parse): **20/20 là giao dịch thật khác nhau** (khác cửa sổ đăng ký
   `PlanBeginDate`/`PlanEndDate`, thường khác cả `RealBuyVolume`/`VolumeAfterTransaction`),
   0/20 là bản ghi đúp thật — không cần sửa thêm khóa, caveat #1 giữ nguyên
   RESOLVED. Số "417 dòng vẫn bị gộp" trong đề bài gốc là số học tiền-fix
   (829−412), không khớp trạng thái code/dữ liệu hiện tại (thực tế 196 dòng/98
   nhóm phụ thuộc `dedup_seq`) — đã ghi rõ chênh lệch này kèm bằng chứng vào
   `DISCLOSURE_BASELINE.md`.
2. **NV0b (commit `9c0773b`)** — web search lịch nghỉ HOSE: phát hiện thiếu
   2026-08-31 + 2026-09-01 (chỉ có 2026-09-02) trong `config/vn_market_holidays.csv`
   — Quốc khánh 2026 nghỉ giao dịch 3 ngày (Hai 31/8 → Tư 2/9), xác nhận CHÍNH
   THỨC qua 3 nguồn độc lập (HOSE/cafef.vn, VSD/VSDC thông báo 2025-11-21,
   dnse.com.vn) — đã bổ sung, ghi rõ nguồn + ngày tra cứu 2026-07-14. Lịch 2027
   vẫn CHƯA được công bố chính thức (xác nhận qua tìm kiếm — Bộ LĐTBXH/Bộ Nội vụ
   thường công bố Tết vào tháng 8-11 năm trước) — giữ nguyên các dòng ESTIMATED,
   chỉ củng cố trích dẫn (Giỗ Tổ Hùng Vương 2027 xác nhận độc lập 16/4 Thứ Sáu;
   ngày nghỉ bù 1/5 rơi Thứ Bảy trích dẫn cơ sở pháp lý Điều 111 Bộ luật Lao động
   2019). 90 dòng, 0 trùng ngày, test suite phụ thuộc lịch nghỉ vẫn 41/41 pass.
3. **NV1 (commit `7381185`)** — `DISCLOSURE_EVENT_STUDY_PREREG.md`, khóa TRƯỚC
   khi viết code join disclosure×giá (FIREWALL hiệu lực từ Round 5 tới giờ, đây
   là lần đầu tiên hai nguồn được nhìn cùng nhau). Khóa: định nghĩa S1/S2/S3 (chỉ
   pha REGISTRATION, cấm tuyệt đối field RESULT/tỷ lệ thực hiện), quy tắc
   point-in-time `available_at` (phát hiện 100% dòng hiện tại là
   `is_backfilled=True`, tức toàn bộ kết quả phụ thuộc giả định lag +1 ngày giao
   dịch — độ nhạy +1/+3/+5 là bắt buộc, không phải phụ), rổ đủ điều kiện (3 tỷ +
   `trading_status`, quyết định rõ dùng snapshot hiện tại vì bảng point-in-time
   chỉ có lịch sử thật từ 2026-07-13), nhãn "bùng nổ" (tái dùng nguyên định nghĩa
   `EVENT_DETECTION_REPORT.md` đã pre-register, không phát minh mới), lift +
   block bootstrap (khối 60 ngày, N=1000, seed=42), lát cắt 3 giai đoạn × 2 nhóm
   thanh khoản (tái dùng biên giai đoạn cũ), tiêu chí PASS/ỨNG VIÊN/âm tính 3 bậc,
   cách diễn giải riêng cho S3 (đối chứng H2, không dùng lại nguyên tiêu chí của
   S1/S2), test phụ CAR + gộp cụm sự kiện <20 ngày.
4. **NV2 (commit `5f8f2b6`)** — chạy đúng prereg, một lần
   (`scratch/disclosure_event_study.py`). Phát hiện + sửa 1 bug trước khi coi kết
   quả là cuối cùng (không phải tune theo kết quả): 387 dòng `stock_features.parquet`
   có `close<=0` (lỗi dữ liệu đã biết, ngoài phạm vi round) làm CAR ra `inf`/`nan`
   cho một số sự kiện S1 — sửa bằng đúng convention loại giá không dương đã có ở
   `src/features/returns.py::add_returns`, chạy lại toàn bộ một lần nữa. Kết quả +
   lineage (git hash, sha256 + số dòng mọi input, hash prereg) trong
   `data/disclosure/event_study_results.json`.
5. **NV3 (commit `b95cc37`)** — `DISCLOSURE_EVENT_STUDY_REPORT.md`. **Test chính
   (lift bùng nổ): NEGATIVE cho cả S1/S2/S3 ở cả 3 lag**, ổn định qua độ nhạy lag
   (không cần gắn cờ "tín hiệu mong manh"). Mẫu hình mô tả đáng chú ý: lift(S1)
   giảm đơn điệu qua 3 giai đoạn (1.14 → 0.84 → 0.31), đảo chiều hẳn so với H1 ở
   giai đoạn gần nhất. **Test phụ (CAR) thách thức H2**: S3 (bán, đối chứng) có
   CAR dương và tăng theo cửa sổ, độ lớn gần ngang S1/S2 (mua) thay vì CAR≤0 như
   H2 dự đoán — phân loại đúng nhánh "H2 bị thách thức" đã khóa sẵn trong prereg,
   không diễn giải lại cho khớp giả thuyết. Theo đúng ràng buộc gốc: **báo cáo,
   dừng lại — không thử thêm cửa sổ/ngưỡng/vai trò mới trong round này.**

**Nghiệm thu GĐ3**: không chạy full test suite riêng cho round này (không có code
sản xuất nào bị đổi — `scratch/disclosure_event_study.py` là script nghiên cứu
một lần, không nối vào pipeline; thay đổi duy nhất chạm production code là
`config/vn_market_holidays.csv`, đã xác nhận 41/41 test phụ thuộc lịch nghỉ pass
ở NV0b). Commit riêng từng nhiệm vụ vào `main`, không push.

## GĐ3.5 — Khám nghiệm có ranh giới: định lượng bias + đóng hồ sơ nhánh (3 nhiệm vụ)

Vòng theo dõi trực tiếp GĐ3, xuất phát từ phát hiện phụ "CAR(S3, bán) ≈ CAR(S1,
mua)" ở `DISCLOSURE_EVENT_STUDY_REPORT.md`. Toàn bộ EXPLORATORY — không kiểm
định lại H1/H2 đã khóa, không mở prereg mới, không chạy test xác nhận nào.

1. **NV1 (commit `7445ca9`)** — `SURVIVORSHIP_BIAS_ESTIMATE.md`: dùng S3 làm
   placebo, đối chiếu chéo bằng excess return không điều kiện sự kiện của TOÀN
   BỘ `(mã, ngày)` trong rổ đủ điều kiện (N=325k–347k, độc lập hoàn toàn với
   việc chọn sự kiện disclosure). Ba ước lượng (placebo S3, gộp tất cả sự kiện,
   không điều kiện) cùng dấu dương, cùng dạng tăng theo cửa sổ, CI chồng lấn
   nhau — nhất quán với giả thuyết survivorship bias nhưng KHÔNG phải bằng
   chứng phân tách nguyên nhân (ghi rõ trong tài liệu). Đề xuất mức sàn hiệu
   chỉnh ~+0.4%/+1.2%/+2.9% ở cửa sổ 20/60/120 ngày cho mọi backtest long-only
   diễn giải excess return, hiệu lực đến khi có point-in-time universe thật
   (Gate #3). Trích dẫn vào `DATA_BASELINE.md` caveat #2.
2. **NV2 (commit `a140633`)** — mục "Exploratory addendum" cuối
   `DISCLOSURE_EVENT_STUDY_REPORT.md`: autopsy mô tả thuần (không CI, không kết
   luận) CAR(S1) theo 4 lát cắt — quy mô đăng ký/ADV (không có dữ liệu free-float
   nên dùng `volume_ma20` theo đúng nhánh dự phòng đã nêu), vai trò người đăng
   ký, cụm nhiều người nội bộ cùng đăng ký trong 20 ngày, nhóm thanh khoản/quy
   mô (`value_ma20` tam phân vị, proxy vốn hóa vì không có dữ liệu vốn hóa
   thật). Hai lát cắt đáng chú ý nhất để sinh giả thuyết cho prereg tương lai:
   "người liên quan gia đình" có CAR cao hơn chính người có chức vụ; cụm ≥2
   người nội bộ cùng đăng ký có median CAR dương ở +60/+120 ngày trong khi đăng
   ký đơn lẻ thì âm. Lát cắt theo quy mô/thanh khoản (mã nhỏ CAR cao hơn mã lớn)
   được gắn cờ là khả năng trùng chính confound survivorship bias đã định lượng
   ở NV1, không phải phát hiện riêng.
3. **NV3 (đóng hồ sơ, commit này)** — xem mục bên dưới.

**Đóng hồ sơ nhánh "disclosure như tín hiệu bùng nổ"**: kết luận âm tính (test
chính NEGATIVE cả 3 tín hiệu × 3 lag ở GĐ3, H2 bị thách thức bởi test phụ CAR ở
cùng round, và phần lớn "excess return" đo được nhiều khả năng là survivorship
bias của chính universe theo GĐ3.5/NV1) — không có tín hiệu disclosure nào đạt
PASS/ỨNG VIÊN trong thiết kế đã pre-register. Nhánh này đóng lại ở đây; không mở
tiếp mà không có yêu cầu/prereg mới từ người dùng.

**Pipeline disclosure GIỮ NGUYÊN chạy live, không tắt** — kết luận âm tính của
nhánh event-study KHÔNG có nghĩa dữ liệu disclosure vô giá trị:
`scripts/update_disclosure_daily.py` vẫn là một phần quy trình vận hành đã ghi ở
vòng 3 (chạy trước khi sinh watchlist/report, cùng `update_prices_daily.py`).
Hai lý do dữ liệu này vẫn quý: (a) tin hủy niêm yết/sáp nhập/đình chỉ thường đi
kèm hoạt động giao dịch nội bộ bất thường trước đó — một nguồn tín hiệu tiềm
năng cho point-in-time universe (Gate #3, `audit/PATH_TO_100.md`) khi nào có
nguồn dữ liệu hủy niêm yết chính thức để đối chiếu; (b) hai lát cắt sinh giả
thuyết ở NV2 trên (người liên quan gia đình, cụm nhiều người nội bộ) vẫn cần dữ
liệu sống để kiểm định trong một prereg tương lai nếu người dùng quyết định theo
đuổi tiếp.

## GĐ3.6 — Phát súng cuối: đối chứng khớp cặp cho 2 giả thuyết cụm/gia đình (đóng nhánh vĩnh viễn)

Vòng theo dõi trực tiếp GĐ3.5, kiểm định XÁC NHẬN (không còn exploratory) hai
giả thuyết đã sinh ra ở addendum trước — cả hai đều trùng prior trong văn liệu
insider-trading học thuật (cluster buying, family-related buying). Khác biệt
cốt lõi: so DCAR với **đối chứng khớp cặp** (5 mã cùng tercile thanh khoản,
cùng `trading_status=ACTIVE`, "sạch" không có disclosure trong `[t−60,t+120]`)
thay vì so CAR với 0 — triệt tiêu phần lớn survivorship drift (~+2.9%/120 ngày,
định lượng ở GĐ3.5/NV1) khỏi cả hai vế của phép so sánh.

1. **NV1 (commit `8e47dfc`)** — `DISCLOSURE_PREREG_2_CLUSTER.md`, khóa TRƯỚC
   code. H1 (cụm mua, ≥2 người nội bộ khác nhau/20 ngày/cùng mã — tái dùng đúng
   `multi_insider_cluster` đã tính từ round trước), H2 (người liên quan gia
   đình — tái dùng đúng `role_group`), H0 nội bộ (đơn lẻ, không cụm không gia
   đình — vai trò kiểm tra tính hợp lệ của chính thiết kế đối chứng, không phải
   giả thuyết cần thắng). Tiêu chí PASS: CI dưới DCAR > 0 đồng thời ở CẢ +60 VÀ
   +120 ngày, VÀ dấu dương ổn định ≥2/3 giai đoạn (tái dùng nguyên biên giai
   đoạn cũ). N(nhóm)<30 → mô tả + đóng nhánh, không hạ tiêu chí. Ghi nhận trung
   thực ngay trong prereg: N thực tế theo addendum trước (~909 cụm, ~556 gia
   đình) cao hơn nhiều "dự kiến không nhiều" của yêu cầu gốc.
2. **NV2 (commit `02be8c0`)** — chạy đúng prereg, một lần. N báo trước kết quả:
   2,318 sự kiện S1 gộp cụm (2,320 ở lag +3/+5, lệch biên gộp cụm nhỏ khi dịch
   `available_at`) → H1=1,023, H2=607, H0=946; 448 sự kiện (19.3%) bị loại vì
   không tìm được đối chứng hợp lệ (báo cáo, không lặng lẽ bỏ qua); trung bình
   4.88/5 đối chứng dùng được mỗi sự kiện giữ lại. Cả ba nhóm vượt xa ngưỡng 30
   sự kiện tối thiểu ở mọi cửa sổ — không rơi vào nhánh N không đủ.
3. **NV3 (commit `3b4986c`)** — `DISCLOSURE_PREREG_2_REPORT.md`. **Cả H1, H2,
   H0 đều NEGATIVE ở cả 3 lag** — không nhóm nào đạt CI dương đồng thời ở +60
   VÀ +120. H0 âm tính xác nhận thiết kế đối chứng không rò rỉ false positive.
   Gần đạt nhất: H2 (gia đình) có CI dương riêng lẻ ở +20/+60 (lag +1/+5), nhưng
   +120 luôn chứa 0 và hiệu ứng dương gần như chỉ đến từ Giai đoạn 1
   (2020–2022, DCAR+120 trung bình +11.3%) — Giai đoạn 2/3 phẳng-đến-âm, đúng
   mẫu hình "hiệu ứng chỉ sống ở giai đoạn dữ liệu sớm" đã thấy lặp lại ở H1/S1
   trước đó. Verdict ổn định qua cả 3 lag, không cần gắn cờ mong manh.

**Đóng nhánh "disclosure như tín hiệu" VĨNH VIỄN cho mục đích tín hiệu** — đây
là round kiểm định có pre-register thứ 3 (test lift/CAR gốc → định lượng
survivorship bias → đối chứng khớp cặp cho 2 giả thuyết có prior học thuật) và
không round nào tìm được nhân tố disclosure đạt ngưỡng ứng viên, kể cả sau khi
đã loại bỏ đúng confound survivorship đã định lượng. Theo đúng ràng buộc đã
khóa: không mở thêm biến thể nào sau kết quả này. **Pipeline
`scripts/update_disclosure_daily.py` vẫn chạy live** trong quy trình vận hành
— lý do giữ lại không đổi so với GĐ3.5 (tiềm năng point-in-time universe qua
tin hủy niêm yết, Gate #3; dữ liệu vẫn sẵn sàng nếu có hướng nghiên cứu khác
không liên quan "dự báo bùng nổ/vượt trội giá" trong tương lai).

## GĐ4 — Kiểm định composite `final_watchlist` lần đầu (kết quả: Nhánh C, chuyển sang không xếp hạng alpha)

`audit/PATH_TO_100.md` mục 3: 75/100 điểm trọng số composite (trend 25 +
momentum 20 + relative_strength 20 + liquidity 10 + volume 5 + risk 10 +
signal 10) chưa từng được kiểm định ở cấp độ tổng thể. Round này: thiết kế +
cây quyết định A/B/C commit trước, chạy một lần, thi hành đúng nhánh trúng.

1. **NV1 (commit `eb765e6`)** — `WATCHLIST_VALIDATION_PREREG.md`. Composite =
   `base_final_score` (trước `warning_penalty` — đúng khung "75/100 điểm trọng
   số" của `PATH_TO_100.md`, không phải `final_score`). Universe =
   `trading_status ACTIVE`. Tái dùng nguyên máy móc IC Newey-West + null test
   đã kiểm chứng ở `SCORE_V2_DESIGN.md`/`score_v2_ic_test.py`/`score_v2_null_test.py`
   — không viết công thức mới. Cây quyết định A/B/C khóa nguyên văn, kèm quy
   tắc "vùng xám → chọn nhánh thận trọng hơn". Hai quyết định khóa sẵn không
   phụ thuộc nhánh: gỡ `liquidity_score` khỏi ranking ở mọi nhánh (bằng chứng
   sẵn có nhiễm survivorship bias); sector mapping không bắt buộc eligibility
   nhưng bắt buộc cho sector-cap (mã thiếu mapping → bucket `UNKNOWN`, cap như
   một ngành thật).
2. **NV2 (commit `36bba52`, script tại `eb765e6`..)** — chạy đúng prereg.
   **Bug thật tìm thấy và sửa giữa chừng**: lần chạy null test đầu cho
   percentile=0.0 tuyệt đối ở MỌI fold, phương sai null=0 — vết tích của một
   lỗi trùng tên cột (`meta_score`) giữa panel và tham số truyền vào
   `run_portfolio_backtest`, khiến bước sắp xếp theo điểm bị bỏ qua hoàn toàn
   (real và random chọn đúng cùng danh mục). Sửa, chạy lại. Kết quả cuối:
   composite IC gần như phẳng (t_NW full/residualized=−0.40, không cùng dấu 3
   giai đoạn); null test trung bình 63.8 nhưng fold 2026 sụp xuống percentile
   0.15 (<<10) — thất bại rõ ràng cả hai vế tiêu chí. Phát hiện phụ: 4/7 thành
   phần yếu/không ý nghĩa; `liquidity_score` đảo chiều có ý nghĩa (t_NW=−4.19,
   xác nhận trực tiếp quyết định gỡ đã khóa sẵn); `risk_score` là thành phần
   duy nhất có bằng chứng mạnh đứng riêng (t_NW=+4.72, đồng dấu dương 3 giai
   đoạn); `signal_score` không tính được (`meta_ranking.parquet` hóa ra là
   snapshot hiện tại, không phải chuỗi lịch sử như prereg mô tả nhầm ban đầu);
   `momentum_score`≡`relative_strength_score` về mặt toán học (trừ hằng số
   theo ngày không đổi thứ hạng cross-sectional) — dư thừa thật trong công
   thức, ghi nhận không sửa.
3. **NV3 (commit `c0a4d82`, `a76b69c`, `450b166`)** — mốc so sánh "watchlist
   tối giản" (v2 + gate hiện hành) chạy mới: null avg 52.8 (<60, không đạt dù
   không fold nào <10) và IC giai đoạn 1 = 2.90 (thiếu 0.10 so ngưỡng 3.0) —
   SÁT nhưng không đạt theo đúng chữ tiêu chí đã khóa. → **Nhánh C** (đúng quy
   tắc "vùng xám → chọn nhánh thận trọng hơn", không tự nới lỏng để "cứu"
   Nhánh B dù trực giác watchlist tối giản có vẻ là tín hiệu thật và
   `alpha_score` v2 của chính nó đã được xác nhận riêng ở một bài test khác
   với ngưỡng lỏng hơn). Thi hành: `final_watchlist.py` thêm
   `ranking_mode="no_alpha_liquidity_sort"` — xếp hạng theo `value_ma20`, bỏ
   ngưỡng `final_score`, dán nhãn rõ trong `reason`; `liquidity_score` gỡ khỏi
   `base_final_score` (10 điểm phân bổ lại tỷ lệ thuận 6 thành phần còn lại);
   thêm sector-cap thật đầu tiên vào `client_ready_watchlist`/`trading_watchlist`
   (trước đây hoàn toàn không có); mở rộng `assert_no_forward_columns` vào
   `src/alpha/scoring.py`/`run_alpha_scoring.py`.
4. **NV4 (commit `776ae6a`, `f27fe0d`, `36bba52`)** — chạy
   `update_prices_daily.py` + `update_disclosure_daily.py` + `update_index_data.py`
   + `run_daily_pipeline.py --offline` theo đúng quy trình chuẩn. 2 bug thật
   tìm thấy khi regenerate thật (không phải lúc test đơn vị): `value_ma20` bị
   cắt khỏi output vì chưa có trong `FINAL_WATCHLIST_COLUMNS`, làm
   `apply_post_cashflow_overlay`'s lần gọi thứ hai trong cùng pipeline
   `KeyError` — thêm cột vào schema cố định; nhãn "không xếp hạng alpha" bị
   chèn lặp đôi vì hàm chạy 2 lần/pipeline — sửa idempotent. So sánh top-10
   `client_ready` (chỉ `data/signals/final_watchlist.csv` có bản "trước" trong
   git — `data/output/*.csv` bị gitignore, không có bản nền): trùng 1/10
   (VIC) — đúng dự kiến khi đổi hẳn tiêu chí xếp hạng, không phải lỗi. Ghi rõ
   giới hạn: dữ liệu cũng mới hơn 2 ngày, không tách bạch được hiệu ứng code
   vs hiệu ứng data trong phép so sánh này.
5. **NV5 (commit `b0ca2fb`)** — `WATCHLIST_VALIDATION_REPORT.md` đầy đủ; cập
   nhật `audit/PATH_TO_100.md` mục 3 (đóng khoảng trống kiểm định — kết quả âm
   tính, không phải điểm số học đạt được; `liquidity_score`/`assert_no_forward_columns`/
   trích dẫn bằng chứng trong config đều XONG; `tail_ratio_60d` trong
   `risk_score` vẫn mở, ngoài phạm vi round này). Full test suite: 295 passed
   sau mọi thay đổi. Commit riêng từng nhiệm vụ vào `main`, không push.

**Không có nhân tố alpha nào trong `final_watchlist.py` được coi là đã kiểm
định sau round này** — pipeline tiếp tục dùng `alpha_score` v2 nguyên trạng ở
các nơi khác (không bị round này rút lại, vì v2 đã qua bài test riêng của
chính nó). Ứng viên rõ nhất cho một prereg đơn-nhân-tố tương lai:
`risk_score` (t_NW=+4.72, đồng dấu dương 3 giai đoạn).

## GĐ5 — Robustness thống kê (PATH_TO_100 mục 9) + giải 2 căng thẳng từ GĐ4

Toàn bộ round: KIỂM ĐỊNH LẠI, không nhân tố mới, không tune — đo và kết luận.
Không đổi tham số/trọng số nào của v2 hay `final_watchlist.py` bất kể kết quả
(đúng ràng buộc gốc).

1. **NV1 (commit `fcafd05`)** — `V2_STABILITY_NOTE.md` giải nghịch lý
   percentile 71.0 (`SCORE_V2_REPORT.md`) vs 52.8 (`WATCHLIST_VALIDATION_REPORT.md`
   GĐ4). 3 nghi phạm liệt kê trước: khác cỗ máy (loại ngay), dữ liệu mới, 2
   gate GĐ4 thêm (`trading_status==ACTIVE`, `minimal_eligible`). Chạy lại
   nguyên văn script gốc trên dữ liệu hiện hành: vẫn 71.0 → loại trừ dữ liệu.
   Chạy thêm 1 cấu hình (ACTIVE-only, không `minimal_eligible`): 70.5 → gần
   như không đổi. **Kết luận bằng loại trừ: gate `minimal_eligible` của
   `final_watchlist.py` (ATR/distance_ma20/drawdown/giá sàn, không chỉ thanh
   khoản) là nguyên nhân gần như toàn bộ chênh lệch.** Khuyến nghị: 71.0
   không còn hợp lệ để trích dẫn cho v2 hoạt động bên trong pipeline đầy đủ
   của `final_watchlist.py`, cần kiểm định lại nếu có quyết định dùng lại v2
   làm cơ sở xếp hạng.
2. **NV2 (đã hoàn thành trước NV1 do chạy song song)** — t_NW của
   `realized_vol_20d`/`value_ma20` trên dữ liệu hiện hành: **−5.48/−3.37**, so
   với **−5.41/−3.33** gốc — cùng dấu, cùng bậc, nhích mạnh hơn nhẹ. Xác nhận,
   không đổi gì.
3. **NV3** — khám nghiệm `risk_score`: corr trung bình ngày với `v2_score`
   = **+0.822** (rất cao), với `realized_vol_20d` = −0.870. Phân rã t=+4.72:
   `atr_pct_14` (t=−5.70) và `realized_vol_20d` (−5.48) mang gần hết bằng
   chứng; `tail_ratio_60d` (t=+0.98) không có ý nghĩa; `risk_penalty_score`
   luôn trung lập (dữ liệu snapshot, không phải lịch sử — phát hiện từ GĐ4).
   **Kết luận (i): risk_score ≈ cụm vol, bằng chứng trùng với v2 — KHÔNG soạn
   prereg đơn-nhân-tố riêng.**
4. **NV4 (commit `9b6edc2`)** — BH-FDR (q=0.05) trên 214 test gộp (192
   `FACTOR_RETEST_V2` rerun trên dữ liệu hiện hành + 34 `WATCHLIST_VALIDATION`
   hợp lệ): **38 sống sót**, so với **27** qua ngưỡng thủ công `|t|>3` —
   **BH-FDR lỏng hơn**, ngược trực giác thường gặp (0 trường hợp đạt `|t|>3`
   mà rớt FDR; 11 trường hợp sống sót FDR mà không đạt `|t|>3`). Bổ sung
   `CLAUDE.md` mục 9: mọi bảng test đa nhân tố từ nay báo kèm q-value FDR.
5. **NV5 (commit `e8a9d7a`)** — Deflated Sharpe Ratio cho v2 (backtest chuẩn
   hiện hành, M=560 "thử nghiệm" ước lượng công khai cách đếm từ 8 nguồn báo
   cáo đã có): **DSR=0.0083** — sau khấu trừ đa kiểm định trung thực, gần như
   không còn bằng chứng kỹ năng thật. Bootstrap CI (block=20 ngày, N=1000,
   seed=42, `src/simulation/bootstrap.py` không sửa): CAGR CI=[−9.6%,+19.3%],
   Sharpe CI=[−0.59,+1.32] — cả hai chứa 0. Chú thích cố định: mọi số
   long-only đọc kèm sàn survivorship (+0.4/+1.2/+2.9%).
6. **NV6 (commit `d4a0c9c`)** — `ROBUSTNESS_REPORT.md` tổng hợp NV1-5; cập
   nhật `audit/PATH_TO_100.md` mục 9 (3/4 việc xong: DSR, FDR, bootstrap CI —
   tách holdout cho tham số portfolio construction vẫn mở, ngoài phạm vi).
   Full test suite: 295 passed. Commit riêng từng nhiệm vụ vào `main`, không
   push.

**3 phát hiện đáng chú ý dành cho quyết định người dùng ở round riêng có
prereg**: (a) DSR của v2 rất thấp — cân nhắc lại mức tin cậy đặt vào v2 cho
quyết định vận hành, dù nó vẫn là nhân tố có bằng chứng độc lập tốt nhất đã
test; (b) 71.0 không còn hợp lệ trích dẫn cho v2-trong-final_watchlist; (c)
`risk_score` không đáng theo đuổi thêm làm nhân tố độc lập.

## GĐ5.5 — Vòng quyết định sau GĐ5: thi hành 3 kết luận + dọn trích dẫn

Không đo thêm, không tune — chỉ thi hành 3 quyết định đã treo từ GĐ5.

1. **NV1 (commit `1b87bae`)** — `SCORE_V2_REPORT.md` mục "Trạng thái sau GĐ5":
   **giữ shadow, không dùng vốn thật.** Lý do: IC ổn định + sống sót FDR
   (bằng chứng nhân tố thật) nhưng DSR=0.0083 (M=560) + bootstrap CI chứa 0
   cho cả CAGR/Sharpe (chưa có bằng chứng chiến lược đáng cược), cả hai số
   CHƯA trừ sàn survivorship. Giữ nguyên 3 điều kiện xem lại cũ (6 tháng
   live / drawdown>25% / lệch shadow v1 >10đ%/60 phiên), bổ sung điều kiện
   thứ 4: khi shadow đủ 6 tháng, tính Sharpe out-of-sample thuần so với CI
   bootstrap đã có — nằm trong/dưới nửa CI thì xác nhận quyết định hiện tại,
   vượt hẳn CI thì mở round xem lại (không tự động nâng cấp). Khuyến nghị
   bằng văn bản: nếu có vốn thật đang theo watchlist/score, đưa về 0 hoặc mức
   "học phí" tối thiểu — không tìm thấy bằng chứng vốn thật trong hồ sơ repo,
   khuyến nghị viết sẵn phòng trường hợp có.
2. **NV2 (commit `21ac52b`)** — grep toàn bộ `src/`/`scratch/`/`*.md` cho mọi
   trích dẫn t_NW/percentile/DSR, lập bảng kiểm: `src/alpha/scoring.py`'s
   docstring trích "71.0" không kèm ngữ cảnh — **SỬA**, bổ sung t_NW tái
   xác nhận GĐ5 + cảnh báo rõ "71.0 chỉ đúng cho v2 kiểm tra độc lập, dùng
   52.8 cho ngữ cảnh trong `final_watchlist.py`". `final_watchlist.py` tự nó
   đã đúng từ GĐ4 (52.8), không cần sửa. `WATCHLIST_VALIDATION_REPORT.md`
   mục 3a: thêm ghi chú trỏ sang `V2_STABILITY_NOTE.md`, không sửa số gốc
   (đúng số đã đo tại thời điểm đó). `WATCHLIST_VALIDATION_PREREG.md` +
   comment trong `scratch/v2_stability_toggle.py`: giữ nguyên — prereg là hồ
   sơ lịch sử khóa cứng, sửa lại sẽ phá vỡ audit trail. Rà thêm
   `META_RANKING_VALIDATION_REPORT.md`/`src/backtest/portfolio_backtest.py`/
   `REMEDIATION_REPORT.md`: không liên quan đến cặp số 71.0/52.8 của v2,
   không sửa.
3. **NV3 (commit `040ef10`)** — đóng hồ sơ `risk_score` trong
   `WATCHLIST_VALIDATION_REPORT.md` (cả mục phát hiện #3 lẫn "Kết luận & bước
   tiếp theo" — trước đó vẫn còn nêu nó là ứng viên mở): bằng chứng trùng cụm
   vol (corr +0.822 với `v2_score`), không còn ứng viên nào mở cho prereg
   đơn-nhân-tố. `src/screening/final_watchlist.py`'s `_score()`: thêm comment
   tại khối `risk_raw` ghi rõ kết luận đóng hồ sơ + đánh dấu `tail_ratio_60d`
   (t=+0.98, không ý nghĩa) và `risk_penalty_score` (luôn trung lập) là
   "unvalidated, giữ vì hiển thị tham khảo" đúng quy ước GĐ4; sửa nốt đoạn
   docstring trọng số cũ ở GĐ4 từng gọi `risk_score` là "ứng viên tốt" —
   trỏ sang kết luận đóng hồ sơ, không để lại khuyến nghị mở trong code sản
   xuất.
4. **NV4 (commit này)** — full test suite: 295 passed sau mọi thay đổi.
   Commit riêng từng nhiệm vụ vào `main`, không push.

## GĐ6 — Polish tối thiểu + đóng gói hồ sơ trước trạng thái nghỉ

Vòng cuối: không đo, không tune, không nhân tố mới — chỉ hoàn thiện kỹ thuật
chọn lọc (`audit/PATH_TO_100.md` mục 10) và đóng gói hồ sơ cho phiên tương lai.

1. **NV1a (commit `4a46e28`)** — `requirements.txt` pin chính xác phiên bản
   (đối chiếu `pip freeze`/`importlib.metadata` với môi trường thật, kể cả
   các gói cài qua conda không hiện version sạch qua `pip freeze`). Giữ
   comment cảnh báo statsmodels 0.14.2 vẫn xung đột import với scipy>=1.17
   (`ImportError: cannot import name '_lazywhere'`) — tái xác minh lỗi còn
   tái hiện trước khi ghi, không copy nguyên comment cũ chưa kiểm tra lại.
2. **NV1b (commit `dd21971`)** — atomic write (temp file + `os.replace`) cho
   `save_parquet` (trung tâm, phủ toàn bộ artifact parquet qua
   `append_parquet`) + `save_csv_atomic` mới, áp có chọn lọc vào các điểm ghi
   watchlist/report CSV cập nhật hằng ngày
   (`final_watchlist.py`'s `save_final_watchlist`/`save_watchlist_outputs`/
   `apply_post_cashflow_overlay`, `run_alpha_scoring.py`'s report CSV) — không
   áp tràn lan cho ~20 điểm `to_csv` khác (audit/diagnostic một lần).
3. **NV1c (commit `70b0726`)** — xác minh THẬT (không chỉ đọc code) nghi vấn
   J1: tạo notebook cố tình lỗi, chạy qua `run_all_notebooks.sh`, xác nhận
   script dừng đúng (exit code 1, không in dòng "Executed N notebook(s)
   successfully") — J1 không tái hiện, không cần sửa. Rà 16 notebook đang hoạt
   động (loại `00_archive`), gắn ô cảnh báo "outdated" đầu 3 notebook có logic
   lệch code hiện tại (`12_meta_ranking_optimization.ipynb` coi `alpha_score`
   như bị dẫn dắt bởi momentum/trend — thực ra v2 chỉ dựa vol/thanh khoản;
   `19_validation_and_stress_test.ipynb`/`20_portfolio_backtester.ipynb` đọc
   `meta_ranking.parquet` như chuỗi lịch sử — thực ra là snapshot hiện tại) —
   không sửa nội dung, chỉ cảnh báo, đúng yêu cầu.
4. **NV2 (commit `0eaf25f`)** — `PROJECT_STATE.md`, cửa ngõ một trang cho mọi
   phiên tương lai: đang live (v2 shadow — kèm phát hiện quan trọng là shadow
   log KHÔNG chạy đều, mới 3 mốc ngày từ 2026-07-09 vì không có cron/launchd;
   watchlist không xếp hạng alpha), đã đóng (nhánh disclosure, kiểm định
   composite, risk_score, nghịch lý 71.0/52.8 — kèm link report), đang chờ (4
   điều kiện xem lại v2 với hạn danh nghĩa 2027-01-09 kèm cảnh báo có thể trễ
   nếu pipeline không chạy đều; Gate #3 survivorship). Quy trình vận hành
   hằng ngày + dấu hiệu bất thường cần chú ý. Bản đồ 10 report nên đọc theo
   thứ tự. `CLAUDE.md` mục 3 cập nhật trỏ tới file này đọc TRƯỚC
   `PUSH_REVIEW.md`/`PATH_TO_100.md`.
5. **NV3 (commit `1934870`)** — `audit/audit_summary.json` thêm
   `path_to_100_progress`: đánh dấu resolved/open/closed-negative cho mọi
   mục `PATH_TO_100.md` đã chạm từ GĐ2 đến GĐ5.5 — không chấm lại điểm
   (`overall_score`/`category_scores` giữ nguyên snapshot gốc 2026-07-12),
   đúng quy ước sẵn có của `remediation_log`.
6. **NV4 (commit này)** — full test suite: 295 passed. Commit riêng từng
   nhiệm vụ vào `main`, không push.

---

## Trạng thái nghỉ đạt ngày 2026-07-16

Dự án dừng ở đây cho đến phiên tiếp theo. Tóm tắt 3 dòng (chi tiết đầy đủ:
`PROJECT_STATE.md`):
- **Đang chạy**: cập nhật giá + disclosure hằng ngày (thủ công, không cron),
  `alpha_score` v2 shadow-only (không vốn thật), `final_watchlist` sắp theo
  thanh khoản (không xếp hạng alpha).
- **Đã đóng dứt điểm**: nhánh disclosure-làm-tín-hiệu (âm tính, 3 round
  pre-register), kiểm định composite `final_watchlist` (Nhánh C), `risk_score`
  (bằng chứng trùng), nghịch lý null-test 71.0/52.8.
- **Còn mở cho phiên sau**: Gate #3 survivorship/point-in-time universe (việc
  lớn nhất còn lại), 4 điều kiện xem lại v2 (hạn danh nghĩa gần nhất
  2027-01-09), `tail_ratio_60d` direction, holdout split cho portfolio
  construction params.

Không có gì đang chờ quyết định gấp — mọi nhánh đang mở đều đã có tài liệu
đầy đủ để một phiên mới tiếp tục mà không cần dựng lại ngữ cảnh từ đầu.
