#!/usr/bin/env python3
"""
Routine: Weekly Review
Runs: 4:00 PM ET, Friday
Purpose: Full portfolio review, synthesize the week, adjust strategy, send summary.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.config import load_alpaca_config, load_telegram_config, load_risk_config
from src.research_client import ResearchClient
from src.config import load_research_config
from src.alpaca_client import AlpacaClient
from src.telegram_client import TelegramClient
from src.memory_manager import read, write, load_all, commit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run():
    logger.info("=== WEEKLY REVIEW ===")
    mem = load_all()
    risk = load_risk_config()

    alpaca = AlpacaClient(load_alpaca_config(), risk)
    research = ResearchClient(load_research_config())
    tg = TelegramClient(load_telegram_config())

    account = alpaca.get_account()
    nav = account["nav"]
    positions = alpaca.get_positions()

    # ── Weekly synthesis ───────────────────────────────────────────────────
    synthesis = research.synthesize_week(
        mem["trade_log"][-1500:],
        mem["learnings"][-1000:],
    )

    # ── Positions review ───────────────────────────────────────────────────
    position_lines = []
    for p in sorted(positions, key=lambda x: x["unrealized_plpc"], reverse=True):
        status = "🟢" if p["unrealized_plpc"] > 0 else "🔴"
        position_lines.append(
            f"{status} {p['symbol']}: {p['qty']} shares | Entry: ${p['avg_entry_price']:.2f} | "
            f"Current: ${p['current_price']:.2f} | {p['unrealized_plpc']:+.2%} (${p['unrealized_pl']:+.0f})"
        )

    # ── Compose Weekly Summary ─────────────────────────────────────────────
    lines = [
        f"📅 *WEEKLY REVIEW — {_week()}. Weekly analysis from AI:*{research.assess_market_regime()[:200]}",
        f"Portfolio NAV: ${nav:,.0f} | Positions: {len(positions)}",
        f"**This week:**\n{synthesis[:400]}",
        "**Positions:**",
    ]
    lines.extend(position_lines[:8])
    tg.send("\n".join(lines))

    # ── Update learnings ───────────────────────────────────────────────────
    learnings = mem["learnings"]
    learnings += f"\n\n## Weekly Review — {_week()}\n\n{synthesis}\n"
    write("learnings.md", learnings)

    commit(f"chore: weekly review {_week()}")
    logger.info("Weekly review complete.")


def _week():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


if __name__ == "__main__":
    run()