# Operations Guide

Tai lieu nay dung de van hanh nhanh he thong quant: cap nhat du lieu, tao feature, chay signal / screener / ranking, va xuat report.

## 1. Quy trinh hang ngay

Neu moi truong da co `ssi_fc_data` va `.env` hop le, day la flow day du:

```bash
# Buoc 1-2: Fetch data
python scripts/update_daily_data.py        # Fetch stock OHLCV cho watchlist
python scripts/update_index_data.py        # Fetch index data + rebuild benchmark

# Buoc 3: Feature engineering
python scripts/generate_features.py        # Sinh clean_daily_ohlcv, stock_features, market_features, index_features, benchmark

# Buoc 4-5: Signal generation
python scripts/generate_signals.py         # Sinh setup_signals (breakout, pullback, volume spike)
python scripts/generate_trade_cards.py     # Sinh breakout_20d_trade_cards (edge scores)

# Buoc 6: Screening
python scripts/run_stealth_accumulation_screen.py  # Chay stealth screen + sector-aware + backtest

# Buoc 7: Cashflow board (symbol-level) — PHAI chay TRUOC ranking (audit F1)
python scripts/build_cashflow_board.py --symbol-only

# Buoc 8: Ranking (eligibility gate doc cashflow_board cung ngay)
python scripts/run_meta_ranking.py         # Tong hop ranking tu signals + stealth + trade cards

# Buoc 9: Cashflow confirmation theo tier + overlay
python scripts/build_cashflow_board.py

# Buoc 10: Report
python scripts/generate_daily_report.py    # Xuat daily_market_note.md
```

Luu y: neu cashflow board thieu hoac cu hon ngay phan tich, gate se tu dong ha cac ma
Client Ready xuong Trading Watchlist (khong con mac dinh "OK" am tham).

Y nghia tung buoc:

- `update_daily_data.py`: cap nhat du lieu gia cho `watchlist` trong `config/strategy_config.yaml`
- `update_index_data.py`: cap nhat du lieu index, rebuild `index_features` va `benchmark_vnindex`
- `generate_features.py`: sinh `clean_daily_ohlcv`, `stock_features`, `market_features`, va `index_features` + `benchmark`
- `generate_signals.py`: sinh `setup_signals.parquet` (breakout, pullback, volume spike)
- `generate_trade_cards.py`: sinh `breakout_20d_trade_cards.parquet` (edge tier, action, quality score)
- `run_stealth_accumulation_screen.py`: chay bo loc stealth accumulation, sector-aware selection, va backtest
- `run_meta_ranking.py`: tong hop signals, stealth, trade cards thanh meta ranking
- `generate_daily_report.py`: xuat bao cao markdown hang ngay

## 1a. Cai SSI FCData dung environment

```bash
python scripts/install_ssi_fcdata.py /path/to/ssi_fc_data-2.2.2.tar.gz
# hoac neu co goi tren index:
python scripts/install_ssi_fcdata.py ssi-fc-data
```

Sau khi cai, check nhanh:

```bash
python scripts/check_fcdata_setup.py
```

## 2. Khi nao dung notebook

Notebook dung cho phan nghien cuu, review, va visual diagnostics.

