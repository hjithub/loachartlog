"""
Economic Context Data Collector for Lost Ark KR

Two data sources:
1. LoaChart API   - Historical item prices (no auth needed)
2. Official KR API - Market data + daily avg prices (requires API key)

Usage:
  python economic_context.py loachart              # Fetch all indicator items from loachart
  python economic_context.py official --key YOUR_JWT  # Fetch from official KR API
  python economic_context.py all --key YOUR_JWT    # Both sources
"""

import requests
import csv
import sys
import os
import time
import json
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Source 1: LoaChart API (no auth, 5-min interval historical data)
# ---------------------------------------------------------------------------

LOACHART_API = "https://api.loachart.com/line_chart"

# Economic indicator items - prices reflect gold supply/demand dynamics
INDICATOR_ITEMS = [
    # Enhancement materials (core gold sinks - price = economy health)
    "운명의 파괴석",
    "운명의 수호석",
    "운명의 돌파석",
    "운명의 파괴석 결정",
    # Fusion materials (crafting cost proxy)
    "아비도스 융화 재료",
    "상급 아비도스 융화 재료",
    "최상급 오레하 융화 재료",
    # Shard pouches (progression demand indicator)
    "운명의 파편 주머니(대)",
    "명예의 파편 주머니(대)",
    # High-value engraving books (whale spending indicator)
    "(유물)원한 각인서",
    "(유물)아드레날린 각인서",
    "(유물)슈퍼 차지 각인서",
    # Gems (gold store-of-value / speculation indicator)
    "4T 보석 1레벨",
    "4T 보석 10레벨 겁화",
    "3T 보석 10레벨 멸화",
]


def fetch_loachart_item(item_name: str) -> list[dict]:
    """Fetch price history for one item from loachart."""
    resp = requests.get(LOACHART_API, params={"itemName": item_name})
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        raise ValueError(f"API error: {data['error']} (item: {item_name})")

    rows = []
    for ts, price in data["v"]:
        dt = datetime.fromtimestamp(ts * 100, tz=timezone.utc)
        rows.append({"datetime": dt.strftime("%Y-%m-%d %H:%M:%S"), "price": price})
    return rows


def fetch_all_loachart(output_dir: str = "economic_data"):
    """Fetch all indicator items and save as individual CSVs + merged CSV."""
    os.makedirs(output_dir, exist_ok=True)

    all_data = {}  # item_name -> rows

    for item in INDICATOR_ITEMS:
        print(f"  Fetching: {item}")
        try:
            rows = fetch_loachart_item(item)
            all_data[item] = rows

            # Save individual CSV
            safe = item.replace(" ", "_").replace(":", "").replace("/", "_")
            safe = safe.replace("(", "").replace(")", "")
            path = os.path.join(output_dir, f"{safe}.csv")
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=["datetime", "price"])
                w.writeheader()
                w.writerows(rows)
            print(f"    {len(rows):,} rows -> {path}")

            time.sleep(0.5)  # Be polite to API
        except Exception as e:
            print(f"    Error: {e}")

    # Build merged wide-format CSV (datetime as index, items as columns)
    if all_data:
        _save_merged(all_data, os.path.join(output_dir, "_merged_indicators.csv"))

    return all_data


def _save_merged(all_data: dict, path: str):
    """Merge all items into a single wide-format CSV keyed by datetime."""
    # Collect all unique datetimes
    dt_index = {}  # datetime_str -> {item: price, ...}
    for item, rows in all_data.items():
        for row in rows:
            dt_str = row["datetime"]
            if dt_str not in dt_index:
                dt_index[dt_str] = {}
            dt_index[dt_str][item] = row["price"]

    sorted_dts = sorted(dt_index.keys())
    items = list(all_data.keys())

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["datetime"] + items)
        for dt_str in sorted_dts:
            row = [dt_str]
            for item in items:
                row.append(dt_index[dt_str].get(item, ""))
            w.writerow(row)

    print(f"\n  Merged {len(sorted_dts):,} timestamps x {len(items)} items -> {path}")


# ---------------------------------------------------------------------------
# Source 2: Official Lost Ark KR API (requires JWT from developer portal)
# Register at: https://developer-lostark.game.onstove.com/
# ---------------------------------------------------------------------------

OFFICIAL_API = "https://developer-lostark.game.onstove.com"

# Category codes for market items (from /markets/options)
MARKET_CATEGORIES = {
    "enhancement_material": 50000,
    "combat_supplies": 60000,
    "cooking": 70000,
    "engraving_recipe": 40000,
    "adventurer_equipment": 20000,
    "gem": 210000,
}

