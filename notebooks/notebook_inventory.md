# Notebook Inventory

## Main Notebooks

| Old Notebook | New Folder | Classification | Reason | Notes |
|---|---|---|---|---|
| `00_project_overview.ipynb` | `notebooks/00_archive/` | `ARCHIVE` | High-level overview is now better handled by `notebooks/README.md` and the client report notebook. | Kept for historical context. |
| `01_validate_environment.ipynb` | `notebooks/01_data_pipeline/` | `KEEP` | Still useful as a lightweight environment / connection sanity check before running research notebooks. | Remains the first notebook to open manually. |
| `02_fetch_daily_ohlcv.ipynb` | `notebooks/00_archive/` | `CONVERTED_TO_SCRIPT` | Daily fetch flow is now handled by `scripts/update_daily_data.py` and `scripts/run_daily_pipeline.py`. | Archived instead of deleted. |
| `03_clean_validate_data.ipynb` | `notebooks/00_archive/` | `CONVERTED_TO_SCRIPT` | Data cleaning / validation is now part of the production pipeline. | Use pipeline outputs instead of running manually. |
| `04_market_distribution.ipynb` | `notebooks/02_market_research/` | `KEEP` | Still useful for explaining return distribution and market structure. | Research notebook. |
| `05_volatility_regime.ipynb` | `notebooks/02_market_research/` | `KEEP` | Useful for volatility context and regime interpretation. | Research notebook. |
| `06_market_regime.ipynb` | `notebooks/02_market_research/` | `KEEP` | Still valuable for entropy, breadth, and regime interpretation. | Research notebook. |
| `07_breakout_research.ipynb` | `notebooks/03_alpha_signals/` | `KEEP` | Keeps the breakout research and validation narrative visible even though pipeline artifacts already exist. | Alpha research notebook. |
| `08_monte_carlo_simulation.ipynb` | `notebooks/02_market_research/` | `KEEP` | Simulation visuals are still useful for research and client explanation. | Research notebook. |
| `09_stealth_accumulation_screen.ipynb` | `notebooks/03_alpha_signals/` | `KEEP` | Core alpha-screen research notebook with useful visuals and explanation. | Production screen exists, but notebook still useful for review. |
| `10_benchmark_diagnostics.ipynb` | `notebooks/02_market_research/` | `KEEP` | Benchmark health / spread diagnostics remain useful for research QA. | Research notebook. |
| `11_trade_card_generation.ipynb` | `notebooks/00_archive/` | `CONVERTED_TO_SCRIPT` | Trade-card generation now runs through `scripts/generate_trade_cards.py`. | Archived instead of deleted. |
| `12_meta_ranking_optimization.ipynb` | `notebooks/03_alpha_signals/` | `KEEP` | Useful for understanding score construction and alpha ranking diagnostics. | Alpha research notebook. |
| `13_advanced_quant_analysis.ipynb` | `notebooks/02_market_research/` | `KEEP` | Contains correlation, beta, divergence, and advanced market analytics worth preserving. | Research notebook. |
| `14_portfolio_construction.ipynb` | `notebooks/04_watchlist_portfolio/` | `KEEP` | Still useful for reviewing allocation frameworks and portfolio diagnostics. | Portfolio research notebook. |
| `15_risk_management.ipynb` | `notebooks/04_watchlist_portfolio/` | `KEEP` | Still useful for understanding drawdown / risk controls around the portfolio stack. | Portfolio research notebook. |
| `16_capital_allocation.ipynb` | `notebooks/04_watchlist_portfolio/` | `KEEP` | Still useful for explaining sizing and capital allocation logic. | Portfolio research notebook. |
| `17_live_watchlist_dashboard.ipynb` | `notebooks/00_archive/` | `ARCHIVE` | Older dashboard-style output overlaps with current metadata outputs and the new client report notebook. | Preserved for reference only. |
| `18_client_watchlist_report.ipynb` | `notebooks/00_archive/` | `ARCHIVE` | Superseded by `notebooks/05_client_report/01_client_market_report.ipynb`. | Kept as historical version. |
| `19_validation_and_stress_test.ipynb` | `notebooks/04_watchlist_portfolio/` | `KEEP` | Still useful for research validation and stress-checking. | Validation notebook. |
| `20_portfolio_backtester.ipynb` | `notebooks/04_watchlist_portfolio/` | `KEEP` | Backtesting notebook still has standalone research value. | Portfolio research notebook. |

## Delete Candidates

**Update (audit A2, 2026-07-08): verified none of these files exist on disk anymore.**
`find notebooks -iname "*checkpoint*"` returns nothing. The table below is kept
as historical record of what was previously flagged; no cleanup action remains.

| Old Notebook | New Folder | Classification | Reason | Notes |
|---|---|---|---|---|
| `notebooks/.ipynb_checkpoints/*.ipynb` | `not changed` | `DELETE_CANDIDATE` (resolved) | Auto-generated checkpoint files duplicate working notebooks and include many obsolete variants. | No longer present on disk. |
| `00_project_overview-checkpoint.ipynb` and other `*-checkpoint.ipynb` files | `not changed` | `DELETE_CANDIDATE` (resolved) | Redundant autosaves with no production value once the main notebook file exists. | No longer present on disk. |
| Legacy checkpoint variants such as `07b_breakout_stoploss_regime-checkpoint.ipynb`, `12b_alpha_research_scoring-checkpoint.ipynb`, `14_stealth_accumulation_lab-checkpoint.ipynb`, `16_meta_ranking_lab-checkpoint.ipynb` | `not changed` | `DELETE_CANDIDATE` (resolved) | Heavily duplicated notebook drafts that no longer match the current production flow. | No longer present on disk. |

## Summary

- `KEEP`: retained as active research / review notebooks
- `CONVERTED_TO_SCRIPT`: logic is now run through `scripts/` and the notebook was archived
- `ARCHIVE`: older but still reference-worthy notebooks moved into `00_archive`
- `DELETE_CANDIDATE`: intentionally not deleted in this phase; listed only for future approval
