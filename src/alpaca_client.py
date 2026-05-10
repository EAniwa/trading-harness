"""
Alpaca brokerage client — uses raw HTTP requests against the Alpaca REST API v2.
No SDK dependency; only `requests`. This avoids the deprecated alpaca-trade-api
package and any breaking-change issues with alpaca-py.

API docs: https://docs.alpaca.markets/reference/getaccount
"""

import logging
import time
from datetime import date, datetime, timezone
from math import floor
from typing import Optional

import requests

from .config import AlpacaConfig, RiskConfig

logger = logging.getLogger(__name__)


class AlpacaClient:
    DATA_URL = "https://data.alpaca.markets/v2"

    def __init__(self, config: AlpacaConfig, risk: RiskConfig):
        base = config.base_url.rstrip("/")
        if base.endswith("/v2"):
            base = base[:-3]
        self.base_url = base
        self.headers = {
            "APCA-API-KEY-ID": config.api_key,
            "APCA-API-SECRET-KEY": config.secret_key,
        }
        self.risk = risk
        self.is_paper = config.is_paper

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _req(self, method: str, url: str, **kwargs) -> dict:
        last_err = None
        for attempt in range(2):
            try:
                resp = requests.request(method, url, headers=self.headers, timeout=15, **kwargs)
                if resp.status_code in (200, 201, 204):
                    if resp.text:
                        return resp.json()
                    return {}
                last_err = f"{resp.status_code}: {resp.text}"
                logger.warning("Alpaca %s %s failed (attempt %d): %s", method, url, attempt + 1, last_err)
            except requests.RequestException as e:
                last_err = str(e)
                logger.warning("Alpaca request error (attempt %d): %s", attempt + 1, e)
            time.sleep(2)
        raise RuntimeError(f"Alpaca request failed: {last_err}")

    # ── Account ──────────────────────────────────────────────────────────────

    def get_account(self) -> dict:
        data = self._req("GET", f"{self.base_url}/v2/account")
        equity = float(data.get("equity", 0))
        last_equity = float(data.get("last_equity", equity))
        return {
            "nav": equity,
            "cash": float(data.get("cash", 0)),
            "buying_power": float(data.get("buying_power", 0)),
            "day_pnl": equity - last_equity,
            "day_pnl_pct": (equity - last_equity) / last_equity if last_equity else 0.0,
        }

    # ── Positions ─────────────────────────────────────────────────────────────

    def get_positions(self) -> list[dict]:
        data = self._req("GET", f"{self.base_url}/v2/positions")
        return [
            {
                "symbol": p["symbol"],
                "qty": int(float(p["qty"])),
                "avg_entry_price": float(p["avg_entry_price"]),
                "current_price": float(p.get("current_price", 0) or 0),
                "market_value": float(p["market_value"]),
                "unrealized_pl": float(p["unrealized_pl"]),
                "unrealized_plpc": float(p["unrealized_plpc"]),
                "cost_basis": float(p["cost_basis"]),
            }
            for p in data
        ]

    # ── Market Data ───────────────────────────────────────────────────────────

    def get_latest_price(self, symbol: str) -> Optional[float]:
        try:
            data = self._req("GET", f"{self.DATA_URL}/stocks/{symbol}/trades/latest")
            return float(data["trade"]["p"])
        except Exception as e:
            logger.warning("Latest price unavailable for %s: %s", symbol, e)
            try:
                data = self._req("GET", f"{self.DATA_URL}/stocks/{symbol}/quotes/latest")
                return float(data["quote"]["ap"]) or float(data["quote"]["bp"])
            except Exception:
                return None

    def get_daily_return(self, symbol: str) -> Optional[float]:
        try:
            data = self._req(
                "GET",
                f"{self.DATA_URL}/stocks/{symbol}/bars",
                params={"timeframe": "1Day", "limit": 2},
            )
            bars = data.get("bars", [])
            if len(bars) < 2:
                return None
            prev_close = float(bars[-2]["c"])
            last_close = float(bars[-1]["c"])
            return (last_close - prev_close) / prev_close
        except Exception as e:
            logger.warning("Daily return unavailable for %s: %s", symbol, e)
            return None

    # ── Orders ────────────────────────────────────────────────────────────────

    def calculate_shares(self, symbol: str, nav: float, conviction: float) -> int:
        position_dollars = min(conviction * 0.02 * nav, self.risk.max_position_pct * nav)
        price = self.get_latest_price(symbol)
        if not price:
            return 0
        return floor(position_dollars / price)

    def submit_market_buy(self, symbol: str, qty: int) -> Optional[dict]:
        if qty <= 0:
            return None
        try:
            order = self._req(
                "POST",
                f"{self.base_url}/v2/orders",
                json={
                    "symbol": symbol,
                    "qty": str(qty),
                    "side": "buy",
                    "type": "market",
                    "time_in_force": "day",
                },
            )
            return {"id": order["id"], "symbol": symbol, "qty": qty, "status": order["status"]}
        except Exception as e:
            logger.error("Buy order failed for %s: %s", symbol, e)
            return {"error": str(e), "symbol": symbol}

    def submit_market_sell(self, symbol: str, qty: int) -> Optional[dict]:
        if qty <= 0:
            return None
        try:
            order = self._req(
                "POST",
                f"{self.base_url}/v2/orders",
                json={
                    "symbol": symbol,
                    "qty": str(qty),
                    "side": "sell",
                    "type": "market",
                    "time_in_force": "day",
                },
            )
            return {"id": order["id"], "symbol": symbol, "qty": qty, "status": order["status"]}
        except Exception as e:
            logger.error("Sell order failed for %s: %s", symbol, e)
            return {"error": str(e), "symbol": symbol}

    def list_open_orders(self, symbol: Optional[str] = None) -> list[dict]:
        params = {"status": "open"}
        if symbol:
            params["symbols"] = symbol
        return self._req("GET", f"{self.base_url}/v2/orders", params=params)

    def cancel_order(self, order_id: str) -> None:
        try:
            self._req("DELETE", f"{self.base_url}/v2/orders/{order_id}")
        except Exception as e:
            logger.warning("Cancel order %s failed: %s", order_id, e)

    def set_trailing_stop(self, symbol: str, trail_percent: float) -> Optional[dict]:
        try:
            existing = self.list_open_orders(symbol=symbol)
            for o in existing:
                if o.get("type") in ("trailing_stop", "stop", "stop_limit"):
                    self.cancel_order(o["id"])
        except Exception:
            pass

        try:
            pos = self._req("GET", f"{self.base_url}/v2/positions/{symbol}")
            qty = int(float(pos["qty"]))
        except Exception:
            return None

        try:
            order = self._req(
                "POST",
                f"{self.base_url}/v2/orders",
                json={
                    "symbol": symbol,
                    "qty": str(qty),
                    "side": "sell",
                    "type": "trailing_stop",
                    "trail_percent": str(trail_percent),
                    "time_in_force": "gtc",
                },
            )
            return {"id": order["id"], "symbol": symbol, "trail_percent": trail_percent}
        except Exception as e:
            logger.error("Trailing stop failed for %s: %s", symbol, e)
            return {"error": str(e)}

    # ── Market Clock ──────────────────────────────────────────────────────────

    def is_market_open(self) -> bool:
        try:
            data = self._req("GET", f"{self.base_url}/v2/clock")
            return bool(data.get("is_open"))
        except Exception:
            return False

    def wait_for_market_open(self, max_wait_seconds: int = 3600) -> bool:
        try:
            data = self._req("GET", f"{self.base_url}/v2/clock")
        except Exception:
            return False
        if data.get("is_open"):
            return True
        next_open = data.get("next_open")
        timestamp = data.get("timestamp")
        if not next_open or not timestamp:
            return False
        no = datetime.fromisoformat(next_open.replace("Z", "+00:00"))
        ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        wait = (no - ts).total_seconds()
        if wait > max_wait_seconds:
            logger.warning("Market opens in %.0f seconds — exceeds wait budget %d", wait, max_wait_seconds)
            return False
        logger.info("Waiting %.0f seconds for market open...", wait)
        time.sleep(min(max(wait + 5, 0), max_wait_seconds))
        return self.is_market_open()

    # ── Order History ────────────────────────────────────────────────────────

    def get_todays_filled_orders(self) -> list[dict]:
        today = date.today().isoformat()
        data = self._req(
            "GET",
            f"{self.base_url}/v2/orders",
            params={"status": "filled", "after": f"{today}T00:00:00Z", "limit": 100},
        )
        return [
            {
                "id": o["id"],
                "symbol": o["symbol"],
                "side": o["side"],
                "qty": int(float(o.get("filled_qty", 0))),
                "fill_price": float(o.get("filled_avg_price") or 0),
                "submitted_at": o.get("submitted_at"),
                "filled_at": o.get("filled_at"),
            }
            for o in data
            if float(o.get("filled_qty", 0)) > 0
        ]