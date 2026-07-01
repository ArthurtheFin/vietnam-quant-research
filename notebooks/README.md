# Notebooks Guide

## Folder Purpose

- `notebooks/00_archive/`
  Legacy notebooks, script-converted flows, and older report/dashboard variants kept only for reference.

- `notebooks/01_data_pipeline/`
  Environment and data pipeline support notebooks that help explain how raw data enters the research stack.

- `notebooks/02_market_research/`
  Market regime, volatility, distribution, benchmark, correlation, entropy, and simulation notebooks for research review.

- `notebooks/03_alpha_signals/`
  Signal research notebooks for breakout, stealth accumulation, trade-card logic, and meta ranking / alpha diagnostics.

- `notebooks/04_watchlist_portfolio/`
  Portfolio construction, risk management, capital allocation, validation, and backtesting notebooks.

- `notebooks/05_client_report/`
  Client-facing notebook outputs that read already-generated pipeline artifacts and summarize the current market / watchlist state.

## Recommended Reading Order

1. `notebooks/01_data_pipeline/01_validate_environment.ipynb`
2. `notebooks/02_market_research/04_market_distribution.ipynb`
3. `notebooks/02_market_research/05_volatility_regime.ipynb`
4. `notebooks/02_market_research/06_market_regime.ipynb`
5. `notebooks/03_alpha_signals/07_breakout_research.ipynb`
6. `notebooks/03_alpha_signals/09_stealth_accumulation_screen.ipynb`
7. `notebooks/03_alpha_signals/12_meta_ranking_optimization.ipynb`
8. `notebooks/04_watchlist_portfolio/14_portfolio_construction.ipynb`
9. `notebooks/04_watchlist_portfolio/15_risk_management.ipynb`
10. `notebooks/04_watchlist_portfolio/16_capital_allocation.ipynb`
11. `notebooks/05_client_report/01_client_market_report.ipynb`

## Which Notebooks Are Research?

- Market research:
  `04_market_distribution.ipynb`, `05_volatility_regime.ipynb`, `06_market_regime.ipynb`, `08_monte_carlo_simulation.ipynb`, `10_benchmark_diagnostics.ipynb`, `13_advanced_quant_analysis.ipynb`

- Alpha / screening research:
  `07_breakout_research.ipynb`, `09_stealth_accumulation_screen.ipynb`, `12_meta_ranking_optimization.ipynb`

- Portfolio / risk research:
  `14_portfolio_construction.ipynb`, `15_risk_management.ipynb`, `16_capital_allocation.ipynb`, `19_validation_and_stress_test.ipynb`, `20_portfolio_backtester.ipynb`

## Which Notebook Is The Main Client Report?

- `notebooks/05_client_report/01_client_market_report.ipynb`

This notebook does not rebuild the pipeline. It reads the latest parquet / json outputs that already exist under `data/`.

## Run Before Opening The Client Report

Primary live workflow:

```bash
python scripts/run_daily_pipeline.py --online --update-index --build-portfolio
```

Fallback if SSI is rate-limited or you only want to reuse existing fresh data:

```bash
python scripts/run_daily_pipeline.py --offline --build-portfolio
```

Then open:

```text
notebooks/05_client_report/01_client_market_report.ipynb
```

## Operating Notes

- Open Jupyter from the project root `vietnam-quant-research` so relative imports and `data/...` paths remain consistent.
- Archived notebooks in `00_archive` are intentionally preserved for reference; they are not part of the preferred daily workflow.
