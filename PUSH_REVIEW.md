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
| `2ebd2b0` | docs: add session handoff note to docs/reports/data/BACKFILL_DESIGN_REPORT.md |

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
| `1566f29` | docs: Round 3/4 write-up + docs/reports/data/DATA_BASELINE.md baseline documentation |
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
| `6f452b2` | docs: before/after comparison for the scoring change + docs/reports/scoring/SCORING_UPDATE_REPORT.md |

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
| `88a97f7` | docs: concentration null test + docs/reports/scoring/CONCENTRATION_ANALYSIS_REPORT.md |
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
| `6cf15a0` | docs: pre-register docs/reports/scoring/SCORE_V2_DESIGN.md before any v2 comparison is run |
| `066014e` | test(alpha): confirmation run for docs/reports/scoring/SCORE_V2_DESIGN.md -- all 3 criteria pass |
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
`final_watchlist.py`'s live scoring (`docs/reports/scoring/SCORE_FORENSIC_REPORT.md` found
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
| `40e928e` | docs(disclosure): docs/reports/data/DISCLOSURE_BASELINE.md -- descriptive stats only, Round 5 |

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

Wrote `docs/reports/data/DISCLOSURE_BASELINE.md` (descriptive stats only -- composition,
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
   thích ứng quy ước bỏ dòng volume=0" nêu trong `docs/reports/data/DATA_BASELINE.md`
   caveat #3: **BÁC BỎ** cho vấn đề mass-rejection này. Kiểm tra trực
   tiếp raw parquet của VIC/FPT/VCB/HPG/VNM/MWG: không có dòng nào
   (kể cả volume=0) sau 2026-07-06 — tức thiếu dữ liệu thật, không
   phải "dòng hợp lệ bị lược". Nguyên nhân thật, đã ghi sẵn trong
   `docs/reports/data/DATA_BASELINE.md:20-21` từ trước: `full_history_v2` được fetch 2
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
   `docs/reports/scoring/SCORE_FORENSIC_REPORT.md`/`docs/reports/scoring/SCORE_V2_REPORT.md`) là ứng viên rõ
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
   năng ngừng giao dịch thật. Cập nhật `docs/reports/data/DATA_BASELINE.md`.
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
   dòng (+412). `docs/reports/data/DISCLOSURE_BASELINE.md` cập nhật caveat #1 → RESOLVED.
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
   `docs/reports/data/DISCLOSURE_BASELINE.md`.
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
3. **NV1 (commit `7381185`)** — `docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_PREREG.md`, khóa TRƯỚC
   khi viết code join disclosure×giá (FIREWALL hiệu lực từ Round 5 tới giờ, đây
   là lần đầu tiên hai nguồn được nhìn cùng nhau). Khóa: định nghĩa S1/S2/S3 (chỉ
   pha REGISTRATION, cấm tuyệt đối field RESULT/tỷ lệ thực hiện), quy tắc
   point-in-time `available_at` (phát hiện 100% dòng hiện tại là
   `is_backfilled=True`, tức toàn bộ kết quả phụ thuộc giả định lag +1 ngày giao
   dịch — độ nhạy +1/+3/+5 là bắt buộc, không phải phụ), rổ đủ điều kiện (3 tỷ +
   `trading_status`, quyết định rõ dùng snapshot hiện tại vì bảng point-in-time
   chỉ có lịch sử thật từ 2026-07-13), nhãn "bùng nổ" (tái dùng nguyên định nghĩa
   `docs/reports/scoring/EVENT_DETECTION_REPORT.md` đã pre-register, không phát minh mới), lift +
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
5. **NV3 (commit `b95cc37`)** — `docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_REPORT.md`. **Test chính
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
mua)" ở `docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_REPORT.md`. Toàn bộ EXPLORATORY — không kiểm
định lại H1/H2 đã khóa, không mở prereg mới, không chạy test xác nhận nào.

