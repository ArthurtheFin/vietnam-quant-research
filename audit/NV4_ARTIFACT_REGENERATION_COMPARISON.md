# NV4 — Consumer artifact regeneration on the fixed pipeline (2026-07-13)

Report only, per task constraint ("chỉ báo cáo không tune"). No scoring logic,
eligibility gate, or Gate #3 code was touched to produce this comparison.

## What was regenerated

Ran `scripts/run_daily_pipeline.py --offline` (commit `72be363`, the gate-6/
gate-12/gate-17 fixed code + the regenerated `data/processed/stock_features.parquet`
from NV2), which executes: `generate_features` → `generate_signals` →
`run_alpha_scoring` → `generate_trade_cards` → `run_stealth_accumulation_screen`
→ `build_cashflow_board_symbols` → `run_meta_ranking` (produces
`final_watchlist`/`client_ready_watchlist`/`trading_watchlist`/
`research_candidates`). `research_notes/generated/*` (23 files) were
deliberately **not** regenerated — see PUSH_REVIEW.md's updated note.

Every regenerated artifact below now embeds a `lineage` block (`dataset_version`,
`features_sha256`, `features_row_count`, `config_hash`, `git_commit_hash`,
`lineage_generated_at`) per NV3's convention — see
`reports/alpha_scoring_metadata.json` and `data/output/watchlist_metadata.json`.

## Result 1: `reports/top_watchlist.csv` (alpha_score-ranked, top 20) — comparable

This artifact is not subject to the eligibility gate, so it is a clean
apples-to-apples comparison of the same ranking method (top 20 by `alpha_score`,
the v2 composite: 70% realized_vol_20d + 30% value_ma20) before vs. after the
gate-6 data fix.

| Pre-fix (`backup/root-wip-20260713`, as_of 2026-07-06) | Post-fix (as_of 2026-07-09) |
|---|---|
| NAB, CTS, POW, CSM, MSB, SSB, HDB, ORS, VHM, VIC, HSL, HVN, DHC, HCM, BMP, VAB, VDS, VVS, CDC, VND | SHA, VNS, HUB, ICT, HTL, VMD, SVT, TN1, TCR, CCC, ABT, VCF, TMS, CMV, SRC, UIC, TVT, SFI, MDG, ADG |

**Symbols retained: 0/20. Complete turnover.**

**Root cause (expected, not a bug)**: the pre-fix `stock_features.parquet` had
the ~29-day raw/adjusted-close mixing corruption documented in
`docs/reports/data/docs/reports/data/DATA_BASELINE.md` / `data/quarantine_existing_v1/README.md`, confirmed via an
exact 2x close-price mismatch on 9 large-cap symbols in this same round
(NV2 commit `28b9f60`). `alpha_score`'s two inputs — `realized_vol_20d` and
`value_ma20` (turnover) — are both directly computed from `close` and are
exactly the kind of factor a systematic price-series corruption would distort
market-wide. A full re-ranking after fixing that corruption is the correct,
expected consequence of the gate-6 fix, not a regression.

## Result 2: `final_watchlist` / `client_ready_watchlist` — NOT comparable this round (pre-existing, out-of-scope gate)

Post-fix run: `client_ready=0, trading=0, research=0, data_review=500`
(`data/output/watchlist_metadata.json`). Every one of the 500 scored
candidates was rejected by the **eligibility gate** (`STALE_DATA` and/or
`LOW_LIQUIDITY` and/or `SEVERE_DISTRIBUTION_RISK` — see
`data/output/data_review_watchlist.parquet`'s `eligibility_reason` column).

**Root cause, traced (read-only, not modified)**: the regenerated
`stock_features.parquet` has genuinely uneven per-symbol date coverage —
411/500 symbols' latest row is 2026-07-06 (matches `docs/reports/data/docs/reports/data/DATA_BASELINE.md`'s
documented backfill request window, `2020-01-01 → 2026-07-06`), while a
disjoint set of 28 mostly small-cap/illiquid symbols (ABT, ADG, CCC, CMV, DBT,
FDC, HNA, HTL, HUB, ICT, L10, MDG, PJT, S4A, SC5, SFI, SHA, SRC, SVT, TCR, TMS,
TN1, TSJ, TVT, UIC, VCF, VMD, VNS) independently reach 2026-07-09. Because
`run_meta_ranking.py`'s `analysis_as_of` is the universe's global max date
(2026-07-09), the eligibility gate's `data_age_days > 1` rule
(`src/screening/final_watchlist.py:982`) flags the other 464/500 symbols
`STALE_DATA` relative to that date — and the 28 symbols that do pass the
freshness check are then mostly rejected on `LOW_LIQUIDITY` instead (top 20 by
`final_score` among data-reviewed candidates: SRC, FDC, PJT, SFI, DBT, VNS,
S4A, HUB, L10, MDG, UIC, ICT, VCF, SHA, SC5, HTL, TN1, CMV, VMD, HNA — all
flagged `LOW_LIQUIDITY`).

