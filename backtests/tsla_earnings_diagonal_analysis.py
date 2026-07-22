#!/usr/bin/env python3
"""TSLA earnings-day diagonal analysis (2026-07-22, report AMC today).

Proposed trade, entered at today's close BEFORE the print, on top of 100 shares:
  - SELL 1x 400C expiring >= 2 weeks out (tested: 2026-08-07 ~16d, 2026-08-14 ~23d)
  - BUY  1x call expiring next Friday 2026-07-31 (~9d), strike gridded

Why this needs its own model: entering on report day means the long leg is
bought at peak event IV and lives through the post-print IV crush, while the
short leg collects a smaller IV premium over a longer window. Leg entry
prices therefore use an event-vol decomposition:

    iv_entry(T)^2 = base_iv^2 + event_move^2 / T

with base_iv = 55% (TSLA's typical non-event level) and event_move = 8%
(one-sigma overnight print move, consistent with the ~7% straddle). After
the print the surface reverts to base_iv. Legs held to their own expiry
settle at intrinsic against the ACTUAL historical path (9-day and 16/23-day
moves measured from each report-day close). All 20 events since Jul-2021.

Outputs: results/tsla_2026-07-22_diagonal_report.md (+ grid CSV).
Run:     python3 backtests/tsla_earnings_diagonal_analysis.py
"""

import csv
import datetime
import math
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "tsla_daily_2021_2026.csv")
OUTDIR = os.path.join(HERE, "results")

SPOT = 375.84            # intraday 2026-07-22, pre-print
RATE = 0.04
BASE_IV = 0.55
EVENT_MOVE = 0.08        # 1-sigma overnight event move (log)
T_LONG = 9 / 365.0       # 2026-07-31
T_SHORT_A = 16 / 365.0   # 2026-08-07
T_SHORT_B = 23 / 365.0   # 2026-08-14
SHORT_K = 400.0

EARNINGS_AMC = [
    "2021-07-26", "2021-10-20",
    "2022-01-26", "2022-04-20", "2022-07-20", "2022-10-19",
    "2023-01-25", "2023-04-19", "2023-07-19", "2023-10-18",
    "2024-01-24", "2024-04-23", "2024-07-23", "2024-10-23",
    "2025-01-29", "2025-04-22", "2025-07-23", "2025-10-22",
    "2026-01-28", "2026-04-22",
]


def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs(kind, s, k, t, r, iv):
    if t <= 0 or iv <= 0:
        return max(0.0, (s - k) if kind == "c" else (k - s))
    d1 = (math.log(s / k) + (r + 0.5 * iv * iv) * t) / (iv * math.sqrt(t))
    d2 = d1 - iv * math.sqrt(t)
    if kind == "c":
        return s * _norm_cdf(d1) - k * math.exp(-r * t) * _norm_cdf(d2)
    return k * math.exp(-r * t) * _norm_cdf(-d2) - s * _norm_cdf(-d1)


def smile(iv, k, s):
    m = math.log(k / s)
    return iv * (1.0 - 0.3 * m + 0.8 * abs(m) + 2.0 * m * m)


def entry_iv(t, k, s):
    core = math.sqrt(BASE_IV ** 2 + EVENT_MOVE ** 2 / t)
    return smile(core, k, s)


def leg_entry(kind, k, t, side):
    mid = bs(kind, SPOT, k, t, RATE, entry_iv(t, k, SPOT))
    return mid * (0.98 if side == "sell" else 1.02)


def load_moves():
    """Per event: (r9, r16, r23) from report-day close, via actual Fridays."""
    bars = list(csv.DictReader(open(DATA)))
    dates = [b["date"] for b in bars]
    close = [float(b["close"]) for b in bars]
    idx = {d: i for i, d in enumerate(dates)}

    def close_on_or_before(target):
        j = None
        for i, d in enumerate(dates):
            if d <= target:
                j = i
            else:
                break
        return close[j] if j is not None else None

    out = []
    for ed in EARNINGS_AMC:
        if ed not in idx:
            continue
        i = idx[ed]
        s0 = close[i]
        y, m, d = map(int, ed.split("-"))
        rd = datetime.date(y, m, d)
        f1 = rd + datetime.timedelta(days=(4 - rd.weekday()) % 7 or 7)  # next Fri
        exp_long = f1 + datetime.timedelta(days=7)
        exp_a = f1 + datetime.timedelta(days=14)
        exp_b = f1 + datetime.timedelta(days=21)
        vals = [close_on_or_before(x.isoformat()) for x in (exp_long, exp_a, exp_b)]
        if any(v is None for v in vals) or vals[2] == s0:
            continue
        out.append((ed, s0, *[v / s0 - 1.0 for v in vals]))
    return out


