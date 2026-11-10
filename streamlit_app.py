import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import yfinance as yf

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
st.markdown("Institutional Smart Money Concepts | Live Data")

# ==========================================
# BULLETPROOF DATA FETCHER (Delta -> Binance -> Yahoo)
# ==========================================
@st.cache_data(ttl=60)
def fetch_data(asset, resolution):
    # 1. TRY DELTA EXCHANGE
    try:
        end_time = int(time.time())
        multiplier = 60 if resolution == '15m' else 3600 if resolution == '1h' else 14400
        start_time = end_time - (300 * multiplier)
        # Map XAUTUSD for Delta
        delta_symbol = "XAUTUSD" if asset == "GOLD" else asset
        url = f"https://api.delta.exchange/v2/history/candles?resolution={resolution}&symbol={delta_symbol}&start={start_time}&end={end_time}"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        data = response.json()
        if 'result' in data and len(data['result']) > 0:
            df = pd.DataFrame(data['result'])
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('time', inplace=True)
            return df.sort_index(), "Delta Exchange (Live)"
    except Exception:
        pass

    # 2. TRY BINANCE (Bulletproof fallback for Crypto & Gold)
    try:
        binance_symbol = "BTCUSDT" if asset == "BTCUSD" else "ETHUSDT" if asset == "ETHUSD" else "SOLUSDT" if asset == "SOLUSD" else "PAXGUSDT" if asset == "GOLD" else asset
        binance_interval = "15m" if resolution == "15m" else "1h" if resolution == "1h" else "4h"
        url = f"https://api.binance.com/api/v3/klines?symbol={binance_symbol}&interval={binance_interval}&limit=300"
        response = requests.get(url, timeout=5)
        data = response.json()
        if isinstance(data, list) and len(data) > 0:
            df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'tbbav', 'tbqav', 'ignore'])
            df['time'] = pd.to_datetime(df['time'], unit='ms')
            df.set_index('time', inplace=True)
            for col in ['open', 'high', 'low', 'close']:
                df[col] = df[col].astype(float)
            return df, "Binance API (Fallback)"
    except Exception:
        pass

    # 3. TRY YAHOO FINANCE (Fixed MultiIndex bug)
    try:
        yf_symbol = "BTC-USD" if asset == "BTCUSD" else "ETH-USD" if asset == "ETHUSD" else "SOL-USD" if asset == "SOLUSD" else "GC=F" if asset == "GOLD" else asset
        yf_interval = "15m" if resolution == "15m" else "1h" if resolution == "1h" else "1d"
        yf_period = "1mo" if resolution == "15m" else "3mo" if resolution == "1h" else "1y"
        
        df = yf.download(yf_symbol, period=yf_period, interval=yf_interval, progress=False)
        if not df.empty:
            # FIX: Handle Yahoo's new MultiIndex columns
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns = [str(c).lower() for c in df.columns]
            return df, "Yahoo Finance (Fallback)"
    except Exception:
        pass

    return pd.DataFrame(), "Failed"

# ==========================================
# TECHNICAL ANALYSIS ENGINE
# ==========================================
def calculate_strategies(df):
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp12 = df['close'].ewm(span=12, adjust=False).mean()
    exp26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp12 - exp26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    return df

def generate_signal(df, mode):
    latest = df.iloc[-1]
    signal = "WAIT"
    reason = []
    
    is_uptrend = latest['close'] > latest['ema_200']
    is_downtrend = latest['close'] < latest['ema_200']
    
    if mode == "Intraday (15m/1H)":
        if is_uptrend and latest['ema_9'] > latest['ema_21'] and latest['rsi'] > 50:
            signal = "BUY"
            reason = ["Price above 200 EMA (Macro Bullish)", "9 EMA crossed above 21 EMA", "RSI > 50 (Momentum)"]
        elif is_downtrend and latest['ema_9'] < latest['ema_21'] and latest['rsi'] < 50:
            signal = "SELL"
            reason = ["Price below 200 EMA (Macro Bearish)", "9 EMA crossed below 21 EMA", "RSI < 50 (Momentum)"]
    else:
        if is_uptrend and latest['ema_50'] > latest['ema_200'] and latest['macd_hist'] > 0:
            signal = "BUY"
            reason = ["Golden Cross (50 > 200 EMA)", "MACD Histogram Positive"]
        elif is_downtrend and latest['ema_50'] < latest['ema_200'] and latest['macd_hist'] < 0:
            signal = "SELL"
            reason = ["Death Cross (50 < 200 EMA)", "MACD Histogram Negative"]
            
    return signal, reason, latest

