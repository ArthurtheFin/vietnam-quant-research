# Portfolio Math Validation — Phase D

Read-only independent recomputation. All work done in `/tmp/audit_phase_d/`
(three scripts: `independent_check.py`, `independent_check2.py`,
`independent_check3.py`); no repository file was modified. Sample portfolio:
the 10-symbol risk-parity portfolio committed at
`data/output/portfolio_weights.parquet` / `data/output/portfolio_risk_report.json`
(symbols: BMP, CTS, MSB, POW, SSB, VAB, VHM, VIC, VND, VPI; `generated_at`
2026-07-09T06:44:53Z).

## 1. Weights and constraint checks

| Check | Result |
|---|---|
| `sum(weights)` | 0.9999999999999999 ≈ 1.0 — **PASS** |
| All weights ≥ 0 (long-only) | **PASS** (min weight 0.0624, SSB) |
| `max_weight` (independent `concentration_metrics()` recompute) | 0.14060758 vs reported 0.14060758 — **EXACT MATCH** |
| `effective_n` (independent recompute) | 9.42003042 vs reported 9.42003042 — **EXACT MATCH** |
| `herfindahl_index` (independent recompute) | 0.10615677 vs reported 0.10615677 — **EXACT MATCH** |

All weight-derived statistics reproduce exactly. `src/risk/management.py::concentration_metrics`
is confirmed correct and its output in `portfolio_risk_report.json` is
genuinely produced by that function on the stored weights, not fabricated
or stale.

## 2. Portfolio variance / volatility formula check

Using `src/portfolio/risk.py::calculate_portfolio_variance` /
`calculate_portfolio_volatility` against an independently-built covariance
matrix (`return_matrix.cov()` on `data/full_history_v2` daily returns for
the 10 symbols):

```
sigma_p^2 (w^T Sigma w) = 0.0001456910
```

**Symbol-order robustness test** (the highest-priority check per the audit
brief): recomputed the same variance after **reversing** the row/column
order of the covariance matrix passed in.

```
variance, normal order:    0.0001456910
variance, reversed order:  0.0001456910   <- identical
```

**PASS — CONFIRMED.** `calculate_portfolio_variance` aligns `weights` and
`covariance` via `weights.index.intersection(covariance.index)` then
`.loc[common_idx]` / `.loc[common_idx, common_idx]` before converting to
numpy — label-based alignment, not positional. A caller can hand it a
covariance matrix in any symbol order and get an identical, correct
answer. This defends specifically against the "mismatched symbol order"
bug class the audit brief flags as a common, severe error. (Independently
corroborates the covariance/risk audit agent's identical finding, arrived
at by static code reading rather than execution — both methods agree.)

## 3. Risk contribution reconciliation

```
sum(total_contribution)     = 0.0120702538
daily portfolio volatility  = 0.0120702538   <- exact match
sum(risk_contribution_pct)  = 100.000000%    <- exact match
```

**PASS — CONFIRMED.** `calculate_risk_contribution`'s marginal/component/
percentage contributions (`MCR_i = (Sigma w)_i / sigma_p`,
`CR_i = w_i * MCR_i`, `%CR_i = CR_i / sigma_p`) sum back to the total
portfolio volatility to 1e-9 precision. The formula is internally
consistent and matches the audit brief's required equations exactly, not
just approximately.

## 4. Realized-return-based metrics — independent recompute does NOT reproduce the committed report

`annual_return`, `annual_volatility`, `sharpe_ratio`, and `max_drawdown` in
`portfolio_risk_report.json` are computed from a **realized historical
portfolio-return series** (`src/risk/management.py::portfolio_return_series`
— fixed weights applied to a real daily-return history, not the
`w^T Sigma w` formula), so they were checked separately from the formula
checks above.

Three independent attempts to reproduce these four numbers, in increasing
fidelity to the documented method:

| Attempt | Source | Rows used | annual_return | annual_volatility | sharpe_ratio | max_drawdown |
|---|---|---|---|---|---|---|
| Reported (`portfolio_risk_report.json`) | — | **1317** | 0.18738 | 0.12681 | 1.41842 | -0.16284 |
| #1: `data/full_history_v2`, tail(1317 rows) | full_history_v2 | 1317 | 0.24229 | 0.20083 | 1.18143 | -0.39149 |
| #2: `data/processed/stock_features.parquet`, exact `_build_return_matrix` replication, no date cutoff | stock_features.parquet | 1621 | 0.22286 | 0.19226 | 1.14345 | -0.39149 |
| #3: same as #2, cutoff at reported `features_latest_date=2026-07-06` | stock_features.parquet | 1621 | 0.23483 | 0.19460 | 1.18200 | -0.39149 |

