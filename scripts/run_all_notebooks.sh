#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

TIMEOUT_SECONDS="${NOTEBOOK_TIMEOUT_SECONDS:-1800}"

NOTEBOOKS=(
  "notebooks/01_validate_environment.ipynb"
  "notebooks/02_fetch_daily_ohlcv.ipynb"
  "notebooks/03_clean_validate_data.ipynb"
  "notebooks/04_market_distribution.ipynb"
  "notebooks/05_volatility_regime.ipynb"
  "notebooks/06_market_regime.ipynb"
  "notebooks/07_breakout_research.ipynb"
  "notebooks/08_monte_carlo_simulation.ipynb"
  "notebooks/09_stealth_accumulation_screen.ipynb"
  "notebooks/10_benchmark_diagnostics.ipynb"
  "notebooks/11_trade_card_generation.ipynb"
  "notebooks/12_meta_ranking_optimization.ipynb"
  "notebooks/13_advanced_quant_analysis.ipynb"
  "notebooks/14_portfolio_construction.ipynb"
  "notebooks/15_risk_management.ipynb"
  "notebooks/16_capital_allocation.ipynb"
  "notebooks/17_live_watchlist_dashboard.ipynb"
  "notebooks/18_client_watchlist_report.ipynb"
  "notebooks/19_validation_and_stress_test.ipynb"
  "notebooks/20_portfolio_backtester.ipynb"
)

run_notebook() {
  local notebook="$1"
  if [[ ! -f "$notebook" ]]; then
    echo "[SKIP] Missing notebook: $notebook"
    return 0
  fi

  echo
  echo "============================================================"
  echo "[RUN] $notebook"
  echo "============================================================"

  jupyter nbconvert \
    --to notebook \
    --execute "$notebook" \
    --inplace \
    --ExecutePreprocessor.timeout="$TIMEOUT_SECONDS"

  echo "[OK] $notebook"
}

if [[ $# -gt 0 ]]; then
  for notebook in "$@"; do
    run_notebook "$notebook"
  done
else
  for notebook in "${NOTEBOOKS[@]}"; do
    run_notebook "$notebook"
  done
fi

echo
echo "All requested notebooks executed successfully."
