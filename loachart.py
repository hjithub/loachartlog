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
        "아비도스 융화재료",        
        "상급 아비도스 융화 재료",
    ]
    print("Example item names:")
    for item in examples:
        print(f"  • {item}")
    print(f"\nFull list (403 items) available at: https://loachart.com/chart")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python loachart.py <item_name> [item_name2] ...")
        print('       python loachart.py "4T 보석 10레벨 겁화"')
        print('       python loachart.py --list')
        sys.exit(1)

    if sys.argv[1] == "--list":
        list_items()
        sys.exit(0)

    for item_name in sys.argv[1:]:
        print(f"Fetching: {item_name}")
        try:
            rows = get_item_data(item_name)
            save_csv(item_name, rows)
        except Exception as e:
            print(f"  Error: {e}")
