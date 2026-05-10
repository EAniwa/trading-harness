"""
Research client for Google AI Studio (Gemini) using raw HTTP requests.
No SDK dependency. Uses the gemini-2.0-flash REST endpoint.
"""

import logging
import time
from typing import Optional

import requests

from .config import ResearchConfig

logger = logging.getLogger(__name__)

MODEL = "gemini-2.0-flash"
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class ResearchClient:
    def __init__(self, config: ResearchConfig):
        self.api_key = config.google_ai_studio_api_key
        self.url = ENDPOINT.format(model=MODEL)

    def _query(self, prompt: str, system: str = "") -> str:
        full = f"{system}\n\n{prompt}" if system else prompt
        body = {"contents": [{"parts": [{"text": full}]}]}
        params = {"key": self.api_key}
        for attempt in range(2):
            try:
                resp = requests.post(self.url, params=params, json=body, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "")
                    return "[empty response from Gemini]"
                logger.warning("Gemini error (attempt %d): %s %s", attempt + 1, resp.status_code, resp.text[:200])
            except requests.RequestException as e:
                logger.warning("Gemini request failed (attempt %d): %s", attempt + 1, e)
            time.sleep(2)
        return "[Gemini API unreachable]"

    def get_macro_pulse(self) -> str:
        return self._query(
            "Provide a concise pre-market macro brief for today including: "
            "S&P 500 and NASDAQ futures levels, VIX estimate, 10Y-2Y yield curve spread, "
            "any Federal Reserve commentary in the last 24 hours, and the 3 most important "
            "economic data releases scheduled for today. Be factual and data-driven. "
            "Format as a structured brief under 300 words.",
            system="You are a professional macro analyst. Be precise, factual, and concise.",
        )

    def screen_news(self, tickers: list[str]) -> str:
        ticker_str = ", ".join(tickers)
        return self._query(
            f"Search for the most important news from the past 24 hours for these stocks: {ticker_str}. "
            "For each stock with notable news, summarize: (1) what happened, (2) bullish/bearish/neutral, "
            "(3) impact on the investment thesis. Focus on material events: earnings, guidance, M&A, regulatory, "
            "management changes, analyst rating changes with price targets.",
            system="You are a buy-side equity research analyst. Be analytical and concise.",
        )

    def deep_fundamental_analysis(self, ticker: str, company_name: str = "", context: str = "") -> str:
        return self._query(
            f"Conduct a deep fundamental analysis of {ticker} ({company_name}). "
            f"Additional context: {context}\n\n"
            "Analyze: revenue quality and growth drivers, margin trajectory and FCF, "
            "balance sheet, competitive moat, valuation vs peers (P/E, EV/EBITDA), key risks. "
            "Write a structured thesis with bull case, bear case, intrinsic value range. "
            "Conclude with: Buy / Watch / Pass.",
            system="You are a fundamental equity analyst. Be rigorous and data-driven.",
        )

    def get_earnings_calendar(self, days_ahead: int = 1) -> str:
        return self._query(
            f"List S&P 500 and NASDAQ-100 companies reporting earnings in the next {days_ahead} trading day(s). "
            "Include: ticker, company name, BMO/AMC, consensus EPS, consensus revenue. "
            "Flag high-impact reports.",
            system="You are a financial data aggregator. Be precise and complete.",
        )

    def get_sector_performance(self) -> str:
        return self._query(
            "Provide 1-month and 1-week performance for sector ETFs: XLK, XLV, XLF, XLE, XLY, XLU, XLI. "
            "Rank best to worst. Note key driver for top and bottom sector.",
            system="You are a sector rotation analyst. Be precise with data.",
        )

    def assess_market_regime(self) -> str:
        return self._query(
            "Assess the current stock market regime as: risk-on, neutral, or risk-off. "
            "Consider: S&P 500 vs 50/200-day MAs, VIX, credit spreads, breadth, yield curve. "
            "Explain in 150 words. End with one line: REGIME: [risk-on / neutral / risk-off]",
            system="You are a quantitative market strategist.",
        )

    def synthesize_week(self, trade_log_excerpt: str, learnings_excerpt: str) -> str:
        return self._query(
            f"Based on the following trade log and learnings from this week, "
            f"provide a 200-word synthesis of: (1) what went well, (2) what went poorly, "
            f"(3) the single most important lesson, (4) one concrete improvement for next week.\n\n"
            f"Trade log:\n{trade_log_excerpt}\n\nLearnings:\n{learnings_excerpt}",
            system="You are a systematic trading coach.",
        )