"""
Abydos Relic (아비도스 유물) price forecast.

Model:
  price_t = trend_t * seasonal_dow * exp(ar_noise)

  - trend: damped-linear on last 60 days, pulled toward 120-day mean
  - seasonal_dow: weekly factor estimated from last 120 days (detrended by 7d MA)
  - ar_noise: AR(1) on log-returns for Monte Carlo uncertainty bands

Outputs:
  charts/abydos_relic_forecast.png
  data/abydos_relic_forecast.csv
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm

for candidate in ("NanumGothic", "Malgun Gothic", "Noto Sans CJK KR", "WenQuanYi Zen Hei", "Unifont"):
    if any(candidate in f.name for f in fm.fontManager.ttflist):
        plt.rcParams["font.family"] = candidate
        break
plt.rcParams["axes.unicode_minus"] = False

CSV = "data/아비도스_유물.csv"
OUT_PNG = "charts/abydos_relic_forecast.png"
OUT_CSV = "data/abydos_relic_forecast.csv"

HORIZON_DAYS = 90
N_SIMS = 2000
TREND_WINDOW = 60
MEAN_REVERT_WINDOW = 120
MEAN_REVERT_HALFLIFE = 45  # days
SEED = 42


def load_daily(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["datetime"])
    df = df[df.price > 0].copy()
    df["date"] = df.datetime.dt.normalize()
    daily = df.groupby("date", as_index=False).price.mean()
    daily["dow"] = daily.date.dt.dayofweek
    return daily


def weekly_seasonality(daily: pd.DataFrame, window: int = 120) -> np.ndarray:
    tail = daily.tail(window).copy()
    tail["ma7"] = tail.price.rolling(7, center=True, min_periods=1).mean()
    tail["ratio"] = tail.price / tail.ma7
    factors = tail.groupby("dow").ratio.mean().reindex(range(7)).values
    # normalize so product across week == 1 (additive neutral in log space)
    factors = factors / factors.mean()
    return factors


def fit_ar1(log_returns: np.ndarray) -> tuple[float, float]:
    r = log_returns[~np.isnan(log_returns)]
    r0, r1 = r[:-1], r[1:]
    phi = float(np.cov(r0, r1, bias=True)[0, 1] / np.var(r0))
    phi = max(-0.9, min(0.9, phi))
    resid = r1 - phi * r0
    sigma = float(resid.std(ddof=1))
    return phi, sigma


def forecast(daily: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)

    last_date = daily.date.iloc[-1]
    last_price = float(daily.price.iloc[-1])

    # Trend: last TREND_WINDOW-day linear slope, damped each day
    tail = daily.tail(TREND_WINDOW).reset_index(drop=True)
    x = np.arange(len(tail))
    slope, _ = np.polyfit(x, tail.price.values, 1)

    long_mean = float(daily.price.tail(MEAN_REVERT_WINDOW).mean())
    alpha = 1 - 0.5 ** (1 / MEAN_REVERT_HALFLIFE)  # daily pull toward long-term mean

    seasonal = weekly_seasonality(daily)

    log_ret = np.log(daily.price / daily.price.shift(1)).values
    phi, sigma = fit_ar1(log_ret)

    horizons = pd.date_range(last_date + pd.Timedelta(days=1), periods=HORIZON_DAYS, freq="D")

    sims = np.zeros((N_SIMS, HORIZON_DAYS))
    for s in range(N_SIMS):
        level = last_price
        prev_r = log_ret[-1] if not np.isnan(log_ret[-1]) else 0.0
        cur_slope = slope
        for t, d in enumerate(horizons):
            # deterministic drift: slope + mean reversion
            drift = cur_slope + alpha * (long_mean - level)
            # noise: AR(1) on log-returns
            eps = rng.normal(0, sigma)
            r = phi * prev_r + eps
            prev_r = r
            level = (level + drift) * np.exp(r)
            # weekly seasonality applied as multiplicative factor vs. its own dow baseline
            seas_ratio = seasonal[d.dayofweek] / seasonal[(d - pd.Timedelta(days=1)).dayofweek]
            level *= seas_ratio
            # damp the slope toward 0 over ~30d
            cur_slope *= 0.97
            sims[s, t] = max(level, 1.0)

    p10 = np.percentile(sims, 10, axis=0)
    p25 = np.percentile(sims, 25, axis=0)
    p50 = np.percentile(sims, 50, axis=0)
    p75 = np.percentile(sims, 75, axis=0)
    p90 = np.percentile(sims, 90, axis=0)
    mean = sims.mean(axis=0)

    return pd.DataFrame({
        "date": horizons, "mean": mean,
        "p10": p10, "p25": p25, "p50": p50, "p75": p75, "p90": p90,
    })


def plot(daily: pd.DataFrame, fc: pd.DataFrame, out_path: str):
    fig, ax = plt.subplots(figsize=(13, 6))
    hist = daily.tail(240)
    ax.plot(hist.date, hist.price, color="#1f77b4", lw=1.2, label="Historical daily avg")
    ax.plot(fc.date, fc.p50, color="#d62728", lw=1.8, label="Forecast (median)")
    ax.fill_between(fc.date, fc.p25, fc.p75, color="#d62728", alpha=0.25, label="50% band")
    ax.fill_between(fc.date, fc.p10, fc.p90, color="#d62728", alpha=0.12, label="80% band")
    ax.axvline(daily.date.iloc[-1], color="gray", ls="--", lw=0.8)
    ax.set_title("Abydos Relic (아비도스 유물) — 90-day Price Forecast")
    ax.set_ylabel("Gold per item")
    ax.set_xlabel("Date")
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(out_path, dpi=110)
    print(f"  Saved {out_path}")


def main():
    daily = load_daily(CSV)
    print(f"Loaded {len(daily)} daily points ({daily.date.min().date()} → {daily.date.max().date()})")
    fc = forecast(daily)
    fc.to_csv(OUT_CSV, index=False, float_format="%.1f")
    print(f"  Saved {OUT_CSV}")
    plot(daily, fc, OUT_PNG)

    last = float(daily.price.iloc[-1])
    print("\n-- Forecast summary --")
    for days in (7, 14, 30, 60, 90):
        row = fc.iloc[days - 1]
        d = (row.p50 - last) / last * 100
        print(f"  +{days:>2}d  {row.date.date()}  median={row.p50:>6.0f}g  "
              f"({d:+.1f}%)  80%band=[{row.p10:>5.0f}, {row.p90:>5.0f}]")


if __name__ == "__main__":
    main()
