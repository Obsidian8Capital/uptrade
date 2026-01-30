"""Page 1 — Bot Overview: status cards, P&L chart, positions table."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pandas as pd
import streamlit as st

from src.dashboard.components.bot_cards import render_bot_grid
from src.dashboard.components.charts import create_pnl_chart

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _fetch_bots(api_url: str) -> list[dict[str, Any]]:
    """Fetch bot list from Hummingbot API."""
    async with httpx.AsyncClient(base_url=api_url, timeout=10.0) as client:
        resp = await client.get("/bot-orchestration/status")
        resp.raise_for_status()
        return resp.json()


def _get_bots(api_url: str) -> list[dict[str, Any]]:
    """Synchronous wrapper around async fetch."""
    try:
        return asyncio.run(_fetch_bots(api_url))
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Could not reach Hummingbot API: {exc}")
        return []


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

st.header("Bot Overview")

hb_host: str = st.session_state.get("hb_host", "localhost:8000")
symbol_filter: str = st.session_state.get("symbol_filter", "")
refresh_secs: int = st.session_state.get("refresh_secs", 30)

api_url = f"http://{hb_host}"
bots = _get_bots(api_url)

# Apply optional symbol filter
if symbol_filter:
    bots = [
        b for b in bots
        if symbol_filter.upper() in (b.get("pair", "") or "").upper()
    ]

# Summary metrics row
col1, col2, col3, col4 = st.columns(4)
running = sum(1 for b in bots if (b.get("status", "")).lower() == "running")
total_pnl = sum(b.get("pnl", 0) or 0 for b in bots)
col1.metric("Total Bots", len(bots))
col2.metric("Running", running)
col3.metric("Stopped", len(bots) - running)
col4.metric("Total P&L", f"${total_pnl:,.2f}")

st.markdown("---")

# Bot cards grid
st.subheader("Active Bots")
render_bot_grid(bots, cols=3)

st.markdown("---")

# P&L chart (placeholder data when API unavailable)
st.subheader("Cumulative P&L")
if bots:
    pnl_records = [
        {"time": b.get("start_time", pd.Timestamp.now()), "pnl": b.get("pnl", 0) or 0}
        for b in bots
    ]
    pnl_df = pd.DataFrame(pnl_records).sort_values("time")
    pnl_df["pnl"] = pnl_df["pnl"].cumsum()
    fig = create_pnl_chart(pnl_df)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No P&L data available — connect to the Hummingbot API.")

st.markdown("---")

# Positions table
st.subheader("Active Positions")
if bots:
    positions = []
    for b in bots:
        for pos in b.get("positions", []):
            positions.append(
                {
                    "Bot": b.get("name", ""),
                    "Pair": pos.get("pair", b.get("pair", "")),
                    "Side": pos.get("side", ""),
                    "Size": pos.get("size", 0),
                    "Entry": pos.get("entry_price", 0),
                    "Current": pos.get("current_price", 0),
                    "Unrealised P&L": pos.get("unrealized_pnl", 0),
                }
            )
    if positions:
        st.dataframe(pd.DataFrame(positions), use_container_width=True)
    else:
        st.info("No open positions.")
else:
    st.info("Connect to the API to see positions.")
