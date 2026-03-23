"""
LoaChart Market Data Extractor
Fetches historical price data from loachart.com and saves as CSV.
"""

import requests
import csv
import sys
from datetime import datetime, timezone

API_URL = "https://api.loachart.com/line_chart"


def get_item_data(item_name: str) -> list[dict]:
    """Fetch price history for a single item."""
    resp = requests.get(API_URL, params={"itemName": item_name})
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        raise ValueError(f"API error: {data['error']} (item: {item_name})")

    rows = []
    for ts, price in data["v"]:
        dt = datetime.fromtimestamp(ts * 100, tz=timezone.utc)
        rows.append({"datetime": dt.strftime("%Y-%m-%d %H:%M:%S"), "price": price})
    return rows


def save_csv(item_name: str, rows: list[dict], filename: str | None = None):
    """Save data to CSV file."""
    if not filename:
        safe_name = item_name.replace(" ", "_").replace(":", "").replace("/", "_")
        filename = f"{safe_name}.csv"

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["datetime", "price"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"  Saved {len(rows):,} rows → {filename}")


def list_items():
    """Print some example item names you can use."""
    examples = [
        "4T 보석 10레벨 겁화",
        "4T 보석 10레벨 작열",
        "4T 보석 1레벨",
        "3T 보석 10레벨 멸화",
        "(고급)질서의 젬 : 견고",
        "(영웅)혼돈의 젬 : 붕괴",
        "(유물)원한 각인서",
        "(유물)아드레날린 각인서",
        "명예의 파편 주머니(대)",
        "운명의 파편 주머니(대)",
        "운명의 파괴석",
        "운명의 파괴석 결정",
        "최상급 오레하 융화 재료",
        "아비도스 융화 재료",
        "상급 아비도스 융화 재료",
    ]
    print("Example item names:")
    for item in examples:
        print(f"  • {item}")
    print(f"\nFull list (403 items) available at: https://loachart.com/chart")


INFLATION_BASKET = [
    "아비도스 융화 재료",
    "상급 아비도스 융화 재료",
    "최상급 오레하 융화 재료",
    "운명의 파괴석",
    "운명의 파괴석 결정",
    "운명의 파편 주머니(대)",
    "4T 보석 1레벨",
    "(유물)원한 각인서",
    "(유물)아드레날린 각인서",
]


def build_inflation_index(items: list[str] | None = None) -> list[dict]:
    """Build a price index by averaging normalized prices across a basket of items.

    Each item's price series is normalized to 100 at the earliest common date,
    then averaged across all items per timestamp to produce the index.
    """
    items = items or INFLATION_BASKET
    # Fetch all items: {item_name: {datetime_str: price}}
    all_data: dict[str, dict[str, float]] = {}
    for item in items:
        print(f"  Fetching: {item}")
        rows = get_item_data(item)
        all_data[item] = {r["datetime"]: r["price"] for r in rows}

    # Find common date range (daily granularity — use date part only)
    # Group by date, take daily average per item
    daily: dict[str, dict[str, float]] = {}  # {item: {date: avg_price}}
    for item, prices in all_data.items():
        by_date: dict[str, list[float]] = {}
        for dt_str, price in prices.items():
            date = dt_str[:10]
            by_date.setdefault(date, []).append(price)
        daily[item] = {d: sum(ps) / len(ps) for d, ps in by_date.items()}

    # Dates where ALL items have data
    common_dates = set.intersection(*(set(d.keys()) for d in daily.values()))
    if not common_dates:
        raise ValueError("No overlapping dates across all items")
    common_dates = sorted(common_dates)
    print(f"  Common date range: {common_dates[0]} → {common_dates[-1]} ({len(common_dates)} days)")

    # Normalize each item: base = price on first common date = 100
    base_date = common_dates[0]
    normalized: dict[str, dict[str, float]] = {}
    for item in items:
        base_price = daily[item][base_date]
        normalized[item] = {d: (daily[item][d] / base_price) * 100 for d in common_dates}

    # Average across items per date
    index_rows = []
    for date in common_dates:
        values = [normalized[item][date] for item in items]
        avg = sum(values) / len(values)
        index_rows.append({"date": date, "index": round(avg, 2)})

    return index_rows


def save_inflation_csv(rows: list[dict], filename: str = "inflation_index.csv"):
    """Save inflation index to CSV."""
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "index"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Saved {len(rows):,} rows → {filename}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python loachart.py <item_name> [item_name2] ...")
        print('       python loachart.py "4T 보석 10레벨 겁화"')
        print('       python loachart.py --list')
        print('       python loachart.py --inflation')
        sys.exit(1)

    if sys.argv[1] == "--list":
        list_items()
        sys.exit(0)

    if sys.argv[1] == "--inflation":
        print("Building inflation index from basket of 9 items...")
        rows = build_inflation_index()
        save_inflation_csv(rows)
        sys.exit(0)

    for item_name in sys.argv[1:]:
        print(f"Fetching: {item_name}")
        try:
            rows = get_item_data(item_name)
            save_csv(item_name, rows)
        except Exception as e:
            print(f"  Error: {e}")
