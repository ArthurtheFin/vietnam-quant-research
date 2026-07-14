# Sector mapping coverage — report only, no decision made (2026-07-14)

audit/PATH_TO_100.md Universe/Eligibility item: "Quyết định rõ: sector
mapping có bắt buộc để đủ điều kiện hay chỉ để báo cáo — và làm theo quyết
định đó." Per this round's explicit instruction, this document reports the
current state and two options with their consequences; **no code was
changed and no decision was made** — that is for the user to pick in a
future round.

## Current coverage

From `scripts/audit_sector_map.py` (`data/output/sector_map_coverage.json`,
sourced from `config/sector_map.csv`):

| | |
|---|---|
| Total symbols | 500 |
| Mapped | 482 (96.4%) |
| Missing (`sector=UNKNOWN`) | 18 (3.6%) |
| Distinct sectors | 24 |

**The 18 missing symbols**: AAH, AG1, AMD, AMP, AMV, APL, APT, ART, ASA,
ATB, BIG, FDC, FOC, KPF, MZG, PSH, VNZ, VVS. Two provenance patterns, per
`data/output/sector_map_missing_symbols.csv`'s `reason` column:
- 11 symbols exist in the HF Vietnam metadata source but with no sector
  label there either (`UNKNOWN_IN_SECTOR_MAP`, source = "HF Vietnam
  metadata + rule normalization").
- 7 symbols aren't in the HF metadata source at all (source = "Project raw
  symbol only - not found in HF metadata"): AMD, ART, ASA, ATB, FDC, KPF, PSH.

**Overlap with the already-excluded INACTIVE_LONG set** (this session's
`src/validation/trading_status.py` work): 7 of the 18 (AMD, APL, ART, ASA,
ATB, KPF, PSH) are already excluded from the eligible universe for being
long-inactive, independent of sector mapping.

**Actual current impact, checked against today's real pipeline output**:
of the 18 unmapped symbols, only **4 are currently in any eligible tier**
(`research_candidates`: AAH, AMV, BIG, MZG) and **0 are in
`trading_watchlist` or `client_ready_watchlist`**. The other 14 are already
excluded by other gates (LOW_LIQUIDITY, STALE_DATA, SEVERE_DISTRIBUTION_RISK,
or INACTIVE_LONG).

## Current role: reporting-only in the actual production path

Grepped every place `sector` is referenced across `src/` and `scripts/`:

- **`src/screening/final_watchlist.py` (the eligibility gate)**: zero
  references. Sector mapping plays no role in client_ready/trading/research
  tier assignment today.
- **`scripts/build_portfolio_stack.py` / `src/portfolio/construction.py`**
  (the actual production portfolio-construction script and its allocators —
  equal-weight, inverse-vol, risk-parity, HRP): zero references. **The
  production portfolio has no sector-concentration protection at all
  today** — none of the four allocators are sector-aware.
- **`src/portfolio/constraints.py::check_sector_constraints`**
  (`max_sector_weight=0.35` default) exists and is fully implemented, but
  is only called from two places, both **not wired into the production
  path**:
  - `src/portfolio/monte_carlo.py` — an alternative, random-portfolio-search
    construction method (not what `build_portfolio_stack.py` uses), where
    it's evaluated as one of several soft constraints per candidate
    portfolio.
  - `src/portfolio/reporting.py` — a constraint-check report generator,
    presumably for describing a portfolio after the fact, not gating it.
- **`src/analytics/sector_board.py` / `scripts/audit_sector_map.py`**: build
  the sector board (leaders, cashflow-by-sector) and this coverage report —
  purely descriptive/reporting outputs, correctly labeled as such.

**Conclusion: sector mapping is 100% reporting-only in the code path that
actually runs today.** The infrastructure for a sector cap exists
(`check_sector_constraints`) but is dormant — connected only to an
unused-in-production Monte Carlo module.

## Two options, with consequences

**Option 1 — Keep reporting-only (status quo).**
- No code change needed.
- Consequence: `client_ready_watchlist`/`portfolio_weights.parquet` can
  concentrate arbitrarily in one sector with zero automatic protection —
  this is a live, unmitigated risk today (e.g. if 5+ of the current 10
  `client_ready` names happened to cluster in Banking, nothing in
  `build_portfolio_stack.py` would notice or rebalance). The sector board
  remains available for a human to review manually before allocating
  capital.
- Consequence for the 18 unmapped symbols: none beyond what other gates
  already do (as shown above, 14/18 are already excluded on other grounds;
  the remaining 4 stay in `research_candidates`, never reaching
  `client_ready`/`trading` regardless of sector mapping under the current
  rules for those tiers).

**Option 2 — Make sector mapping mandatory for eligibility.**
- Requires code changes this round did not make: add a new
  `UNKNOWN_SECTOR`-style rejection reason to
  `apply_eligibility_gate` (mirroring how `INACTIVE_LONG`/coverage-ratio
  were wired in this round), sourced from `config/sector_map.csv` the same
  way `trading_status`/`excluded_symbols_by_status` were — and separately,
  wire `check_sector_constraints` into `build_portfolio_stack.py`'s actual
  allocation step (currently only exists in the unused Monte Carlo path) if
  the goal is genuine portfolio-level sector-cap enforcement, not just
  eligibility-level exclusion of unmapped symbols.
- Consequence: as measured today, this would only additionally exclude 4
  symbols currently in `research_candidates` (AAH, AMV, BIG, MZG) — a small,
  precisely-bounded impact right now, though it would grow if
  `config/sector_map.csv` coverage degrades over time (e.g. new listings
  not yet mapped) unless the sector map is kept current.
- Enforcing the portfolio-level 35% cap (the constraints.py default)
  additionally means: whatever allocator currently runs (risk-parity by
  default) would need a rebalancing/capping step added, which does not
  exist in `build_portfolio_stack.py` today and was not scoped or built
  this round.

## Recommendation (not acted on)

Given the current 96.4% coverage and near-zero live impact (4 symbols),
the coverage gap itself is not the more urgent gap — **the absence of any
sector-concentration check in the actual production allocator is**. If a
future round picks Option 2, prioritize wiring `check_sector_constraints`
(or an equivalent cap) into `build_portfolio_stack.py`'s real allocation
path over adding a new eligibility-rejection reason for the 4 currently-affected
symbols.
