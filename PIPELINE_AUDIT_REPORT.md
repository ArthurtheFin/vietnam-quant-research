# PIPELINE_AUDIT_REPORT — full offline re-run + critical data-staleness finding

You asked me to re-run the whole project and report whether outputs and the
workflow are healthy. The mechanical pipeline runs cleanly (table below) —
but re-running it **regenerated `data/processed/stock_features.parquet` from
raw data using the current code**, and that single act overturned the basis
for every "validated" formula shipped so far in this session. That is the
headline finding; the routine pipeline health table is secondary.

## Headline finding: the entire validated strategy was calibrated on stale, pre-fix feature data

The `stock_features.parquet` this whole session's research was built on
(`STRATEGY_RESEARCH_REPORT.md`, `DEPLOY_REPORT.md`, `META_RANKING_VALIDATION_REPORT.md`,
and the two production changes already pushed to PR #1) had file mtime
**2026-07-07 08:35** — **it predates commit `4b42df4` (2026-07-08 09:29,
"fix(G4): flag out-of-band returns as corporate actions instead of clipping")**
by about a day. That audit fix was already merged into this branch's history
before any of this session's research began, but the cached parquet was
never regenerated to reflect it — every subsequent script simply reused the
stale file.

**What G4 actually does**: a daily return whose magnitude exceeds the
exchange price band (a strong sign of an unadjusted stock split/dividend,
common for VN equities) used to be *clipped* to a bounded value; G4 changed
this to *NaN it out* instead, correctly refusing to treat an unadjusted
corporate action as a real trading return. That's the right fix on its own
terms. But because `return_20d`/`forward_return_20d` are 20-day rolling
products of `return_1d`, **a single NaN'd day poisons the entire 20-day
window around it** — one flagged day silently turns off up to 20 rows on
either side.

Measured impact of regenerating with this fix now properly applied:

| | Old (stale, pre-G4-effective) file | New (regenerated, current code) |
|---|---|---|
| `suspect_corporate_action` days flagged | (didn't exist as a column) | 1,545 / 179,803 (0.86%) |
| `return_20d` rows that are NaN | 10,002 | 38,645 (**+286%**) |
| `forward_return_20d` rows that are NaN | 19,468 | 47,079 (**+142%**) |
| Flagged events by year | — | 2020-2022: 0 &nbsp; 2023: 566 &nbsp; 2024: 487 &nbsp; 2025: 391 &nbsp; 2026: 101 |

The flagged events concentrate entirely in 2023-2026 (real, actively-traded
names: HPG, PNJ, VJC, HSG, DXG, VTP among the most-flagged — plausibly real
VN stock-dividend/bonus-share events, not a data bug), which is exactly the
period the "validated" formula's rolling-fold years 2023-2026 were tested
on.

### Re-running the exact same validation scripts, unchanged, on the regenerated data

| Fold | Reported (stale data, `STRATEGY_RESEARCH_REPORT.md` §6) | **Re-run just now (fresh data)** |
|---|---|---|
| 2022 | -27.6% | -27.6% (unaffected — no flags before 2023) |
| 2023 | +13.1% | +11.2% |
| 2024 | +2.0% | +0.2% |
| **2025** | **+11.6%** | **-32.3%** |
| 2026 | +5.3% | +14.5% |
| **Avg** | **+0.9%** | **-6.8%** |
| **Median** | +5.3% | +0.2% |
| **Win rate** | 80% | 60% |

2025 alone flips from the strategy's second-best year to worse than its
known worst year. And the single-split walk-forward check (`scratch/walk_forward_validation.py`,
train 2020-2023 / test 2024-2026) is worse than the fold table alone
suggests:

- **TRAIN-period IC on fresh data**: `distance_ma20` -0.135 (t=-1.34, not
  significant), `return_20d` **+0.015** (t=+0.11 — sign flipped from the
  original -0.282, and indistinguishable from zero), `realized_vol_20d`
  **+0.096** (t=+0.92 — sign flipped from -0.253, also indistinguishable
  from zero). Only `distance_ma20` keeps its original sign, and even that
  is no longer statistically significant.
- **Backtest on TEST period (2024-2026)**: the TRAIN-derived formula gets
  CAGR +3.20% — but a **shuffled version of the same formula averages
  +5.03%** (5 seeds: -8.58% to +19.18%), i.e. the real formula does **not
  beat random** on fresh data. This is the identical shuffle-test signature
  used throughout this whole session to discredit the old momentum fallback
  and `score_meta_ranking()`.

**This means the 3-factor formula deployed to production this session
(replacing the backtest fallback, and then replacing `score_meta_ranking()`
outright) shows no evidence of alpha once tested on properly regenerated,
current-code feature data — by the exact same test that was used to certify
it as validated in the first place.**

One test in the suite is already flagging this correctly and should **not**
be "fixed" by loosening its tolerance:
`tests/test_reversal_quality_score.py::test_full_history_calibration_matches_strategy_research_report`
now fails because the real-data calibration (0.408/0.287/0.305) has drifted
outside the ±0.01 band around the hardcoded `DEFAULT_WEIGHTS` (0.39/0.32/0.29)
— that drift is the same phenomenon, caught automatically.

**I have not reverted or changed any production code in response to this.**
This needs your decision, not a unilateral fix — see "Recommended next
steps" at the end.

## Routine pipeline health (the part you asked for directly)

Ran `python scripts/run_daily_pipeline.py --offline --build-sector --build-portfolio --build-research-notes`,
then separately confirmed `scripts/build_portfolio_stack.py` (skipped by the
pipeline's own freshness gate in this run — see below) also runs cleanly on
its own.

| Step | Status | Duration | Output |
|---|---|---|---|
| generate_features | OK | 11.6s | stock_features.parquet (179,803 rows, 501 symbols), benchmark_vnindex.parquet |
| generate_signals | OK | 2.3s | setup_signals.parquet (179,803 rows) |
| run_alpha_scoring | OK | 8.1s | alpha_scores.parquet (179,803 rows) |
| generate_trade_cards | OK | 1.4s | 501 trade cards |
| run_stealth_accumulation_screen | OK | 24.5s | 163,091 history rows, 9 latest leaders, 6 watchlist names |
| build_cashflow_board_symbols | OK | 1.9s | 501 symbols |
| run_meta_ranking | OK | 3.1s | 501 ranked, 20 trading watchlist, 10 client-ready |
| build_sector_board | OK | 1.9s | 24 sectors, 96.4% mapping coverage (18 symbols unmapped) |
| build_cashflow_board (full) | OK | 2.8s | 501 symbols, 190 data-quality warnings, 67 low-liquidity, 74 zero-volume |
| build_research_notes | OK | 0.7s | 10 notes generated |
| build_portfolio_stack (run standalone) | OK | ~2s | 10 symbols, 0 missing, weights sum to 1.0 across all 4 allocators |

**Total pipeline wall time: ~58 seconds for the core 10 steps.** No script
crashed; every step returned exit code 0 and produced its declared output
files.

### Things that fired as designed, not bugs

- **Freshness check → overall run status ERROR.** "Dataset frozen: latest
  data 2026-07-06 is 2 trading sessions behind expected 2026-07-08." This is
  correct: I ran `--offline` deliberately (no live SSI fetch), so cached
  data is 2 sessions stale relative to today. The pipeline correctly
  **skipped building the portfolio stack** rather than compute on stale
  data (`"Skipped portfolio stack because freshness check returned ERROR"`),
  which is why I ran `build_portfolio_stack.py` standalone above just to
  confirm the code path itself still works.
- **Automated bias check → `passed: false`.** By design:
  `setup_signals.parquet` intentionally retains `forward_return_Nd` research
  labels; every client-facing artifact strips them before saving (confirmed
  by the `UserWarning: ... dropping forward-looking column(s) ...` lines
  during `run_meta_ranking`). Informational only, matches the code comment.
- **`meta_score` distribution (using the now-live 3-factor formula)**: 501
  symbols, range 2.4-100, mean 51.5, bucket split 66 Prime / 130 High
  Conviction / 124 Secondary / 181 Low Priority — structurally healthy,
  independent of whether the formula itself has alpha (that's the headline
  finding above, not a pipeline-mechanics issue).
- Cashflow board sector-score warnings ("small sample size N<5") for
  Insurance/Consumer Services/Business Services/Textiles/Education/
  Agriculture — expected for thin sectors, informational.

### Side effect of running the pipeline

Regenerating outputs modified several git-tracked report files
(`data/signals/final_watchlist.csv`, `reports/daily_alpha_ranking.csv`,
`reports/final_watchlist.xlsx`, `reports/top_watchlist.csv`,
`research_notes/generated/*.md`) — these are tracked in git (unlike most of
`data/`, which is gitignored). **Left uncommitted**, since regenerating
sample report snapshots wasn't something you asked me to commit.

## Recommended next steps (your call, not mine to decide unilaterally)

1. **Do not treat the currently-deployed 3-factor formula's "validated"
   status as reliable** until it's re-validated on properly regenerated
   feature data across the board (all of `STRATEGY_RESEARCH_REPORT.md`'s
   research would need to be re-run from scratch on fresh data — this is a
   substantial redo, not a small patch).
2. Decide whether the G4 NaN-propagation behavior itself is too aggressive
   (20-day window poisoned by 1 flagged day) — a shorter-window or
   interpolation-based handling might preserve more usable signal without
   reintroducing the fake-shock problem G4 was fixing. That's a genuine
   design question, not an obvious bug either way.
3. Given production already runs the (now-uncertain) 3-factor formula for
   both the backtest fallback and `score_meta_ranking()`, decide whether to
   pause/flag that in the live pipeline pending re-validation, or leave it
   running while research catches up.
4. Not touched: the `test_full_history_calibration_matches_strategy_research_report`
   test failure should stay failing (or be updated to the new real
   calibration) — it is correctly detecting this drift, not being flaky.
