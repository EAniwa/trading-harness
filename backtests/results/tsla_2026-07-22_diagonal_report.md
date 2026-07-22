# TSLA diagonal — entered 375.84 on report day 2026-07-22

Model: base IV 55%, event move 8% 1-sigma; n=20 events

Short 400C credit: 08-07 exp ≈ $12.43/sh, 08-14 exp ≈ $15.34/sh
Entry IVs: next-week ATM ≈ 75%, 2-wk 400C ≈ 70%, post-print surface reverts toward 55%

## IV crush on the long (next-week) call — day-after value

| strike | cost today | flat | +4% | +7% | +10% | -5% | breakeven move |
|---|---|---|---|---|---|---|---|
| 375 | 18.63 | 12.81 | 22.71 | 31.60 | 41.36 | 5.38 | +2.5% |
| 380 | 16.32 | 10.52 | 19.29 | 27.67 | 37.05 | 4.25 | +2.9% |
| 390 | 12.52 | 6.96 | 13.32 | 20.48 | 28.94 | 2.61 | +3.7% |
| 400 | 9.53 | 4.48 | 9.08 | 14.38 | 21.68 | 1.59 | +4.4% |

## Buying next-week calls at today's close (pre-print), held to expiry

| strike | cost/sh | mean P&L | median P&L | win % | worst | best |
|---|---|---|---|---|---|---|
| +C 375 (07-31) alone | -18.63 | +365 | -963 | 35% | -2139 | +6907 |
| +C 380 (07-31) alone | -16.32 | +370 | -843 | 35% | -1874 | +6700 |
| +C 385 (07-31) alone | -14.31 | +374 | -858 | 35% | -1643 | +6471 |
| +C 390 (07-31) alone | -12.52 | +371 | -774 | 30% | -1437 | +6225 |
| +C 395 (07-31) alone | -10.93 | +382 | -676 | 30% | -1277 | +5963 |
| +C 400 (07-31) alone | -9.53 | +387 | -589 | 30% | -1114 | +5686 |

## Covered 400 call alone (shares + short 400C)

| structure | net/sh | mean P&L | median P&L | win % | worst | best | beats shares % | edge vs shares |
|---|---|---|---|---|---|---|---|---|
| shares + short 400C (08-07) | +12.43 | +173 | +266 | 55% | -3823 | +3773 | 65% | -805 |
| shares + short 400C (08-14) | +15.34 | -89 | -71 | 50% | -5590 | +4073 | 40% | -1068 |

## Proposed diagonal (shares + short 2wk 400C + long 1wk call)

| structure | net/sh | mean P&L | median P&L | win % | worst | best | beats shares % | edge vs shares |
|---|---|---|---|---|---|---|---|---|
| short 400C 08-07 + long 375C 07-31 | -6.20 | +538 | -983 | 45% | -5044 | +9717 | 35% | -440 |
| short 400C 08-07 + long 380C 07-31 | -3.89 | +543 | -938 | 40% | -4893 | +9510 | 25% | -435 |
| short 400C 08-07 + long 385C 07-31 | -1.88 | +547 | -809 | 40% | -4761 | +9281 | 20% | -432 |
| short 400C 08-07 + long 390C 07-31 | -0.09 | +544 | -953 | 40% | -4644 | +9035 | 15% | -434 |
| short 400C 08-07 + long 395C 07-31 | +1.50 | +556 | -875 | 40% | -4540 | +8773 | 70% | -423 |
| short 400C 08-07 + long 400C 07-31 | +2.90 | +560 | -760 | 40% | -4448 | +8496 | 70% | -419 |
| short 400C 08-14 + long 375C 07-31 | -3.29 | +276 | -1194 | 40% | -7205 | +9941 | 35% | -702 |
| short 400C 08-14 + long 380C 07-31 | -0.98 | +281 | -1075 | 40% | -7005 | +9734 | 35% | -698 |
| short 400C 08-14 + long 385C 07-31 | +1.03 | +285 | -971 | 40% | -6831 | +9505 | 25% | -694 |
| short 400C 08-14 + long 390C 07-31 | +2.83 | +282 | -878 | 45% | -6675 | +9258 | 30% | -697 |
| short 400C 08-14 + long 395C 07-31 | +4.41 | +294 | -796 | 45% | -6538 | +8996 | 35% | -685 |
| short 400C 08-14 + long 400C 07-31 | +5.81 | +298 | -724 | 45% | -6417 | +8720 | 40% | -681 |

## Reverse calendar for contrast (sell 1wk 400C, buy 2wk 400C)

| structure | net/sh | mean P&L | median P&L | win % | worst | best | beats shares % | edge vs shares |
|---|---|---|---|---|---|---|---|---|
| shares + cal 400 (net -3.78) | -3.78 | +1333 | -1311 | 40% | -4886 | +17766 | 30% | +354 |

Frequency: price finished a +6.4% move (the 400-strike distance) above strike in 6/20 events at the 1-week mark and 8/20 at the 2-week mark.

Baseline shares-only (16d horizon): mean +979, median -999, worst -4638, best +11876

Leg prices are modeled (event-vol Black-Scholes), not live quotes. Historical strikes are moneyness-scaled to each event's entry price.