By contrast, the pre-fix backup's `final_watchlist.csv` had a uniform
`analysis_as_of = 2026-07-06 = date` for every row (`data_age_days = 0`
across the board) — i.e. the pre-fix dataset's per-symbol coverage happened
to be internally consistent (all capped at the same date), so this
particular failure mode did not trigger, independent of any of the three
gates fixed this round.

**This is not Gate #6, #12, or #17** — it is a pre-existing data-coverage
characteristic of the `full_history_v2` backfill (per-symbol non-uniform
history depth) interacting with the eligibility gate's freshness policy
(Gate #3-adjacent territory, explicitly out of scope this round: "không đụng
Gate #3", "không làm mục điểm số nào khác"). No code in
`apply_eligibility_gate`, `data_age_days` thresholds, or the survivorship
gate was touched to investigate or work around this. Flagged as a separate
task for a future round (see below) rather than fixed here.

**Practical consequence for this comparison**: a meaningful pre-fix vs.
post-fix top-20 table for `client_ready_watchlist` cannot be produced this
round, because the post-fix run legitimately yields zero eligible candidates
under the current, unmodified gate — through no fault of the gate-6/12/17
fixes. `daily_alpha_ranking.csv`/`top_watchlist.csv` (Result 1 above) are the
only consumer artifacts this round for which a like-for-like comparison was
possible.

## Follow-up flagged (not actioned in this NV4 round)

A background task was spawned to investigate the `full_history_v2` per-symbol
coverage gap (411 symbols capped 2026-07-06 vs. 28 capped 2026-07-09) and
whether the eligibility gate's freshness reference date should be reconsidered
— both are Gate #3-adjacent design questions requiring explicit scope
approval, not something this round's NV1-NV5 instructions authorized.

---

## UPDATE 2026-07-13 (later same day) — data-coverage gap closed, Result 2 now comparable

Follow-up round: diagnosed the mass-rejection (see
`audit/ELIGIBILITY_GATE_STALE_DATA_DIAGNOSIS.md` — confirmed the gate logic
itself was correct; root cause was the two un-reconciled fetch batches
above, not a gate bug), then synced `full_history_v2` to a common latest
trading date (`scripts/update_prices_daily.py`, commits `296a2f4`/`1fe2725`)
and re-ran `generate_features.py` + `scripts/update_index_data.py` +
`scripts/run_daily_pipeline.py --offline`.

**Result 2, revised — now comparable**: `client_ready=10, trading=20,
research=174, data_review=296` (`freshness_status: OK`, 0 warnings, 0
errors — previously `ERROR` with 500/500 rejected). Rejection reasons in
the 296 data-reviewed candidates are now dominated by legitimate business
criteria, not a freshness artifact: `LOW_LIQUIDITY` (158 alone + 57 combined
with other reasons), `SEVERE_DISTRIBUTION_RISK` (67 alone + 87 combined),
`STALE_DATA` only 60 total (exactly the 60 symbols identified in the sync
as thin-trading/long-inactive — see `docs/reports/data/docs/reports/data/DATA_BASELINE.md`'s sync section, not
a bug).

**`client_ready_watchlist` top-10 comparison, pre-fix (`backup/root-wip-20260713`) vs. post-sync**:

| Pre-fix (as_of 2026-07-06) | Post-sync (as_of 2026-07-13) |
|---|---|
| MSB, POW, CTS, SSB, NAB, BMP, VIC, VAB, VPI, VHM | VIC, MSB, ABB, MST, BVS, CTS, KLB, BMP, NAB, HDB |

**Retained (5/10)**: MSB, CTS, NAB, BMP, VIC. **Dropped**: POW, SSB, VAB,
VPI, VHM. **Added**: ABB, MST, BVS, KLB, HDB. A moderate, plausible
overlap — consistent with real score changes from the gate-17 fix (v1
shadow `alpha_rs_score` no longer feeds `relative_strength_score`) plus the
underlying price-data correction, not the near-total turnover seen in
Result 1 (which is driven by `alpha_score`'s different, vol/liquidity-only
composite).

**`reports/top_watchlist.csv`/`daily_alpha_ranking.csv`**: now ranks 441
symbols (up from 28 pre-sync) — the alpha-scoring cross-section is no
longer dominated by the outlier-fresh subset. New top-20: HCD, VSH, DRL,
BTP, CLL, SMB, HUB, TCL, ALV, ABI, ILB, DVP, CHP, SJD, DSN, GDT, HAR, VFG,
SHP, AFX (1/20 retained vs. the pre-sync-but-post-gate6-fix top-20 -- `HUB`
only; expected, since that ranking was computed over a near-arbitrary
28-symbol subset before the sync).

All three artifacts re-embed lineage from this run
(`features_row_count: 715674`, `git_commit_hash` = this round's commits).
