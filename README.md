# Vietnam Quant Research — FCData Screening System

Project này được thiết kế cho workflow:

```text
SSI FCData -> parquet/local cache -> feature engineering -> signals -> screening -> ranking -> daily report
```

Mục tiêu không phải xem bảng giá, mà là đo edge: xác suất thắng, expected value, tail risk, volatility regime, stealth accumulation, và cách phân bổ vốn thực chiến.

## 1. Cài đặt

```bash
cd vietnam-quant-research
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

Cài FCData package của SSI:

```bash
python scripts/install_ssi_fcdata.py /path/to/ssi_fc_data-2.2.2.tar.gz
# hoặc
python scripts/install_ssi_fcdata.py ssi-fc-data
```

## 2. Cấu hình key SSI

Tạo file `.env` từ mẫu:

```bash
cp .env.example .env
```

Điền key:

```text
SSI_CONSUMER_ID=...
SSI_CONSUMER_SECRET=...
SSI_URL=https://fc-data.ssi.com.vn/
SSI_STREAM_URL=https://fc-datahub.ssi.com.vn/
```

Không commit `.env` lên Git.

## 3. Daily Workflow

Xem hướng dẫn vận hành đầy đủ tại [docs/OPERATIONS.md](docs/OPERATIONS.md).

### One-time setup
```bash
python scripts/check_fcdata_setup.py
python scripts/install_ssi_fcdata.py /path/to/ssi_fc_data-2.2.2.tar.gz
```

### Daily pipeline (9 bước)
```bash
# Bước 1-2: Fetch data
python scripts/update_daily_data.py        # Fetch stock OHLCV
python scripts/update_index_data.py        # Fetch index + benchmark

# Bước 3: Feature engineering
python scripts/generate_features.py        # → stock_features, clean_daily_ohlcv, market_features, index_features

# Bước 4-5: Signal generation
python scripts/generate_signals.py         # → setup_signals
python scripts/generate_trade_cards.py     # → breakout_20d_trade_cards

# Bước 6: Screening
python scripts/run_stealth_accumulation_screen.py  # → stealth accumulation outputs

# Bước 7: Ranking
python scripts/run_meta_ranking.py         # → meta ranking watchlist

# Bước 8: Report
python scripts/generate_daily_report.py    # → data/reports/daily_market_note.md

# Bước 9: Risk Dashboard & Simulation
python scripts/main_visual_dashboard.py     # → Export charts to reports/figures/ and tables to reports/tables/
```

## 4. Config

Toàn bộ cấu hình nằm trong `config/strategy_config.yaml`:
- **universe**: markets, indexes, watchlist, start_date
- **returns/trend/volatility/distribution**: feature engineering params
- **signals**: signal generation thresholds
- **backtest/monte_carlo/risk**: backtest và risk params

Screen config riêng: `config/screens/stealth_accumulation.yaml`

## 5. Output chính

- `data/processed/clean_daily_ohlcv.parquet` — Clean OHLCV data
- `data/processed/stock_features.parquet` — All computed features
- `data/processed/market_features.parquet` — Market breadth + regime
- `data/processed/index_features.parquet` — Index features
- `data/processed/benchmark_vnindex.parquet` — VNINDEX benchmark
- `data/signals/setup_signals.parquet` — Breakout/pullback/volume spike signals
- `data/signals/breakout_20d_trade_cards.parquet` — Trade cards with edge scores
- `data/signals/stealth_accumulation_*.parquet` — Stealth screening outputs
- `data/signals/meta_ranking_*.parquet` — Meta ranking outputs
- `data/reports/daily_market_note.md` — Daily actionable report
- `reports/tables/decision_rules.csv` — Asset screening classification labels (Strong, Avoid, etc.)
- `reports/tables/risk_summary.csv`, `return_summary.csv`, `beta_summary.csv` — Asset risk metrics tables
- `reports/tables/portfolio_metrics.csv`, `simulation_summary.csv` — Portfolio analytics & block bootstrap outcomes
- `reports/figures/` — Dashboard visualization charts (Matplotlib/Seaborn)

## 6. Notebook map

```text
00_project_overview.ipynb       — Tổng quan project
01_validate_environment.ipynb   — Test SSI connection & environment
02_fetch_daily_ohlcv.ipynb      — Fetch daily OHLCV, phase-1 liquidity scan, auto watchlist seed
03_clean_validate_data.ipynb    — Data cleaning lab
04_market_distribution.ipynb    — Return distributions
05_volatility_regime.ipynb      — Volatility analysis & regimes
06_market_regime.ipynb          — Market regime detection
07_breakout_research.ipynb      — Backtest framework
08_monte_carlo_simulation.ipynb — Monte Carlo simulation
09_stealth_accumulation_screen.ipynb — Stealth screen development
10_benchmark_diagnostics.ipynb  — Benchmark diagnostics
11_trade_card_generation.ipynb   — Trade card builder
12_meta_ranking_optimization.ipynb — Meta ranking development
13_advanced_quant_analysis.ipynb — Advanced correlation/quant analysis
14_portfolio_construction.ipynb — Portfolio construction
15_risk_management.ipynb        — Risk management
16_capital_allocation.ipynb     — Capital allocation
17_live_watchlist_dashboard.ipynb — Watchlist dashboard
18_client_watchlist_report.ipynb — Client report
19_validation_and_stress_test.ipynb — Validation, robustness, stress testing
20_portfolio_backtester.ipynb   — Portfolio backtesting workflow
```

## 7. Lưu ý benchmark

- Nếu có `data/processed/benchmark_vnindex.parquet`, backtest screener sẽ ưu tiên dùng `VNINDEX` thật.
- Nếu chưa có dữ liệu index raw, hệ thống sẽ fallback sang `market_proxy` và ghi rõ `benchmark_source` trong output.

## 8. Không có FCTrading

Project này chỉ dùng FCData. Execution / đặt lệnh thực hiện thủ công trên brokerage.
