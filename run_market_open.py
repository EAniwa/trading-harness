#!/usr/bin/env python3
"""
Routine: Market Open Execution
Runs: 8:30 AM ET, Mon–Fri
Purpose: Execute planned trades from pre-market, set trailing stops, send alerts.
Waits for actual market open (9:30 AM ET) before submitting orders.
"""

import logging
import sys
from math import floor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.config import load_alpaca_config, load_telegram_config, load_risk_config
from src.alpaca_client import AlpacaClient
from src.telegram_client import TelegramClient
from src.risk_manager import check_daily_loss_cap, calculate_trailing_stop_pct
from src.memory_manager import read, write, load_all, commit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run():
    logger.info("=== MARKET OPEN EXECUTION ROUTINE ===")
    mem = load_all()
    risk = load_risk_config()

    alpaca = AlpacaClient(load_alpaca_config(), risk)
    tg = TelegramClient(load_telegram_config())

    # ── 1. Pre-trade checks ─────────────────────────────────────────────────
    account = alpaca.get_account()
    nav = account["nav"]
    cash = account["cash"]
    day_pnl_pct = account["day_pnl_pct"]

    loss_result = check_daily_loss_cap(day_pnl_pct, risk)
    if not loss_result.passed:
        tg.send_guardrail_breach(
            "daily_loss_cap",
            f"{day_pnl_pct:.2%}",
            f"-{risk.daily_loss_cap_pct:.0%}",
        )
        logger.warning("Daily loss cap breached. Aborting execution.")
        return

    positions = alpaca.get_positions()
    logger.info(f"NAV: ${nav:,.0f} | Cash: ${cash:,.0f} | {len(positions)} positions")

    # ── 2. Wait for market open ────────────────────────────────────────────
    logger.info("Waiting for market open...")
    if not alpaca.wait_for_market_open():
        logger.warning("Could not confirm market open. Aborting execution.")
        tg.send("⚠️ Market open confirmation failed. No orders submitted.")
        return

    logger.info("Market is open. Proceeding with execution.")

    # ── 3. Set trailing stops on all existing positions ───────────────────
    stop_count = 0
    for pos in positions:
        plpc = pos["unrealized_plpc"]
        trail_pct = calculate_trailing_stop_pct(plpc, risk)
        result = alpaca.set_trailing_stop(pos["symbol"], trail_pct)
        if result and "error" not in result:
            stop_count += 1
            logger.info(f"Trailing stop set on {pos['symbol']}: {trail_pct:.0%}")

    # ── 4. Execute planned trades from pre-market ───────────────────────────
    trade_ideas = _parse_trade_ideas(mem["research_notes"])
    executed = []
    total_deployed = 0.0

    for idea in trade_ideas:
        ticker = idea["symbol"].upper()
        conviction = idea.get("conviction", 1.0)

        # Check if already in a position for this ticker
        existing = next((p for p in positions if p["symbol"].upper() == ticker), None)

        # Position sizing
        position_dollars = min(conviction * 0.02 * nav, risk.max_position_pct * nav)
        price = alpaca.get_latest_price(ticker)
        if not price:
            logger.warning(f"No price for {ticker}. Skipping.")
            continue

        shares = floor(position_dollars / price)
        if shares < 1:
            logger.info(f"Position size too small for {ticker}. Skipping.")
            continue

        # Alert before order
        position_pct = position_dollars / nav
        stop_price = price * (1 - risk.hard_stop_pct)
        tg.send_trade_alert(
            side="buy",
            symbol=ticker,
            qty=shares,
            price=price,
            position_pct=position_pct,
            thesis=idea.get("thesis", ""),
            stop_price=stop_price,
        )

        # Submit order
        result = alpaca.submit_market_buy(ticker, shares)
        if result and "id" in result:
            executed.append({"symbol": ticker, "qty": shares, "price": price, "id": result["id"]})
            total_deployed += shares * price
            logger.info(f"BUY {ticker}: {shares} shares @ ${price:.2f}")
        else:
            logger.error(f"Order failed for {ticker}: {result}")

    # ── 5. Market Open Telegram Summary ────────────────────────────────────
    cash_after = cash - total_deployed
    lines = [
        f"🔔 *MARKET OPEN — {_today()} 9:35 AM*",
        f"Trades executed: {len(executed)}",
    ]
    for t in executed:
        lines.append(f"  • {t['symbol']}: +{t['qty']} shares @ ${t['price']:.2f}")
    lines.append(f"Total deployed: ${total_deployed:,.0f}")
    lines.append(f"Cash remaining: {cash_after/nav:.0%} (${cash_after:,.0f})")
    lines.append(f"NAV: ${nav:,.0f}")
    lines.append(f"Stops active: {stop_count} positions")
    tg.send("\n".join(lines))

    # ── 6. Write Memory ────────────────────────────────────────────────────
    trade_log = mem["trade_log"]
    for t in executed:
        trade_log += f"\n- {t['symbol']}: BUY {t['qty']} shares @ ${t['price']:.2f}"
    write("trade_log.md", trade_log)
    commit(f"chore: market open {_today()}")
    logger.info(f"Market open routine complete. {len(executed)} trades executed.")


def _parse_trade_ideas(research_notes: str) -> list[dict]:
    """Extract trade ideas from research_notes. Format: **TICKER** — action — rationale"""
    import re
    ideas = []
    lines = research_notes.split("\n")
    for line in lines:
        if "BUY" in line.upper() or "NEW ENTRY" in line.upper():
            ticker_match = re.search(r"\b([A-Z]{2,5})\b", line)
            if ticker_match:
                ideas.append({"symbol": ticker_match.group(1), "thesis": line})
    return ideas[:3]  # max 3 trades per session


def _today():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


if __name__ == "__main__":
    run()