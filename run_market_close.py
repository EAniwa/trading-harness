#!/usr/bin/env python3
"""
Routine: Market Close Journal
Runs: 3:00 PM ET, Mon–Fri
Purpose: Record performance, journal insights, update all memory files.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.config import load_alpaca_config, load_telegram_config, load_risk_config
from src.alpaca_client import AlpacaClient
from src.telegram_client import TelegramClient
from src.memory_manager import read, write, load_all, commit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run():
    logger.info("=== MARKET CLOSE JOURNAL ===")
    mem = load_all()
    risk = load_risk_config()

    alpaca = AlpacaClient(load_alpaca_config(), risk)
    tg = TelegramClient(load_telegram_config())

    account = alpaca.get_account()
    nav = account["nav"]
    cash = account["cash"]
    day_pnl = account["day_pnl"]
    day_pnl_pct = account["day_pnl_pct"]
    positions = alpaca.get_positions()
    todays_orders = alpaca.get_todays_filled_orders()

    # Benchmark: get SPY closing price
    spy_return = alpaca.get_daily_return("SPY") or 0.0
    relative = day_pnl_pct - spy_return

    # ── Compose Market Close Message ──────────────────────────────────────
    top_positions = sorted(positions, key=lambda p: p["unrealized_pl"], reverse=True)[:3]
    lines = [
        f"📈 *MARKET CLOSE — {_today()}*",
        f"NAV: ${nav:,.0f} | Day P&L: {day_pnl_pct:+.2%}",
        f"S&P 500: {spy_return:+.2%} | Relative: {relative:+.2%}",
        f"Open positions: {len(positions)}",
    ]
    if top_positions:
        lines.append("Top performers:")
        for p in top_positions:
            lines.append(f"  {p['symbol']}: {p['unrealized_plpc']:+.2%} (${p['unrealized_pl']:+.0f})")

    if todays_orders:
        lines.append("Trades today:")
        for o in todays_orders:
            side_icon = "🟢" if o["side"] == "buy" else "🔴"
            lines.append(f"  {side_icon} {o['side'].upper()} {o['symbol']} {o['qty']} shares @ ${o['fill_price']:.2f}")

    lines.append(f"Cash: {cash/nav:.0%}")
    tg.send("\n".join(lines))

    # ── Update Trade Log ───────────────────────────────────────────────────
    entry = (
        f"\n\n**{_today()}**\n"
        f"Starting NAV: ${nav - day_pnl:,.0f} | Ending NAV: ${nav:,.0f}\n"
        f"Day P&L: {day_pnl_pct:+.2%} | S&P 500: {spy_return:+.2%} | Relative: {relative:+.2%}\n"
        f"Trades: {len(todays_orders)} executed\n"
        f"Cash: {cash/nav:.0%}"
    )
    trade_log = mem["trade_log"] + entry
    write("trade_log.md", trade_log)

    # ── Update Research Notes ──────────────────────────────────────────────
    notes = mem["research_notes"]
    notes += f"\n\n## Market Close — {_today()}\n\nDay P&L: {day_pnl_pct:+.2%} | NAV: ${nav:,.0f}"
    write("research_notes.md", notes)

    commit(f"chore: market close {_today()}")
    logger.info("Market close journal complete.")


def _today():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


if __name__ == "__main__":
    run()