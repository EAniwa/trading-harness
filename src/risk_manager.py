"""
Risk management layer. All guardrail checks live here.
Returns structured results so callers can decide what action to take.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from .config import RiskConfig

logger = logging.getLogger(__name__)


@dataclass
class RiskCheckResult:
    passed: bool
    breach_type: Optional[str]
    current_value: Optional[float]
    limit: Optional[float]
    message: str


def check_position_size(
    proposed_dollars: float, nav: float, risk: RiskConfig
) -> RiskCheckResult:
    pct = proposed_dollars / nav
    if pct > risk.max_position_pct:
        return RiskCheckResult(
            passed=False,
            breach_type="max_position_size",
            current_value=pct,
            limit=risk.max_position_pct,
            message=f"Position {pct:.1%} exceeds max {risk.max_position_pct:.0%}",
        )
    return RiskCheckResult(passed=True, breach_type=None, current_value=pct, limit=risk.max_position_pct, message="OK")


def check_daily_loss_cap(day_pnl_pct: float, risk: RiskConfig) -> RiskCheckResult:
    if day_pnl_pct <= -risk.daily_loss_cap_pct:
        return RiskCheckResult(
            passed=False,
            breach_type="daily_loss_cap",
            current_value=day_pnl_pct,
            limit=-risk.daily_loss_cap_pct,
            message=f"Daily P&L {day_pnl_pct:.2%} hit loss cap -{risk.daily_loss_cap_pct:.0%}",
        )
    return RiskCheckResult(passed=True, breach_type=None, current_value=day_pnl_pct, limit=-risk.daily_loss_cap_pct, message="OK")


def check_max_drawdown(current_nav: float, peak_nav: float, risk: RiskConfig) -> RiskCheckResult:
    if peak_nav <= 0:
        return RiskCheckResult(passed=True, breach_type=None, current_value=0, limit=None, message="OK")
    drawdown = (peak_nav - current_nav) / peak_nav
    if drawdown >= risk.max_drawdown_pct:
        return RiskCheckResult(
            passed=False,
            breach_type="max_drawdown",
            current_value=-drawdown,
            limit=-risk.max_drawdown_pct,
            message=f"Drawdown {drawdown:.2%} exceeds max {risk.max_drawdown_pct:.0%}",
        )
    return RiskCheckResult(passed=True, breach_type=None, current_value=-drawdown, limit=-risk.max_drawdown_pct, message="OK")


def check_sector_concentration(
    sector_dollars: float, nav: float, risk: RiskConfig
) -> RiskCheckResult:
    pct = sector_dollars / nav
    if pct > risk.max_sector_pct:
        return RiskCheckResult(
            passed=False,
            breach_type="sector_concentration",
            current_value=pct,
            limit=risk.max_sector_pct,
            message=f"Sector exposure {pct:.1%} exceeds max {risk.max_sector_pct:.0%}",
        )
    return RiskCheckResult(passed=True, breach_type=None, current_value=pct, limit=risk.max_sector_pct, message="OK")


def check_cash_floor(cash: float, nav: float, risk: RiskConfig) -> RiskCheckResult:
    cash_pct = cash / nav
    if cash_pct < risk.min_cash_pct:
        return RiskCheckResult(
            passed=False,
            breach_type="cash_floor",
            current_value=cash_pct,
            limit=risk.min_cash_pct,
            message=f"Cash {cash_pct:.1%} below minimum {risk.min_cash_pct:.0%}",
        )
    return RiskCheckResult(passed=True, breach_type=None, current_value=cash_pct, limit=risk.min_cash_pct, message="OK")


def is_instrument_allowed(symbol: str) -> tuple[bool, str]:
    symbol = symbol.upper()
    forbidden_patterns = ["SQQQ", "TQQQ", "SPXU", "SPXS", "UVXY", "SVXY", "LABD", "LABU", "TZA", "TNA"]
    if symbol in forbidden_patterns:
        return False, f"{symbol} is a leveraged/inverse ETF — forbidden"
    return True, "OK"


def calculate_trailing_stop_pct(unrealized_plpc: float, risk: RiskConfig) -> float:
    if unrealized_plpc >= 0.20:
        return risk.tight_trailing_stop_pct
    return risk.trailing_stop_pct