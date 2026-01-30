"""Bot status card rendering helpers for Streamlit."""

from __future__ import annotations

from typing import Any

import streamlit as st


_STATUS_COLOURS: dict[str, str] = {
    "running": "#26a69a",
    "stopped": "#ef5350",
    "error": "#ff9800",
    "starting": "#42a5f5",
    "unknown": "#9e9e9e",
}


def _status_dot(status: str) -> str:
    colour = _STATUS_COLOURS.get(status.lower(), _STATUS_COLOURS["unknown"])
    label = status.capitalize()
    return f":{colour}[\\u25CF] **{label}**"


def render_bot_card(bot: dict[str, Any]) -> None:
    """Render a single bot as a Streamlit metric card.

    Expected *bot* keys (all optional except ``name``):
        name, status, pnl, pair, exchange, uptime
    """
    name: str = bot.get("name", "unnamed")
    status: str = bot.get("status", "unknown")
    pnl: float | None = bot.get("pnl")
    pair: str = bot.get("pair", "")
    exchange: str = bot.get("exchange", "")

    colour = _STATUS_COLOURS.get(status.lower(), _STATUS_COLOURS["unknown"])

    st.markdown(
        f"""
<div style="
    border: 1px solid {colour};
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 8px;
    background: rgba(255,255,255,0.03);
">
    <div style="font-size:0.85em;color:#aaa;">{exchange} &middot; {pair}</div>
    <div style="font-size:1.15em;font-weight:600;">{name}</div>
    <div style="margin-top:4px;">
        <span style="color:{colour};">&#9679;</span>
        <span style="font-size:0.9em;">{status.capitalize()}</span>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

    if pnl is not None:
        delta_color = "normal" if pnl >= 0 else "inverse"
        st.metric(label="P&L", value=f"${pnl:,.2f}", delta=f"{pnl:+,.2f}", delta_color=delta_color)


def render_bot_grid(bots: list[dict[str, Any]], cols: int = 3) -> None:
    """Render a responsive grid of bot cards.

    *bots* is a list of dicts accepted by :func:`render_bot_card`.
    """
    if not bots:
        st.info("No bots found.")
        return

    columns = st.columns(cols)
    for idx, bot in enumerate(bots):
        with columns[idx % cols]:
            render_bot_card(bot)
