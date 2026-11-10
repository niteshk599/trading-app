import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time

# ==========================================
# PAGE CONFIGURATION & STYLING
# ==========================================
st.set_page_config(page_title="Apex Delta Terminal", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .reportview-container { background: #0e1117; }
    .metric-box { background: #1e222d; padding: 15px; border-radius: 10px; border: 1px solid #2a2e39; margin-bottom: 10px; }
    .buy-signal { background: rgba(0, 255, 136, 0.1); border-left: 5px solid #00ff88; padding: 15px; border-radius: 5px; }
    .sell-signal { background: rgba(255, 74, 74, 0.1); border-left: 5px solid #ff4a4a; padding: 15px; border-radius: 5px; }
    .neutral-signal { background: rgba(255, 255, 255, 0.1); border-left: 5px solid #ffffff; padding: 15px; border-radius: 5px; }
    h1, h2, h3 { color: #ffffff !important; }
</style>
""", unsafe_allow_html=True)

st.title("🏛️ Apex Delta Trading Terminal")
st.markdown("Institutional Smart Money Concepts | Live Delta Exchange Data")

# ==========================================
# DELTA EXCHANGE API DATA FETCHER
# ==========================================
@st.cache_data(ttl=60) # Cache for 1 minute to prevent rate limits
def fetch_delta_data(symbol, resolution):
    # Calculate timestamps for Delta API
    end_time = int(time.time())
    # Fetch enough data for 200 EMA (approx 300 candles)
    if resolution in ['15m', '1h']:
        start_time = end_time - (300 * int(resolution[:-1]) * 60)
    elif resolution == '4h':
        start_time = end_time - (300 * 4 * 3600)
    else:
        start_time = end_time - (300 * 24 * 3600)

    url = f"https://api.delta.exchange/v2/history/candles?resolution={resolution}&symbol={symbol}&start={start_time}&end={end_time}"
    
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        data = response.json()
        if 'result' in data and len(data['result']) > 0:
            df = pd.DataFrame(data['result'])
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('time', inplace=True)
            df = df.sort_index()
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

# ==========================================
# TECHNICAL ANALYSIS ENGINE
# ==========================================
def calculate_strategies(df):
    # 1. EMAs
    df['EMA_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # 2. RSI (14)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # 3. MACD
    exp12 = df['close'].ewm(span=12, adjust=False).mean()
    exp26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp12 - exp26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    # 4. Market Structure (Swing Highs/Lows for S/R)
    df['Swing_High'] = df['high'].rolling(window=5, center=True).max()
    df['Swing_Low'] = df['low'].rolling(window=5, center=True).min()
    
    return df

def generate_signal(df, mode):
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    signal = "WAIT"
    reason = []
    
    # Trend Filter
    is_uptrend = latest['close'] > latest['EMA_200']
    is_downtrend = latest['close'] < latest['EMA_200']
    
    if mode == "Intraday (15m/1H)":
        # Intraday Logic (9/21 EMA Cross + RSI)
        if is_uptrend and latest['EMA_9'] > latest['EMA_21'] and latest['RSI'] > 50:
            signal = "BUY"
            reason.append("Price above 200 EMA (Macro Bullish)")
            reason.append("9 EMA crossed above 21 EMA")
            reason.append("RSI > 50 (Bullish Momentum)")
        elif is_downtrend and latest['EMA_9'] < latest['EMA_21'] and latest['RSI'] < 50:
            signal = "SELL"
            reason.append("Price below 200 EMA (Macro Bearish)")
            reason.append("9 EMA crossed below 21 EMA")
            reason.append("RSI < 50 (Bearish Momentum)")
            
    else: # Swing Mode (4H/1D)
        # Swing Logic (MACD + EMA Alignment)
        if is_uptrend and latest['EMA_50'] > latest['EMA_200'] and latest['MACD_Hist'] > 0:
            signal = "BUY"
            reason.append("Golden Cross (50 EMA > 200 EMA)")
            reason.append("MACD Histogram Positive")
        elif is_downtrend and latest['EMA_50'] < latest['EMA_200'] and latest['MACD_Hist'] < 0:
            signal = "SELL"
            reason.append("Death Cross (50 EMA < 200 EMA)")
            reason.append("MACD Histogram Negative")
            
    return signal, reason, latest

# ==========================================
# UI LAYOUT & SIDEBAR
# ==========================================
st.sidebar.header("⚙️ Terminal Settings")
# Delta Exchange India Symbols
asset = st.sidebar.selectbox("Select Asset", ["BTCUSD", "ETHUSD", "XAUUSD", "SOLUSD"])
trade_mode = st.sidebar.radio("Trading Strategy", ["Intraday (15m/1H)", "Swing (4H/1D)"])

# Set Timeframe based on mode
if trade_mode == "Intraday (15m/1H)":
    resolution = "15m"
else:
    resolution = "4h"

# Fetch Data
df = fetch_delta_data(asset, resolution)

if not df.empty:
    df = calculate_strategies(df)
    signal, reason, latest = generate_signal(df, trade_mode)
    
    # --- TOP METRICS ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(f"{asset} Price", f"${latest['close']:,.2f}")
    col2.metric("RSI (14)", f"{latest['RSI']:.2f}", "Overbought" if latest['RSI']>70 else "Oversold" if latest['RSI']<30 else "Neutral")
    col3.metric("MACD", f"{latest['MACD']:.2f}")
    col4.metric("Trend (200 EMA)", "BULLISH" if latest['close'] > latest['EMA_200'] else "BEARISH")
    
    st.markdown("---")
    
    # --- CHART & ACTION PANEL ---
    col_chart, col_action = st.columns([3, 1])
    
    with col_chart:
        st.subheader(f"{asset} - {resolution} Chart (Delta Exchange)")
        
        # Create Subplots (Price, RSI, MACD)
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.03, 
                            row_heights=[0.6, 0.2, 0.2],
                            subplot_titles=("Price Action", "RSI", "MACD"))
        
        # Candlesticks
        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['high'], 
                                     low=df['low'], close=df['close'], name='Price'), row=1, col=1)
        
        # EMAs
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_9'], line=dict(color='#00ff88', width=1), name='9 EMA'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_21'], line=dict(color='#ff4a4a', width=1), name='21 EMA'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_50'], line=dict(color='#ff9900', width=1.5), name='50 EMA'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_200'], line=dict(color='#ffffff', width=2), name='200 EMA'), row=1, col=1)
        
        # Key Levels (Recent High/Low)
        recent_high = df['high'].tail(50).max()
        recent_low = df['low'].tail(50).min()
        fig.add_hline(y=recent_high, line_dash="dash", line_color="red", annotation_text="Resistance", row=1, col=1)
        fig.add_hline(y=recent_low, line_dash="dash", line_color="green", annotation_text="Support", row=1, col=1)
        
        # RSI
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple', width=1.5), name='RSI'), row=2, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1)
        
        # MACD
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name='MACD Hist'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='blue', width=1), name='MACD'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD_Signal'], line=dict(color='orange', width=1), name='Signal'), row=3, col=1)
        
        fig.update_layout(template="plotly_dark", height=800, xaxis_rangeslider_visible=False, showlegend=True, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)
        
    with col_action:
        st.subheader("🎯 Execution Plan")
        
        # Signal Box
        if signal == "BUY":
            st.markdown(f'<div class="buy-signal"><h3>🟢 LONG (BUY)</h3></div>', unsafe_allow_html=True)
            entry = latest['close']
            sl = recent_low * 0.995 # Just below support
            risk = entry - sl
            tp1 = entry + (risk * 1.5)
            tp2 = entry + (risk * 3.0)
        elif signal == "SELL":
            st.markdown(f'<div class="sell-signal"><h3>🔴 SHORT (SELL)</h3></div>', unsafe_allow_html=True)
            entry = latest['close']
            sl = recent_high * 1.005 # Just above resistance
            risk = sl - entry
            tp1 = entry - (risk * 1.5)
            tp2 = entry - (risk * 3.0)
        else:
            st.markdown(f'<div class="neutral-signal"><h3>⚪ NO TRADE (WAIT)</h3></div>', unsafe_allow_html=True)
            entry, sl, tp1, tp2 = 0, 0, 0, 0
            
        st.markdown("### Strategy Rationale")
        for r in reason:
            st.write(f"• {r}")
            
        if signal != "WAIT":
            st.markdown("---")
            st.markdown(f"**Entry Price:** `${entry:,.2f}`")
            st.markdown(f"**Stop Loss:** `${sl:,.2f}`")
            st.markdown(f"**Take Profit 1 (1.5R):** `${tp1:,.2f}`")
            st.markdown(f"**Take Profit 2 (3.0R):** `${tp2:,.2f}`")
            st.markdown(f"**Risk/Reward:** `1:3` (to TP2)")
            
        st.markdown("---")
        st.subheader("📊 Key SMC Levels")
        st.write(f"**Major Resistance:** `${recent_high:,.2f}`")
        st.write(f"**Major Support:** `${recent_low:,.2f}`")
        st.write(f"**Equilibrium (50%):** `${(recent_high + recent_low)/2:,.2f}`")

else:
    st.error("Failed to fetch data from Delta Exchange. Please verify the asset symbol or try again.")