# Key items to track from the official API (for daily avg price history)
OFFICIAL_TRACK_ITEMS = [
    # These will be resolved to item IDs via /markets/items search
    ("운명의 파괴석", 50000),
    ("운명의 수호석", 50000),
    ("운명의 돌파석", 50000),
    ("아비도스 융화 재료", 50000),
    ("상급 아비도스 융화 재료", 50000),
]


class OfficialAPIClient:
    """Client for the official Lost Ark KR Open API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "accept": "application/json",
            "authorization": f"bearer {api_key}",
            "Content-Type": "application/json",
        })

    def get_market_options(self) -> dict:
        """GET /markets/options - available categories and options."""
        resp = self.session.get(f"{OFFICIAL_API}/markets/options")
        resp.raise_for_status()
        return resp.json()

    def search_market(self, category_code: int, item_name: str = "",
                      sort: str = "CURRENT_MIN_PRICE", page: int = 1) -> dict:
        """POST /markets/items - search market listings."""
        body = {
            "Sort": sort,
            "CategoryCode": category_code,
            "PageNo": page,
            "SortCondition": "ASC",
        }
        if item_name:
            body["ItemName"] = item_name

        resp = self.session.post(f"{OFFICIAL_API}/markets/items", json=body)
        resp.raise_for_status()
        return resp.json()

    def get_item_history(self, item_id: int) -> dict:
        """GET /markets/items/{itemId} - daily avg price + volume history."""
        resp = self.session.get(f"{OFFICIAL_API}/markets/items/{item_id}")
        resp.raise_for_status()
        return resp.json()

    def fetch_tracked_items(self, output_dir: str = "economic_data"):
        """Fetch daily price history for all tracked items."""
        os.makedirs(output_dir, exist_ok=True)
        results = {}

        for item_name, cat_code in OFFICIAL_TRACK_ITEMS:
            print(f"  Searching: {item_name}")
            try:
                search = self.search_market(cat_code, item_name)
                items = search.get("Items", [])
                if not items:
                    print(f"    Not found in market")
                    continue

                item = items[0]
                item_id = item["Id"]
                bundle = item.get("BundleCount", 1)
                print(f"    Found: ID={item_id}, Bundle={bundle}")

                history = self.get_item_history(item_id)
                rows = []
                for entry in history:
                    rows.append({
                        "date": entry.get("Date", ""),
                        "avg_price": entry.get("AvgPrice", 0),
                        "trade_count": entry.get("TradeCount", 0),
                        "bundle_count": bundle,
                        "price_per_unit": round(entry.get("AvgPrice", 0) / bundle, 2) if bundle > 0 else 0,
                    })

                results[item_name] = rows

                safe = item_name.replace(" ", "_").replace(":", "").replace("/", "_")
                safe = safe.replace("(", "").replace(")", "")
                path = os.path.join(output_dir, f"official_{safe}.csv")
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.DictWriter(f, fieldnames=["date", "avg_price", "trade_count", "bundle_count", "price_per_unit"])
                    w.writeheader()
                    w.writerows(rows)
                print(f"    {len(rows)} days -> {path}")

                time.sleep(1)  # Rate limit: 100/min
            except Exception as e:
                print(f"    Error: {e}")

        return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    source = sys.argv[1].lower()
    api_key = None

    # Parse --key argument
    for i, arg in enumerate(sys.argv):
        if arg == "--key" and i + 1 < len(sys.argv):
            api_key = sys.argv[i + 1]
            break

    # Also check env var
    if not api_key:
        api_key = os.environ.get("LOSTARK_API_KEY")

    if source in ("loachart", "all"):
        print("\n[LoaChart] Fetching economic indicator items...")
        fetch_all_loachart()

    if source in ("official", "all"):
        if not api_key:
            print("\nError: Official API requires --key YOUR_JWT or LOSTARK_API_KEY env var")
            print("Register at: https://developer-lostark.game.onstove.com/")
            sys.exit(1)

        print("\n[Official API] Fetching market data...")
        client = OfficialAPIClient(api_key)

        # First, dump available categories for reference
        try:
            options = client.get_market_options()
            print(f"  Available categories: {json.dumps(options, ensure_ascii=False)[:500]}...")
        except Exception as e:
            print(f"  Warning: Could not fetch options: {e}")

        client.fetch_tracked_items()

    print("\nDone.")


if __name__ == "__main__":
    main()
