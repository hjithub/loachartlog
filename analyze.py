"""
Lost Ark KR Gold Price Analysis v2
Content-based categorization + Gold flow analysis + Inflation index model.

Usage: python analyze.py
"""

import pandas as pd
import json
import numpy as np
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import timedelta
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler

# ============= GOLD FLOW PHRASES =============
GOLD_SOURCE_PHRASES = [
    '골드 획득', '골드를 획득', '골드 보상', '클리어 보상', '골드 지급', '골드가 지급',
    '추가 보상', '보상 추가', '보상이 추가', '보상 증가', '보상이 증가',
]
GOLD_SINK_PHRASES = [
    '골드 소모', '골드가 소모', '골드를 소모', '수수료', '재련 비용', '강화 비용',
    '제작 비용', '귀속', '거래 불가', '골드 차감', '비용이 증가', '비용 증가',
]
GOLD_SRC_REDUCTION = ['보상 감소', '보상이 감소', '획득량.*감소']
GOLD_SNK_REDUCTION = ['비용 감소', '비용이 감소', '수수료.*감소', '수수료.*인하']

# ============= CONTENT CATEGORIES =============
CATEGORIES = {
    'new_raid': ['신규 레이드', '군단장', '카제로스', '어비스 던전', '가디언 토벌', '에피소드'],
    'honing_change': ['재련 확률', '재련 비용', '재련 시스템', '강화 확률', '상한 돌파', '재련 단계',
                      '재련', '강화'],
    'new_tier': ['시즌', '티어', '아이템 레벨', '신규 장비'],
    'event_reward': ['이벤트', '출석 보상', '접속 보상', '기간 한정', '특별 보상'],
    'gem_engraving': ['보석', '각인', '젬'],
    'market_system': ['거래소', '경매', '시세'],
}


def count_phrases(content, phrases):
    total = 0
    for phrase in phrases:
        if '.*' in phrase:
            total += len(re.findall(phrase, content))
        else:
            total += content.count(phrase)
    return total


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
    mask = (daily.date >= d - timedelta(days=days_before)) & (daily.date <= d + timedelta(days=days_after))
    v = daily[mask]
    return v.price.mean() if len(v) > 0 else None


def build_features(daily, patches, notices, inflation):
    rows = []
    for i, p in enumerate(patches):
        content = p['content']; size = len(content)
        pdate = pd.to_datetime(p['date'].replace('.', '-'))
        if pdate < daily.date.min() or pdate > daily.date.max() - timedelta(days=7):
            continue

        pre = get_price_window(daily, pdate, days_before=3)
        post1w = get_price_window(daily, pdate, days_after=7)
        post1m = get_price_window(daily, pdate, days_after=30)
        if pre is None or post1w is None:
            continue

        d1w = (post1w - pre) / pre * 100
        d1m = ((post1m - pre) / pre * 100) if post1m else None
        dsl = (pdate - pd.to_datetime(patches[i - 1]['date'].replace('.', '-'))).days if i > 0 else 30

        # Gold flow
        src = count_phrases(content, GOLD_SOURCE_PHRASES)
        snk = count_phrases(content, GOLD_SINK_PHRASES)
        src_red = count_phrases(content, GOLD_SRC_REDUCTION)
        snk_red = count_phrases(content, GOLD_SNK_REDUCTION)
        gold_flow = (src + snk_red) - (snk + src_red)

        # Content categories
        cat_scores = {cat: count_phrases(content, kws) for cat, kws in CATEGORIES.items()}
        primary_cat = max(cat_scores, key=cat_scores.get) if any(cat_scores.values()) else 'other'

        # Macro
        mm = ((notices.date >= pdate - timedelta(days=30)) & (notices.date < pdate) & (notices.badge == '점검')).sum()
        pre7 = get_price_window(daily, pdate, days_before=10, days_after=3)
        pt = ((pre - pre7) / pre7 * 100) if pre7 else 0

        rows.append({
            'date': pdate, 'title': p['title'][:40],
            'patch_size': size, 'log_size': np.log(size), 'days_since_last': dsl,
            'gold_source': src, 'gold_sink': snk, 'gold_flow': gold_flow,
            'cat_raid': cat_scores['new_raid'], 'cat_honing': cat_scores['honing_change'],
            'cat_new_tier': cat_scores['new_tier'], 'cat_event': cat_scores['event_reward'],
            'cat_gem': cat_scores['gem_engraving'], 'cat_market': cat_scores['market_system'],
            'is_new_tier': 1 if cat_scores['new_tier'] >= 3 else 0,
            'primary_cat': primary_cat,
            'maint_30d': mm, 'pre_price': pre, 'pre_trend': pt,
            'delta_1w': d1w, 'delta_1m': d1m,
            'direction_1w': 1 if d1w > 0 else 0,
        })

    return pd.DataFrame(rows)


FEATURES = [
    'log_size', 'days_since_last',
    'gold_flow', 'gold_source', 'gold_sink',
    'cat_raid', 'cat_honing', 'cat_new_tier', 'cat_event', 'cat_gem', 'cat_market',
    'is_new_tier',
    'maint_30d', 'pre_trend',
]


def run_analysis(df):
    X = df[FEATURES].values
    y = df['direction_1w'].values

    # Content-based
    print("=" * 90)
    print("CONTENT-BASED ANALYSIS (patch type → price direction)")
    print("=" * 90)
    cat_stats = df.groupby('primary_cat').agg(
        count=('delta_1w', 'count'), avg_delta=('delta_1w', 'mean'),
        std_delta=('delta_1w', 'std'), pct_up=('direction_1w', 'mean')
    ).sort_values('avg_delta')
    for cat, row in cat_stats.iterrows():
        sign = "+" if row.avg_delta > 0 else ""
        print(f"  {cat:20s} n={int(row['count']):>2} | avg={sign}{row.avg_delta:.1f}% ±{row.std_delta:.1f}% | UP={row.pct_up:.0%}")

    # Gold flow
    print(f"\nGold flow correlation with Δ1w: {df.gold_flow.corr(df.delta_1w):+.3f}")
    print(f"Gold source correlation: {df.gold_source.corr(df.delta_1w):+.3f}")
    print(f"Gold sink correlation: {df.gold_sink.corr(df.delta_1w):+.3f}")

    # Model
    print("\n" + "=" * 90)
    print("COMBINED MODEL")
    print("=" * 90)
    rf = RandomForestClassifier(n_estimators=100, max_depth=3, random_state=42)
    cv = cross_val_score(rf, X, y, cv=10, scoring='accuracy')
    rf.fit(X, y)
    print(f"Baseline (always UP): {y.mean():.1%}")
    print(f"Random Forest CV: {cv.mean():.1%} ±{cv.std():.1%}")

    imp = pd.Series(rf.feature_importances_, index=FEATURES).sort_values(ascending=False)
    print("\nFeature Importance:")
    for f, v in imp.items():
        bar = "█" * int(v * 50)
        print(f"  {f:20s} {v:.3f} {bar}")

    # Walk-forward
    correct = sum(
        1 for split in range(30, len(df))
        if RandomForestClassifier(n_estimators=100, max_depth=3, random_state=42)
        .fit(X[:split], y[:split]).predict(X[split:split + 1])[0] == y[split]
    )
    total = len(df) - 30
    print(f"\nWalk-forward: {correct / total:.1%} ({correct}/{total})")


if __name__ == "__main__":
    daily, patches, notices, inflation = load_data()
    df = build_features(daily, patches, notices, inflation)
    run_analysis(df)
