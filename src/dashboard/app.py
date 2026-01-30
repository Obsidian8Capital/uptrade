"""UpTrade Dashboard — main Streamlit entry point.

Launch with:
    streamlit run src/dashboard/app.py
"""

from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Page config (must be the first Streamlit command)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="UpTrade Dashboard",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Sidebar — global controls
# ---------------------------------------------------------------------------
st.sidebar.title("UpTrade")
st.sidebar.caption("Bot Monitoring Dashboard")

# Connection status
hb_host = st.sidebar.text_input("Hummingbot API host", value="localhost:8000")
st.sidebar.markdown("---")

# Auto-refresh interval
refresh_secs = st.sidebar.slider(
    "Refresh interval (s)", min_value=5, max_value=120, value=30, step=5
)

# Symbol filter (available to all pages via session state)
symbol_filter = st.sidebar.text_input(
    "Symbol filter", value="", placeholder="e.g. BTC-USDT"
)
st.session_state["hb_host"] = hb_host
st.session_state["refresh_secs"] = refresh_secs
st.session_state["symbol_filter"] = symbol_filter

# ---------------------------------------------------------------------------
# Main landing page
# ---------------------------------------------------------------------------
st.title("UpTrade Dashboard")
st.markdown(
    """
Welcome to the **UpTrade** monitoring dashboard.

Use the sidebar to navigate:

| Page | Description |
|------|-------------|
| **Bot Overview** | Live bot statuses, P&L summary, active positions |
| **Signals** | OHLCV candlestick charts with indicator signal overlays |

---

*Select a page from the sidebar to get started.*
"""
)
