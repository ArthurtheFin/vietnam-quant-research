"""
Monte Carlo Pipeline.py
=======================
Project: Quant Trader Lab - Portfolio Optimization
Author: quant.traderr (Instagram)
License: MIT

Description:
    A production-ready pipeline for Monte Carlo Asset Price Simulation.
    
    It uses a Geometric Brownian Motion (GBM) model calibrated on historical 
    volatility and drift to project future price paths.

    Note: This is proprietary info.

    Pipeline Steps:
    1.  **Data Acquisition**: Loads local VN stock data from parquet or downloads.
    2.  **Simulation Engine**: Runs vectorized Monte Carlo simulations.
    3.  **Analysis**: Computes VaR, Expected Returns, and Confidence Intervals.
    4.  **Static Visualization**: Generates a high-quality snapshot of the pathways.

Dependencies:
    pip install numpy pandas yfinance matplotlib
"""

import time
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import os
from pathlib import Path

# Ignore warnings
warnings.filterwarnings("ignore")

# --- CONFIGURATION ---

CONFIG = {
    # Data
    "TICKER": "CTG",            # Default symbol - just change this to run!
    "LOOKBACK_YEARS": 1,
    "INTERVAL": "1d",
    
    # Simulation
    "SIMULATIONS": 25000,
    "DAYS_TO_PROJECT": 60,
    "START_CAPITAL": 10000,      # Automatically set to latest close price
    "RANDOM_SEED": None,         # Set integer for reproducibility
    
    # Output
    "OUTPUT_IMAGE": "monte_carlo_static.png",
    
    # Aesthetics
    "COLOR_BG": '#0e0e0e',
    "COLOR_LINE": (0.0, 1.0, 1.0, 0.005), # Cyan, very low alpha
    "COLOR_MEAN": '#00aaff',
    "COLOR_BEST": '#00ff41',
    "COLOR_WORST": '#ff0055',
    "COLOR_GRID": '#1f1f1f'
}

# --- UTILS ---

def log(msg):
    """Simple logger."""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")

# --- MODULE 1: DATA ---

def fetch_market_data():
    """
    Fetches historical market data to calibrate drift and volatility from local parquet.
    """
    symbol = CONFIG['TICKER']
    log(f"[Data] Loading data for {symbol}...")
    
    try:
        data_path = Path("data/processed/clean_daily_ohlcv.parquet")
        if not data_path.exists():
            log(f"[Warning] Local data not found at {data_path}, falling back to yfinance...")
            import yfinance as yf
            ticker_suffix = f"{symbol}.HM" if ".HM" not in symbol and ".HN" not in symbol else symbol
            data = yf.download(ticker_suffix, period=f"{CONFIG['LOOKBACK_YEARS']}y", interval=CONFIG['INTERVAL'], progress=False)
            if isinstance(data.columns, pd.MultiIndex): 
                data = data.xs(ticker_suffix, axis=1, level=1)
            prices = data['Close']
        else:
            df = pd.read_parquet(data_path)
            symbol_df = df[df["symbol"].str.upper() == symbol.upper()].sort_values("date")
            if symbol_df.empty:
                raise ValueError(f"Khong tim thay du lieu cho ma {symbol} trong data/processed/clean_daily_ohlcv.parquet")
            prices = symbol_df['close']
            
        if prices.empty:
            raise ValueError("No data returned.")
            
        returns = prices.pct_change().dropna().values
        latest_price = float(prices.iloc[-1])
        
        # Save auto-configured values to CONFIG
        CONFIG['START_CAPITAL'] = latest_price
        # Auto-configure stop (5% stop loss) and target (10% take profit)
        CONFIG['STOP_PRICE'] = latest_price * 0.95
        CONFIG['TARGET_PRICE'] = latest_price * 1.10
        
        log(f"[Data] Loaded {len(returns)} days of returns. Latest Close (Entry): {latest_price:,.2f} VND")
        return returns
    
    except Exception as e:
        log(f"[Error] Data fetch failed: {e}")
        # Fallback dummy data for testing connectivity
        log("[Warning] Using dummy gaussian data.")
        CONFIG['START_CAPITAL'] = 10000.0
        CONFIG['STOP_PRICE'] = 9500.0
        CONFIG['TARGET_PRICE'] = 11000.0
        return np.random.normal(0, 0.02, 252)

# --- MODULE 2: SIMULATION ENGINE ---

class MonteCarloEngine:
    def __init__(self, returns):
        self.returns = returns
        self.simulations = CONFIG['SIMULATIONS']
        self.days = CONFIG['DAYS_TO_PROJECT']
        self.start_capital = CONFIG['START_CAPITAL']
        
    def run(self):
        """
        Executes the Monte Carlo Simulation using Bootstrap Resampling 
        (sampling from historical returns).
        """
        log(f"[Simulation] Starting {self.simulations} simulations for {self.days} days...")
        
        start_time = time.time()
        
        # Vectorized Bootstrap Resampling
        random_idx = np.random.randint(0, len(self.returns), size=(self.days, self.simulations))
        sim_returns = self.returns[random_idx]
        
        # Calculate Cumulative Returns
        sim_paths = self.start_capital * (1 + sim_returns).cumprod(axis=0)
        
        # Add start point (Day 0)
        sim_paths = np.vstack([np.full((1, self.simulations), self.start_capital), sim_paths])
        
        duration = time.time() - start_time
        log(f"[Simulation] Completed in {duration:.2f}s.")
        
        return sim_paths

# --- MODULE 3: ANALYSIS & VISUALIZATION ---