def stats(pnls, base=None):
    r = {"mean": statistics.mean(pnls), "median": statistics.median(pnls),
         "win_rate": sum(1 for p in pnls if p > 0) / len(pnls),
         "worst": min(pnls), "best": max(pnls)}
    if base:
        edge = [a - b for a, b in zip(pnls, base)]
        r["mean_edge_vs_shares"] = statistics.mean(edge)
        r["beat_shares_rate"] = sum(1 for e in edge if e > 0) / len(edge)
    return r


def main():
    moves = load_moves()
    os.makedirs(OUTDIR, exist_ok=True)
    lines = [f"# TSLA diagonal — entered {SPOT} on report day 2026-07-22\n"]
    lines.append(f"Model: base IV {BASE_IV:.0%}, event move {EVENT_MOVE:.0%} 1-sigma; "
                 f"n={len(moves)} events\n")

    # premiums for today's trade
    prem_400_a = leg_entry("c", SHORT_K, T_SHORT_A, "sell")
    prem_400_b = leg_entry("c", SHORT_K, T_SHORT_B, "sell")
    lines.append(f"Short 400C credit: 08-07 exp ≈ ${prem_400_a:.2f}/sh, "
                 f"08-14 exp ≈ ${prem_400_b:.2f}/sh")
    lines.append(f"Entry IVs: next-week ATM ≈ {entry_iv(T_LONG, SPOT, SPOT):.0%}, "
                 f"2-wk 400C ≈ {entry_iv(T_SHORT_A, SHORT_K, SPOT):.0%}, "
                 f"post-print surface reverts toward {BASE_IV:.0%}\n")

    # IV-crush illustration on the long leg: value tomorrow vs entry
    lines.append("## IV crush on the long (next-week) call — day-after value\n")
    lines.append("| strike | cost today | flat | +4% | +7% | +10% | -5% | breakeven move |")
    lines.append("|---|---|---|---|---|---|---|---|")
    t_after = 8 / 365.0
    for k in (375, 380, 390, 400):
        cost = leg_entry("c", k, T_LONG, "buy")
        vals = {}
        for mv in (0.0, 0.04, 0.07, 0.10, -0.05):
            s1 = SPOT * (1 + mv)
            vals[mv] = bs("c", s1, k, t_after, RATE, smile(BASE_IV, k, s1))
        be = None
        for bp in [x / 1000 for x in range(0, 200)]:
            s1 = SPOT * (1 + bp)
            if bs("c", s1, k, t_after, RATE, smile(BASE_IV, k, s1)) >= cost:
                be = bp
                break
        lines.append(f"| {k} | {cost:.2f} | {vals[0.0]:.2f} | {vals[0.04]:.2f} | "
                     f"{vals[0.07]:.2f} | {vals[0.10]:.2f} | {vals[-0.05]:.2f} | "
                     f"{'+' + format(be, '.1%') if be is not None else '>20%'} |")
    lines.append("")

    base16 = [100.0 * s0 * r16 for _, s0, r9, r16, r23 in moves]

    def run_family(title, rows):
        lines.append(f"## {title}\n")
        lines.append("| structure | net/sh | mean P&L | median P&L | win % | worst "
                     "| best | beats shares % | edge vs shares |")
        lines.append("|---|---|---|---|---|---|---|---|---|".replace("|---" * 9, "|---" * 9))
        for name, net, pnls in rows:
            st = stats(pnls, base16)
            lines.append(f"| {name} | {net:+.2f} | {st['mean']:+.0f} | {st['median']:+.0f} | "
                         f"{st['win_rate']:.0%} | {st['worst']:+.0f} | {st['best']:+.0f} | "
                         f"{st['beat_shares_rate']:.0%} | {st['mean_edge_vs_shares']:+.0f} |")
        lines.append("")

    grid = []

    # 1) long next-week call alone (no shares) — the timing question
    rows = []
    for k in (375, 380, 385, 390, 395, 400):
        cost = leg_entry("c", k, T_LONG, "buy")
        mny = k / SPOT
        pnls = [100.0 * (max(0.0, s0 * (1 + r9) - mny * s0) - cost * s0 / SPOT)
                for _, s0, r9, r16, r23 in moves]
        st = stats(pnls)
        rows.append((f"+C {k} (07-31) alone", -cost, pnls))
        grid.append((f"long_call_{k}_0731", -cost, st))
    lines.append("## Buying next-week calls at today's close (pre-print), held to expiry\n")
    lines.append("| strike | cost/sh | mean P&L | median P&L | win % | worst | best |")
    lines.append("|---|---|---|---|---|---|---|")
    for name, net, pnls in rows:
        st = stats(pnls)
        lines.append(f"| {name} | {net:+.2f} | {st['mean']:+.0f} | {st['median']:+.0f} | "
                     f"{st['win_rate']:.0%} | {st['worst']:+.0f} | {st['best']:+.0f} |")
    lines.append("")

    # 2) covered short 400C alone, both expiries
    rows = []
    for label, t_s, r_key in [("08-07", T_SHORT_A, "r16"), ("08-14", T_SHORT_B, "r23")]:
        prem = leg_entry("c", SHORT_K, t_s, "sell")
        mny = SHORT_K / SPOT
        pnls = []
        for _, s0, r9, r16, r23 in moves:
            r_s = r16 if r_key == "r16" else r23
            pnls.append(100.0 * s0 * r_s +
                        100.0 * (prem * s0 / SPOT - max(0.0, s0 * (1 + r_s) - mny * s0)))
        rows.append((f"shares + short 400C ({label})", prem, pnls))
    run_family("Covered 400 call alone (shares + short 400C)", rows)

    # 3) full diagonal: shares + short 400C + long next-week call
    rows = []
    for label, t_s, r_key in [("08-07", T_SHORT_A, "r16"), ("08-14", T_SHORT_B, "r23")]:
        prem = leg_entry("c", SHORT_K, t_s, "sell")
        for k in (375, 380, 385, 390, 395, 400):
            cost = leg_entry("c", k, T_LONG, "buy")
            mny_s, mny_l = SHORT_K / SPOT, k / SPOT
            net = prem - cost
            pnls = []
            for _, s0, r9, r16, r23 in moves:
                r_s = r16 if r_key == "r16" else r23
                p = 100.0 * s0 * r_s
                p += 100.0 * (prem * s0 / SPOT - max(0.0, s0 * (1 + r_s) - mny_s * s0))
                p += 100.0 * (max(0.0, s0 * (1 + r9) - mny_l * s0) - cost * s0 / SPOT)
                pnls.append(p)
            rows.append((f"short 400C {label} + long {k}C 07-31", net, pnls))
    run_family("Proposed diagonal (shares + short 2wk 400C + long 1wk call)", rows)

    # 4) reverse (IV-favorable) calendar for contrast: sell 1wk 400C, buy 2wk 400C
    prem_f = leg_entry("c", SHORT_K, T_LONG, "sell")
    cost_b = leg_entry("c", SHORT_K, T_SHORT_A, "buy")
    pnls = []
    for _, s0, r9, r16, r23 in moves:
        mny = SHORT_K / SPOT
        p = 100.0 * s0 * r16
        p += 100.0 * (prem_f * s0 / SPOT - max(0.0, s0 * (1 + r9) - mny * s0))
        p += 100.0 * (max(0.0, s0 * (1 + r16) - mny * s0) - cost_b * s0 / SPOT)
        pnls.append(p)
    run_family("Reverse calendar for contrast (sell 1wk 400C, buy 2wk 400C)",
               [(f"shares + cal 400 (net {prem_f - cost_b:+.2f})", prem_f - cost_b, pnls)])

    # frequency stats
    hit9 = sum(1 for _, s0, r9, r16, r23 in moves if (1 + r9) >= SHORT_K / SPOT)
    hit16 = sum(1 for _, s0, r9, r16, r23 in moves if (1 + r16) >= SHORT_K / SPOT)
    lines.append(f"Frequency: price finished a +{SHORT_K / SPOT - 1:.1%} move "
                 f"(the 400-strike distance) above strike in {hit9}/{len(moves)} events "
                 f"at the 1-week mark and {hit16}/{len(moves)} at the 2-week mark.\n")
    lines.append("Baseline shares-only (16d horizon): "
                 f"mean {statistics.mean(base16):+.0f}, median {statistics.median(base16):+.0f}, "
                 f"worst {min(base16):+.0f}, best {max(base16):+.0f}\n")
    lines.append("Leg prices are modeled (event-vol Black-Scholes), not live quotes. "
                 "Historical strikes are moneyness-scaled to each event's entry price.\n")

    with open(os.path.join(OUTDIR, "tsla_2026-07-22_diagonal_report.md"), "w") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
