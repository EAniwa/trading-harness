"""
Telegram notification client.
Sends trade alerts and daily summaries to the configured chat.
"""

import logging
import time
from typing import Optional

import requests

from .config import TelegramConfig

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramClient:
    def __init__(self, config: TelegramConfig):
        self.bot_token = config.bot_token
        self.chat_id = config.chat_id

    def send(self, message: str, parse_mode: str = "Markdown") -> bool:
        url = TELEGRAM_API.format(token=self.bot_token)
        payload = {"chat_id": self.chat_id, "text": message, "parse_mode": parse_mode}
        for attempt in range(3):
            try:
                resp = requests.post(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    return True
                logger.warning("Telegram send failed (attempt %d): %s", attempt + 1, resp.text)
            except requests.RequestException as e:
                logger.error("Telegram request error (attempt %d): %s", attempt + 1, e)
            time.sleep(2)
        return False

    def send_urgent(self, message: str) -> bool:
        return self.send(f"🚨 *URGENT ALERT*\n\n{message}")

    def send_trade_alert(
        self,
        side: str,
        symbol: str,
        qty: int,
        price: float,
        position_pct: float,
        thesis: str,
        stop_price: Optional[float] = None,
    ) -> bool:
        icon = "🟢" if side.lower() == "buy" else "🔴"
        side_label = "BUYING" if side.lower() == "buy" else "SELLING"
        lines = [
            f"{icon} *{side_label} {symbol}*",
            f"Shares: {qty} @ ~${price:.2f}",
            f"Position size: {position_pct:.1%} of NAV",
            f"Thesis: _{thesis}_",
        ]
        if stop_price:
            lines.append(f"Stop: ${stop_price:.2f}")
        return self.send("\n".join(lines))

    def send_guardrail_breach(self, rule: str, current_value: str, limit: str) -> bool:
        return self.send_urgent(
            f"*Guardrail breached:* {rule}\n"
            f"Current: `{current_value}` | Limit: `{limit}`\n"
            f"All new orders halted. Human review required."
        )