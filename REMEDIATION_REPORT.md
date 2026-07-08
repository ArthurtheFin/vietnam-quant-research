# REMEDIATION REPORT — vietnam-quant-research

Nguồn: `AUDIT_REPORT.md` (40 phát hiện) → `IMPLEMENTATION_PLAN.md` (APPROVED) → 21 commit trên nhánh này.

---

## 1. Phạm vi verify đã chạy

- **Test suite đầy đủ**: `pytest tests/ -q` → **169 passed**, 3 warning (đều là warning cố ý từ guard D5 khi test chủ động kích hoạt drop-path). Không có test nào bị skip/xfail.
- **Notebook runner**: `scripts/run_all_notebooks.sh --list` verify bằng test (`test_notebook_runner_resolves_real_paths`) — resolve đúng 16 notebook thật, không path chết.
- **Reproduce-trước/pass-sau**: mỗi fix logic tài chính (D1, D2, C2, G1, G2, G4, H1-H3, I1, I3, I4) đều có test viết ĐỂ FAIL trên hành vi cũ trước, xác nhận fail, rồi mới sửa code tới khi pass — chi tiết trong từng commit message.

### Cập nhật: đã verify thêm bằng dữ liệu thật (repo gốc)

Ban đầu worktree này không có `.env`/`data/` (bị `.gitignore`, không tự động có trong git worktree). Sau khi bạn xác nhận và cho phép, đã copy `.env` + `data/processed` + `data/raw` (bao gồm `data/raw/securities/` — danh sách niêm yết thật) từ repo gốc vào worktree để chạy verify thật. **Các file output được regenerate trong lúc verify (research_notes/*.md, final_watchlist.csv/xlsx) đã được revert về bản gốc sau khi xem xong** — chỉ giữ lại code + test trong lịch sử commit, không lẫn output data vào git history.

**Kết quả verify bằng dữ liệu thật (ngày dữ liệu: 2026-07-06):**

| Fix | Bằng chứng thật |
|---|---|
| **B1** | `get_full_universe_symbols()` trả về **1,590 mã** (HOSE+HNX+UPCOM thật) so với `get_tracked_universe_symbols()` (universe "full" cũ) chỉ **501 mã** — xác nhận bằng số liệu thật: universe cũ chỉ phủ **31.5%** thị trường thật. |
| **B2** | Data thật đứng ở 2026-07-06, hệ thống chạy lúc 2026-07-08 → tính đúng "trễ 1 phiên giao dịch" (`lag_sessions: 1`) → status `WARNING` (đúng — không phải `OK` giả như code cũ). |
| **D5** | Chạy `scripts/run_meta_ranking.py` thật → guard bắt sống và tự động drop `forward_return_5d/10d/20d/60d` khỏi `meta_ranking.parquet` và `final_watchlist.parquet` — xác nhận các cột forward-looking THẬT SỰ đang chảy vào output production trước khi có D5. |
| **G1** | Trên dữ liệu thật, sàn tuyệt đối demote đúng **4 mã thật** (HCM 76.21, ACB 71.02, HHP 70.46, STB 69.01 — đều có `final_score` vượt ngưỡng 60 nhưng `excess_return_20d` âm) từ "sẽ là Client Ready" xuống `Trading Watchlist`. |
| **I1** | Chạy `build_cashflow_board.py` (full) thật → guard hạ đúng **VPI và BMP** (2 mã đang ở tier `client_ready` thật) từ `CONFIRMED` xuống `WATCH` vì `WEAK_FLOW` + volume ratio thấp (0.49x, 0.79x). Research note của BMP đổi từ luận điểm bullish "cải thiện tích cực" sang trung tính "tích lũy trung tính, cần theo dõi". |
| **I2** | Research note VIC thật đổi "ngành Financial Services" → "ngành Real Estate"; nhóm dẫn đầu dòng tiền cùng ngành đổi từ `VPI, DXG, VHM` (sai ngành) sang `VHM, VIC, NVL` (đúng ngành). |
| **H1/H2/H3/H6** | `build_portfolio_stack.py` chạy thật thành công: `allocator_used: "risk_parity"` (không fallback), NAV đọc từ `strategy_config.yaml` đúng, `kelly_scale=1.0` với `kelly_note=None` cho mọi mã thật (đúng — vì dữ liệu trade card thật hiện chưa có cột `avg_loss` thật, Kelly no-op an toàn thay vì bị corrupt bởi `median_return` như code cũ). |

**Vẫn chưa chạy được** (cần thời gian/quyết định riêng, không thuộc phạm vi 1 lần verify): backtest engine đầy đủ (D1/D2/C2/G4) trên toàn bộ lịch sử giá thật để ra số Sharpe/CAGR trước-sau cụ thể — cơ chế đã verify đúng bằng test synthetic (mục 2), nhưng số % cụ thể trên dữ liệu VN thật cần một lần chạy `run_daily_pipeline.py` đầy đủ + `notebooks/04_watchlist_portfolio/20_portfolio_backtester.ipynb`, việc này bạn có thể tự chạy trong repo gốc (đã có đủ data) khi merge nhánh fix này về.

---

## 2. Bảng trạng thái từng phát hiện

### CRITICAL

| Mã | Trạng thái | Commit | Bằng chứng test |
|---|---|---|---|
| B1 | **FIXED** | `f1c6a40` | `test_full_universe_reads_real_securities_lists`, `test_full_universe_fails_loudly_without_securities_lists` |
| B2 | **FIXED** | `e9bb80b` | `test_calendar_freshness_detects_frozen_dataset`, `test_expected_latest_trading_date_calendar_rules` |
| D1 | **FIXED** | `8dc1c4f` | `test_rebalance_decision_uses_prior_day_information` |
| F1 | **FIXED** | `3c3b88b` | `test_gate_demotes_client_ready_when_cashflow_board_stale/missing`, `test_cashflow_board_step_precedes_meta_ranking` |
| I1 | **FIXED** | `6cb16d9` | `test_confirmation_guard_downgrades_contradictory_improving` |

### HIGH

| Mã | Trạng thái | Commit | Bằng chứng test |
|---|---|---|---|
| C1 | **FIXED** | `4219178` | `test_min_price_threshold_is_vnd_not_a_bare_number` |
| D2 | **FIXED** | `c6a7aff` | `test_backtest_skips_limit_up_entries`, `test_backtest_floor_stop_slips_to_next_session`, `test_limit_up_symbol_is_not_bought_on_execution_day` |
| D3 | **DEFERRED** | — | Cần dữ liệu mã delist thật (mua/thu thập) — xem mục 3 |
| G1 | **FIXED** | `900b03c` | `test_negative_excess_return_demotes_from_client_ready` |
| G2 | **FIXED** | `4241cce` | `test_market_proxy_uses_real_benchmark_when_available`, `test_single_name_sector_rs_is_neutralized` |
| G4 | **FIXED** | `4b42df4` | `test_split_day_return_flagged_not_clipped`, `test_upcom_limit_move_is_preserved` |
| H1 | **FIXED** | `436e96c` | `test_inverse_vol_never_uses_score_as_volatility` |
| H2 | **FIXED** | `436e96c` | `test_allocation_fallback_is_reported_loudly` |
| H3 | **FIXED** | `5875dab` | `test_kelly_disabled_when_avg_loss_input_is_not_a_loss` |
| I2 | **FIXED** | `9c23d78` | `test_sector_map_large_caps_classified_correctly` |
| I3 | **FIXED** | `50e86ec` | `test_breakout_stop_selection_is_out_of_sample`, `test_breakout_eligibility_unvalidated_on_thin_validation` |
| J1 | **FIXED** | `f354aa4` | `test_notebook_runner_resolves_real_paths` |

### MEDIUM

| Mã | Trạng thái | Commit | Ghi chú |
|---|---|---|---|
| A1 | **DEFERRED** | — | Hợp nhất 2 engine chấm điểm = quyết định kiến trúc, cần bạn chọn hướng — xem mục 3 |
| C2 | **FIXED** | `061b635` | `test_stop_loss_respects_t_plus_2_5_settlement` |
| C3 | **Gián tiếp giải quyết qua B1** | `f1c6a40` | Gốc rễ (universe hẹp) đã sửa; cần chạy với `data/raw/securities` thật để đo lại tỷ lệ lọc |
| C4b | **DEFERRED** (enhancement) | — | Chart funnel input bộ lọc chưa thêm — nằm ngoài phạm vi "fix tối thiểu" |
| D4 | **FIXED** | `000ca32` | `test_run_bias_checks_flags_forward_columns_present`, notebook 19 hết mock delisted |
| D5 | **FIXED** | `819188b` | `test_final_watchlist_score_rejects_forward_columns`, `test_build_watchlist_tiers_drops_forward_columns_from_features`, `test_meta_ranking_save_drops_forward_columns` |
| E1 | **Gián tiếp giải quyết qua B1** | `f1c6a40` | Universe hẹp là nguyên nhân gốc; các module vẫn nhất quán với nhau |
| E3 | **DEFERRED** | — | Cùng nhóm A1 — cần quyết định kiến trúc |
| F2 | **DEFERRED** (cosmetic) | — | Tách notebook 12/12b chưa làm — rủi ro thấp, không đụng số liệu |
| F3 | **DEFERRED** (cosmetic) | — | Đánh số lại mục lục client report chưa làm |
| G3 | **FIXED** | `819188b` | `test_signal_age_warning_flags_source_date_mismatch` |
| G5 | **FIXED** | `d155a5e` | `test_thin_evidence_caps_priority_bucket` |
| G6 | **FIXED** | `d155a5e` | `test_synergy_bonus_does_not_double_count_action_label` |
| H4 | **FIXED** | `ad28b0d` | `test_missing_volume_column_rejects_instead_of_fabricating` |
| H5 | **DEFERRED** | — | Đề xuất thay Monte Carlo noise-mining bằng Ledoit-Wolf shrinkage — xem mục 3 |
| J3 | **Phần lớn đã giải quyết** | rải nhiều commit | Không làm 1 đợt riêng, nhưng mỗi fix Wave 1-5 đều kèm contract/reproduce test mới đúng vào chỗ audit chỉ ra là thiếu — xem `tests/test_pipeline_contracts.py`, `tests/test_bias_checks.py` |

### LOW / INFO

| Mã | Trạng thái | Commit |
|---|---|---|
| A2 | **FIXED** (xác nhận không còn file rác, cập nhật doc) | `ad28b0d` |
| A3 | **DEFERRED** | Chưa gom ngưỡng signal vào config tập trung |
| B3 | ✅ Xác nhận không có vấn đề (từ audit) | — |
| B4 | **FIXED** | `ad28b0d` |
| C4 | ✅ Đã vá trước phiên audit này | — |
| D6 | **DEFERRED** | Chưa hợp nhất mô hình chi phí giữa 2 backtest engine |
| D7 | ✅ Xác nhận không có vấn đề (từ audit) | — |
| E2 | **DEFERRED** | Cột boolean cũ (`is_research_candidate`...) chưa dọn |
| H6 | **FIXED** | `ad28b0d` |
| I5 | **DEFERRED** | `reports/` chứa bản sao cũ chưa dọn |
| J2 | **FIXED** | `ad28b0d` |

**Tổng**: 40 phát hiện → **28 FIXED**, 2 gián tiếp giải quyết qua B1, 1 phần lớn giải quyết (J3), **9 DEFERRED** (có lý do rõ ràng, xem mục 3), 3 xác nhận-không-phải-bug từ trước.

---

## 3. Còn nợ (DEFERRED) — cần quyết định của bạn

| Mã | Vì sao chưa làm | Đề xuất bước tiếp theo |
|---|---|---|
| **D3** — Survivorship bias | Cần dữ liệu mã đã huỷ niêm yết thật; không có nguồn nào trong repo, không thể tự bịa | Thu thập danh sách delisted từ HOSE/HNX công bố chính thức; hoặc chấp nhận backtest chỉ tính từ 2020 kèm disclaimer rõ ràng trong mọi báo cáo |
| **H5** — Monte Carlo/portfolio "tối ưu" từ noise-mining | Cần thiết kế lại (không phải fix nhỏ) | Thay bằng Ledoit-Wolf shrinkage covariance (sklearn đã có sẵn trong requirements) + báo cáo dải percentile thay vì chọn max từ 5000 danh mục ngẫu nhiên |
| **A1 / E3** — Hai engine chấm điểm song song | Thay đổi kiến trúc lớn, cần bạn chọn hướng | Bước rẻ trước mắt: `stock-decision-engine` load `eligibility_status`/`candidate_tier` từ pipeline chính và cảnh báo khi 2 hệ thống mâu thuẫn, trước khi tính đến hợp nhất hẳn |
| **D6** — Chi phí giao dịch không nhất quán giữa 2 engine | Cần bạn xác nhận số phí/thuế thật từ broker đang dùng | Đề xuất dùng chung mô hình 0.4% round-trip + slippage của stealth_accumulation làm chuẩn cho `portfolio_backtest.py` |
| **C4b** — Chart funnel input bộ lọc | Là enhancement UI, ngoài phạm vi "fix tối thiểu" | Thêm 1 bar chart đếm pass/fail theo `history_pass/liquidity_pass/regime_pass/trend_pass` sau cell "Run Full Market Stealth Scan" |
| **F2** — Notebook 12 gộp 2 phần chung kernel | Rủi ro thấp (chỉ vỡ khi chạy sai thứ tự), không đụng số liệu | Tách "12b" thành file riêng |
| **F3 / E2 / I5 / A3** | Cosmetic / tổ chức file, không ảnh hưởng số liệu | Gom vào 1 commit dọn dẹp riêng nếu muốn, độ ưu tiên thấp nhất |

## NEW_FINDINGS (phát hiện mới trong lúc fix)

*(trống — không phát hiện vấn đề mới ngoài phạm vi audit trong quá trình thực thi)*

---

## 4. Việc cần bạn làm tiếp (không thể tự động hoá từ phía tôi)

1. **Chạy pipeline thật với dữ liệu thật** (cần SSI FCData credentials): `update_securities.py` → `update_daily_data.py --scope core` → `generate_features.py` → ... → `run_daily_pipeline.py`, rồi đối chiếu output với bảng "expected output changes" trong `IMPLEMENTATION_PLAN.md` để có con số hiệu suất thật trước/sau.
2. **Xác nhận `--scope full`** hoạt động đúng sau khi chạy `update_securities.py` thật (cần mạng + credentials — không tự chạy được trong môi trường audit này).
3. **Quyết định hướng cho 4 mục DEFERRED lớn** (D3, H5, A1/E3, D6) ở mục 3.