def analyze_and_visualize(sim_paths):
    """
    Calculates stats and generates a static summary image.
    """
    days = sim_paths.shape[0]
    final_values = sim_paths[-1, :]
    entry = CONFIG['START_CAPITAL']
    stop = CONFIG.get('STOP_PRICE', entry * 0.95)
    target = CONFIG.get('TARGET_PRICE', entry * 1.10)
    
    # Statistics
    mean_path = np.mean(sim_paths, axis=1)
    upper_path = np.percentile(sim_paths, 95, axis=1) # 95th percentile (Best Case)
    lower_path = np.percentile(sim_paths, 5, axis=1)  # 5th percentile (VaR)
    
    median_profit = np.median(final_values) - entry
    exp_return = (np.mean(final_values) / entry) - 1
    
    log("=== RESULTS SUMMARY ===")
    log(f"Projected Median Profit: {median_profit:+,.2f} VND")
    log(f"Expected Return (Mean): {exp_return:.2%}")
    log(f"95% Best Case Equity: {upper_path[-1]:,.2f} VND")
    log(f"95% Worst Case Equity: {lower_path[-1]:,.2f} VND")
    
    # --- VISUALIZATION ---
    log("[Visual] Generating static snapshot...")
    
    fig = plt.figure(figsize=(16, 10))
    fig.patch.set_facecolor(CONFIG['COLOR_BG'])
    gs = GridSpec(2, 1, height_ratios=[3, 1], hspace=0.3)
    ax_main = fig.add_subplot(gs[0])
    ax_hist = fig.add_subplot(gs[1])
    
    # 1. Trajectories Plot
    ax_main.set_facecolor(CONFIG['COLOR_BG'])
    ax_main.grid(True, color=CONFIG['COLOR_GRID'], linestyle='--')
    ax_main.set_title(f"Monte Carlo Simulation: {CONFIG['TICKER']} ({CONFIG['SIMULATIONS']} runs)", 
                      color='white', fontsize=16, weight='bold', pad=20)
    ax_main.set_ylabel("Projected Price (VND)", color='gray')
    ax_main.tick_params(colors='gray')
    for spine in ax_main.spines.values(): spine.set_edgecolor('#333')
    
    ax_main.set_xlim(0, days-1)
    ax_main.set_ylim(0, np.max(upper_path) * 1.1)
    
    # Plot a subset of paths to show density cloud
    step = max(1, CONFIG['SIMULATIONS'] // 2000)
    ax_main.plot(sim_paths[:, ::step], color=CONFIG['COLOR_LINE'], linewidth=1.0)
    
    # Stats Lines
    x_axis = np.arange(days)
    ax_main.plot(x_axis, mean_path, color=CONFIG['COLOR_MEAN'], linewidth=2.5, label='Average Projection')
    ax_main.plot(x_axis, upper_path, color=CONFIG['COLOR_BEST'], linewidth=1.5, linestyle='--', label='95% Best Case')
    ax_main.plot(x_axis, lower_path, color=CONFIG['COLOR_WORST'], linewidth=1.5, linestyle='--', label='95% VaR (Worst Case)')
    
    # Plot stop, entry, target lines
    ax_main.axhline(y=entry, color='yellow', linestyle='-', linewidth=1.0, alpha=0.5, label=f'Entry Price: {entry:,.0f}')
    ax_main.axhline(y=stop, color='red', linestyle='-.', linewidth=1.2, alpha=0.7, label=f'Stop Loss: {stop:,.0f} (-5%)')
    ax_main.axhline(y=target, color='green', linestyle='-.', linewidth=1.2, alpha=0.7, label=f'Target Price: {target:,.0f} (+10%)')
    
    leg = ax_main.legend(loc='upper left', facecolor=CONFIG['COLOR_BG'], edgecolor='#333')
    for text in leg.get_texts(): text.set_color('white')
    
    # 2. Histogram Plot
    ax_hist.set_facecolor(CONFIG['COLOR_BG'])
    ax_hist.grid(True, color=CONFIG['COLOR_GRID'], linestyle=':')
    ax_hist.set_xlabel("Final Price (VND)", color='gray')
    ax_hist.set_ylabel("Frequency", color='gray')
    ax_hist.tick_params(colors='gray')
    for spine in ax_hist.spines.values(): spine.set_edgecolor('#333')
    ax_hist.set_title(f"Final Distribution @ Day {days-1}", color='white', fontsize=10)
    
    ax_hist.hist(final_values, bins=100, color='#5a7d9a', edgecolor=CONFIG['COLOR_BG'], alpha=0.9)
    # Vertical lines in histogram
    ax_hist.axvline(x=entry, color='yellow', linestyle='-', linewidth=1.0, alpha=0.5)
    ax_hist.axvline(x=stop, color='red', linestyle='-.', linewidth=1.0, alpha=0.7)
    ax_hist.axvline(x=target, color='green', linestyle='-.', linewidth=1.0, alpha=0.7)
    
    # Save
    out_path = os.path.join(os.path.dirname(__file__), CONFIG['OUTPUT_IMAGE'])
    plt.savefig(out_path, facecolor=CONFIG['COLOR_BG'], dpi=100)
    plt.close(fig)
    log(f"[Visual] Saved to {out_path}")

# --- MAIN ---

def main():
    log("=== MONTE CARLO PIPELINE ===")
    
    # 1. Data
    returns = fetch_market_data()
    
    # 2. Simulation
    engine = MonteCarloEngine(returns)
    paths = engine.run()
    
    # 3. Analysis & Output
    analyze_and_visualize(paths)
    
    log("=== PIPELINE FINISHED ===")

if __name__ == "__main__":
    main()
