#!/usr/bin/env python3
"""
Utility: validate all API credentials and connections.
Run with: python3 scripts/validate.py
"""
import os
from pathlib import Path

# Load .env if it exists
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from src.config import load_research_config, load_alpaca_config, load_telegram_config, load_risk_config
from src.research_client import ResearchClient
from src.alpaca_client import AlpacaClient
from src.telegram_client import TelegramClient


def main():
    print("=" * 50)
    print("TRADING HARNESS — VALIDATION")
    print("=" * 50)

    # Config
    r_cfg = load_research_config()
    a_cfg = load_alpaca_config()
    t_cfg = load_telegram_config()
    print(f"\n[CONFIG] DeepSeek model: {r_cfg.deepseek_model}")
    print(f"[CONFIG] DeepSeek reasoning: {r_cfg.deepseek_reasoning_model}")
    print(f"[CONFIG] Alpaca: {'PAPER' if a_cfg.is_paper else 'LIVE'} @ {a_cfg.base_url}")

    # DeepSeek
    print("\n[DEEPSEEK] Testing...")
    rc = ResearchClient(r_cfg)
    pulse = rc.get_macro_pulse()
    print(f"[DEEPSEEK] ✓ get_macro_pulse OK ({len(pulse)} chars)")
    regime = rc.assess_market_regime()
    print(f"[DEEPSEEK] ✓ assess_market_regime OK: {regime[:80]}...")

    # Alpaca
    print("\n[ALPACA] Testing...")
    ac = AlpacaClient(a_cfg, load_risk_config())
    acct = ac.get_account()
    print(f"[ALPACA] ✓ account OK — NAV: ${acct['nav']:,.0f} | Cash: ${acct['cash']:,.0f}")
    positions = ac.get_positions()
    print(f"[ALPACA] ✓ positions OK — {len(positions)} open")
    price = ac.get_latest_price("AAPL")
    print(f"[ALPACA] ✓ latest price AAPL: ${price}")

    # Telegram
    print("\n[TELEGRAM] Testing...")
    tc = TelegramClient(t_cfg)
    ok = tc.send("✅ Trading harness validation passed")
    print(f"[TELEGRAM] ✓ send message: {ok}")

    print("\n" + "=" * 50)
    print("ALL SYSTEMS OPERATIONAL")
    print("=" * 50)


if __name__ == "__main__":
    main()