# ==========================================
# UI LAYOUT & SIDEBAR
# ==========================================
st.sidebar.header("⚙️ Terminal Settings")
# Asset Options mapped for all APIs
asset = st.sidebar.selectbox("Select Asset", ["BTCUSD", "ETHUSD", "SOLUSD", "GOLD"])
trade_mode = st.sidebar.radio("Trading Strategy", ["Intraday (15m/1H)", "Swing (4H/1D)"])

if trade_mode == "Intraday (15m/1H)":
    resolution = "15m"
else:
    resolution = "4h"

# Fetch Data
with st.spinner("Fetching live data and calculating institutional levels..."):
    df, data_source = fetch_data(asset, resolution)

if not df.empty:
    df = calculate_strategies(df)
    signal, reason, latest = generate_signal(df, trade_mode)
    
    # Top Status Bar
    st.info(f"📡 Data Source: **{data_source}** | Asset: **{asset}** | Timeframe: **{resolution}**")
    
    # --- TOP METRICS ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(f"{asset} Price", f"${latest['close']:,.2f}")
    col2.metric("RSI (14)", f"{latest['rsi']:.2f}", "Overbought" if latest['rsi']>70 else "Oversold" if latest['rsi']<30 else "Neutral")
    col3.metric("MACD", f"{latest['macd']:.2f}")
    col4.metric("Trend (200 EMA)", "BULLISH" if latest['close'] > latest['ema_200'] else "BEARISH")
    
    st.markdown("---")
    
    # --- CHART & ACTION PANEL ---
    col_chart, col_action = st.columns([3, 1])
    
    with col_chart:
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, 
                            row_heights=[0.6, 0.2, 0.2], subplot_titles=("Price Action", "RSI", "MACD"))
        
        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='Price'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['ema_9'], line=dict(color='#00ff88', width=1), name='9 EMA'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['ema_21'], line=dict(color='#ff4a4a', width=1), name='21 EMA'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['ema_50'], line=dict(color='#ff9900', width=1.5), name='50 EMA'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['ema_200'], line=dict(color='#ffffff', width=2), name='200 EMA'), row=1, col=1)
        
        recent_high = df['high'].tail(50).max()
        recent_low = df['low'].tail(50).min()
        fig.add_hline(y=recent_high, line_dash="dash", line_color="red", annotation_text="Resistance", row=1, col=1)
        fig.add_hline(y=recent_low, line_dash="dash", line_color="green", annotation_text="Support", row=1, col=1)
        
        fig.add_trace(go.Scatter(x=df.index, y=df['rsi'], line=dict(color='purple', width=1.5), name='RSI'), row=2, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1)
        
        fig.add_trace(go.Bar(x=df.index, y=df['macd_hist'], name='MACD Hist'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['macd'], line=dict(color='blue', width=1), name='MACD'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['macd_signal'], line=dict(color='orange', width=1), name='Signal'), row=3, col=1)
        
        fig.update_layout(template="plotly_dark", height=750, xaxis_rangeslider_visible=False, showlegend=True, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)
        
    with col_action:
        if signal == "BUY":
            st.markdown(f'<div class="buy-signal"><h3>🟢 LONG (BUY)</h3></div>', unsafe_allow_html=True)
            entry = latest['close']
            sl = recent_low * 0.995 
            risk = entry - sl
            tp1 = entry + (risk * 1.5)
            tp2 = entry + (risk * 3.0)
        elif signal == "SELL":
            st.markdown(f'<div class="sell-signal"><h3>🔴 SHORT (SELL)</h3></div>', unsafe_allow_html=True)
            entry = latest['close']
            sl = recent_high * 1.005 
            risk = sl - entry
            tp1 = entry - (risk * 1.5)
            tp2 = entry - (risk * 3.0)
        else:
            st.markdown(f'<div class="neutral-signal"><h3>⚪ NO TRADE</h3></div>', unsafe_allow_html=True)
            entry, sl, tp1, tp2 = 0, 0, 0, 0
            
        st.markdown("### Strategy Rationale")
        for r in reason:
            st.write(f"• {r}")
            
        if signal != "WAIT":
            st.markdown("---")
            st.markdown(f"**Entry:** `${entry:,.2f}`")
            st.markdown(f"**Stop Loss:** `${sl:,.2f}`")
            st.markdown(f"**TP1 (1.5R):** `${tp1:,.2f}`")
            st.markdown(f"**TP2 (3.0R):** `${tp2:,.2f}`")
            
        st.markdown("---")
        st.subheader("📊 SMC Levels")
        st.write(f"**Resistance:** `${recent_high:,.2f}`")
        st.write(f"**Support:** `${recent_low:,.2f}`")
        st.write(f"**Equilibrium:** `${(recent_high + recent_low)/2:,.2f}`")

else:
    st.error("Data sources are currently blocked. Please wait 5 minutes and refresh the page.")
