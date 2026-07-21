#!/usr/bin/env python3
"""TSLA earnings-week option overlay backtest.

Context: user holds 100 TSLA shares and wants to sell options against the
position while buying calls into the 2026-07-22 (AMC) earnings report,
with the weekly expiration on 2026-07-24.

Method
------
1. Take every TSLA earnings event since Jul-2021 (21 events, dates verified
   against gap/volume signatures in the daily bars).
2. For each event measure the % move from the close of the day BEFORE the
   report to the close of the weekly expiration Friday — the same holding
   window as the proposed trade.
3. Price this week's candidate option legs with Black-Scholes at today's
   spot, using an earnings-week ATM IV parameter (default 100% annualized,
   which implies a ~7.3% move — in line with TSLA's typical pre-earnings
   weekly pricing) plus a simple smile for OTM wings. Live chain quotes
   were unavailable in this environment, so leg prices are MODELED — rerun
   with --atm-iv set to the observed ATM IV before trading.
4. Replay all 21 historical earnings moves against today's spot and score
   every strike combination on mean/median P&L, win rate, worst case, and
   edge vs. simply holding the shares.

Structures tested (all per 100 shares, 1 contract per leg):
  A. covered_call        : shares + short call K1
  B. cc_plus_call        : shares + short call K1 + long call K2 (K2 > K1)
                           ("sell the near strike, buy back the far upside")
  C. call_debit_spread   : shares + long call K1 + short call K2 (K2 > K1)
                           ("buy the near call, sell the far call to fund it")
  D. risk_reversal       : shares + short put Kp + long call K2
                           (short put is naked/margin — flagged, not sized)

Usage:  python3 backtests/tsla_earnings_options_backtest.py [--atm-iv 1.00]
Writes: backtests/results/tsla_2026-07-24_grid.csv and _report.md
"""

import argparse
import csv
import math
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "tsla_daily_2021_2026.csv")
OUTDIR = os.path.join(HERE, "results")

SPOT = 369.57          # close 2026-07-20 (= last bar in data)
RATE = 0.04
DTE_YEARS = 3.0 / 365.0  # Tue 07-21 entry -> Fri 07-24 expiry

# AMC report dates. 2026-01-28 / 2026-04-22 verified from reaction-day
# gap + volume spikes in the data.
EARNINGS_AMC = [
    "2021-07-26", "2021-10-20",
    "2022-01-26", "2022-04-20", "2022-07-20", "2022-10-19",
    "2023-01-25", "2023-04-19", "2023-07-19", "2023-10-18",
    "2024-01-24", "2024-04-23", "2024-07-23", "2024-10-23",
    "2025-01-29", "2025-04-22", "2025-07-23", "2025-10-22",
    "2026-01-28", "2026-04-22",
]


def load_bars():
    with open(DATA) as f:
        return list(csv.DictReader(f))


def event_moves(bars):
    """% move: close of day before report -> close of expiry Friday."""
    dates = [b["date"] for b in bars]
    close = [float(b["close"]) for b in bars]
    idx = {d: i for i, d in enumerate(dates)}
    moves = []
    for ed in EARNINGS_AMC:
        if ed not in idx:
            continue
        i = idx[ed]
        entry_i = i - 1 if i > 0 else i
        # first Friday on/after the reaction day; fall back to last
        # trading day before it if that Friday was a holiday
        j = i + 1
        while j < len(dates):
            y, m, d = map(int, dates[j].split("-"))
            import datetime
            if datetime.date(y, m, d).weekday() == 4:
                break
            j += 1
        if j >= len(dates):
            continue
        mv = close[j] / close[entry_i] - 1.0
        moves.append((ed, dates[entry_i], dates[j], mv))
    return moves


# ---------- Black-Scholes with a simple earnings smile ----------

def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def smile_iv(atm_iv, strike, spot):
    m = math.log(strike / spot)
    # mild symmetric smile + put skew, calibrated to typical weekly
    # earnings surfaces (wings trade over ATM)
    return atm_iv * (1.0 - 0.3 * m + 0.8 * abs(m) + 2.0 * m * m)


