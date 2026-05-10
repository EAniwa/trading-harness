# Trading Harness

Autonomous fundamentals-driven trading agent. Beats S&P 500 on a rolling 12-month basis through concentrated, high-conviction equity positions backed by rigorous fundamental analysis.

## Architecture

```
trading-harness/
├── src/
│   ├── alpaca_client.py     # Alpaca brokerage API client
│   ├── research_client.py   # Google Gemini research API
│   ├── risk_manager.py     # Guardrails and position checks
│   ├── telegram_client.py   # Alert bot
│   ├── memory_manager.py    # Persistent memory file I/O
│   └── config.py            # Environment variable loader
├── run_premarket.py         # 6:00 AM ET — research, no orders
├── run_market_open.py       # 8:30 AM ET — execute after 9:30 AM
├── run_midday.py            # 12:00 PM ET — monitor & adjust stops
├── run_market_close.py      # 3:00 PM ET — journal & P&L
├── run_weekly_review.py     # Friday 4:00 PM ET — full review
├── memory/
│   ├── strategy.md          # Guardrails and rules
│   ├── learnings.md         # Post-mortems and lessons
│   ├── trade_log.md         # All trades and P&L
│   └── research_notes.md    # Watch list, macro, research
├── CLAUDE.md                # Full operating manual
└── requirements.txt         # dependencies
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in all API keys in .env
```

## Run a Routine

```bash
python run_premarket.py
python run_market_open.py
python run_midday.py
python run_market_close.py
python run_weekly_review.py
```

## Schedule with Cron

```bash
# Pre-market — 6:00 AM ET Mon–Fri
0 6 * * 1-5 cd /path/to/trading-harness && python run_premarket.py

# Market open — 8:30 AM ET Mon–Fri
30 8 * * 1-5 cd /path/to/trading-harness && python run_market_open.py

# Midday — 12:00 PM ET Mon–Fri
0 12 * * 1-5 cd /path/to/trading-harness && python run_midday.py

# Market close — 3:00 PM ET Mon–Fri
0 15 * * 1-5 cd /path/to/trading-harness && python run_market_close.py

# Weekly review — 4:00 PM ET Friday
0 16 * * 5 cd /path/to/trading-harness && python run_weekly_review.py
```

## Guardrails

| Rule | Limit |
|------|-------|
| Max position | 5% of NAV |
| Max sector | 25% of NAV |
| Daily loss cap | -2% halts new buys |
| Max drawdown | -10% halts all trading |
| Min cash | 10% always |
| Allowed | Equities + ETFs only |
| Forbidden | Options, futures, crypto, leveraged ETFs, stocks < $5 |

## APIs Required

- **Alpaca** — brokerage (paper or live)
- **Google AI Studio** — Gemini for research and news
- **Telegram Bot** — alerts and summaries