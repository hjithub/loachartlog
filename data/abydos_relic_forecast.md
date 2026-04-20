# 아비도스 유물 — 90-day Price Forecast

**Last observation:** 2026-03-25, 1,267g
**Horizon:** 2026-03-26 → 2026-06-23 (90 days)
**Model:** damped-linear trend + 120-day mean-reversion pull + weekly seasonality, AR(1) log-return noise, 2,000 Monte Carlo paths.

## Historical context

| Period | Avg | Range |
|---|---|---|
| 2024-07 launch | 510g | 367 – 725 |
| 2025-06 peak phase 1 | 1,125g | 1,047 – 1,178 |
| 2025-12 dip | 910g | 713 – 1,196 |
| 2026-02 rebound | 1,127g | 958 – 1,268 |
| 2026-03 (latest) | 1,306g | 1,236 – 1,367 |

The item has transitioned from a ~450g early-floor asset to a structurally higher 1,000 – 1,300g range, driven by inflation (see `inflation_index.csv`) and recurring demand from 융화 재료 crafting.

## Point forecast (median)

| Horizon | Date | Median | Δ vs last | 80% band |
|---|---|---|---|---|
| +7d  | 2026-04-01 | 1,298g | +2.4%  | 1,127 – 1,463 |
| +14d | 2026-04-08 | 1,298g | +2.4%  | 1,085 – 1,572 |
| +30d | 2026-04-24 | 1,328g | +4.8%  | 1,042 – 1,708 |
| +60d | 2026-05-24 | 1,228g | −3.1%  | 924 – 1,681 |
| +90d | 2026-06-23 | 1,187g | −6.3%  | 852 – 1,664 |

## Read

- **Near term (0 – 4 weeks):** bias slightly up. The last 60 days show a positive slope (+7.9g/day pre-damping) and 2026-03 printed the highest monthly average on record. Expect 1,250 – 1,400g as the working range unless a patch changes gold flow.
- **Mid term (1 – 3 months):** drift lower toward ~1,180g as the slope dampens and mean-reversion pulls price toward the 120-day average (~1,044g). Wide uncertainty — 80% band spans roughly ±35%.
- **Weekly seasonality:** Thu/Fri run +1.5 – 2.0% above the weekly mean; Mon/Sun run −1.2 – 1.6% below. Sellers should prefer Thu/Fri, buyers Mon/Sun, all else equal.

## Key risks (not in the model)

1. **Patch shocks.** `analyze.py` shows gold-flow-heavy patches move 아비도스 융화 재료 by several percent in the week that follows; this item tracks the same demand curve. A 신규 티어 or 재련 비용 adjustment could break out of the 80% band in either direction.
2. **Event-driven supply spikes.** 출석 보상 / 기간 한정 distributions of 유물 bundles temporarily flood supply; history shows 10 – 20% dips within 1 – 2 weeks of large events.
3. **Inflation drift.** If the basket index keeps climbing, the mean-reversion anchor (1,044g) is too low and medians above understate fair value.

## Files

- `charts/abydos_relic_forecast.png` — chart with 50% / 80% bands
- `data/abydos_relic_forecast.csv` — per-day percentiles
- `forecast_abydos_relic.py` — reproducible script

Re-run with `python3 forecast_abydos_relic.py` after refreshing `data/아비도스_유물.csv` via `python3 loachart.py "아비도스 유물"`.