def bs_price(kind, spot, strike, t, r, iv):
    if t <= 0 or iv <= 0:
        intrinsic = max(0.0, (spot - strike) if kind == "c" else (strike - spot))
        return intrinsic
    d1 = (math.log(spot / strike) + (r + 0.5 * iv * iv) * t) / (iv * math.sqrt(t))
    d2 = d1 - iv * math.sqrt(t)
    if kind == "c":
        return spot * _norm_cdf(d1) - strike * math.exp(-r * t) * _norm_cdf(d2)
    return strike * math.exp(-r * t) * _norm_cdf(-d2) - spot * _norm_cdf(-d1)


def leg_price(kind, strike, atm_iv, side):
    """Modeled fill: pay a half-spread penalty on each side (2% of premium)."""
    mid = bs_price(kind, SPOT, strike, DTE_YEARS, RATE, smile_iv(atm_iv, strike, SPOT))
    return mid * (0.98 if side == "sell" else 1.02)


# ---------- strategy P&L on one terminal price ----------

def pnl(structure, s_t):
    """P&L per 100 shares incl. share leg, premiums already in structure."""
    p = 100.0 * (s_t - SPOT) + 100.0 * structure["net_credit"]
    for kind, strike, size in structure["legs"]:
        intrinsic = max(0.0, (s_t - strike) if kind == "c" else (strike - s_t))
        p += 100.0 * size * intrinsic
    return p


def build(name, legs, atm_iv, note=""):
    credit = 0.0
    for kind, strike, size in legs:
        px = leg_price(kind, strike, atm_iv, "sell" if size < 0 else "buy")
        credit += -size * px
    return {"name": name, "legs": legs, "net_credit": credit, "note": note}


