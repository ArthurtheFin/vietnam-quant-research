# Quarantine — notebook 14/15/16 chain artifacts (2026-07-27)

These four files were written into `data/signals/` by notebooks 14/15/16 running
by hand. `data/signals/` is pipeline-owned, so as of Đợt 3 (NV1) the whole chain
writes and reads `notebooks/outputs/` instead. The copies were moved here rather
than deleted: they are gitignored, so a delete would be unrecoverable.

| File | mtime when quarantined | Written by |
|---|---|---|
| `portfolio_construction_weights.parquet` | 2026-07-23 11:02 | nb14 |
| `selected_portfolio_weights.parquet` | 2026-07-23 11:02 | nb14 |
| `risk_overlay_weights.parquet` | 2026-07-02 12:58 | nb15 |
| `capital_allocation_plan.parquet` | 2026-07-02 12:58 | nb16 |

**Why they had to go.** None of the four has a single reader in `src/` or
`scripts/` — only the notebooks read each other's output. After the Đợt 2 write
guard stopped nb14 from refreshing `data/signals/`, nb15 kept reading the old
`selected_portfolio_weights.parquet` behind an `os.path.exists()` check and said
nothing about it. Leaving the files in place would have preserved exactly that
trap. With them gone, nb15 takes its designed HRP fallback and prints why.

**Do not read from here.** Regenerate by running, in order:
`notebooks/04_watchlist_portfolio/14_portfolio_construction.ipynb` →
`15_risk_management.ipynb` → `16_capital_allocation.ipynb`. Output lands in
`notebooks/outputs/`.

Note the numbers in these files come from the in-sample selection chain
described in `notebooks/AUDIT_NOTEBOOKS_REPORT.md` (nb14 picks the best Sharpe
among ~53,000 candidates evaluated on the same sample used to fit them). They
are kept for forensic reference only, not as a baseline to compare against.
