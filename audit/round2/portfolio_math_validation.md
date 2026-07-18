# Portfolio Math Validation — Round 2 (Phase D, independent recompute)

All checks below were run fresh this round, in-process (no writes outside
`/tmp` and this `audit/round2/` directory — the committed
`data/output/portfolio_risk_report.json`/`portfolio_weights.parquet` were
only READ, never regenerated or overwritten, per this round's
inventory-only constraint). Full session transcript of the commands is in
`test_execution_log.md`.

Sample portfolio: the currently-committed 10-symbol `risk_parity`
allocation in `data/output/portfolio_weights.parquet` / risk report in
`data/output/portfolio_risk_report.json` (generated 2026-07-14, source
`client_ready_watchlist`, cutoff `features_latest_date=2026-07-13`).
Symbols: ABB, BMP, BVS, CTS, HDB, KLB, MSB, MST, NAB, VIC.

---

## 1. Reproducibility (Gate #12)

**Method**: read the current `data/processed/stock_features.parquet` via
`OFFICIAL_FEATURES_PATH`, truncate to the committed report's own stated
cutoff (`2026-07-13`), rebuild the return matrix with the exact documented
function (`scripts/build_portfolio_stack.py::_build_return_matrix`), and
call `src/risk/management.py::build_portfolio_risk_report` with the
committed `risk_parity` weights — the same method, same symbols, same
weights, same cutoff the original report used.

| Metric | Committed report | Independent recompute | Match (1e-6) |
|---|---:|---:|---|
| `track_record_days` / return-matrix rows | 1626 | 1626 | **exact** |
| `annual_return` | 0.2897334856979199 | 0.2897334856979199 | **True** |
| `annual_volatility` | 0.2314774214620675 | 0.2314774214620675 | **True** |
| `sharpe_ratio` | 1.2162436451526828 | 1.2162436451526828 | **True** |
| `max_drawdown` | -0.5066971570117109 | -0.5066971570117109 | **True** |

**Determinism check**: ran the identical recompute twice in immediate
succession against the current file — bit-identical both times on all 4
metrics.

**Contrast with Round 1**: the original P0-3 finding, using the same
methodology against the pre-fix file, reproduced **1621 rows vs. 1317
reported** and none of the 4 headline metrics matched. This round's
result — exact match on row count and all 4 metrics — is the direct
consequence of Gate #6's fix (production now reads the regenerated,
hash-pinned file) plus Gate #12's lineage-embedding fix (the report now
records the exact cutoff/hash needed to reproduce it).

**Verdict**: Gate #12 **RESOLVED, CONFIRMED** (not theoretical — empirically reproduced).

## 2. Portfolio variance formula (`w^T Σw`)

**Method**: independently computed `w^T Σw` from the same return matrix
above, using the weights `risk_parity` column.

First attempt used pandas' default pairwise-deletion `.cov()` (ddof=1, no
NaN handling) — **did not match** (`0.24041` recomputed via the official
method vs. `0.23148` via this naive approach), a ~4% gap. Root-caused by
reading `src/risk/management.py::portfolio_return_series` directly: it
calls `return_matrix.reindex(...).fillna(0.0)` before summing — i.e. it
treats a symbol's no-trade day as a 0% return rather than excluding it
(see NEW finding in `delta_scorecard.md`). Re-ran using the exact same
convention (`fillna(0.0)`, `ddof=0`):

```
sum(weights)            = 1.0
max(weight)              = 0.138499524290148   (committed max_weight: 0.138499524290148, exact match)
w^T Σw  (fillna(0.0), ddof=0, Σ annualized ×252):
  portfolio_volatility   = 0.23147742146206754
  committed annual_volatility = 0.2314774214620675
  match (1e-6): True
```

**Verdict**: formula confirmed correct once the production code's own
NaN-handling convention is matched exactly. Gate #4 **not triggered,
re-verified**.

## 3. Symbol-order alignment (weights vs. covariance matrix)

**Method**: reversed the column order of the return matrix (and
correspondingly the weight vector, aligned by symbol name, not position)
and recomputed portfolio variance.

```
Forward order  portfolio_variance = 0.05779911412538831
Reversed order portfolio_variance = 0.057799114125388316
Match (1e-12): True
```

**Verdict**: Gate #5 **not triggered, re-verified**. No positional
(as opposed to label-based) alignment bug found.

## 4. Risk contribution reconciliation (MCR / CR / %CR)

**Method**: `MCR_i = (Σw)_i / σp`, `CR_i = w_i × MCR_i`, `%CR_i = CR_i / σp`,
computed independently on the same sample.

```
sum(CR_i)   = 0.24041446322005738
σp          = 0.24041446322005736
match (1e-9): True

sum(%CR_i)  = 1.0000000000000002   (floating-point-exact 100%)
```

**Verdict**: risk-contribution math confirmed correct and internally
consistent.

## 5. Constraint compliance

| Constraint | Result |
|---|---|
| sum(weights) = 1 | **1.0** exactly |
| weights >= 0 (long-only) | Confirmed (risk_parity allocator, no negative weights observed) |
| max_weight matches committed report | **Exact match** (0.138499524290148) |

## 6. Annualization

`annualized_volatility` uses `r.std(ddof=0) * sqrt(252)`; `annualized_return`
uses `(1+r).prod() ** (252/len(r)) - 1`. Both confirmed by direct source
read (`src/risk/management.py:52-70`) and by the exact reproduction in
section 1 above — no daily/annual or ddof-convention mixing bug found once
the NaN convention (section 2) is accounted for.

## 7. NEW data-quality observation surfaced by this validation

3 of the 10 sample-portfolio symbols have a non-trivial NaN-day fraction
in the return matrix (ABB 249/1626 = 15.3%, MSB 245/1626 = 15.1%,
NAB 198/1626 = 12.2%), all silently zero-filled by
`portfolio_return_series` rather than excluded. This does not indicate a
formula bug (section 2 confirms the formula is internally consistent) but
is an undocumented convention that could understate realized volatility
for thinly-traded names — see `delta_scorecard.md` NEW findings and
`quantitative_finance_gap_matrix.csv`'s corresponding row for the full
writeup and recommended action.

---

**Scope note**: per this round's inventory-only constraint, no new
portfolio was constructed and no output file was regenerated or
overwritten — every check above reads existing committed artifacts and
performs the recompute in-memory/`/tmp` only.
