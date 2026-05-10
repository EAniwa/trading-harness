#!/usr/bin/env python3
"""
Routine: Pre-Market Research
Runs: 6:00 AM ET, Mon–Fri
Purpose: Gather macro intelligence, check portfolio health, draft trade ideas.
No order execution here.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.config import load_alpaca_config, load_telegram_config, load_research_config, load_risk_config
from src.alpaca_client import AlpacaClient
from src.research_client import ResearchClient
from src.telegram_client import TelegramClient
from src.risk_manager import check_daily_loss_cap, check_max_drawdown, check_cash_floor
from src.memory_manager import read, write, load_all, commit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run():
    logger.info("=== PRE-MARKET RESEARCH ROUTINE ===")
    mem = load_all()
    logger.info("Memory loaded.")

    # ── 1. Macro Pulse ──────────────────────────────────────────────────────
    research = ResearchClient(load_research_config())
    macro = research.get_macro_pulse()
    regime = research.assess_market_regime()
    sectors = research.get_sector_performance()

    # ── 2. Portfolio Health ────────────────────────────────────────────────
    alpaca = AlpacaClient(load_alpaca_config(), load_risk_config())
    risk = load_risk_config()

    account = alpaca.get_account()
    nav = account["nav"]
    cash = account["cash"]
    day_pnl_pct = account["day_pnl_pct"]
    positions = alpaca.get_positions()

    # Guardrail checks
    breach = None
    for check_fn, label, value in [
        (lambda: check_daily_loss_cap(day_pnl_pct, risk), "Daily Loss Cap", f"{day_pnl_pct:.2%}"),
        (lambda: check_cash_floor(cash, nav, risk), "Cash Floor", f"{cash/nav:.1%}"),
    ]:
        result = check_fn()
        if not result.passed:
            breach = result
            break

    if breach:
        tg = TelegramClient(load_telegram_config())
        tg.send_guardrail_breach(breach.breach_type, str(breach.current_value), str(breach.limit))

    # ── 3. News Screen ─────────────────────────────────────────────────────
    tickers = [p["symbol"] for p in positions]
    watch_list = _parse_watch_list(mem["research_notes"])
    all_tickers = list(set(tickers + watch_list))
    news = research.screen_news(all_tickers) if all_tickers else "No tickers to screen."

    # ── 4. Compose Telegram Brief ───────────────────────────────────────────
    regime_line = regime.split("REGIME:")[-1].strip() if "REGIME:" in regime else "unknown"
    short_regime = "risk-on" if "risk-on" in regime_line else ("risk-off" if "risk-off" in regime_line else "neutral")

    today = _utc_now()[:10]
    msg = (
        f"📊 *PRE-MARKET BRIEF — {today}*\n"
        f"Regime: {short_regime.upper()}\n"
        f"Portfolio NAV: ${nav:,.0f} | Cash: {cash/nav:.0%}\n"
        f"Day P&L so far: {day_pnl_pct:+.2%}\n"
        f"Open positions: {len(positions)}\n\n"
        f"_Macro_: {macro[:300]}\n\n"
        f"_News_: {news[:400]}"
    )
    tg = TelegramClient(load_telegram_config())
    tg.send(msg)

    # ── 5. Write Memory ────────────────────────────────────────────────────
    updated_notes = mem["research_notes"]
    updated_notes += f"\n\n## Pre-Market — {today}\n\n**Macro:**\n{macro}\n\n**Regime:** {regime_line}\n\n**Sectors:**\n{sectors}\n\n**News:**\n{news}\n"
    write("research_notes.md", updated_notes)
    commit(f"chore: pre-market update {today}")
    logger.info("Pre-market routine complete.")


def _parse_watch_list(research_notes: str) -> list[str]:
    import re
    matches = re.findall(r"^\s*[-*]?\s*([A-Z]{2,5})\s", research_notes, re.MULTILINE)
    return [m.upper() for m in matches[:10]]


def _utc_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


if __name__ == "__main__":
    run()