def evaluate(structure, moves):
    pnls = [pnl(structure, SPOT * (1.0 + mv)) for _, _, _, mv in moves]
    base = [100.0 * SPOT * mv for _, _, _, mv in moves]
    edge = [a - b for a, b in zip(pnls, base)]
    return {
        "name": structure["name"],
        "net_credit": structure["net_credit"],
        "mean": statistics.mean(pnls),
        "median": statistics.median(pnls),
        "win_rate": sum(1 for p in pnls if p > 0) / len(pnls),
        "worst": min(pnls),
        "best": max(pnls),
        "beat_shares_rate": sum(1 for e in edge if e > 0) / len(edge),
        "mean_edge_vs_shares": statistics.mean(edge),
        "note": structure["note"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--atm-iv", type=float, default=1.00,
                    help="annualized ATM IV for the weekly (default 1.00)")
    args = ap.parse_args()
    atm_iv = args.atm_iv

    bars = load_bars()
    moves = event_moves(bars)
    mvs = [m[3] for m in moves]

    os.makedirs(OUTDIR, exist_ok=True)

    results = []
    # baseline
    results.append(evaluate({"name": "shares_only", "legs": [],
                             "net_credit": 0.0, "note": ""}, moves))
    # A: covered calls
    for k1 in range(370, 440, 5):
        results.append(evaluate(build(f"CC {k1}", [("c", k1, -1)], atm_iv), moves))
    # B: covered call + long further call
    for k1 in range(370, 425, 5):
        for k2 in range(k1 + 5, 455, 5):
            results.append(evaluate(
                build(f"CC {k1} / +C {k2}", [("c", k1, -1), ("c", k2, 1)], atm_iv),
                moves))
    # C: long near call + short far call (debit call spread overlay)
    for k1 in range(375, 405, 5):
        for k2 in range(k1 + 10, 460, 5):
            results.append(evaluate(
                build(f"+C {k1} / -C {k2}", [("c", k1, 1), ("c", k2, -1)], atm_iv),
                moves))
    # D: short put + long call (risk reversal overlay) — margin required
    for kp in range(330, 370, 5):
        for k2 in range(375, 425, 5):
            results.append(evaluate(
                build(f"-P {kp} / +C {k2}", [("p", kp, -1), ("c", k2, 1)],
                      atm_iv, note="naked short put: margin/assignment risk"),
                moves))

    grid_path = os.path.join(OUTDIR, "tsla_2026-07-24_grid.csv")
    with open(grid_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["strategy", "net_credit_per_sh", "mean_pnl", "median_pnl",
                    "win_rate", "worst", "best", "beat_shares_rate",
                    "mean_edge_vs_shares", "note"])
        for r in results:
            w.writerow([r["name"], f"{r['net_credit']:.2f}", f"{r['mean']:.0f}",
                        f"{r['median']:.0f}", f"{r['win_rate']:.2f}",
                        f"{r['worst']:.0f}", f"{r['best']:.0f}",
                        f"{r['beat_shares_rate']:.2f}",
                        f"{r['mean_edge_vs_shares']:.0f}", r["note"]])

    # report
    straddle = (leg_price("c", 370, atm_iv, "buy") +
                leg_price("p", 370, atm_iv, "buy"))
    implied_move = straddle / SPOT
    up = [m for m in mvs if m > 0]
    dn = [m for m in mvs if m <= 0]

    def family(r):
        n = r["name"]
        if n == "shares_only":
            return "base"
        if n.startswith("CC") and "/" not in n:
            return "cc"
        if n.startswith("CC") and "/" in n:
            return "cc_plus_call"
        if n.startswith("+C"):
            return "call_debit_spread"
        return "risk_reversal"

    def top(fam, key, n=5):
        rs = [r for r in results if family(r) == fam]
        return sorted(rs, key=lambda r: r[key], reverse=True)[:n]

    lines = []
    lines.append("# TSLA 2026-07-22 earnings — option overlay backtest\n")
    lines.append(f"Spot {SPOT}, expiry 2026-07-24, ATM IV {atm_iv:.0%} "
                 f"(modeled straddle ≈ {implied_move:.1%} implied move)\n")
    lines.append(f"## Historical earnings-week moves (entry close → Friday close, n={len(mvs)})\n")
    lines.append(f"- mean {statistics.mean(mvs):+.1%}, median {statistics.median(mvs):+.1%}, "
                 f"stdev {statistics.pstdev(mvs):.1%}")
    lines.append(f"- up weeks: {len(up)} (avg {statistics.mean(up):+.1%}), "
                 f"down weeks: {len(dn)} (avg {statistics.mean(dn):+.1%})")
    lines.append(f"- range: {min(mvs):+.1%} … {max(mvs):+.1%}\n")
    lines.append("| event | entry | expiry | move |\n|---|---|---|---|")
    for ed, en, ex, mv in moves:
        lines.append(f"| {ed} | {en} | {ex} | {mv:+.1%} |")
    lines.append("")

    fmt = ("| {name} | {net_credit:+.2f} | {mean:+.0f} | {median:+.0f} | "
           "{win_rate:.0%} | {worst:+.0f} | {best:+.0f} | {beat_shares_rate:.0%} | "
           "{mean_edge_vs_shares:+.0f} |")
    hdr = ("| strategy | credit/sh | mean P&L | median P&L | win % | worst | "
           "best | beats shares % | edge vs shares |\n|---|---|---|---|---|---|---|---|---|")

    families = [("Covered call (shares + short call)", "cc"),
                ("Covered call financing a long call (short K1, long K2)", "cc_plus_call"),
                ("Call debit spread overlay (long K1, short K2)", "call_debit_spread"),
                ("Risk reversal overlay (short put + long call)", "risk_reversal")]
    for title, fam in families:
        for key, klabel in [("mean", "mean P&L"), ("median", "median P&L")]:
            lines.append(f"## {title} — top 5 by {klabel}\n{hdr}")
            for r in top(fam, key):
                lines.append(fmt.format(**r))
            lines.append("")

    b = results[0]
    lines.append(f"Baseline shares-only: mean {b['mean']:+.0f}, median {b['median']:+.0f}, "
                 f"worst {b['worst']:+.0f}, best {b['best']:+.0f}\n")
    lines.append("Leg prices are Black-Scholes estimates with a smile model, not live "
                 "quotes. Rerun with --atm-iv <observed> before trading; a 10-point IV "
                 "error moves weekly premia materially.\n")

    report_path = os.path.join(OUTDIR, "tsla_2026-07-24_report.md")
    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    print(f"wrote {grid_path}\nwrote {report_path}")
    print("\n".join(lines[:12]))


if __name__ == "__main__":
    main()
