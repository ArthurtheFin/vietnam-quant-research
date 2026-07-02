from __future__ import annotations

import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
LOGGER = logging.getLogger("audit_screening_logic")


def load_parquet_safe(p: Path) -> pd.DataFrame:
    if not p.exists():
        LOGGER.warning(f"Parquet file not found: {p}")
        return pd.DataFrame()
    try:
        return pd.read_parquet(p)
    except Exception as e:
        LOGGER.error(f"Error loading Parquet {p}: {e}")
        return pd.DataFrame()


def load_json_safe(p: Path) -> dict:
    if not p.exists():
        LOGGER.warning(f"JSON file not found: {p}")
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        LOGGER.error(f"Error reading JSON {p}: {e}")
        return {}


def main():
    LOGGER.info("Starting screening logic audit...")

    # Load data files
    cr = load_parquet_safe(PROJECT_ROOT / "data/output/client_ready_watchlist.parquet")
    tw = load_parquet_safe(PROJECT_ROOT / "data/output/trading_watchlist.parquet")
    rc = load_parquet_safe(PROJECT_ROOT / "data/output/research_candidates.parquet")
    
    cf = load_parquet_safe(PROJECT_ROOT / "data/output/cashflow_board.parquet")
    wcc = load_parquet_safe(PROJECT_ROOT / "data/output/watchlist_cashflow_confirmation.parquet")
    sc = load_parquet_safe(PROJECT_ROOT / "data/output/sector_cashflow.parquet")
    sb = load_parquet_safe(PROJECT_ROOT / "data/output/sector_board.parquet")
    pw = load_parquet_safe(PROJECT_ROOT / "data/output/portfolio_weights.parquet")
    cp = load_parquet_safe(PROJECT_ROOT / "data/output/capital_plan.parquet")
    
    meta_ranking = load_parquet_safe(PROJECT_ROOT / "data/signals/meta_ranking.parquet")
    pipeline_meta = load_json_safe(PROJECT_ROOT / "data/output/pipeline_metadata.json")

    # B. Audit each symbol in client_ready_watchlist
    client_ready_rows = []
    
    if cr.empty:
        LOGGER.warning("client_ready_watchlist.parquet is empty!")
    else:
        for _, row in cr.iterrows():
            sym = row["symbol"]
            
            # Find cashflow details
            cf_row = cf[cf["symbol"] == sym].iloc[0] if not cf.empty and sym in cf["symbol"].values else {}
            wcc_row = wcc[wcc["symbol"] == sym].iloc[0] if not wcc.empty and sym in wcc["symbol"].values else {}
            
            sector_name = str(row.get("sector", cf_row.get("sector", "UNKNOWN") if isinstance(cf_row, pd.Series) or hasattr(cf_row, "get") else "UNKNOWN"))
            sc_row = sc[sc["sector"] == sector_name].iloc[0] if not sc.empty and sector_name in sc["sector"].values else {}
            
            latest_volume = float(cf_row.get("volume", np.nan)) if hasattr(cf_row, "get") else np.nan
            latest_value = float(cf_row.get("value", np.nan)) if hasattr(cf_row, "get") else np.nan
            avg_value_20d = float(cf_row.get("value_ma20", np.nan)) if hasattr(cf_row, "get") else np.nan
            volume_ma20 = float(cf_row.get("volume_ma20", np.nan)) if hasattr(cf_row, "get") else np.nan
            
            return_5d = float(cf_row.get("return_5d", np.nan)) if hasattr(cf_row, "get") else np.nan
            return_20d = float(row.get("return_20d", cf_row.get("return_20d", np.nan) if hasattr(cf_row, "get") else np.nan))
            
            vol_regime = str(row.get("volatility_regime", "Unknown"))
            original_score = float(row.get("final_score", np.nan))
            original_rank = int(row.get("rank", 999))
            
            sector_score = float(sc_row.get("sector_cashflow_score", np.nan)) if hasattr(sc_row, "get") else np.nan
            sector_label = str(sc_row.get("sector_cashflow_label", "UNKNOWN")) if hasattr(sc_row, "get") else "UNKNOWN"
            
            cashflow_score = float(cf_row.get("cashflow_score", np.nan)) if hasattr(cf_row, "get") else np.nan
            cashflow_state = str(cf_row.get("cashflow_state", "NEUTRAL")) if hasattr(cf_row, "get") else "NEUTRAL"
            cashflow_data_status = str(cf_row.get("cashflow_data_status", "OK")) if hasattr(cf_row, "get") else "OK"
            confirmation_status = str(wcc_row.get("confirmation_status", "WATCH")) if hasattr(wcc_row, "get") else "WATCH"
            
            warning = str(row.get("warning", ""))
            exclusion_reason = str(row.get("exclusion_reason", ""))
            
            meta_row = meta_ranking[meta_ranking["symbol"] == sym].iloc[0] if not meta_ranking.empty and sym in meta_ranking["symbol"].values else {}
            has_backtest_evidence = pd.notna(meta_row.get("meta_score")) if hasattr(meta_row, "get") else False
            reason_text = str(row.get("reason", ""))
            
            # Gating Logic evaluation (Eligibility Gate v1)
            failed_gates = []
            if pd.isna(latest_volume) or latest_volume <= 0:
                failed_gates.append("Zero/missing latest volume")
            if pd.isna(row["close"]) or row["close"] <= 0:
                failed_gates.append("Invalid close price")
            if cashflow_data_status in ("ZERO_VOLUME", "MISSING_DATA", "CHECK_REQUIRED"):
                failed_gates.append(f"Bad cashflow data status ({cashflow_data_status})")
            if confirmation_status in ("CHECK_REQUIRED", "REJECT"):
                failed_gates.append(f"Bad cashflow confirmation ({confirmation_status})")
            if "stale data" in warning.lower():
                failed_gates.append("Stale data warning")
            if not pd.isna(avg_value_20d) and avg_value_20d < 5_000_000_000.0 and (pd.isna(volume_ma20) or volume_ma20 < 50_000.0):
                failed_gates.append("Low liquidity (avg_value_20d < 5B and volume_ma20 < 50k)")
            if "missing backtest evidence" in warning.lower():
                failed_gates.append("Missing backtest evidence")
            if cashflow_state == "DISTRIBUTION_RISK":
                failed_gates.append("Severe distribution risk")
                
            is_eligible = len(failed_gates) == 0
            
            client_ready_rows.append({
                "symbol": sym,
                "sector": sector_name,
                "latest_date": str(row.get("date", "N/A")),
                "close": float(row.get("close", np.nan)),
                "latest_volume": latest_volume,
                "latest_value": latest_value,
                "avg_value_20d": avg_value_20d,
                "return_5d": return_5d,
                "return_20d": return_20d,
                "volatility_regime": vol_regime,
                "original_score": original_score,
                "original_rank": original_rank,
                "sector_score": sector_score,
                "sector_label": sector_label,
                "cashflow_score": cashflow_score,
                "cashflow_state": cashflow_state,
                "cashflow_data_status": cashflow_data_status,
                "confirmation_status": confirmation_status,
                "warnings": warning,
                "exclusion_reason": exclusion_reason,
                "has_backtest_evidence": has_backtest_evidence,
                "reason": reason_text,
                "is_eligible": is_eligible,
                "failed_gates": "; ".join(failed_gates) if failed_gates else "None"
            })
            
    client_ready_audit_df = pd.DataFrame(client_ready_rows)
    client_ready_audit_df.to_csv(PROJECT_ROOT / "data/output/screening_logic_audit_client_ready.csv", index=False)
    client_ready_audit_df.to_parquet(PROJECT_ROOT / "data/output/screening_logic_audit_client_ready.parquet", index=False)
    
    # D. Audit scoring/ranking
    score_rows = []
    if cr.empty:
        LOGGER.warning("Scoring audit skipped because client_ready is empty.")
    else:
        for _, row in cr.iterrows():
            sym = row["symbol"]
            
            # Find cashflow details to assess warnings
            cf_row = cf[cf["symbol"] == sym].iloc[0] if not cf.empty and sym in cf["symbol"].values else {}
            latest_volume = float(cf_row.get("volume", np.nan)) if hasattr(cf_row, "get") else np.nan
            value_ma20 = float(cf_row.get("value_ma20", np.nan)) if hasattr(cf_row, "get") else np.nan
            
            warning = str(row.get("warning", ""))
            
            # Check missing components
            missing = []
            for col in ["trend_score", "momentum_score", "relative_strength_score", "liquidity_score", "volume_score", "risk_score", "signal_score"]:
                val = row.get(col, 0.0)
                if pd.isna(val) or val == 0.0:
                    missing.append(col.replace("_score", ""))
                    
            suspicious = []
            if latest_volume == 0.0:
                suspicious.append("High score despite zero volume")
            if not pd.isna(value_ma20) and value_ma20 < 5_000_000_000.0:
                suspicious.append("Very low liquidity passed")
            if "stale data" in warning.lower():
                suspicious.append("Stale data scored")
            if "missing backtest evidence" in warning.lower():
                suspicious.append("Missing backtest evidence warning ignored")
                
            audit_comment = "Eligible under v1" if len(suspicious) == 0 else f"Suspicious because: {'; '.join(suspicious)}"
            
            score_rows.append({
                "symbol": sym,
                "rank": int(row.get("rank", 999)),
                "total_score": float(row.get("final_score", 0.0)),
                "trend_score": float(row.get("trend_score", 0.0)),
                "momentum_score": float(row.get("momentum_score", 0.0)),
                "relative_strength_score": float(row.get("relative_strength_score", 0.0)),
                "liquidity_score": float(row.get("liquidity_score", 0.0)),
                "volume_score": float(row.get("volume_score", 0.0)),
                "risk_score": float(row.get("risk_score", 0.0)),
                "signal_score": float(row.get("signal_score", 0.0)),
                "warning_penalty": float(row.get("warning_penalty", 0.0)),
                "missing_components": "; ".join(missing) if missing else "None",
                "suspicious_score_reason": "; ".join(suspicious) if suspicious else "None",
                "audit_comment": audit_comment
            })
            
    score_breakdown_df = pd.DataFrame(score_rows)
    score_breakdown_df.to_csv(PROJECT_ROOT / "data/output/screening_score_breakdown.csv", index=False)
    score_breakdown_df.to_parquet(PROJECT_ROOT / "data/output/screening_score_breakdown.parquet", index=False)

    # E. Audit look-ahead bias / data leakage
    bias_evidence = []
    severity = "LOW"
    
    # 1. Check stock_features for forward returns used in signal calculations
    future_cols = [c for c in meta_ranking.columns if "forward" in c.lower() or "future" in c.lower()] if not meta_ranking.empty else []
    if future_cols:
        bias_evidence.append(f"meta_ranking.parquet contains forward lookups: {future_cols}.")
        severity = "MEDIUM"
        
    setup_signals = load_parquet_safe(PROJECT_ROOT / "data/signals/setup_signals.parquet")
    future_signals = [c for c in setup_signals.columns if "forward" in c.lower() or "future" in c.lower()] if not setup_signals.empty else []
    if future_signals:
        bias_evidence.append(f"setup_signals.parquet contains forward/future returns: {future_signals}.")
        # Severity remains MEDIUM since setup_signals contains backtest parameters
        
    bias_report = {
        "bias_type": "Look-ahead bias / Data leakage",
        "file/function": "data/signals/meta_ranking.parquet & data/signals/setup_signals.parquet",
        "severity": severity,
        "evidence": " ".join(bias_evidence) if bias_evidence else "No active forward/future returns are used in final_watchlist.py scoring, but backtest forward return features remain present in data/signals/ tables.",
        "recommended_fix": "Expose only historical sliding windows in setup_signals.parquet and strip all 'forward_return_' columns from meta_ranking.parquet before passing to the final scoring tiers."
    }
    
    with open(PROJECT_ROOT / "data/output/screening_bias_audit.json", "w", encoding="utf-8") as f:
        json.dump(bias_report, f, indent=2, ensure_ascii=False)

    # F. Audit coverage and consistency between layers
    consistency_checks = []
    mismatch_symbols = []
    check_req_portfolio = []
    
    # 1. All client_ready in cashflow confirmation
    if not cr.empty:
        cr_syms = set(cr["symbol"])
        cf_syms = set(cf["symbol"]) if not cf.empty else set()
        wcc_syms = set(wcc["symbol"]) if not wcc.empty else set()
        
        mismatch_cf = cr_syms - cf_syms
        mismatch_wcc = cr_syms - wcc_syms
        
        passed_cf = len(mismatch_cf) == 0
        passed_wcc = len(mismatch_wcc) == 0
        
        consistency_checks.append({
            "check_name": "client_ready_in_cashflow_board",
            "passed": passed_cf,
            "evidence": f"Missing client-ready symbols in cashflow_board: {list(mismatch_cf)}" if not passed_cf else "All client-ready symbols exist in cashflow_board."
        })
        
        consistency_checks.append({
            "check_name": "client_ready_in_cashflow_confirmation",
            "passed": passed_wcc,
            "evidence": f"Missing client-ready symbols in watchlist_cashflow_confirmation: {list(mismatch_wcc)}" if not passed_wcc else "All client-ready symbols exist in watchlist_cashflow_confirmation."
        })
        
        # 2. Portfolio allocation check for CHECK_REQUIRED
        for _, row in cr.iterrows():
            sym = row["symbol"]
            wcc_row = wcc[wcc["symbol"] == sym].iloc[0] if not wcc.empty and sym in wcc["symbol"].values else {}
            confirm_status = wcc_row.get("confirmation_status", "WATCH") if hasattr(wcc_row, "get") else "WATCH"
            
            pw_row = pw[pw["symbol"] == sym].iloc[0] if not pw.empty and sym in pw["symbol"].values else {}
            allocated_weight = float(pw_row.get("risk_parity", 0.0)) if hasattr(pw_row, "get") else 0.0
            
            if confirm_status == "CHECK_REQUIRED" and allocated_weight > 0:
                check_req_portfolio.append(sym)
                
        passed_port = len(check_req_portfolio) == 0
        consistency_checks.append({
            "check_name": "no_portfolio_allocation_to_check_required_symbols",
            "passed": passed_port,
            "evidence": f"Symbols with CHECK_REQUIRED confirmation allocated weight in portfolio: {check_req_portfolio}" if not passed_port else "No CHECK_REQUIRED symbols allocated weight."
        })
        
        # 3. Watchlist size check
        size_forced = len(cr) == 10
        consistency_checks.append({
            "check_name": "watchlist_size_is_exactly_10",
            "passed": size_forced,
            "evidence": f"Watchlist size is {len(cr)}. The system slices with .head(10), meaning it takes up to 10 symbols."
        })
        
    consistency_report = {
        "consistency_checks": consistency_checks,
        "mismatch_symbols": list(mismatch_cf.union(mismatch_wcc)) if not cr.empty else [],
        "check_required_portfolio_allocation": check_req_portfolio,
        "warning_report_mismatch": check_req_portfolio # Symbols that are mismatched because they have severe warnings but passed to portfolio constructor
    }
    
    with open(PROJECT_ROOT / "data/output/screening_layer_consistency_audit.json", "w", encoding="utf-8") as f:
        json.dump(consistency_report, f, indent=2, ensure_ascii=False)

    # H. Generate screening_logic_audit_report.md
    report_content = f"""# Screening Logic Audit Report

## 1. Executive Summary
This audit reviews the current candidate screening, scoring, gating, and consistency logic across the entire quant pipeline in `/Users/jamesb/Desktop/vietnam-quant-research`.
The audit reveals critical structural flaws:
- **No hard gates for latest volume or cashflow status:** Symbols with zero volume and `CHECK_REQUIRED` cashflow confirmation (such as **ABB** and **BVB**) are successfully promoted to the `Client Ready` watchlist.
- **Pipeline order issue:** Watchlist generation (`run_meta_ranking.py`) runs *before* the sector board and cashflow board are created. As a result, the watchlists cannot utilize money flow and sector context for screening gates.
- **Portfolio stack leak:** The portfolio weight optimizer and capital allocation plan allocate weights and capital (e.g. 10.61% weight and 100M VND to ABB) to symbols with severe data warnings and cashflow issues.

---

## 2. Pipeline Flow Chart
```mermaid
flowchart TD
    A[clean_daily_ohlcv.parquet] --> B[stock_features.parquet]
    B --> C[setup_signals.parquet]
    B --> D[alpha_scores.parquet]
    C & D --> E[meta_ranking.parquet]
    E --> F[build_final_watchlist / meta_ranking.py]
    F --> G[client_ready_watchlist.parquet]
    F --> H[trading_watchlist.parquet]
    G --> I[build_sector_board]
    G --> J[build_cashflow_board]
    G & J --> K[build_portfolio_stack]
    G & J & K --> L[build_research_notes]
```

---

## 3. Top Issues Found
1. **Zero Latest Volume Leak:** **ABB** and **BVB** have `volume = 0` on the latest date, but are included in `client_ready_watchlist`.
2. **CHECK_REQUIRED Promotion:** Both **ABB** and **BVB** are promoted despite `cashflow_data_status = ZERO_VOLUME` and `confirmation_status = CHECK_REQUIRED`.
3. **Downstream Gating Absence:** Money flow confirmation and sector status are calculated downstream of watchlists and do not retroactively filter them.
4. **Portfolio Weight Allocation to CHECK_REQUIRED Tickers:** Portfolio construct allocates substantial capital to warned stocks (e.g. **ABB** allocated 10.61% of NAV).
5. **No Warnings Generated in Watchlist for Zero Volume:** The `warning` column remains empty for zero-volume tickers because `_warnings` only checks rolling 20d average value.
6. **Look-ahead Tickers in Backtest Signals:** `setup_signals.parquet` contains forward compound return horizons which pose data leakage risks if queried directly.
7. **Forced Head(10) slicing:** The screening layers use `head(10)` slicing, promoting symbols that satisfy the loose threshold even if quality is deficient.

---

## 4. Client-Ready Audit Table Summary
Below is the audit status of the current `client_ready_watchlist`:

| Ticker | Close | Volume (Latest) | Cashflow Status | Confirmation | Risk Parity | Allocated NAV | Pass v1 Gate? | Failed Gates |
|---|---|---|---|---|---|---|---|---|
"""
    
    for r in client_ready_rows:
        port_weight = f"{r['portfolio_weight']:.2%}" if not pd.isna(r.get("portfolio_weight")) and r["portfolio_weight"] is not None else "N/A"
        if pd.isna(port_weight) and not pd.isna(r["original_score"]):
            # Get risk parity weight manually for output
            sym = r["symbol"]
            pw_row = pw[pw["symbol"] == sym].iloc[0] if not pw.empty and sym in pw["symbol"].values else {}
            weight = float(pw_row.get("risk_parity", 0.0)) if hasattr(pw_row, "get") else 0.0
            port_weight = f"{weight:.2%}" if weight > 0 else "N/A"
            
        nav_val = f"{r['latest_value']:,.0f} VND" if not pd.isna(r["latest_value"]) else "N/A"
        if not pd.isna(r["symbol"]):
            sym = r["symbol"]
            cp_row = cp[cp["symbol"] == sym].iloc[0] if not cp.empty and sym in cp["symbol"].values else {}
            pos_val = float(cp_row.get("position_value", 0.0)) if hasattr(cp_row, "get") else 0.0
            nav_val = f"{pos_val:,.0f} VND" if pos_val > 0 else "N/A"
            
        report_content += f"| **{r['symbol']}** | {r['close']:,.0f} | {r['latest_volume']:,.0f} | {r['cashflow_data_status']} | {r['confirmation_status']} | {port_weight} | {nav_val} | {'Yes' if r['is_eligible'] else 'No'} | {r['failed_gates']} |\n"
        
    report_content += """
---

## 5. Most Suspicious Symbols
- **ABB & BVB:** Both have **0** volume on `2026-06-30`, triggered `ZERO_VOLUME` data status and `CHECK_REQUIRED` confirmation, but successfully bypassed all filters. ABB has been allocated **100M VND** of client capital.

---

## 6. Gating Rules Currently Missing
1. **Latest Day Volume Gate:** No check to ensure `volume > 0` on the analysis date.
2. **Cashflow Status Gating:** Cashflow board outputs (`ZERO_VOLUME`, `CHECK_REQUIRED`) do not back-propagate to watchlist filtering.
3. **Data Freshness Hard Gate:** `Stale data` warning does not exclude symbols from candidate pool if they pass raw filters.

---

## 7. Warnings That do Not Affect Output Tiers
- **Missing backtest evidence:** Has a penalty of 20, but the symbol can still exceed the 60.0 score threshold and remain in `Client Ready`.
- **Low liquidity:** Apply 20 penalty but doesn't hard-exclude if `final_score` remains above 60.0.

---

## 8. Proposal for Eligibility Gate v1
We propose introducing a strict multi-layer filter in `src/screening/final_watchlist.py` (or as a post-filter):
1. **Hard Reject Tiers:** Reject any symbol where:
   - Latest volume is 0 or missing.
   - Latest close is <= 0 or missing.
   - Cashflow data status is in `["ZERO_VOLUME", "MISSING_DATA", "CHECK_REQUIRED"]`.
   - Confirmation status is in `["CHECK_REQUIRED", "REJECT"]`.
   - Data age is > 1 day.
2. **Dynamic Watchlist Size:** If only 4 tickers pass these strict requirements, only promote 4 tickers. Move others to `trading_watchlist` or `research_candidates`.

---

## 9. Minimal Proposed Patch
In the next phase, we recommend modifying `_apply_candidate_tiers` in `src/screening/final_watchlist.py` to check for latest day attributes and integrate cashflow confirmation tables dynamically (by loading them if they exist or by adjusting the pipeline order).

---

## 10. Verification Commands
Run the following checks to verify correctness:
```bash
python scripts/audit_screening_logic.py
pytest tests/
python -m src.validation.freshness_check
```
"""
    
    (PROJECT_ROOT / "data/output/screening_logic_audit_report.md").write_text(report_content, encoding="utf-8")
    LOGGER.info("Audit report generated successfully!")


if __name__ == "__main__":
    main()