**None of the three reproduce the committed report**, including attempt
#3, which uses the exact same source file, the exact same
`_build_return_matrix` pivot logic from `scripts/build_portfolio_stack.py`,
the exact same weights, and the report's own stated `features_latest_date`
cutoff.

**Root cause, as far as this read-only audit could establish**: the row
count itself doesn't match (1621 now vs. 1317 reported) even though the
**maximum date is identical** in both cases (2026-07-06). Per-symbol
date ranges in the current `data/processed/stock_features.parquet` show
VAB starting 2021-07-20 (1229 rows) and SSB starting 2021-03-24 (1318
rows) — i.e., some of these 10 symbols have measurably *more* historical
rows now than a 1317-row matrix would imply. Since the maximum date is
unchanged but the total count grew, the most likely explanation is that
`data/processed/stock_features.parquet` — which several other reports in
this repo (`PUSH_REVIEW.md`, `DATA_BASELINE.md`) already describe as
being refreshed by a **separate, ongoing background process not
associated with any commit in this session** — has had *more historical*
data backfilled into it for at least one of these symbols between the
report's `generated_at` (2026-07-09) and now (2026-07-12), extending
some symbols' start dates backward. This is a plausible, benign
explanation for *why* the numbers differ, but it does not change the
finding below.

**The finding, stated plainly**: `data/output/portfolio_risk_report.json`
cannot currently be reproduced from the data available in the repository
today, using the documented calculation method, even down to the input
row count. No hash, snapshot ID, or frozen copy of the exact
`data/processed/stock_features.parquet` state used to generate the
committed report exists anywhere (`portfolio_stack_metadata.json` records
`return_matrix_rows: 1317` as a fact but not a means of reconstructing
which 1317 rows). This directly connects to, and adds concrete empirical
evidence for, the data-lineage gap already identified in Section 2 (no
git-commit-hash or config-version field recorded with pipeline outputs) —
that gap is not merely a completeness nicety; it measurably prevents
reproducing this specific committed output today. **This is CONFIRMED
evidence for critical failure gate #12 ("Results cannot be reproduced"),**
scoped specifically to realized-history-dependent metrics (the
weights/formula-based metrics in Sections 1-3 above reproduce exactly,
since they don't depend on the mutable historical window).

## 5. A related, separately-confirmed methodological gap found during this check

While building the independent return matrix, `portfolio_return_series`
(`src/risk/management.py`) was observed to `fillna(0.0)` the aligned
return matrix before summing:

```python
aligned = return_matrix.reindex(columns=w.index).fillna(0.0)
portfolio_returns = aligned.mul(w, axis=1).sum(axis=1)
```

For any date before a symbol's listing/history start (e.g. VAB before
2021-07-20), this treats "the symbol did not exist yet" as "the symbol
returned exactly 0% that day" — the symbol's assigned static weight is
applied to a return of 0 rather than the day being excluded or the
remaining symbols' weights being rescaled to sum to 1 for that
sub-period. This silently blends artificial zero-return days into the
realized return series for any portfolio containing symbols with
unequal history lengths (true of the sample portfolio here: history
lengths range from 1229 to 1622 days across the 10 symbols). **[NEW]**
finding, not previously documented in any existing report. Severity:
MEDIUM — it does not affect the weights (already-computed, static) but
does distort realized-return-based risk statistics for any period where
the portfolio's constituent symbols have unequal listing history, which
is the common case for a real Vietnam-equities universe with staggered
IPO dates. This compounds (via a different mechanism) the already-known,
larger survivorship-bias/point-in-time-universe gap — this is about
*within-portfolio* partial-history handling, not the *whole-universe*
listing question.

## Summary

| Check | Verdict |
|---|---|
| Weights sum to 1, non-negative | PASS |
| Concentration metrics (max weight, effective N, HHI) | PASS — exact match |
| Portfolio variance formula (`w^T Sigma w`) | PASS — correct quadratic form |
| Symbol-order alignment (weights vs. covariance) | PASS — CONFIRMED robust via reversed-order test |
| Risk contribution formulas (MCR/CR/%CR) | PASS — reconciles exactly |
| Realized annual_return/volatility/Sharpe/max_drawdown reproducibility | **FAIL** — not reproducible from currently-available data; root cause is a data-lineage/versioning gap, not a formula error |
| Partial-history (`fillna(0)`) handling in realized-return series | **NEW finding** — MEDIUM severity, distorts realized-return metrics for portfolios with staggered listing dates |