1. **NV1 (commit `7445ca9`)** — `docs/reports/scoring/SURVIVORSHIP_BIAS_ESTIMATE.md`: dùng S3 làm
   placebo, đối chiếu chéo bằng excess return không điều kiện sự kiện của TOÀN
   BỘ `(mã, ngày)` trong rổ đủ điều kiện (N=325k–347k, độc lập hoàn toàn với
   việc chọn sự kiện disclosure). Ba ước lượng (placebo S3, gộp tất cả sự kiện,
   không điều kiện) cùng dấu dương, cùng dạng tăng theo cửa sổ, CI chồng lấn
   nhau — nhất quán với giả thuyết survivorship bias nhưng KHÔNG phải bằng
   chứng phân tách nguyên nhân (ghi rõ trong tài liệu). Đề xuất mức sàn hiệu
   chỉnh ~+0.4%/+1.2%/+2.9% ở cửa sổ 20/60/120 ngày cho mọi backtest long-only
   diễn giải excess return, hiệu lực đến khi có point-in-time universe thật
   (Gate #3). Trích dẫn vào `docs/reports/data/DATA_BASELINE.md` caveat #2.
2. **NV2 (commit `a140633`)** — mục "Exploratory addendum" cuối
   `docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_REPORT.md`: autopsy mô tả thuần (không CI, không kết
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

1. **NV1 (commit `8e47dfc`)** — `docs/reports/disclosure/DISCLOSURE_PREREG_2_CLUSTER.md`, khóa TRƯỚC
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
3. **NV3 (commit `3b4986c`)** — `docs/reports/disclosure/DISCLOSURE_PREREG_2_REPORT.md`. **Cả H1, H2,
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

1. **NV1 (commit `eb765e6`)** — `docs/reports/scoring/WATCHLIST_VALIDATION_PREREG.md`. Composite =
   `base_final_score` (trước `warning_penalty` — đúng khung "75/100 điểm trọng
   số" của `PATH_TO_100.md`, không phải `final_score`). Universe =
   `trading_status ACTIVE`. Tái dùng nguyên máy móc IC Newey-West + null test
   đã kiểm chứng ở `docs/reports/scoring/SCORE_V2_DESIGN.md`/`score_v2_ic_test.py`/`score_v2_null_test.py`
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
5. **NV5 (commit `b0ca2fb`)** — `docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md` đầy đủ; cập
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

1. **NV1 (commit `fcafd05`)** — `docs/reports/scoring/V2_STABILITY_NOTE.md` giải nghịch lý
   percentile 71.0 (`docs/reports/scoring/SCORE_V2_REPORT.md`) vs 52.8 (`docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md`
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
6. **NV6 (commit `d4a0c9c`)** — `docs/reports/scoring/ROBUSTNESS_REPORT.md` tổng hợp NV1-5; cập
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

1. **NV1 (commit `1b87bae`)** — `docs/reports/scoring/SCORE_V2_REPORT.md` mục "Trạng thái sau GĐ5":
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
   đã đúng từ GĐ4 (52.8), không cần sửa. `docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md`
   mục 3a: thêm ghi chú trỏ sang `docs/reports/scoring/V2_STABILITY_NOTE.md`, không sửa số gốc
   (đúng số đã đo tại thời điểm đó). `docs/reports/scoring/WATCHLIST_VALIDATION_PREREG.md` +
   comment trong `scratch/v2_stability_toggle.py`: giữ nguyên — prereg là hồ
   sơ lịch sử khóa cứng, sửa lại sẽ phá vỡ audit trail. Rà thêm
   `docs/reports/scoring/META_RANKING_VALIDATION_REPORT.md`/`src/backtest/portfolio_backtest.py`/
   `docs/reports/codebase_audit/REMEDIATION_REPORT.md`: không liên quan đến cặp số 71.0/52.8 của v2,
   không sửa.
3. **NV3 (commit `040ef10`)** — đóng hồ sơ `risk_score` trong
   `docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md` (cả mục phát hiện #3 lẫn "Kết luận & bước
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

## GĐ7 — Tự động hóa nhịp ngày — hoàn tất trạng thái nghỉ

Việc cuối trước khi dừng hẳn: biến quy trình vận hành thủ công (mục 4,
`PROJECT_STATE.md`) thành tự động, để trạng thái nghỉ không lặng lẽ trở
thành "shadow log ngừng cập nhật" sau vài tuần không ai chạy tay.

1. **NV1 (commit `a01e418`)** — `scripts/daily_run.sh`, script điều phối
   duy nhất: `update_prices_daily` → `update_disclosure_daily` →
   `update_index_data` → `run_daily_pipeline --offline` (bước này tự chứa
   `run_alpha_scoring` + xây lại `final_watchlist`). Best-effort, KHÔNG
   `set -e` — mỗi bước chạy bất kể bước trước fail hay không (các script
   con đã tự soft-fail theo từng mã, luôn exit 0), log riêng từng bước
   (START/OK/FAIL kèm thời gian) vào `logs/daily_run.log`, dòng FAIL bọc
   trong `######` để dễ tìm. Tự kiểm thử logic (không phải chạy thật) bằng
   một bước giả lập fail giữa chừng — xác nhận: script tiếp tục các bước
   sau, dòng FAIL hiện đúng, mã thoát cuối = số bước fail.
2. **NV2 (commit `b18e68d`)** — LaunchAgent
   (`~/Library/LaunchAgents/com.vietnam-quant-research.dailyrun.plist`,
   bản gốc `scripts/com.vietnam-quant-research.dailyrun.plist`): lịch
   `StartCalendarInterval` 19:00 các ngày trong tuần + `RunAtLoad=true` cho
   cơ chế chạy bù (máy tắt/ngủ lúc 19:00 → lần đăng nhập/khởi động kế tiếp
   tự chạy bù); `daily_run.sh` tự kiểm tra dòng SUMMARY mới nhất trong log
   để không chạy trùng 2 lần/ngày (không cần file trạng thái riêng), thêm
   `--force` để chạy tay bỏ qua kiểm tra này.

   **Phát hiện quan trọng, xác nhận bằng thử nghiệm thật (không chỉ đọc
   code)**: `launchctl load` thành công, agent đăng ký được, nhưng khi
   launchd thực sự sinh tiến trình chạy script thì báo
   `Operation not permitted` ngay khi vào thư mục dự án. Đối chứng bằng
   một job thử trỏ vào `/tmp` (chạy trơn tru) so với job giống hệt trỏ vào
   `~/Desktop/...` (lỗi giống hệt) xác định nguyên nhân: **macOS TCC (Privacy
   & Security) bảo vệ thư mục `~/Desktop`, tiến trình do launchd sinh ra
   không tự thừa hưởng quyền Full Disk Access mà phiên Terminal tương tác
   đang có.** Không thể tự sửa bằng code — cần người dùng vào System
   Settings → Privacy & Security → Full Disk Access → thêm `/bin/bash` thủ
   công (hướng dẫn đầy đủ + 3 dòng kiểm tra/tắt agent: `PROJECT_STATE.md`
   mục 4). Đến khi đó, agent vẫn nạp đúng nhưng mỗi lần trigger chỉ ghi lỗi
   vào `logs/launchd_stderr.log`, không có tác dụng — chạy tay
   `bash scripts/daily_run.sh` không bị ảnh hưởng (không qua launchd).
3. **NV3 (commit `59a9d57`)** — ghi chú trung thực: KHÔNG dựng lại điểm số
   cho khoảng trống 07-09→07-16 (sẽ là look-ahead ngụy tạo vào một bản ghi
   out-of-sample). Xác nhận trong `docs/reports/scoring/SCORE_V2_REPORT.md`: chuỗi liên tục thật
   bắt đầu từ **2026-07-16** (ngày tự động hóa có hiệu lực), không phải
   2026-07-09. Dời mốc "đủ 6 tháng" của điều kiện xem lại #1 (và do đó điều
   kiện #4) từ hạn danh nghĩa cũ 2027-01-09 sang **2027-01-16** trong
   `docs/reports/scoring/SCORE_V2_REPORT.md` + `PROJECT_STATE.md`. 3 mốc thưa cũ giữ nguyên
   trong file (dữ liệu thật, không xóa), chỉ không tính vào "6 tháng liên
   tục".
4. **NV4 (commit `9db5586`, `6f5d506`, `d80434a`)** — chạy thật (không qua
   launchd, tay trực tiếp do TCC) một chu kỳ `daily_run.sh` đầy đủ: 4/4
   bước OK (`update_prices_daily` 748s, `update_disclosure_daily` 1334s,
   `update_index_data` 7s, `run_daily_pipeline` 116s, tổng ~37 phút). Xác
   nhận `alpha_score_shadow_log.parquet` có mốc **2026-07-16** mới (431 mã)
   — đúng ngày chuỗi liên tục bắt đầu theo NV3; `pipeline_metadata.json`
   lineage mới toàn bộ (stock/feature/benchmark date = 2026-07-16);
   `final_watchlist.csv` regenerate, xếp hạng đúng theo `value_ma20` giảm
   dần (Nhánh C). Full test suite: 295 passed.

**Tổng kết trạng thái nghỉ, cập nhật**: tự động hóa ĐÃ triển khai đúng như
yêu cầu (script + LaunchAgent + chạy bù + backfill trung thực), nhưng
**chưa THỰC SỰ tự động cho đến khi người dùng cấp Full Disk Access cho
`/bin/bash`** (việc 2 phút, hướng dẫn ở `PROJECT_STATE.md` mục 4) — cho
đến lúc đó, nhịp ngày vẫn cần chạy tay (`bash scripts/daily_run.sh`) như
trước, không tệ hơn trạng thái trước round này. Không có gì khác thay đổi
so với "Trạng thái nghỉ đạt ngày 2026-07-16" ở trên.

## Phase 10 — audit thuần `stock-decision-engine/`, không sửa code (this session)

**Bối cảnh**: người dùng gỡ quy tắc read-only trước đây áp cho
`stock-decision-engine/` (notebook quyết định cổ phiếu độc lập, 20 lần chạy
thật/172 file output cho 16 mã, chưa từng backtest) và yêu cầu một vòng audit
thuần — không sửa code, không tune, không backtest — để biến "cảm giác chưa
chất lượng" thành danh sách vấn đề có bằng chứng. Báo cáo đầy đủ:
`stock-decision-engine/AUDIT_SDE_REPORT.md`.

**NV0**: kiểm tra git status — toàn bộ 185 file trong
`stock-decision-engine/` đã track sẵn, không có gì chưa commit, không cần
snapshot bổ sung.

**NV1**: bản đồ kiến trúc đầy đủ — entry point (notebook, sửa `TICKER` ở
cell đầu) → `data.py`/`features.py`/`simulation.py`/`scoring.py`/`report.py`/
`visualization.py`. Liệt kê đầy đủ công thức 8 sub-score (`market_regime` 10%,
`trend` 20%, `momentum` 15%, `relative_strength` 15%, `alpha` 15%, `risk`
10%, `liquidity` 10%, `simulation` 5%) — toàn bộ ngưỡng/trọng số hard-code
trong `config.yaml`/`scoring.py`, không citation.

**NV2 (phát hiện chính)**: engine KHÔNG tự fetch giá — đọc lại
`data/processed/clean_daily_ohlcv.parquet` của dự án chính (có fallback tới
`data/raw/daily_ohlcv/` — đường dẫn dự án chính đánh dấu "Forbidden", hiện
không kích hoạt được vì thư mục rỗng). Chạy ladder test (yêu cầu gốc:
HPG/TCB; áp dụng cho toàn bộ 16 mã SDE có output vì không có TCB) so
`data/quarantine_existing_v1/clean_daily_ohlcv.parquet` (bản cũ, đúng bản
SDE đã đọc) với `data/full_history_v2/raw/`: **5/16 mã (BID, HDB, HPG, TPB,
VCB) dính raw/adjusted-close mixing bug đã biết** (4-7 mức ratio riêng biệt,
29-47% ngày lệch >5%, lệch tối đa 38-115%); 11/16 mã sạch (ratio=1.000 mọi
ngày). Đối chiếu mốc git xác nhận: TOÀN BỘ 20 lần chạy (nhúng ngày
2026-06-24 → 2026-07-06) đều SỚM HƠN ngày `data/processed/` được vá thật
(2026-07-13, `28b9f60`) — nên 6/20 lần chạy trên 5 mã trên chắc chắn dùng dữ
liệu rolling-window (MA/vol/RSI/ATR) đã nhiễu một phần. Nếu chạy lại HÔM NAY
dữ liệu sẽ sạch (file hiện tại đã regenerate từ `full_history_v2`, mới nhất
2026-07-16). Không output nào có lineage metadata (vi phạm `CLAUDE.md` mục
6). Không vi phạm firewall disclosure.

**NV3 (bằng chứng gián tiếp mạnh nhất)**: không tìm thấy look-ahead/leakage
nào trong cách tính đặc trưng (điểm tích cực). Nhưng `src/screening/final_watchlist.py`
có đúng 5 sub-score TRÙNG TÊN với SDE (`trend_score`, `momentum_score`,
`relative_strength_score`, `liquidity_score`, `risk_score`) — composite đó đã
bị `WATCHLIST_VALIDATION_REPORT.md` đóng hồ sơ ÂM TÍNH; và
`SCORE_FORENSIC_REPORT.md` tìm thấy họ nhân tố "đuổi theo sức mạnh giá gần
đây" (momentum/rs/trend, 70% trọng số `alpha_score` v1) đảo dấu IC từ
+0.014/+0.016 (2023-2025) sang **−0.106/−0.105 (2026)** — đúng giai đoạn 20
lần chạy SDE nằm trong đó. 50% trọng số cuối của SDE (`trend`+`momentum`+
`relative_strength`) rơi đúng vào họ nhân tố này — không kết luận SDE có
cùng lỗi định lượng chính xác (công thức khác), nhưng là bằng chứng gián
tiếp mạnh để nghi ngờ. Không sub-score nào đạt VALIDATED; tất cả 8 xếp
PLAUSIBLE_BUT_UNVALIDATED (2 cái — momentum, relative_strength — gắn nhãn
rủi ro cao).

**Kết quả**: `AUDIT_SDE_REPORT.md` — 8 finding theo severity (2 HIGH, 3
MEDIUM, 2 LOW, 1 INFO), bảng phân loại 8 sub-score, khuyến nghị tạm thời cho
172 file output hiện có (6 lần chạy trên mã dính bug: không tin cậy các
sub-score rolling-window cho đến khi chạy lại; 14 lần chạy còn lại: đọc như
checklist TA có tổ chức, không phải điểm số đã kiểm định), và đề xuất kế
hoạch Vòng 2 (point-in-time re-scoring trên `full_history_v2`, universe lớn
hơn 16 mã, prereg trước khi chạy, BH-FDR nếu test nhiều sub-score, cộng danh
sách rõ cái gì KHÔNG kiểm định được — Monte Carlo cần test kiểu calibration
chứ không phải IC, `market_regime` không có cross-sectional variation).
**Không sửa một dòng code nào của `stock-decision-engine/` trong round này.**

**Lưu ý cho session sau**: người dùng nói CLAUDE.md đã được cập nhật để gỡ
quy tắc read-only cho `stock-decision-engine/`, nhưng file `CLAUDE.md` hiện
tại KHÔNG có ghi chú này (đã kiểm tra `grep -i stock-decision-engine
CLAUDE.md` và toàn bộ lịch sử git của file — không có kết quả). Có thể người
dùng nhớ nhầm, hoặc thay đổi đó chưa từng được lưu. Chưa tự ý thêm ghi chú
này vào CLAUDE.md trong round này (ngoài phạm vi NV0-NV4 đã giao) — cần xác
nhận lại với người dùng ở lần trao đổi kế tiếp.

## Phase 11 — SDE: sửa chân dữ liệu + regenerate + khóa prereg Vòng 3 (this session)

**Bối cảnh**: tiếp nối Phase 10 (audit thuần) — 2 finding HIGH đã có bằng
chứng, round này sửa CHÂN DỮ LIỆU + regenerate + viết prereg cho kiểm định
điểm số ở Vòng 3, KHÔNG đổi công thức/trọng số/ngưỡng điểm nào (nội dung
điểm chỉ đổi sau khi Vòng 3 chạy, theo cây quyết định đã khóa trước).

**NV0 (commit `44204a6`)**: `CLAUDE.md` mục 10 — ghi rõ
`stock-decision-engine/` gỡ read-only từ 2026-07-17 (việc treo từ Phase 10:
người dùng nói đã cập nhật nhưng file thực tế chưa có — nay thêm chính
thức), phạm vi sửa đổi theo kế hoạch khóa trong `AUDIT_SDE_REPORT.md`.

**NV1 (commit `8795764`)**: nối `stock-decision-engine/src/data.py` về
`src/data/dataset_config.py::OFFICIAL_CLEAN_OHLCV_PATH` thay vì hard-code
đường dẫn riêng — gỡ hoàn toàn fallback tới `data/raw/daily_ohlcv/`
(đường dẫn dự án chính đánh dấu "Forbidden"). Mở rộng
`tests/test_dataset_config.py` (test hồi quy Gate #6 có sẵn) để quét thêm
`stock-decision-engine/src/` — không viết test mới, chỉ mở rộng phạm vi
quét của 3 test đã có. `report.py::save_outputs` nhúng `lineage_*`
(dataset_version/features_sha256/features_row_count/config_hash/
git_commit_hash/lineage_generated_at) vào mọi `*_metrics.csv`, tái dùng
nguyên `src/utils/pipeline_io.py::build_lineage_metadata` của dự án chính
thay vì viết lại. Notebook cập nhật truyền `root=PROJECT_ROOT` tường minh.
Smoke test end-to-end xác nhận hoạt động đúng; full suite 295 passed.

**NV2 (commit `861654c`)**: regenerate cả 20 lần chạy cũ (16 mã) đúng NGÀY
as-of từng lần (không phải chạy "hôm nay" — mới sẽ trộn lẫn hiệu ứng fix bug
với 3 tuần biến động giá thật, làm sai lệch phép so sánh). Script:
`scratch/sde_regenerate_gate6.py`. 60 file cũ (date-scoped:
decision_summary/sub_scores/metrics) chuyển vào
`stock-decision-engine/outputs/archive_pre_gate6_fix_2026-07-17/` kèm
README; 112 PNG chart (không gắn theo ngày, chỉ theo mã) bị ghi đè tại
chỗ, bản cũ vẫn còn trong lịch sử git. Bảng so sánh đầy đủ:
`stock-decision-engine/GATE6_REGEN_COMPARISON.csv` — **5/20 quyết định bị
LẬT nhãn** (BMP, SSI, TPB, VIB, VPL), không chỉ ở 6 lần chạy dính bug giá.

**Phát hiện phụ khi regenerate (không có trong Phase 10)**: trước khi
backfill đầy đủ hoàn tất (2026-07-10, 4 ngày trước lần chạy SDE cuối cùng),
`clean_daily_ohlcv.parquet` chỉ có lịch sử NGẮN cho hầu hết mã SDE (POW 295
dòng, SSI 328, STB 332, ACB/GEX 345, VIX 295, VPL 288 — so với
`lookback_days=756` config yêu cầu) — độc lập với bug raw/adjusted-close,
ảnh hưởng rộng hơn (7/16 mã thêm, kể cả mã KHÔNG dính bug giá) tới toàn bộ
thống kê full-window (Sharpe/Sortino/Calmar/Jensen alpha/information
ratio/max_drawdown/CVaR/skewness — hết `alpha` sub-score, một phần `risk`).
Ghi thành finding #9 mới trong `AUDIT_SDE_REPORT.md`, đã RESOLVED cho dữ
liệu hiện tại (đủ sâu từ 2026-07-10) nhưng 60 file archive vẫn mang defect
này — đúng lý do bị archive, không dùng cho quyết định.

**NV3 (commit `4b88631`)**: `stock-decision-engine/SDE_SCORING_PREREG.md` —
khóa trước, CHƯA CHẠY. Đối tượng: `final_score` + 8 sub-score (trừ 3 ngoại
lệ có lý do: `simulation` cần calibration test không phải IC vì là xác
suất không phải nhân tố xếp hạng; `alpha`'s phần backtest.profit_factor
không tái tạo point-in-time được; `market_regime` không có biến thiên
cross-sectional vì chỉ dựa 1 chuỗi VNINDEX). Máy đo ĐÚNG bộ đã khóa cho
`final_watchlist` (`WATCHLIST_VALIDATION_PREREG.md`): IC Newey-West
maxlags=20, full+top150, raw+residualized, 3 giai đoạn tertile; null test
2.000 danh mục/fold seed=42, 5 fold theo năm; BH-FDR trên 7 đối tượng × 2
universe × 2 target. Cây quyết định 3 nhánh (A: giữ khung/gỡ sub-score IC
âm; B: tái thiết quanh sub-score có bằng chứng, phần còn lại dán nhãn
"unvalidated"; C: hạ thành bảng dữ kiện thô, không còn final_score/decision)
— y hệt cấu trúc đã dùng cho `final_watchlist`. Ghi sẵn kỳ vọng TRƯỚC khi
chạy (không phải kết luận): 50% trọng số SDE trùng họ nhân tố đã đóng hồ sơ
âm tính bên dự án chính, nên kỳ vọng hợp lý là IC cũng âm/không rõ ràng —
để không diễn giải kết quả âm tính (nếu xảy ra) như một bất ngờ cần thêm
sự hoài nghi mà kết quả dương không bị soi cùng mức.

**NV4**: full suite 295 passed (không đổi qua toàn bộ round).
`AUDIT_SDE_REPORT.md` cập nhật: finding #1/#3/#6/#7 → RESOLVED kèm commit,
finding #9 mới (window truncation) thêm vào bảng severity, mục 5-7 viết lại
phản ánh trạng thái sau Vòng 2, mục 7 rút gọn thành pointer tới
`SDE_SCORING_PREREG.md` (tránh trùng lặp nội dung giữa hai file).

**Trạng thái cuối round**: dữ liệu SDE sạch cho mọi lần chạy tương lai
(miễn `daily_run.sh` tiếp tục chạy đều). Công thức/trọng số điểm chưa đổi
một chữ nào. Vòng 3 (chạy `SDE_SCORING_PREREG.md`) chưa thực hiện — chờ
phiên riêng theo đúng ràng buộc round này.

## Phase 12 — SDE Vòng 3: chạy phiên tòa, kết luận Nhánh C (this session)

**Bối cảnh**: tiếp nối Phase 11 — `SDE_SCORING_PREREG.md` đã khóa, round
này chạy đúng một lần, thi hành nhánh trúng theo cây quyết định đã khóa
trước. Không chỉnh tham số sau khi thấy số.

**NV1**: xây bridge point-in-time re-scoring (chưa có trước round này) —
vòng hóa `enrich()`+`bootstrap_monte_carlo()`+`score_decision()` (bản gốc)
theo (symbol, ngày rebalance) trên toàn bộ universe `trading_status==ACTIVE`
(462 mã), `lookback_days=756` đúng config, `backtest={"available": False}`
mọi ngày lịch sử (trung thực, không phải sửa công thức). Phát hiện giữa
chừng: `run_portfolio_backtest` tự tính lại lịch rebalance theo TỪNG FOLD
(khác pha với lịch toàn cục) — phải build thêm panel thứ hai
(`sde_round3_panel_foldaligned.parquet`) khớp đúng ngày null-test sẽ dùng,
nếu không hầu hết quyết định sẽ âm thầm rơi vào fallback mean-reversion
thay vì dùng `final_score` thật — cùng loại lỗi đã ghi trong
`scratch/watchlist_validation_null.py`.

Panel chính: 17.620 dòng, 438 mã, 204 ngày, **2023-01-16 → 2026-07-03**.
2.708 lượt bị loại vì chưa đủ 756 phiên (finding #9) — không chấm cửa sổ
cụt. Chỉ 43 ngày cross-section đạt ≥15 mã/ngày cho IC test.

**Kết quả IC Newey-West + FDR (28 test, q=0.05)**: `final_score`
t_NW(full,residualized)=**+1.28** (xa ngưỡng 3). Chỉ 2/28 sống sót FDR:
`risk` (+3.96, dương — đối tượng duy nhất có bằng chứng riêng) và
`liquidity` (−3.80, ÂM — bằng chứng để loại, không phải để giữ).
**Null test** (2.000 danh mục/fold, seed=42): percentile trung bình
**31.2** (không >60), fold 2023=**0.75** (<10) → thất bại cả hai vế OR
của Nhánh A.

**Phát hiện mới, không có trong prereg**: chia 43 ngày thành 3 giai đoạn
cho ~15 ngày/giai đoạn — DƯỚI ngưỡng N≥30 mà `newey_west_tstat()` yêu
cầu → **mọi t_NW theo giai đoạn đều là NaN, cho cả 7 đối tượng**. Tiêu chí
"đồng dấu 3 giai đoạn" (bắt buộc cho cả Nhánh A và B) không thể xác nhận
được cho bất kỳ đối tượng nào — giới hạn cấu trúc từ `lookback_days=756`
cộng với backfill hoàn tất muộn (2026-07-10), không phải lỗi thực thi.

**Áp cây quyết định**: Nhánh A không đạt (IC lẫn null đều fail rõ ràng).
Nhánh B không xác nhận được đầy đủ (`risk` đạt bảng chính nhưng không xác
nhận được 3-giai-đoạn; `liquidity` âm không phải ứng viên giữ). Theo quy
ước "vùng xám → chọn nhánh thận trọng hơn, ưu tiên C trên B" đã khóa:
**NHÁNH C.**

Đối chiếu kỳ vọng đã ghi trước (`SDE_SCORING_PREREG.md` mục 5): kỳ vọng
"trend/momentum/relative_strength không đạt" — ĐÚNG. Kỳ vọng "nếu risk có
bằng chứng, khả năng trùng cụm vol" — khớp hướng (risk là đối tượng duy
nhất sống sót). Điều KHÔNG được ghi trước: giả định ngầm 3-giai-đoạn tính
được — thực tế không tính được cho bất kỳ đối tượng nào, khiến Nhánh B
không bao giờ xác nhận đủ được với dữ liệu hiện tại của SDE.

**NV2 — thi hành Nhánh C**: `stock-decision-engine/src/scoring.py` —
`score_decision()` (WEIGHTS, hard_filters, decision label, confidence) gỡ
bỏ hoàn toàn, không comment/deprecate. `build_facts_table()` thay thế: vẫn
8 nhóm "reading" 0-100 (công thức đếm tiêu chí TA không đổi) nhưng không
còn cộng trọng số thành một số quyết định, không còn nhãn BUY CANDIDATE/
WATCH/WEAK SETUP/AVOID/GOOD STOCK BAD ENTRY. `report.py` (`facts_summary`
thay `decision_summary`), `visualization.py` (`facts_breakdown.png` thay
`score_breakdown.png`), notebook, `config.yaml` (gỡ `score_thresholds`
chết) cập nhật theo. Regenerate cả 20 output cũ trên công thức mới, đúng
as-of date như round trước — output cũ (dùng dữ liệu sạch nhưng công thức
cũ) archive tại `outputs/archive_pre_round3_branchc_2026-07-17/` kèm
README; bảng so sánh cuối: `ROUND3_BRANCHC_REGEN_COMPARISON.csv`. 16 file
`*_score_breakdown.png` lỗi thời (đã có bản `*_facts_breakdown.png` thay
thế) đã xóa khỏi git.

**NV3**: `stock-decision-engine/SDE_SCORING_REPORT.md` — kết quả đầy đủ,
nhánh đã thi hành + lý do, đối chiếu kỳ vọng cả hai chiều, khuyến nghị sử
dụng cuối cùng (SDE không còn là công cụ khuyến nghị mua/bán — chỉ còn
bảng tra cứu chỉ số kỹ thuật/thống kê thô). `AUDIT_SDE_REPORT.md` finding
#2 → RESOLVED (Nhánh C), finding #9 bổ sung hệ quả 3-giai-đoạn. `CLAUDE.md`
mục 10 cập nhật: cấm thêm lại điểm tổng hợp/decision cho đến khi có bằng
chứng IC/null-test mới đạt tiêu chí. Full suite: 295 passed, không đổi.

**Trạng thái cuối round**: `stock-decision-engine` không còn sinh
`final_score`/`decision` ở bất kỳ đâu — đã kiểm định và không đạt, không
phải "chưa kiểm định" nữa. Notebook giờ là bảng dữ kiện tham khảo thuần.

## Phase 13 — xác minh con số "43 ngày" trong SDE_SCORING_REPORT (this session)

**Bối cảnh**: người dùng yêu cầu xác minh riêng con số "43 ngày cross-section"
trong `SDE_SCORING_REPORT.md` — chỉ điều tra + ghi chú, KHÔNG chạy lại
prereg, KHÔNG đổi phán quyết Nhánh C.

**Điều tra**: câu hỏi ban đầu chỉ vào `sde_prereg_round3_panel_foldaligned.py`
— xác minh cho thấy đó là quy kết SAI, script đó chỉ phục vụ null-test.
Con số 43 thật ra đến từ 2 nơi khác: (1)
`scratch/sde_prereg_round3_panel.py`'s `rebalance_dates =
all_dates[::REBALANCE_PERIOD]` (`REBALANCE_PERIOD=20`) — quyết định đã
khóa trước trong `SDE_SCORING_PREREG.md` mục 1 (đánh đổi chi phí tính
toán, không phải tùy tiện); (2)
`scratch/sde_prereg_round3_ic_null.py::daily_ic_series`'s `MIN_ELIGIBLE=15`
— bộ lọc cross-section.

Kiểm tra phân phối thật của `sde_round3_panel.parquet` (204 "ngày" phân
biệt): **lưỡng cực rõ rệt** — 44 ngày có 237-430 mã (các ngày rebalance
TOÀN CỤC thật, universe KHÔNG hề hẹp), 160 ngày chỉ có 1-3 mã (nhiễu, do
129/462 mã ACTIVE có lịch giao dịch gappy — nhiều mã mới niêm yết, vd. VPL
chỉ 296/1.630 phiên — khiến `metrics['date']` của riêng chúng lệch khỏi 44
ngày cụm chính). `MIN_ELIGIBLE=15` lọc đúng chức năng, loại 160 ngày nhiễu.
44 − 1 = 43: ngày rebalance cuối (2026-07-03) thiếu `forward_return_20d`
vì `stock_features.parquet` chỉ có dữ liệu đến 2026-07-16 (cần thêm ~20
phiên nữa, chưa tồn tại) — bị `target_col.notna()` loại tự động.

**Kết luận xác minh — lựa chọn (a) trong 2 phương án đã cho**: 43 là
**ràng buộc chính đáng**, không phải artifact/bug — panel-building và bộ
lọc hoạt động đúng thiết kế, gần tối đa khả thi cho phạm vi đã pre-register.
Sửa một câu giải thích SAI trong bản gốc report (đổ lỗi "universe hẹp" —
không đúng, universe rộng, vấn đề là tần suất lấy mẫu + nhiễu lịch giao
dịch). **Phán quyết Nhánh C giữ nguyên.**

**Cập nhật `SDE_SCORING_REPORT.md`**: thêm mục 4b (bằng chứng xác minh đầy
đủ, trích code + số liệu) và mục 5 "Giới hạn phiên tòa" (ghi nhận trung
thực: N=43 gần sàn tối thiểu N≥30 cho Newey-West, khiến 3-giai-đoạn không
tính được; phần lớn sức nặng kết luận Nhánh C đến từ prior đã có sẵn của
dự án chính — `SCORE_FORENSIC_REPORT.md`/`WATCHLIST_VALIDATION_REPORT.md`
— không phải sức mạnh thống kê riêng của phiên tòa Vòng 3; nếu tương lai
muốn mở lại câu hỏi, cần một prereg MỚI trên panel đầy đủ hơn, không tái
dùng kết quả round này). Đánh số lại mục 5-10 cũ thành 6-11, sửa các
cross-reference nội bộ theo. Không sửa code, không chạy lại script nào.
Full suite: 295 passed, không đổi (đúng như kỳ vọng — không đụng code).

## Phase 14 — Audit lại toàn dự án theo khung gốc (Round 2), đo delta so với 58/100

**Bối cảnh**: audit lại đúng khung `claude_code_quantitative_finance_audit_prompt.md`
(tìm thấy ở `~/Downloads/`, đọc lại toàn bộ) — cùng scorecard 100 điểm, 17
critical gate, severity/confidence levels — để đo tiến độ thật kể từ audit
gốc 2026-07-12 (58/100). INVENTORY-ONLY: không sửa/tạo/xóa file ngoài
`audit/round2/`, không chạy pipeline ghi trạng thái, không gọi dịch vụ
ngoài. `stock-decision-engine/` không còn read-only nhưng chấm thành phụ
lục riêng, không cộng vào 100 điểm chính, để bảng điểm chính so sánh được
với lần trước.

**Kết quả: 78/100 (từ 58/100), "Strong foundation" (từ "Experimental").**
Mọi claim "đã sửa" đều được **tự kiểm chứng độc lập** round này (verify-
not-rediscover + nhãn KNOWN_OPEN/RESOLVED_VERIFIED/RESOLVED_UNVERIFIED/NEW
cho cả 77 dòng gap matrix), không chỉ đọc lại report cũ:

- **Gate #6** (dữ liệu cũ) — RESOLVED_VERIFIED: grep xác nhận
  `build_portfolio_stack.py` đọc qua `dataset_config.OFFICIAL_FEATURES_PATH`,
  chạy lại `tests/test_dataset_config.py` (6/6 pass).
- **Gate #12** (không tái lập được) — RESOLVED_VERIFIED, bằng chứng mạnh
  nhất round này: tính lại độc lập từ đầu (đúng công thức, đúng 10 mã,
  đúng trọng số, đúng ngày cắt đã ghi trong lineage) ra khớp CHÍNH XÁC
  đến 1e-9 cho cả 4 chỉ số (`annual_return`/`annual_volatility`/
  `sharpe_ratio`/`max_drawdown`) VÀ khớp đúng số dòng (1626=1626) — round
  1 từng cho 1621 vs 1317, không khớp gì cả.
- **Gate #17** (model chưa kiểm định nhưng báo như đã kiểm định) —
  RESOLVED_VERIFIED: grep xác nhận `alpha_rs_score` đã gỡ, chạy lại 3
  test hồi quy, kiểm tra trực tiếp artifact `final_watchlist.parquet`
  sống — 0 cột shadow.
- **Gate #3** (survivorship bias) — VẪN MỞ, xác nhận lại: grep
  `check_survivorship_bias` — 0 nơi gọi.

**Delta lớn nhất**: Signal/Alpha 4→9/12 (+5) — composite `final_watchlist`
lần đầu tiên được IC/null-test toàn bộ, kết quả ÂM TÍNH, hệ thống đã đổi
hành vi sống theo đúng kết luận (Nhánh C) — coi là điểm CỘNG (kết luận
nghiên cứu có bằng chứng), không phải MISSING, đúng chỉ dẫn round này.
Robustness 4→7/8 (+3) — DSR/BH-FDR/bootstrap CI đều mới, xác nhận có thật
trong `ROBUSTNESS_REPORT.md`. Covariance/Risk 8→11/12 (+3) — Gate #12.
Engineering 4→5/5 (full điểm) — pin dependency, atomic write, lịch Tết âm
lịch, 1 test lỗi cũ đều xác nhận đã sửa.

**Phát hiện MỚI (không có trong 75 dòng gốc)**: `portfolio_return_series`
âm thầm coi ngày không giao dịch là return 0% (fillna(0.0)) thay vì loại
trừ — phát hiện khi tự tính `w^T Sigma w` độc lập không khớp (0.2404 vs
0.2315) cho đến khi khớp đúng convention này; 3/10 mã trong sample
portfolio hiện tại có 12-15% ngày NaN. Không phải bug (công thức tự nhất
quán khi áp đúng convention) nhưng chưa được ghi tài liệu. Cũng ghi nhận:
daily automation (LaunchAgent) bị chặn TCC macOS, cần người dùng thao tác
tay (đã biết từ Phase 11-12, không phải phát hiện code mới nhưng chưa có
trong 75 dòng gốc vì automation chưa tồn tại lúc đó).

**Phụ lục stock-decision-engine**: 43/100, Experimental, 1 critical gate
mở (survivorship kế thừa từ cùng universe). 3 gate khác (dữ liệu cũ, tái
lập, model chưa kiểm định) đã sửa TUẦN NÀY và xác nhận độc lập — thực ra
sửa triệt để hơn dự án chính (gỡ hẳn composite thay vì chỉ vá).

**Kết luận không đổi dù điểm tăng 20**: theo đúng luật "high score không
override critical failure" của khung audit — vẫn KHÔNG được xếp
production-grade, vẫn KHÔNG dùng vốn thật, vì Gate #3 (point-in-time
universe) vẫn mở. Đây là việc lớn nhất còn lại, không đổi so với round 1.

**Deliverables**: `audit/round2/` — 9 file gốc theo khung + `delta_scorecard.md`
(mới, theo yêu cầu round này) + 2 file phụ lục SDE. `audit_summary.json`
thêm `previous_score`/`delta`. Full suite 295 passed (không đụng code).
Một commit duy nhất, không push.

## Phase 15 — sự cố LaunchAgent PATH + PROJECT_HANDBOOK.md (3 lô, this session)

**Bối cảnh**: session mới yêu cầu viết `docs/PROJECT_HANDBOOK.md` — sổ tay
toàn thư thay thế `docs/DAILY_OPERATING_GUIDE.md` làm tài liệu gốc cho chủ
dự án/người ngoài. Giữa lô 1 và lô 2, phát hiện sự cố vận hành thật cần xử
lý khẩn trước khi viết tiếp (theo đúng yêu cầu người dùng).

**Lô 1** (Phần 0-2): hệ thống là/không là gì, trạng thái tại ngày viết, vận
hành hằng ngày (checklist, cỗ máy tự động, giải phẫu log thật), đọc hiểu
từng output (final_watchlist, SDE facts table, chart PNG, shadow log,
trading_status, disclosure, notebook). Trong lúc xác minh log thật cho mục
1.4, phát hiện phụ: LaunchAgent tối 2026-07-17 fail 4/4 bước
(`ModuleNotFoundError`) — khác với chẩn đoán TCC cũ trong `PROJECT_STATE.md`.

**Sự cố LaunchAgent PATH — chẩn đoán + sửa + kiểm chứng** (commit `bcd61d2`):
`scripts/daily_run.sh`'s `PYTHON_BIN` mặc định tra `PATH`, trong `launchd`
(không kế thừa PATH shell tương tác) rơi về Python hệ thống macOS (không có
`pandas`/`requests`/`yaml`). Sửa: hardcode đường dẫn tuyệt đối
`/opt/anaconda3/bin/python3`. Kiểm chứng qua đúng cơ chế `launchd`
(`launchctl kickstart`, không phải chạy tay `bash`): `SUMMARY: 4/4 steps OK`
tối 2026-07-18. Khoảng trống shadow log ngày 2026-07-17 đã đóng — **0 ngày
giao dịch bị mất** (`run_alpha_scoring.py` stamp theo `date` thật của dữ
liệu, không phải ngày chạy) — chi tiết: `PROJECT_STATE.md` mục 4,
`docs/reports/scoring/SCORE_V2_REPORT.md` mục "Cập nhật 2026-07-18" (commit
`3434bf2`). Data commit riêng cho lần catch-up: `3f71a32`. Tại thời điểm
hoàn thành lô 3, agent vẫn CHƯA có một lần kích hoạt TỰ NHIÊN (không
kickstart) kể từ fix — cơ hội đầu tiên: tối Thứ Hai 2026-07-20 19:00, ghi
thành dòng theo dõi trong sổ tay (mục 0.3/1.2), không che giấu.

**Lô 2** (Phần 3-6): workflow ra quyết định đầu tư (cây 4 bước, quy tắc
sizing 5% value_ma20 đóng khung là heuristic không phải nghiên cứu, 2 ví dụ
thật VHM/ATS, template nhật ký quyết định); kiến thức nền 11 khái niệm (mỗi
khái niệm: định nghĩa → vì sao dự án cần → ví dụ thật trích report+commit →
"chỉ nhớ một điều"); biên niên sử 1 trang + bảng 8 hồ sơ đã đóng + bảng 7
bug lớn; xử lý sự cố 8 dòng (bao gồm bài học PATH/env vs launchd vừa xử lý).

**Lô 3** (Phần 7 + Phụ lục + hoàn thiện + PDF): 4 điều kiện xem lại v2 chép
nguyên văn; kịch bản THẮNG/THUA sau 2027-01-16 (đánh dấu [suy luận] rõ ràng
những chỗ không có trong report gốc); lộ trình Gate #3; danh sách "chưa
test" (khối ngoại/margin/index event — xác nhận qua grep chưa từng xuất
hiện trong repo); dịch 10 quy tắc `CLAUDE.md` sang ngôn ngữ người thường.
Phụ lục A (bản đồ repo), B (15 report), C (~30 thuật ngữ Anh-Việt), D (lệnh
copy-paste). Mục lục tự động + đọc lại toàn bộ để nhất quán số liệu/tham
chiếu chéo + grep cuối cùng không còn câu hàm ý khuyến nghị mua/bán.

**Xuất PDF** (`docs/PROJECT_HANDBOOK.pdf`, `scratch/render_handbook_pdf.py`):
không có pandoc/wkhtmltopdf/weasyprint trong môi trường; thay vì cài công cụ
hệ thống nặng (LaTeX/cairo-pango/Chromium), dùng `markdown` + `xhtml2pdf`
(thuần Python, đã có sẵn/pip-install nhẹ, xác nhận không đụng
`pandas`/`numpy`/`scipy` đã pin). 2 vấn đề kỹ thuật thật gặp và sửa: (1)
tiếng Việt hiện dấu thành ô vuông — do đăng ký font qua `pdfmetrics.registerFont`
trực tiếp không tới được registry riêng của `xhtml2pdf` (đọc thẳng source
`xhtml2pdf/context.py` xác nhận), sửa bằng `@font-face` CSS chuẩn trỏ tới
`Arial Unicode.ttf` (copy sang đường dẫn không khoảng trắng); (2) bảng dài
bị cắt ở lề trang — `word-break`/`table-layout:fixed`/zero-width-space đều
KHÔNG có tác dụng trong engine này (xác nhận bằng test cô lập), chỉ khoảng
trắng thật mới tạo điểm ngắt dòng — sửa bằng chèn khoảng trắng thật sau `/`
trong nội dung `<td>` (không đụng `_` để không phá vỡ tên cột ngắn). Phát
hiện + sửa thêm 1 bug tự gây ra: script chèn anchor mục lục ban đầu không
theo dõi trạng thái fenced-code-block, biến 7 dòng comment bash trong Phụ
lục D thành "heading" giả — sửa bằng script fence-aware, xóa 65 anchor cũ,
dựng lại 55 anchor đúng. PDF cuối: 29 trang, ~822KB, mục lục có link nội bộ
thật (xác nhận qua `PyMuPDF` link annotations), 3 chart PNG thật nhúng ở
mục 2.3 (ACB, 2026-07-17).

**Cập nhật tài liệu khác**: `CLAUDE.md` mục 3, `PROJECT_STATE.md` mục 5,
`docs/DAILY_OPERATING_GUIDE.md` (banner "đã hợp nhất") đều trỏ về
`docs/PROJECT_HANDBOOK.md` làm tài liệu gốc mới.

**Nghiệm thu cuối**: xem báo cáo cuối trong phiên làm việc (số trang/từ, danh
sách [chưa xác minh]/[suy luận] còn lại, 3 câu tự kiểm). Commit riêng từng
lô + sự cố + PDF + cập nhật tài liệu khác, không push.

## Audit `notebooks/02_market_research/` — 2026-07-20/21

**Audit thuần** (không sửa logic, không backtest mới, không xóa gì) cho 6
notebook đo market regime/thị trường: `04_market_distribution`,
`05_volatility_regime`, `06_market_regime`, `08_monte_carlo_simulation`,
`10_benchmark_diagnostics`, `13_advanced_quant_analysis`. Báo cáo đầy đủ:
`docs/reports/codebase_audit/MARKET_REGIME_AUDIT.md`.

**Sự cố trong lúc audit (đã xử lý, không có gì mất)**: chạy thật cả 6
notebook qua `jupyter nbconvert --execute` để xác nhận "chạy được không"
(NV1) vô tình ghi đè 2 file production thật vì mỗi notebook tự `os.chdir()`
về project root rồi ghi output bằng đường dẫn tương đối — không phải sandbox
như dự kiến. `data/processed/stock_features.parquet` (từ notebook 05) bị
ghi đè bằng bản THIẾU CỘT so với bản chính thức (~25-30 cột so với 49 cột
thật). `data/processed/market_features.parquet` (từ notebook 06) bị ghi đè
bằng bản CÓ BUG ĐÃ BIẾT (`market_regime` 0 ngày Risk-on — xem finding chính
dưới đây). Báo ngay cho người dùng trước khi đi tiếp (AskUserQuestion), được
xác nhận chạy `python scripts/generate_features.py` — đúng con đường
production tạo 2 file này (đọc `full_history_v2`, không phải backtest/test
mới) — để khôi phục đúng. Xác nhận lại sau khi chạy: `stock_features.parquet`
đủ 49 cột, `market_regime` ra đủ 3 nhãn (`Neutral 857/Risk-off 503/Risk-on
272`). Cả 2 file đều gitignored, không có gì cần commit cho việc khôi phục
này.

**Finding chính (INCORRECT, xác nhận bằng chạy thật + đối chiếu commit)**:
`06_market_regime.ipynb` gọi `add_market_regime(breadth)` **thiếu tham số
`benchmark=`** — tái hiện đúng bug đã biết và đã sửa ở `src/models/regime.py`
(docstring dòng 25-30: thiếu benchmark → `index_above_ma50/200` luôn False →
"Risk-on structurally unreachable"). Notebook cuối sửa `b437c5d`
(2026-07-01), fix ở `regime.py` là commit `86412ed` (2026-07-09) — notebook
có trước fix 8 ngày, chưa bao giờ được cập nhật theo. Hệ quả: mỗi lần ai đó
chạy tay notebook này, `market_features.parquet` (dùng bởi
`run_stealth_accumulation_screen.py`'s `regime_pass` filter) bị âm thầm ghi
đè về trạng thái pre-fix.

**Finding thứ 2 (bug số liệu, notebook 10)**: `mean_return_spread = -inf`
hiển thị thật trong `10_benchmark_diagnostics.ipynb`. Truy nguyên: 387 dòng
`close==0` trong `clean_daily_ohlcv.parquet` (166 mã, toàn bộ 2020-01-13 →
2020-02-25, warmup era — đã biết qua `validate_ohlcv`'s `non_positive_close`
metric từ trước) tạo `return_1d=inf` khi giá về dương ngày kế tiếp;
`build_market_proxy_benchmark` (`src/analytics/benchmark.py`) không có guard
chống inf khi lấy trung bình cross-sectional (khác với `_clean_benchmark_returns`
cùng file, CÓ guard cho phía benchmark) → 25 ngày Jan-Mar 2020 có
`market_proxy_return_1d=inf`, kéo `mean_return_spread` cả kỳ xuống `-inf`.

**Entropy (yêu cầu riêng của người dùng)**: `market_entropy_regime`
(`src/analytics/entropy.py`) — nhãn "Structured" (ngưỡng ≤0.35) **chưa bao
giờ xuất hiện trong 6.5 năm dữ liệu thật**, ở cả 3 cửa sổ 21d/63d/126d (min
đo được: 0.455-0.529, luôn trên ngưỡng). Về thực hành chỉ hoạt động như bộ
phân loại 2 nhãn (Transitional/Chaotic). Nghi vấn kỹ thuật (chưa kiểm chứng
riêng): `n_bins=24` cố định trong khi `window=21` cho tỷ lệ mẫu/bin <1 —
thiên lệch dương đã biết của ước lượng Shannon entropy từ histogram thưa
mẫu. Ngoài ra: chưa từng được kiểm định khả năng dự báo ở đâu trong dự án
(`FOLD_AUTOPSY_REPORT.md` test 3 label khác nhưng không test entropy — đây
là khoảng trống thật, không phải đã-test-và-fail).

**Phân loại đầy đủ + trùng lặp với report cũ** (breadth/vol-regime đã thử ở
`FOLD_AUTOPSY_REPORT`, momentum đã thất bại ở `FACTOR_RETEST_V2_REPORT`,
breadth-collapse persistence overlay ở `CRASH_RISK_RESEARCH_REPORT`): xem
bảng đầy đủ trong `MARKET_REGIME_AUDIT.md` NV2. Không tìm thấy look-ahead
(full-sample normalize) nào trong 6 notebook — toàn bộ dùng rolling/expanding
đúng cách.

**Đề xuất chưa làm** (ưu tiên theo chi phí S trước): (1) sửa notebook 06
truyền `benchmark=`; (2) thêm guard inf vào `build_market_proxy_benchmark`;
(3) đồng bộ cột output notebook 05 với `generate_features.py` hoặc đổi path
để không trùng file production; (4) đổi output path notebook 04/08 ra khỏi
`data/processed/`/`data/signals/` (xác nhận không consumer nào đọc lại);
(5-8) prereg mới cho entropy/pair-divergence/monte-carlo out-of-sample/
breadth-persistence overlay — việc lớn hơn, để vòng sau quyết định.

## Sửa 3 bug kỹ thuật từ MARKET_REGIME_AUDIT + chặn tận gốc ghi đè production — 2026-07-21

Vòng theo dõi trực tiếp round audit trên. **Chỉ sửa bug kỹ thuật cụ thể**
((1) `06_market_regime.ipynb` thiếu `benchmark=`, (2) `-inf` trong
`build_market_proxy_benchmark`, (3) ngưỡng entropy 0.35/0.70 không rõ
nguồn gốc) — **không cải tiến model, không thêm chỉ báo regime mới, không
kiểm định predictive power (IC/backtest)** cho bất kỳ công cụ nào, đúng
ràng buộc đã cho. Chi tiết đầy đủ (bảng so sánh trước/sau, docstring trích
dẫn): `docs/reports/codebase_audit/MARKET_REGIME_AUDIT.md` mục "Cập nhật
2026-07-21". 4 commit, mỗi nhiệm vụ 1 commit riêng, không push:

1. **NV1 (commit `36661b6` guard infra + notebook 04/08;
   commit `d3b59d7` wiring 05/06/10)** — sửa bug gốc: notebook 06 giờ đọc
   `benchmark_vnindex.parquet` và gọi
   `add_market_regime(breadth, benchmark=benchmark)` đúng chữ ký (trước đó
   thiếu tham số, âm thầm tái hiện bug `Risk-on` không đạt được đã sửa ở
   `src/models/regime.py` 8 ngày sau khi notebook được viết). Xác nhận:
   `market_regime` từ `Risk-off 1296/Neutral 335/Risk-on 0` →
   `Neutral 857/Risk-off 503/Risk-on 272`.
   **Quan trọng hơn cả bug fix**: thêm `src/data/production_guard.py` —
   `guard_production_write(path)` chặn ghi vào 3 path chính thức
   (`dataset_config.py`) trừ khi có xác nhận rõ ràng
   (`ALLOW_PRODUCTION_WRITE=1` hoặc `allow=True`), áp dụng cho **cả 6**
   notebook trong `02_market_research/` (không chỉ notebook 06): 04/08 đổi
   hẳn sang ghi vào `notebooks/outputs/` (output mồ côi, không consumer,
   không cần guard nữa); 05/06 (path production thật) gắn guard trước
   `save_parquet()`. Test (`tests/test_production_guard.py`, 7 test) gồm cả
   kịch bản "mock chạy notebook" xác nhận `save_parquet` không bao giờ
   được gọi khi thiếu xác nhận. Xác nhận thật: chạy lại cả 5 notebook
   (`nbconvert --execute --inplace`, không set env var) — mtime
   `data/processed/{stock_features,market_features}.parquet` không đổi.
2. **NV2 (commit `5b630b9`)** — `build_market_proxy_benchmark`
   (`src/analytics/benchmark.py`) giờ NaN-out giá `<=0` trước
   `pct_change()`, đúng convention đã có sẵn ở `add_returns`
   (`src/features/returns.py`) cho cùng loại lỗi (387 dòng `close==0`,
   warmup 2020-01/02). Test mới tái tạo đúng pattern lỗi. Chạy lại notebook
   10: `mean_return_spread` từ `-inf` → `0.003895`.
3. **NV3 (commit `b62c2df`)** — thêm `derive_entropy_regime_thresholds`
   (hàm xác định percentile thuần, cùng loại "hiệu chỉnh xác định từ dữ
   liệu, không phải tune" như `derive_factor_weights` của
   `reversal_quality_score` trước đây). Hardcode kết quả từ
   `market_entropy_21d` toàn lịch sử (2020-01→2026-07, N=1611,
   `scratch/derive_entropy_regime_thresholds.py` tái lập được):
   `low_threshold` 0.35→**0.692**, `high_threshold` 0.70→**0.818**. Cả 2
   ngưỡng đều sửa, không chỉ ngưỡng thấp — đã thử chỉ sửa ngưỡng thấp,
   giữ 0.70 cũ, kết quả "Transitional" sụp còn ~4% (0.70 thực ra chỉ nằm ở
   percentile ~20 của phân phối thật, không hề "cao"). Kết quả trên dữ
   liệu thật: `Structured 0→230`, `Chaotic 1316→228`,
   `Transitional 295→1153` (~15/70/15, cân bằng). Dán nhãn "đã hiệu chỉnh,
   CHƯA kiểm định predictive power" ở cả 3 nơi hiển thị: docstring nguồn,
   annotation trên `entropy_regime_chart` (giờ dùng chung 1 hằng số với
   classifier, trước đó hardcode riêng lẻ, có thể lệch nhau), và print rõ
   trong `06_market_regime.ipynb`.
4. **NV4 (nghiệm thu, commit tài liệu này)** — chạy
   `python scripts/generate_features.py` (không dùng notebook cho bước
   này, đúng bài học sự cố audit trước) để đảm bảo
   `market_features.parquet` production phản ánh đúng cả NV1 và NV3. Full
   suite: 306 passed (+11 test mới, `git diff abaa6a0 HEAD -- tests/`
   xác nhận), 0 fail. Adjacent risk ghi nhận không sửa (ngoài phạm vi):
   `build_market_entropy_profile` có cùng pattern thiếu guard `close<=0`
   như NV2 từng sửa, nhưng nhánh đó hiện không bị kích hoạt bởi bất kỳ
   caller thật nào (cả 2 caller đều truyền `features` đã có `return_1d`
   sẵn) — cờ cho vòng sau nếu có caller mới.

## Prereg + kiểm định predictive power của regime module — 2026-07-21 (kết quả: âm tính)

Lần đầu tiên `market_regime`/`market_entropy_regime` được kiểm định độc
lập như tín hiệu dự báo (trước giờ chỉ dùng làm filter mô tả, vd.
`regime_pass` trong stealth screen). Đúng kỷ luật prereg-trước-code đã
dùng cho disclosure event study/SCORE_V2. 3 nhiệm vụ, mỗi nhiệm vụ 1
commit, không push:

1. **NV1 (commit `613b33f`)** — `docs/reports/scoring/MARKET_REGIME_PREREG.md` khóa TRƯỚC
   khi viết code phân tích. Chốt: 2 đối tượng (`market_regime`,
   `market_entropy_regime`) — **breadth (`pct_above_ma50`) loại khỏi vòng
   này** (không phải vì NaN — xác nhận lại 1632/1632 non-null — mà vì
   không có sẵn dạng phân loại rời rạc, tự dựng ngưỡng mới sẽ tính là
   "thêm chỉ báo mới", bị cấm theo RÀNG BUỘC); 3 giả thuyết H1 (vol có
   điều kiện 20 ngày tới), H2 (persistence, Markov + đo trực tiếp), H3
   (return có điều kiện — làm lại đúng câu `docs/reports/scoring/FOLD_AUTOPSY_REPORT.md` NV2
   đã thử với 5 fold và thiếu lực, giờ chạy trên 1631 ngày); công thức
   biến mục tiêu khóa chính xác (`forward_vol_20d` tự tính theo convention
   `add_realized_volatility`, `forward_return_20d` dùng nguyên cột có
   sẵn); chia 3 giai đoạn đều theo số phiên (544/544/544, trùng gần đúng
   "biên giai đoạn cũ" của `EVENT_DETECTION_REPORT.md` nhưng suy ra độc
   lập, không phải cố tình tái dùng — và xác nhận không có vấn đề thiếu
   coverage 2020-2022 như báo cáo kia vì `stock_count` ổn định suốt); máy
   đo block-bootstrap (block=20, N=2000, seed=42) thay t-test ngây thơ
   (regime tự tương quan theo ngày); tiêu chí PASS/FAIL khóa chính xác
   cho từng giả thuyết.
2. **NV2 (commit `27b8173`)** — `scratch/market_regime_study.py` chạy đúng
   prereg 1 lần, không tune. Báo N mỗi trạng thái TRƯỚC kết quả (đúng yêu
   cầu) — nhóm mỏng nhất: Structured@P2 chỉ 27 ngày, Risk-on@P2/P3
   68/63 ngày. **Kết quả: 0/12 combo (H1/H2/H3 × 2 chỉ báo) đạt tiêu chí
   đã khóa** — âm tính toàn diện.
3. **NV3 (commit `c14fd80`, cập nhật hồ sơ commit `d9b43c9`)** —
   `docs/reports/scoring/MARKET_REGIME_STUDY_REPORT.md`. Chi tiết đầy đủ trong report; điểm
   đáng chú ý nhất: (a) **naive Mann-Whitney+BH-FDR "tìm thấy" 17/36 so
   sánh có ý nghĩa, block-bootstrap đúng phương pháp chỉ 6/36, và 0/12
   combo giữ được cả 3 giai đoạn** — bằng chứng thực nghiệm trực tiếp
   (không chỉ lý thuyết) cho lý do phải dùng block-bootstrap với dữ liệu
   tự tương quan; (b) H2 cho thấy trạng thái đa số (Neutral/Risk-off,
   Transitional) khá bền nhưng trạng thái cực đoan (Risk-on, Structured,
   Chaotic) rã về gần ngẫu nhiên trong vài tuần — sắc thái thật dù không
   đổi kết luận FAIL; (c) 2 near-miss ở H1 (Risk-on−Risk-off,
   Transitional−Chaotic: cùng dấu cả 3 giai đoạn, CI chỉ loại trừ 0 ở
   1/3) ghi nhận cho tương lai, không phải kết luận. Thêm dòng #9 vào
   "5.2. Bảng hồ sơ đã đóng" (`docs/PROJECT_HANDBOOK.md`).

**Không làm trong vòng này** (đúng RÀNG BUỘC): không kiểm định regime ×
chọn mã (không join cấp-mã, không tính null-test percentile của bất kỳ
composite nào cùng regime); không thêm chỉ báo mới; không tune tham số
sau khi thấy kết quả; kết quả âm tính không kéo theo thử định nghĩa
trạng thái khác. Full suite sau vòng này: 306 passed (không đổi so với
trước — vòng này không sửa code sản xuất, chỉ thêm 1 script nghiên cứu +
tài liệu).

## Ghi 2 phát hiện phụ từ MARKET_REGIME_STUDY vào đúng chỗ — 2026-07-21

Hồ sơ #9 đã đóng ở vòng trước — vòng này KHÔNG phân tích thêm, KHÔNG mở
lại câu hỏi đã đóng, chỉ đưa 2 phát hiện phụ đã có sẵn trong
`docs/reports/scoring/MARKET_REGIME_STUDY_REPORT.md` vào đúng vị trí tài liệu. 2 nhiệm vụ,
mỗi nhiệm vụ 1 commit, không push:

1. **NV1 (commit `7ac5cc5`)** — `docs/PROJECT_HANDBOOK.md` mục 4.4 (IC
   Spearman & Newey-West HAC) thêm "Ví dụ THẬT thứ hai": block bootstrap
   là cùng họ vấn đề với Newey-West (naive stat nói dối khi dữ liệu tự
   tương quan) nhưng sửa cho trường hợp khác — Newey-West chỉ sửa khi
   TARGET chồng lấn, block bootstrap cần khi chính BIẾN NHÓM cũng tự
   tương quan (regime). Ví dụ: `market_regime` "Risk-on − Risk-off", H1,
   P1 — naive Mann-Whitney p=2.99e-08 (trông rất mạnh) vs CI
   block-bootstrap `[-0.144, 0.017]` (chứa 0). Toàn nghiên cứu:
   naive+FDR "tìm" 17/36, block-bootstrap chỉ giữ 6/36.
2. **NV2 (commit `76ffad6`)** — thêm 1 khối QUAN SÁT dán nhãn rõ (không
   phải kết luận, không đổi verdict FAIL của H2) vào
   `docs/reports/scoring/MARKET_REGIME_STUDY_REPORT.md` mục 4: trạng thái cực trị
   (Risk-on/Structured/Chaotic) rã về gần ngẫu nhiên trong vài tuần
   (persistence lag=20 chỉ 29.0%/13.0%/14.5%), trạng thái trung tâm
   (Neutral/Transitional) dính >60%+ ở phần lớn phạm vi. Ghi rõ: đây là
   hình dạng dữ liệu nhận thấy SAU KHI xem kết quả (không phải giả thuyết
   đã pre-register), gợi ý cho một overlay tương lai CHỈ hành động ở
   trạng thái cực trị — CHƯA phải cơ sở để dùng, cần prereg riêng nếu
   theo đuổi.

Không có thay đổi code, không có phân tích/chạy script mới, không đổi bất
kỳ kết luận PASS/FAIL nào của hồ sơ #9. Full suite không cần chạy lại
(chỉ sửa 2 file tài liệu).

## Chuẩn hóa ddof=1 (Finding #1 GSQUANT_REFERENCE_CHECK) + hợp nhất 2 implementation Sharpe — 2026-07-21

Sửa kỹ thuật thuần theo bằng chứng đã có từ `GSQUANT_REFERENCE_CHECK.md`
Finding #1 — không phải tune. 5 nhiệm vụ, mỗi nhiệm vụ 1 commit, không push:

1. **NV1 (commit `d69f85e`)** — trước khi sửa, grep TƯƠI lại toàn bộ 10 điểm
   (không tin report suông) — khớp chính xác với report gốc. Đổi `ddof=0`→
   `ddof=1` ở `src/risk/management.py` (6 điểm: `annualized_volatility`,
   `sharpe_ratio`, `rolling_sharpe_series`, `expanding_sharpe_series`,
   `sharpe_stability_report`, `portfolio_beta`'s guard) và
   `stock-decision-engine/src/risk.py` (4 điểm: `downside_deviation`, vol
   trong `ratios()`, `information_ratio`, `tracking_error`). KHÔNG đụng
   `sortino_ratio`'s downside deviation (dùng `np.mean`, đúng convention
   Sortino chuẩn — chia cho N đầy đủ, không phải lựa chọn biased/unbiased std
   — không phải cùng loại vấn đề) hay `src/analytics/entropy.py:15`/
   `scripts/build_portfolio_stack.py:98` (cùng loại `ddof=0` nhưng KHÔNG nằm
   trong 10 điểm đã nêu — ngoài phạm vi, để lại cho vòng sau).
2. **NV2 (commit `fe253e5`)** — `scripts/main_visual_dashboard.py`'s
   `calculate_sharpe_ratio` (implementation Sharpe độc lập thứ 2) gỡ bỏ hoàn
   toàn, thay bằng import `sharpe_ratio` từ `src.risk.management` trực tiếp
   — đúng nguyên tắc "một nguồn sự thật" đã dùng cho Gate #6. Xác nhận đại số
   trước khi sửa: 2 công thức đã tương đương toán học từ trước (chỉ khác
   `ddof`), giờ cho ra CÙNG một function object.
3. **NV3 (commit `fb8bce8`)** — `tests/test_ddof_consistency.py` (9 test):
   AST-scan 2 file đã sửa chặn tái xuất hiện `ddof=0`; snapshot test so khớp
   công thức unbiased qua numpy độc lập (sai số <1e-9); test xác nhận `ddof`
   thật sự đổi số (không phải no-op, và luôn đúng chiều "ddof=0 thổi phồng
   Sharpe"); test xác nhận 2 nơi gọi Sharpe giờ là cùng 1 function object
   (không chỉ cùng kết quả).
4. **NV4 (commit `2dfc6bc`)** — đánh giá tác động ngược, truy chuỗi import
   THẬT (không suy đoán): `WATCHLIST_VALIDATION_REPORT.md` không dùng module
   bị ảnh hưởng; `SCORE_V2_REPORT.md` chỉ trích dẫn số từ `ROBUSTNESS_REPORT.md`;
   **`ROBUSTNESS_REPORT.md`'s Sharpe=0.32 (N=1,120) CÓ đi qua hàm đã sửa**
   (`scratch/dsr_and_bootstrap_v2.py` → `run_portfolio_backtest` →
   `calculate_sharpe` → `src.risk.management.sharpe_ratio`) — lệch định
   lượng `sqrt(1120/1119)≈1.00045` (+0.045%), dưới độ chính xác hiển thị của
   report, **không đổi kết luận DSR=0.0083** (tính độc lập, đã `ddof=1` từ
   trước) **hay kết luận "CI chứa 0"**. Không chạy lại backtest nào (đúng
   yêu cầu) — lệch tính trực tiếp từ N đã biết. Không tìm thấy report nào
   dùng cửa sổ ngắn N<63 làm căn cứ quyết định (grep toàn `docs/` cho tên
   field `sharpe_stability_score`/`rolling_sharpe_latest`/
   `expanding_sharpe_latest` ra rỗng) — không cần gắn cờ riêng.
   **Phát hiện phụ mới, chưa sửa**: `scratch/dsr_and_bootstrap_v2.py:125`
   dùng `numpy.std(axis=1)` mặc định `ddof=0` (khác pandas!) để sinh khoảng
   CI Sharpe đã công bố `[−0.59, +1.32]` — file này KHÔNG nằm trong 10 điểm
   NV1, không do vòng này gây ra, cũng chưa sửa — cờ cho vòng sau, chưa định
   lượng độ lệch.
5. **NV5 (commit `2dfc6bc`, cùng commit với NV4)** — cập nhật
   `GSQUANT_REFERENCE_CHECK.md` đánh dấu Finding #1 RESOLVED kèm commit. Full
   suite: **315 passed** (306 trước đó + 9 test mới), 0 fail.

**Không đụng trong vòng này** (đúng RÀNG BUỘC): Finding #2 (annualization
hardcode) và Finding #3 (percentile tie-handling) — vẫn nguyên trong danh
sách chờ của `GSQUANT_REFERENCE_CHECK.md`, không tự sửa lẫn vào để giữ commit
sạch, dễ review.

## Đóng hồ sơ họ bug ddof (vòng 2/2) — sửa CI đã công bố + quét lần cuối — 2026-07-21

NV4 vòng trước phát hiện `scratch/dsr_and_bootstrap_v2.py:125` dùng
`ddof=0` mặc định của numpy, ăn trực tiếp vào một khoảng tin cậy ĐÃ CÔNG BỐ
trong `ROBUSTNESS_REPORT.md` — khác các fix trước ở chỗ nó chạm tới ranh
giới kết luận, không chỉ một số hiển thị. Vòng này sửa + định lượng, đúng
RÀNG BUỘC (sửa lỗi tính toán đã xác định, không tune, không mở lại kết
luận). 4 nhiệm vụ, mỗi nhiệm vụ 1 commit, không push:

1. **NV1 (commit `4057031`)** — trước khi sửa, grep lại toàn bộ `scratch/`
   cho mọi `.std(`/`.var(`/`.cov(` (không chỉ dòng 125 đã nêu) — xác nhận
   đây là điểm DUY NHẤT trong `scratch/` thuộc họ bug (mọi chỗ khác đã
   `ddof=1` tường minh, hoặc cặp `.rolling().cov()`/`.rolling().var()` cho
   beta — bất biến với ddof). Sửa `sims.std(axis=1)` → `sims.std(axis=1,
   ddof=1)`.
2. **NV2 (commit `4f3994c`)** — định lượng tác động lên kết luận ĐÃ CÔNG BỐ:
   chạy lại đúng script gốc (cùng seed=42, cùng dữ liệu, cùng cửa sổ
   backtest — N=1,120 không đổi, xác nhận không có data drift từ lần chạy
   gốc 16/7). Sharpe CI: cũ `[−0.5907, +1.3172]` → mới `[−0.5905, +1.3167]`
   — lệch ±0.045%, khớp gần như tuyệt đối hệ số lý thuyết
   `sqrt(1120/1119)=1.000447` (mọi giá trị Sharpe mô phỏng dùng chung
   `horizon_days=N`, nên co giãn theo đúng 1 hệ số hằng — lý thuyết và số
   chạy lại thật khớp nhau). **Cả CI cũ và mới đều chứa 0 — kết luận không
   đổi.** DSR=0.0083 không đổi (tính độc lập, đã `ddof=1` từ đầu). Cập nhật
   số vào `ROBUSTNESS_REPORT.md`, dán nhãn rõ "đã sửa lỗi tính toán, không
   phải nghiên cứu mới".
3. **NV3 (commit `5438775` + `84d5e1d`)** — quét lần cuối TOÀN repo (`src/`,
   `scripts/`, `scratch/`, `notebooks/`, `stock-decision-engine/`) cho mọi
   `.std(`/`.var(`/`.cov(` không chỉ chỗ có sẵn `ddof`. Sửa thêm 4 điểm để
   đóng hồ sơ dứt điểm: `src/simulation/bootstrap.py:81`
   (`summarize_simulation`, cùng pattern numpy-mặc-định-ddof=0),
   `scripts/build_portfolio_stack.py:98` (fallback path thật, hiếm kích
   hoạt), `src/analytics/entropy.py:15` (dead code — 0 lời gọi, sửa chỉ để
   nhất quán), `stock-decision-engine/src/features.py:158` (trùng công thức
   với `risk.py:14` đã sửa vòng 1). Mọi `.std(`/`.var(`/`.cov(` còn lại
   trong repo đã xác nhận an toàn (pandas mặc định `ddof=1`, hoặc tỷ số
   cov/var bất biến với ddof) — liệt kê đầy đủ trong
   `GSQUANT_REFERENCE_CHECK.md`. **Không còn điểm nào cần theo dõi.**
   `tests/test_ddof_consistency.py` mở rộng: AST scanner giờ phủ 7 file,
   thêm scanner riêng chặn `.std()`/`.var()` KHÔNG có `ddof` trên 2 file
   thao tác mảng numpy thô, 11 test snapshot mới.
4. **NV4 (commit `84d5e1d`, cùng đợt với tài liệu)** — full suite: **326
   passed** (315 trước đó + 11 test mới), 0 fail. `ROBUSTNESS_REPORT.md` và
   `GSQUANT_REFERENCE_CHECK.md` cập nhật đầy đủ, Finding #1 (họ bug ddof)
   **ĐÃ ĐÓNG HỒ SƠ HOÀN TOÀN** qua 2 vòng.

**Không đụng**: Finding #2/#3 (annualization hardcode, percentile
tie-handling) — vẫn ngoài phạm vi, còn trong danh sách chờ.

## Audit toàn bộ notebook còn lại (13 file, cả 2 dự án) — 2026-07-21

**Bối cảnh**: sau `MARKET_REGIME_AUDIT.md` (6 notebook `02_market_research/`,
2 bug nghiêm trọng), nghi ngờ hợp lý các notebook khác chưa từng được audit
tương tự. Vòng này: kiểm kê + chạy thật top-to-bottom toàn bộ 13 notebook
còn lại (dự án chính + `stock-decision-engine/`), **audit thuần** — không
sửa logic, không xóa gì. Báo cáo đầy đủ:
`docs/reports/codebase_audit/NOTEBOOK_AUDIT_FULL.md`.

**Bài học phương pháp áp dụng ngay từ đầu** (rút từ chính sự cố
`MARKET_REGIME_AUDIT.md`): mọi notebook chạy trong sandbox cô lập (rsync
toàn bộ repo vào scratch, `nbconvert` chạy BÊN TRONG sandbox, không bao giờ
trỏ vào thư mục gốc thật). Đã xác nhận bằng đối chiếu mtime/`git status`/
`git diff` thư mục gốc thật trước/sau mỗi lần chạy — 0 file thật nào bị đổi
trong suốt vòng audit, kể cả khi 2 notebook cố ý thử ghi đè production.

**Phát hiện nguy cơ ghi-đè-production — đã báo NGAY, dừng lại chờ xác nhận
trước khi quét tiếp** (đúng bài học cũ, không đợi hết audit mới báo): 2
notebook trong `00_archive/` (`02_fetch_daily_ohlcv.ipynb`,
`03_clean_validate_data.ipynb`) ghi thẳng `data/processed/clean_daily_ohlcv.parquet`
— 1 trong 3 path chính thức — **hoàn toàn không qua `guard_production_write()`**,
xác nhận `guard` hiện chỉ được wire vào 2 notebook của `02_market_research/`,
chưa từng mở rộng ra chỗ khác. `03_*` còn âm thầm tạo dữ liệu RỖNG (đọc từ
`data/raw/daily_ohlcv/` — đã bị `full_history_v2` thay thế, giờ rỗng hoàn
toàn) mà không raise lỗi nào. Người dùng xác nhận: ghi nhận, tiếp tục quét
phần còn lại, không sửa trong vòng này.

**Kết quả (13 notebook)**: 10 VALIDATED (chạy đúng, khớp `src/` hiện tại —
gồm `15_risk_management.ipynb` tự động kế thừa fix `ddof=1` vì import trực
tiếp từ `src.risk.management`, không có phép tính cục bộ nào), 4 BROKEN xác
nhận qua chạy thật:
- `12_meta_ranking_optimization.ipynb` — `ModuleNotFoundError` (cell
  project-root dùng logic yếu hơn chuẩn `find_project_root()` của các
  notebook khác).
- `19_validation_and_stress_test.ipynb` — không hoàn thành trong 30 phút
  (truyền dữ liệu giá thô thay vì `features` đã tính sẵn vào
  `run_breakout_research`).
- `20_portfolio_backtester.ipynb` — `ValueError` vì thiếu `benchmark_features=`,
  tham số bắt buộc từ commit `bef0de6` gỡ fallback benchmark ngầm — **đúng
  loại "gọi hàm lỗi thời" y hệt vụ `06_market_regime`**.
- `17_live_watchlist_dashboard.ipynb` (`00_archive/`) — `AttributeError` vì
  cột `forward_return_20d` không còn trong schema hiện tại.

Cộng 1 CONVERTED_TO_SCRIPT (`11_trade_card_generation.ipynb`, đã có
`scripts/generate_trade_cards.py` thay thế) và 2 rủi ro-ghi-đè-production
nêu trên. Không tìm thấy look-ahead/full-sample-normalize nào trong bất kỳ
notebook nào chạy hoàn chỉnh.

**Sự cố phương pháp đáng ghi lại (không phải sự cố an toàn — không có gì
mất)**: 2 lần đầu (`07_breakout_research.ipynb` timeout 600s mặc định,
`12_meta_ranking_optimization.ipynb` lỗi import) đọc nhầm output CŨ đã lưu
sẵn trong `.ipynb` (từ lần chạy thật gần nhất của người dùng) là "output vừa
chạy", vì `nbconvert` không ghi file khi gặp lỗi/timeout không bắt được. Đã
xác minh lại bằng traceback thật trong log terminal + đối chiếu mtime trước
khi kết luận — không có gì bị ghi sai ở đâu cả, chỉ là hiểu nhầm tạm thời
trong lúc audit, được tự sửa trước khi báo cáo.

**Đã cập nhật**: `docs/PROJECT_HANDBOOK.md` mục 2.8 (bảng trạng thái
notebook, khớp kết quả chạy thật thay vì chỉ dựa vào banner tự khai).

**Đề xuất chưa làm (để vòng sau)**: mở rộng `guard_production_write()`/
`PROTECTED_PATHS` ra ngoài `02_market_research/`; sửa 4 notebook BROKEN;
cân nhắc archive/xóa 2 notebook rủi ro cao + `11_trade_card_generation.ipynb`.
Chi tiết đầy đủ trong `NOTEBOOK_AUDIT_FULL.md`.

## Vòng theo dõi trực tiếp: mở rộng guard + sửa BROKEN + rào chắn cấu trúc — 2026-07-21/22

Ba nhiệm vụ theo đúng thứ tự ưu tiên đã giao (an toàn dữ liệu trước, sửa lỗi
chạy được sau, rào chắn chống tái phát cuối cùng). 3 commit riêng, không
push:

1. **NV1 (commit `aa97ae2`)** — mở rộng `production_guard.py`: quét lại toàn
   bộ 23 notebook thật (không phải 26 như ước tính), xác nhận đúng 2
   notebook ghi thẳng path bảo vệ mà chưa có guard —
   `00_archive/02_fetch_daily_ohlcv.ipynb` và `03_clean_validate_data.ipynb`
   (cả 2 ghi `clean_daily_ohlcv.parquet`). Thêm guard cùng pattern với
   `02_market_research/05+06`. Chẩn đoán RÕ nguyên nhân dữ liệu rỗng của
   `03_*`: đọc `data/raw/daily_ohlcv/` = `LEGACY_PRICE_RAW_DIR`
   (`src/data/dataset_config.py:46`), đã rỗng hoàn toàn từ khi gate #6 fix
   (2026-07-13) — ghi rõ trong code, KHÔNG sửa logic đọc (ngoài phạm vi NV1).
   Xác nhận qua sandbox cô lập: guard chặn đúng, in thông báo rõ, file thật ở
   gốc dự án không đổi (`cmp` khớp).
2. **NV2 (commit `0406234`, 3/4 notebook)** — sửa theo đúng chữ ký hàm hiện
   tại: `12_meta_ranking_optimization.ipynb` (thay cell project-root yếu
   bằng `find_project_root()` chuẩn), `20_portfolio_backtester.ipynb` (thêm
   `benchmark_features=` bắt buộc từ commit `bef0de6`),
   `17_live_watchlist_dashboard.ipynb` (đổi fallback cột từ
   `forward_return_20d` — không tồn tại, look-ahead — sang `median_return`,
   cùng họ thống kê với `avg_return`). Cả 3 xác nhận hết lỗi qua chạy thật
   trong sandbox cô lập. `19_validation_and_stress_test.ipynb`: root cause
   (input thô thay vì `features` đã tính sẵn) đã sửa trong working tree,
   đo trực tiếp xác nhận `run_breakout_research` với input đúng hoàn tất
   sạch ~22 phút (không lỗi) — nhưng cell còn 3 lệnh gọi sensitivity/cost/
   risk khác cộng dồn đủ vượt 40 phút trong 2 lần thử nbconvert (kể cả chạy
   cô lập hoàn toàn, không tiến trình nặng nào khác). Đây là chi phí tính
   toán THẬT của thiết kế nghiên cứu nhiều tầng trên toàn universe, không
   phải bug — đúng ràng buộc đã cho, không tối ưu/cắt bớt logic. Commit này
   giữ lại cho 3 notebook đã xác nhận đầy đủ; `19_*` chờ xác nhận runtime
   dài hơn trước khi commit riêng.
3. **NV3 (commit `9d63572`)** — `scripts/check_notebooks.py` +
   `make check-notebooks`: chạy toàn bộ notebook top-to-bottom trong sandbox
   cô lập (rsync riêng, sync lại trước mỗi file để tránh nhiễu chéo), báo
   PASS/FAIL/SKIPPED + traceback rút gọn, log JSON. Notebook gọi API sống
   không giới hạn (SSI) bỏ qua mặc định (`--include-live` để chạy). Notebook
   nặng có timeout riêng dài hơn, lý do ghi rõ trong code. Smoke-test xác
   nhận đúng logic skip/timeout. Thêm CLAUDE.md mục 11: đổi chữ ký hàm được
   notebook gọi tới → phải chạy `make check-notebooks` trước khi coi xong.

**Nghiệm thu**: full suite 326 passed, 0 failed (không đổi — chỉ sửa
`.ipynb`, không đụng `src/`/`tests/`). Đã cập nhật
`docs/reports/codebase_audit/NOTEBOOK_AUDIT_FULL.md` (mục "Cập nhật
2026-07-21/22") và `docs/PROJECT_HANDBOOK.md` mục 2.8.

**Cập nhật cuối — `19_validation_and_stress_test.ipynb` xác nhận xong
(commit theo sau)**: sau 2 lần thử timeout 1800s/2400s vẫn `CellTimeoutError`
(cell thật cộng dồn `run_breakout_research` + 3 lệnh sensitivity/cost/risk
khác trong cùng 1 ngân sách thời gian), chạy lại với timeout 5400s (cô lập
hoàn toàn) → **hoàn tất SẠCH, thời gian thật ~51 phút**. `scripts/check_notebooks.py`
cập nhật timeout riêng cho notebook này lên 4500s để phản ánh đúng chi phí
thật. **4/4 notebook BROKEN đã sửa + xác nhận xong trong vòng này.**

## Dọn dẹp gitignore + commit sync tự động 2 ngày + push — 2026-07-22

`git status` cho thấy `daily_run` đã tự chạy đúng lịch qua launchd 2 ngày
liên tiếp không cần can thiệp tay (2026-07-19, 2026-07-20). 3 nhiệm vụ, mỗi
nhiệm vụ 1 commit:

1. **Gitignore (commit `6a0cfcd`)** — `logs/` xuất hiện untracked dù đã có
   `*.log` vì `scripts/check_notebooks.py` (thêm vòng trước) ghi thêm 1 file
   `.json` không khớp pattern; đổi sang ignore cả thư mục `logs/`. Thêm
   `docs/.Rhistory` (file rác 0 byte, không liên quan dự án). Không có gì
   trong `logs/`/`docs/.Rhistory` từng được track trước đó.
2. **Data sync (commit `7582996`, "data: automated daily sync 2026-07-19 →
   2026-07-20")** — xác nhận qua log thật (`daily_price_update_log.jsonl`,
   `daily_update_log.jsonl` đều có 2 `run_at` mới, 0 lỗi fetch) trước khi
   commit: 1470 file — giá 2 ngày (`data/full_history_v2/raw/*.parquet` +
   440 mã), disclosure raw 2 ngày (~1000 file JSON mới), watchlist
   (`data/signals/final_watchlist.csv`, `reports/*`), SDE outputs (GEX cập
   nhật + TCB mới, cả file lẫn `stock_buy_decision.ipynb`'s `TICKER` param —
   xác nhận trước khi gộp: chỉ đổi tham số/output, không đổi logic cell
   nào). `14_portfolio_construction.ipynb` cũng đổi nhưng xác nhận chỉ
   output (source từng cell so HEAD giống hệt) — gộp chung vì cùng bản chất
   dữ liệu tự sinh.
3. **Push** — `git push origin main`: `7a0a386..7582996`, xác nhận
   `origin/main` khớp local main tuyệt đối (`rev-parse` 2 bên bằng nhau).

Cập nhật `PROJECT_STATE.md` (mục LaunchAgent): đánh dấu xác nhận qua nhiều
tầng dữ liệu thật độc lập (giá/disclosure/watchlist/SDE), không chỉ qua
log cục bộ.

## Đáp lại adversarial review (AI thứ 2) — xử lý có chọn lọc, 5 nhiệm vụ — 2026-07-22

Review từ một AI thứ 2 lọc ra 3 finding có căn cứ mạnh + 2 claim cần verify.
Vòng này XỬ LÝ CÓ CHỌN LỌC — verify trước khi sửa, không sửa mù theo toàn bộ
review. 5 commit riêng biệt, không push (yêu cầu rõ: đây là sửa lại số đã
công bố, cần review trước):

1. **NV1 (commit `f28fb8b`) — Verify Newey-West, KHÔNG sửa**: cài/dùng
   `statsmodels` (đã có sẵn 0.14.2, import trực tiếp
   `statsmodels.regression.linear_model`/`statsmodels.stats.sandwich_covariance`,
   bỏ qua `statsmodels.api` bị lỗi do scipy>=1.17), so `_newey_west_mean_se`
   với `OLS(...).fit(cov_type="HAC")` trên 27 tổ hợp tổng hợp (AR(1),
   n/maxlags/tự tương quan khác nhau) + 3 chuỗi IC thật (n=1592-1608,
   maxlags=20, đúng tham số dùng để tạo bảng đã công bố). **Khớp 0.0000% ở
   mọi trường hợp** — claim của review SAI, không sửa code. Chi tiết:
   `docs/reports/scoring/ROBUSTNESS_REPORT.md` mục 2b.
2. **NV2 (commit `a0ec130`) — đếm lại M cho DSR**: quét `git log --all` cho
   toàn bộ 57 script `scratch/*.py` từng tồn tại (không chỉ những gì còn
   trích dẫn), tìm ra 5 nguồn có bảng số thật chưa từng gộp vào M=560 cũ
   (`MARKET_REGIME_STUDY_REPORT` +12, `CRASH_RISK_RESEARCH_REPORT` +4,
   `SCORE_FORENSIC_REPORT` NV3 +8, quantile-spread +3, một đợt factor-screen
   Phase B sớm hơn ~53 nhân tố chưa từng lên report), sửa lại 1 dòng ước
   lượng cũ (portfolio-sensitivity: 9→4, tìm được bảng số thật). Báo 3
   scenario thay vì 1 số cứng: bảo thủ M=560 (0.83%), trung bình M=635
   (0.75%), rộng M=678 (0.71%) — **kết luận không đổi ở cả 3 mức M**.
3. **NV3 (commit `b0f017b`) — sửa circular logic sàn survivorship**: sàn
   +0.4/+1.2/+2.9% là HỖN HỢP survivorship bias + size/liquidity-tilt của bộ
   lọc "đủ điều kiện", không tách được ở round trước, và trước đây bị mô tả
   như một mức TRỪ CHÍNH XÁC. Viết lại `SURVIVORSHIP_BIAS_ESTIMATE.md` +
   quét sửa cách diễn giải ở `ROBUSTNESS_REPORT.md`, `SCORE_V2_REPORT.md`,
   `PROJECT_HANDBOOK.md` (mermaid + Bước 4), `DAILY_OPERATING_GUIDE.md`,
   `PROJECT_STATE.md` — giờ dùng như CẬN TRÊN thô, không phải mức trừ chính
   xác. Không đụng 2 file prereg đã khóa (`WATCHLIST_VALIDATION_PREREG.md`,
   `SDE_SCORING_PREREG.md`) và 3 report chỉ narrate mô tả (không có claim
   hành động cần sửa).
4. **NV4 (commit `9973a21`) — caveat explore-rồi-confirm cho Prereg 2**:
   thêm mục 6 vào `DISCLOSURE_PREREG_2_REPORT.md` — thừa nhận thiết kế đối
   chứng khớp cặp bị thông tin bởi mẫu hình quan sát ở round 1 trên CÙNG
   dataset (không phải out-of-sample sạch), giải thích H0 (đối chứng nội bộ,
   khóa trước, cùng dataset "đã khám phá") là bằng chứng GIÁN TIẾP giảm nhẹ
   rủi ro này (nếu thiết kế chỉ đang tái tạo pattern giả, H0 nhiều khả năng
   cũng dương giả — nhưng ra âm tính sạch), và mức tin cậy nên đọc thấp hơn
   một bậc so với prereg thuần túy. Kết luận đóng nhánh KHÔNG đổi.
5. **NV5 (kiểm tra thuần, không sửa)** — 3 nghi vấn bug dự đoán:
   - **Lot size fractional shares**: XÁC NHẬN CÓ THẬT.
     `src/capital/management.py` dùng `np.floor(value/price)` ra số cổ phiếu
     lẻ (vd. 4722), không làm tròn xuống bội số 100 (`config/vn_market_rules.yaml`'s
     `lot_size: 100` xác nhận grep 0 kết quả sử dụng, khớp
     `audit/PATH_TO_100.md` dòng 174 đã ghi từ trước). **Không ảnh hưởng bất
     kỳ con số đã công bố nào** — `src/backtest/portfolio_backtest.py` (động
     cơ đứng sau MỌI CAGR/Sharpe/DSR/t_NW đã công bố) xác nhận grep 0 kết
     quả cho `quantity`/`shares`/`lot` — hoạt động thuần trên tỷ trọng liên
     tục, không bao giờ tính số cổ phiếu rời rạc. Chỉ ảnh hưởng
     `build_capital_plan`/`align_capital_plan_to_target_weights` (công cụ
     sizing SỐNG, thực thi tương lai) — đúng diện hoãn GĐ6, không sửa.
   - **Bootstrap cross-sectional structure**: KIỂM TRA, KHÔNG TÌM THẤY BUG.
     Cả 2 hàm bootstrap trong repo (`block_bootstrap_returns` cho CI DSR,
     `bootstrap_price_paths` cho Monte Carlo 1 mã) đều thao tác trên MỘT
     chuỗi return duy nhất — không có chiều cross-sectional (nhiều mã) nào
     để "bỏ qua". Hàm DUY NHẤT có cấu trúc cross-sectional thật
     (`generate_random_portfolios`, notebook 14) dùng đúng ma trận hiệp
     phương sai thật, không giả định độc lập. (Giới hạn time-series
     autocorrelation của `bootstrap_price_paths` đã ghi nhận riêng từ
     `MARKET_REGIME_AUDIT.md` — khác vấn đề, không phải phát hiện mới.)
   - **Disclosure calendar-join lag**: KIỂM TRA, KHÔNG TÌM THẤY BUG.
     `next_trading_day` (`src/data/disclosure_parser.py`) dùng đúng lịch
     giao dịch thật (bỏ qua cuối tuần + `config/vn_market_holidays.csv`),
     không phải cộng ngày lịch ngây thơ. Join `available_at` dùng
     `np.searchsorted(..., side="left")` — căn đúng ngày giao dịch đầu tiên
     từ lúc thông tin công khai. Placeholder "+1 ngày giao dịch" cho dữ liệu
     backfill đã tự nhận là ước lượng — và độ nhạy của nó với chính giả
     định lag đã được kiểm định trực tiếp trong `DISCLOSURE_PREREG_2_REPORT.md`
     mục 4 (lag +1/+3/+5, verdict KHÔNG đổi ở cả 3 mức) — nên bất kỳ sai số
     hiệu chỉnh còn lại trong placeholder này cũng không đe dọa kết luận âm
     tính đã công bố.

**Nghiệm thu**: full suite 326 passed (không đụng `src/`/`tests/` ở bất kỳ
NV nào trừ đọc-only trong NV5). Toàn bộ 5 commit trên `main`, **CHƯA push**
theo đúng yêu cầu — chờ review trước vì đây là sửa lại chính các con số đã
công bố.