- `00_project_overview` & `01_validate_environment` & `02_fetch_daily_ohlcv` & `03_clean_validate_data`: Cài đặt môi trường, tải dữ liệu OHLCV, và làm sạch dữ liệu.
- `04_market_distribution` & `05_volatility_regime` & `06_market_regime`: Đánh giá phân phối thị trường, hệ số biến động và trạng thái thị trường (market regime).
- `07_breakout_research` & `07b_breakout_stoploss_regime`: Nghiên cứu hệ thống breakout, tối ưu hóa chặn lỗ theo regime.
- `08_monte_carlo_simulation`: Mô phỏng Monte Carlo dự báo quỹ đạo giá, tỷ lệ chạm mục tiêu/chặn lỗ và phân phối xác suất.
- `09_stealth_accumulation_screen`: Bộ lọc tích lũy gom hàng stealth accumulation và kiểm soát tỷ trọng ngành.
- `10_benchmark_diagnostics`: Cân chỉnh chỉ số và chuẩn hóa với VNINDEX benchmark.
- `11_trade_card_generation`: Tạo thẻ giao dịch (trade cards) và tính điểm chất lượng setup giao dịch.
- `12_meta_ranking_optimization`: Tối ưu hóa tổng hợp thứ hạng đa yếu tố (meta ranking).
- `12b_alpha_research_scoring`: Chấm điểm Alpha đa nhân tố (momentum, relative strength, trend, volume, volatility contraction, liquidity) và xuất báo cáo xếp hạng.
- `13_advanced_quant_analysis`: Phân tích định lượng nâng cao (entropy, động lượng chéo, cặp giao dịch phân kỳ).
- `14_portfolio_construction`: Xây dựng danh mục tối ưu (Equal Weight, Inverse Vol, Risk Parity, HRP, Max Sharpe) và vẽ đường biên hiệu quả (Efficient Frontier).
- `15_risk_management`: Quản lý rủi ro danh mục (capping tỷ trọng, mục tiêu biến động, dừng lỗ sụt giảm tài sản drawdown).
- `16_capital_allocation`: Phân bổ vốn chi tiết (ATR/Kelly sizing) đồng bộ với tỷ trọng của quản lý rủi ro.
- `17_live_watchlist_dashboard`: Dashboard watchlist theo thời gian thực và kế hoạch phân bổ vốn.
- `18_client_watchlist_report`: Báo cáo tổng hợp gửi khách hàng.

Neu ban chi muon cap nhat output de dung hang ngay, uu tien script. Neu muon soi logic, review score, doi tham so, dung notebook.

## 3. Doi universe, watchlist, index

Sua o `config/strategy_config.yaml` phan `universe`:

```yaml
universe:
  markets: [HOSE, HNX, UPCOM]
  indexes: [VNINDEX, VN30, HNXIndex, HNXUpcomIndex]
  watchlist:
    - ACB
    - FPT
    ...
  start_date: '2020-01-01'
```

Neu them ma moi:

1. them vao `watchlist`
2. chay lai `python scripts/update_daily_data.py`
3. chay lai `python scripts/generate_features.py`

## 4. Doi screener va sector map

Sua o `config/screens/stealth_accumulation.yaml`.

Nhung phan quan trong:

- `filters`: min price, min liquidity, volatility / market regime cho phep
- `thresholds`: nguong stage A/B/C, watchlist score, fakeout risk
- `output.top_n`: so ma hien thi
- `sector.max_names_per_sector`: gioi han so ma moi nganh
- `sector.symbol_map`: map `symbol -> sector`
- `backtest`: holding periods, top_n, benchmark path

## 5. Doi benchmark

Benchmark uu tien:

1. `data/processed/benchmark_vnindex.parquet`
2. fallback `market_proxy`

Neu muon dung `VNINDEX` that:

1. dam bao co `ssi_fc_data`
2. chay `python scripts/check_fcdata_setup.py`
3. chay `python scripts/update_index_data.py`
4. chay `python scripts/generate_features.py`

## 6. Cac output chinh

Processed:

- `data/processed/clean_daily_ohlcv.parquet` — Clean standardized OHLCV
- `data/processed/stock_features.parquet` — All computed stock features
- `data/processed/market_features.parquet` — Market breadth + regime
- `data/processed/index_features.parquet` — Index features
- `data/processed/benchmark_vnindex.parquet` — VNINDEX benchmark

Signals / screening:

- `data/signals/setup_signals.parquet` — Breakout/pullback/volume signals
- `data/signals/breakout_20d_trade_cards.parquet` — Trade cards with edge
- `data/signals/stealth_accumulation_*.parquet` — Stealth screening outputs
- `data/signals/meta_ranking_*.parquet` — Meta ranking outputs

Reports:

- `data/reports/daily_market_note.md` — Daily actionable report

## 7. Troubleshooting

Neu gap van de, check theo thu tu:

1. `python scripts/check_fcdata_setup.py` — kiem tra SSI connection
2. `python scripts/check_index_status.py` — kiem tra index data
3. Mo `01_test_fcdata_connection.ipynb` — debug connection chi tiet

Neu script bao thieu data:
- Kiem tra da chay du cac buoc truoc do chua (xem Section 1)
- Kiem tra folder `data/raw/daily_ohlcv/` co file parquet khong

Neu notebook bao loi function signature cu:
1. restart kernel
2. chay lai cell import
3. chay lai notebook
