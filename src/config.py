"""
Central configuration loader. All secrets come from environment variables only.
Never hardcode credentials here or anywhere else in the codebase.
"""

import os
from dataclasses import dataclass


@dataclass
class AlpacaConfig:
    api_key: str
    secret_key: str
    base_url: str
    is_paper: bool


@dataclass
class TelegramConfig:
    bot_token: str
    chat_id: str


@dataclass
class ResearchConfig:
    google_ai_studio_api_key: str


@dataclass
class RiskConfig:
    max_position_pct: float = 0.05          # 5% of NAV
    max_sector_pct: float = 0.25            # 25% of NAV
    daily_loss_cap_pct: float = -0.02       # -2% halts new buys
    max_drawdown_pct: float = -0.10        # -10% halts all trading
    hard_stop_pct: float = -0.07           # -7% from cost basis
    trailing_stop_pct: float = 0.10        # 10% trailing stop
    tight_trailing_stop_pct: float = 0.07  # 7% after +20% gain
    profit_trim_trigger_pct: float = 0.25  # trim at +25%
    min_cash_pct: float = 0.10              # always keep 10% cash
    min_market_cap: float = 500_000_000    # $500M
    min_daily_volume: float = 5_000_000    # $5M ADV


def load_alpaca_config() -> AlpacaConfig:
    api_key = os.environ["ALPACA_API_KEY"]
    secret_key = os.environ["ALPACA_SECRET_KEY"]
    base_url = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
    is_paper = "paper" in base_url
    return AlpacaConfig(api_key=api_key, secret_key=secret_key, base_url=base_url, is_paper=is_paper)


def load_telegram_config() -> TelegramConfig:
    return TelegramConfig(
        bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        chat_id=os.environ["TELEGRAM_CHAT_ID"],
    )


def load_research_config() -> ResearchConfig:
    return ResearchConfig(google_ai_studio_api_key=os.environ["GOOGLE_AI_STUDIO_API_KEY"])


def load_risk_config() -> RiskConfig:
    return RiskConfig()