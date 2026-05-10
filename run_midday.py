#!/usr/bin/env python3
"""
Routine: Midday Review
Runs: 12:00 PM ET, Mon–Fri
Purpose: Check portfolio, adjust stops if needed, record observations.
No new orders unless emergency.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.config import load_alpaca_config, load_telegram_config, load_risk_config
from src.alpaca_client import AlpacaClient
from src.telegram_client import TelegramClient
from src.risk_manager import check_daily_loss_cap, check_max_drawdown
from src.memory_manager import read, write, load_all, commit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run():
    logger.info("=== MIDDAY REVIEW ===")
    mem = load_all()
    risk = load_risk_config()

    alpaca = AlpacaClient(load_alpaca_config(), risk)
    tg = TelegramClient(load_telegram_config())

    account = alpaca.get_account()
    nav = account["nav"]
    cash = account["cash"]
    day_pnl_pct = account["day_pnl_pct"]
    positions = alpaca.get_positions()

    # Check loss cap
    loss_check = check_daily_loss_cap(day_pnl_pct, risk)
    if not loss_check.passed:
        tg.send_guardrail_breach("daily_loss_cap", f"{day_pnl_pct:.2%}", f"-{risk.daily_loss_cap_pct:.0%}")

    # Check each position against hard stop
    stopped_positions = []
    for pos in positions:
        if pos["unrealized_plpc"] <= risk.hard_stop_pct:
            result = alpaca.submit_market_sell(pos["symbol"], pos["qty"])
            if result and "id" in result:
                stopped_positions.append(pos["symbol"])
                logger.warning(f"Hard stop triggered for {pos['symbol']}: {pos['unrealized_plpc']:.2%}")

    # Alert if anything stopped out
    if stopped_positions:
        tg.send(f"⚠️ *Hard stops executed:* {', '.join(stopped_positions)}")

    # Compose midday summary
    regime_note = mem["research_notes"].split("REGIME:")[-1].split("\n")[0].strip() if "REGIME:" in mem["research_notes"] else "see AM brief"
    lines = [
        f"🌤️ *MIDDAY CHECK — {_today()}*",
        f"NAV: ${nav:,.0f} | Day P&L: {day_pnl_pct:+.2%}",
        f"Cash: {cash/nav:.0%} | Positions: {len(positions)}",
        f"Regime: {regime_note}",
    ]
    if stopped_positions:
        lines.append(f"Stops triggered: {', '.join(stopped_positions)}")
    else:
        lines.append("No stops triggered.")

    tg.send("\n".join(lines))

    notes = mem["research_notes"] + f"\n\n## Midday — {_today()}\n\nNAV: ${nav:,.0f} | Day P&L: {day_pnl_pct:+.2%}"
    write("research_notes.md", notes)
    logger.info("Midday review complete.")


def _today():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


if __name__ == "__main__":
    run()