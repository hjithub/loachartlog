"""
Lost Ark KR Gold Price Analysis
Correlates game patches with price movements, builds prediction model.

Usage: python analyze.py
Outputs: charts (PNG) + console summary
"""

import pandas as pd
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import cross_val_score

ECONOMY_KEYWORDS = [
    '골드', '크리스탈', '거래소', '재련', '보상', '교환', '골드 획득', '골드 소모',
    '경매', '시세', '수수료', '귀속', '거래 가능', '거래 불가', '재화', '실링', '보석', '각인서',
]


def load_data():
    price = pd.read_csv("아비도스_융화_재료.csv", parse_dates=["datetime"])
    price_clean = price[price.price > 0].copy()
    daily = price_clean.groupby(price_clean.datetime.dt.date)['price'].mean().reset_index()
    daily.columns = ['date', 'price']
    daily['date'] = pd.to_datetime(daily['date'])

    with open("lostark_update_details.json", "r") as f:
        patches = json.load(f)

    notices = pd.read_csv("lostark_patch_notices.csv", parse_dates=["date"])

    inflation = pd.read_csv("inflation_index.csv", parse_dates=["date"])

    return daily, patches, notices, inflation


def get_price_window(daily, date, days_before=0, days_after=0):
    d = pd.to_datetime(date)
    start = d - timedelta(days=days_before)
    end = d + timedelta(days=days_after)
    mask = (daily.date >= start) & (daily.date <= end)
    vals = daily[mask]
    return vals.price.mean() if len(vals) > 0 else None


def build_feature_matrix(daily, patches, notices):
    rows = []
    for i, p in enumerate(patches):
        content = p['content']
        size = len(content)
        pdate = pd.to_datetime(p['date'].replace('.', '-'))

        if pdate < daily.date.min() or pdate > daily.date.max() - timedelta(days=7):
            continue

        pre_price = get_price_window(daily, pdate, days_before=3, days_after=0)
        post_1w = get_price_window(daily, pdate, days_before=0, days_after=7)
        post_1m = get_price_window(daily, pdate, days_before=0, days_after=30)

        if pre_price is None or post_1w is None:
            continue

        delta_1w = (post_1w - pre_price) / pre_price * 100
        delta_1m = ((post_1m - pre_price) / pre_price * 100) if post_1m else None

        # Days since last patch
        if i > 0:
            prev_date = pd.to_datetime(patches[i - 1]['date'].replace('.', '-'))
            days_since_last = (pdate - prev_date).days
        else:
            days_since_last = 30

        # Keyword features
        total_kw = sum(content.count(kw) for kw in ECONOMY_KEYWORDS)
        gold_count = content.count('골드')
        trade_count = sum(content.count(kw) for kw in ['거래소', '경매', '거래 가능', '거래 불가', '시세'])
        mat_count = sum(content.count(kw) for kw in ['재련', '재화', '보석', '각인서', '융화'])

        # Maintenance frequency (30 days prior)
        d_ts = pdate
        maint_mask = (notices.date >= d_ts - timedelta(days=30)) & (notices.date < d_ts) & (notices.badge == '점검')
        maint_count_30d = maint_mask.sum()

        # Pre-patch trend
        pre_7d = get_price_window(daily, pdate, days_before=10, days_after=3)
        pre_trend = ((pre_price - pre_7d) / pre_7d * 100) if pre_7d else 0

        rows.append({
            'date': pdate,
            'title': p['title'][:40],
            'patch_size': size,
            'log_patch_size': np.log(size),
            'days_since_last': days_since_last,
            'total_kw_hits': total_kw,
            'gold_mentions': gold_count,
            'trade_mentions': trade_count,
            'material_mentions': mat_count,
            'kw_density': total_kw / (size / 1000),
            'maint_30d': maint_count_30d,
            'pre_price': pre_price,
            'pre_trend': pre_trend,
            'delta_1w': delta_1w,
            'delta_1m': delta_1m,
            'direction_1w': 1 if delta_1w > 0 else 0,
        })

    return pd.DataFrame(rows)


def run_model(df):
    features = ['patch_size', 'log_patch_size', 'days_since_last', 'total_kw_hits',
                'gold_mentions', 'trade_mentions', 'material_mentions', 'kw_density',
                'maint_30d', 'pre_trend']
    X = df[features].values
    y = df['direction_1w'].values

    print("=" * 80)
    print("PREDICTION MODEL")
    print("=" * 80)
    print(f"Samples: {len(df)} | UP: {y.sum()} | DOWN: {len(y) - y.sum()}")

    # Decision Tree
    dt = DecisionTreeClassifier(max_depth=3, random_state=42)
    dt.fit(X, y)
    dt_cv = cross_val_score(dt, X, y, cv=10, scoring='accuracy')
    print(f"\nDecision Tree (depth=3): train={dt.score(X, y):.1%}, CV={dt_cv.mean():.1%} (±{dt_cv.std():.1%})")

    importances = pd.Series(dt.feature_importances_, index=features).sort_values(ascending=False)
    print("  Top features:", ", ".join(f"{f}={v:.3f}" for f, v in importances.items() if v > 0))

    # Random Forest
    rf = RandomForestClassifier(n_estimators=100, max_depth=3, random_state=42)
    rf.fit(X, y)
    rf_cv = cross_val_score(rf, X, y, cv=10, scoring='accuracy')
    print(f"\nRandom Forest: train={rf.score(X, y):.1%}, CV={rf_cv.mean():.1%} (±{rf_cv.std():.1%})")

    rf_imp = pd.Series(rf.feature_importances_, index=features).sort_values(ascending=False)
    print("  Top features:", ", ".join(f"{f}={v:.3f}" for f, v in rf_imp.head(5).items()))

    # Correlations
    print("\nCorrelations with 1-week Δ%:")
    for feat in features:
        corr = df[feat].corr(df['delta_1w'])
        if abs(corr) > 0.1:
            print(f"  {feat:25s} r={corr:+.3f}")

    return rf, features


