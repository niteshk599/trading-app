import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# Set page configuration
st.set_page_config(page_title="Apex Trading Terminal", layout="wide")

st.title("🏛️ Apex Multi-Asset Trading Terminal")
st.markdown("Professional algorithmic analysis for Gold, Bitcoin, and Stocks.")

# Sidebar Controls
st.sidebar.header("Dashboard Settings")
ticker = st.sidebar.selectbox("Select Asset", ["BTC-USD", "GC=F", "AAPL", "XAUUSD", "SPY"])
timeframe = st.sidebar.selectbox("Timeframe", ["1h", "4h", "1d"])

# Define period based on timeframe
period = "1mo" if timeframe != "1d" else "1y"

@st.cache_data(ttl=300)
def get_data(ticker, period, interval):
    # Download data
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    if df.empty:
        return df
        
    # Fix for new yfinance multi-index columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    # Calculate EMAs
    df['EMA_20'] = df['Close'].rolling(20).mean()
    df['EMA_50'] = df['Close'].rolling(50).mean()
    return df

df = get_data(ticker, period, timeframe)

if not df.empty:
    latest = df.iloc[-1]
    price = float(latest['Close'])
    trend = "BULLISH" if price > latest['EMA_50'] else "BEARISH"
    
    # Top Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Current Price", f"${price:,.2f}")
    col2.metric("Market Trend", trend)
    col3.metric("50 EMA Level", f"${latest['EMA_50']:,.2f}")
    
    st.markdown("---")
    
    # Chart and Analysis
    col_chart, col_analysis = st.columns([2, 1])
    
    with col_chart:
        st.subheader(f"{ticker} Chart")
        fig = go.Figure()
        
        # Candlesticks
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], 
            low=df['Low'], close=df['Close'], name='Price'
        ))
        
        # EMAs
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_20'], line=dict(color='#00ff88', width=1.5), name='20 EMA'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_50'], line=dict(color='#ff4a4a', width=1.5), name='50 EMA'))
        
        # Chart Layout
        fig.update_layout(
            template="plotly_dark", 
            height=500, 
            xaxis_rangeslider_visible=False, 
            margin=dict(l=0, r=0, t=0, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)
        
    with col_analysis:
        st.subheader("🤖 Algorithmic Setup")
        
        # Trade Scenarios
        if trend == "BULLISH":
            st.success("**BUY SCENARIO**")
            st.write(f"**Trigger:** Price holds above 20 EMA (${latest['EMA_20']:,.2f})")
            st.write(f"**Stop Loss:** 50 EMA (${latest['EMA_50']:,.2f})")
            st.write(f"**Target:** Next major resistance.")
        else:
            st.error("**SELL SCENARIO**")
            st.write(f"**Trigger:** Rejection at 50 EMA (${latest['EMA_50']:,.2f})")
            st.write(f"**Stop Loss:** Above 20 EMA (${latest['EMA_20']:,.2f})")
            st.write(f"**Target:** Next major support.")
            
        st.markdown("---")
        
        # Key Levels
        st.subheader("📊 Key Levels (Last 20 Candles)")
        st.write(f"**Recent High:** ${float(df['High'].tail(20).max()):,.2f}")
        st.write(f"**Recent Low:** ${float(df['Low'].tail(20).min()):,.2f}")
else:
    st.error("Failed to load data. Please check the ticker symbol or try again later.")