def print_key_findings(df):
    print("\n" + "=" * 80)
    print("KEY FINDINGS")
    print("=" * 80)

    large = df[df.patch_size >= 30000]
    small = df[df.patch_size < 30000]
    print(f"\nLarge patches (≥30K chars): avg Δ1w = {large.delta_1w.mean():+.1f}% (n={len(large)})")
    print(f"Small patches (<30K chars): avg Δ1w = {small.delta_1w.mean():+.1f}% (n={len(small)})")

    high_gold = df[df.gold_mentions >= 20]
    low_gold = df[df.gold_mentions < 20]
    print(f"\nHigh gold mentions (≥20): avg Δ1w = {high_gold.delta_1w.mean():+.1f}% (n={len(high_gold)})")
    print(f"Low gold mentions (<20):  avg Δ1w = {low_gold.delta_1w.mean():+.1f}% (n={len(low_gold)})")

    high_trade = df[df.trade_mentions >= 5]
    low_trade = df[df.trade_mentions < 5]
    print(f"\nHigh trade keywords (≥5): avg Δ1w = {high_trade.delta_1w.mean():+.1f}% (n={len(high_trade)})")
    print(f"Low trade keywords (<5):  avg Δ1w = {low_trade.delta_1w.mean():+.1f}% (n={len(low_trade)})")


def generate_charts(daily, patches, df, inflation):
    # Chart 1: Price timeline with major patches
    fig, ax = plt.subplots(figsize=(16, 6))
    ax.plot(daily.date, daily.price, linewidth=0.8, color='#2196F3')
    major = [(p['date'].replace('.', '-'), len(p['content'])) for p in patches if len(p['content']) >= 30000]
    for pdate, size in major:
        d = pd.to_datetime(pdate)
        if d >= daily.date.min() and d <= daily.date.max():
            ax.axvline(d, color='red', alpha=0.4, linewidth=0.8, linestyle='--')
            nearest = daily.iloc[(daily.date - d).abs().argsort()[:1]]
            ax.annotate(f'{pdate}\n({size // 1000}K)', xy=(d, nearest.price.values[0]),
                        fontsize=5.5, rotation=90, va='bottom', ha='right', color='red', alpha=0.7)
    ax.set_title('Abidos Fusion Material Price + Major Patches (>30K chars)')
    ax.set_ylabel('Price (Gold)')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('chart_price_patches.png', dpi=150)
    plt.close()

    # Chart 2: Patch size vs 1-week delta
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ['red' if d < 0 else 'green' for d in df.delta_1w]
    sizes_s = [max(20, min(200, s / 200)) for s in df.total_kw_hits]
    ax.scatter(df.patch_size / 1000, df.delta_1w, c=colors, s=sizes_s, alpha=0.6,
               edgecolors='black', linewidth=0.5)
    ax.axhline(0, color='gray', linewidth=0.5, linestyle='--')
    ax.set_xlabel('Patch Size (K chars)')
    ax.set_ylabel('Price Change 1-week (%)')
    ax.set_title('Patch Size vs 1-Week Price Change\n(dot size = economy keyword count)')
    plt.tight_layout()
    plt.savefig('chart_size_vs_delta.png', dpi=150)
    plt.close()

    # Chart 3: Inflation index
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(inflation.date, inflation['index'], linewidth=1.5, color='#FF5722')
    ax.axhline(100, color='gray', linewidth=0.5, linestyle='--')
    ax.fill_between(inflation.date, 100, inflation['index'], alpha=0.2, color='#FF5722')
    ax.set_title('Lost Ark KR Inflation Index (9-item basket, normalized to 100)')
    ax.set_ylabel('Index')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('chart_inflation_index.png', dpi=150)
    plt.close()

    print("Charts saved: chart_price_patches.png, chart_size_vs_delta.png, chart_inflation_index.png")


if __name__ == "__main__":
    daily, patches, notices, inflation = load_data()
    df = build_feature_matrix(daily, patches, notices)
    run_model(df)
    print_key_findings(df)
    generate_charts(daily, patches, df, inflation)
