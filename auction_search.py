"""
Lost Ark Auction House Search — Accessory 연마 효과 Filter
Searches the KR auction house API for accessories matching specific 연마 (polishing) effects.

Usage:
  export LOSTARK_API_KEY="your_key"
  python auction_search.py
"""

import urllib.request
import json
import os
import sys
import time

API_URL = "https://developer-lostark.game.onstove.com/auctions/items"

# === 연마 효과 codes (FirstOption=7) ===
YEONMA = {
    "추가 피해": 41,
    "적에게 주는 피해 증가": 42,
    "세레나데, 신앙, 조화 게이지 획득량 증가": 43,
    "낙인력": 44,
    "공격력 %": 45,
    "무기 공격력 %": 46,
    "파티원 회복 효과": 47,
    "파티원 보호막 효과": 48,
    "치명타 적중률": 49,
    "치명타 피해": 50,
    "아군 공격력 강화 효과": 51,
    "아군 피해량 강화 효과": 52,
    "공격력 +": 53,
    "무기 공격력 +": 54,
    "최대 생명력": 55,
    "최대 마나": 56,
    "상태이상 공격 지속시간": 57,
    "전투 중 생명력 회복량": 58,
}

# === Accessory categories ===
ACCESSORY_CATS = {
    "all": 200000,
    "목걸이": 200010,
    "귀걸이": 200020,
    "반지": 200030,
}

# === Search presets ===
SEARCHES = {
    "서폿 1 (생명력/공강/피강)": {
        "category": "all",
        "filters": [
            ("최대 생명력", 6500, 6500),
            ("아군 공격력 강화 효과", 5, 5),
            ("아군 피해량 강화 효과", 7, 7),
        ],
    },
    "서폿 2 (게이지/생명력/낙인력)": {
        "category": "all",
        "filters": [
            ("세레나데, 신앙, 조화 게이지 획득량 증가", 6, 6),
            ("최대 생명력", 6500, 6500),
            ("낙인력", 8, 8),
        ],
    },
}


def search_auction(api_key, category_code, etc_options, item_tier=4,
                   item_grade="고대", sort="BUY_PRICE", page=0):
    body = {
        "ItemLevelMin": 0,
        "ItemLevelMax": 0,
        "ItemGradeQuality": None,
        "ItemUpgradeLevel": None,
        "ItemTradeAllowCount": None,
        "SkillOptions": [],
        "EtcOptions": etc_options,
        "Sort": sort,
        "CategoryCode": category_code,
        "CharacterClass": "",
        "ItemTier": item_tier,
        "ItemGrade": item_grade,
        "ItemName": "",
        "PageNo": page,
        "SortCondition": "ASC",
    }

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "accept": "application/json",
            "authorization": f"bearer {api_key}",
            "content-type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def build_etc_options(filters):
    opts = []
    for name, min_val, max_val in filters:
        code = YEONMA.get(name)
        if code is None:
            print(f"  WARNING: unknown 연마 효과 '{name}', skipping")
            continue
        opts.append({
            "FirstOption": 7,
            "SecondOption": code,
            "MinValue": min_val,
            "MaxValue": max_val,
        })
    return opts


def format_gold(n):
    if n is None:
        return "-"
    return f"{n:,}g"


def print_results(result, search_name):
    items = result.get("Items") or []
    total = result.get("TotalCount", 0)

    print(f"\n{'='*70}")
    print(f"  {search_name}")
    print(f"  총 {total}건")
    print(f"{'='*70}")

    if not items:
        print("  결과 없음")
        return

    for i, item in enumerate(items[:10], 1):
        info = item.get("AuctionInfo", {})
        buy = info.get("BuyPrice")
        bid = info.get("StartPrice")
        end = info.get("EndDate", "")[:16]
        grade = item.get("Grade", "")
        name = item.get("Name", "")
        quality = item.get("GradeQuality", "-")
        tier = item.get("Tier", "")
        trade_count = info.get("TradeAllowCount", "?")

        print(f"\n  [{i}] {grade} {name}  (품질 {quality}, T{tier})")
        print(f"      즉시구매: {format_gold(buy)}  |  최소입찰: {format_gold(bid)}  |  거래횟수: {trade_count}회")
        print(f"      마감: {end}")

        # Print options
        options = item.get("Options", [])
        for opt in options:
            opt_type = opt.get("Type", "")
            opt_name = opt.get("OptionName", "")
            opt_val = opt.get("Value", "")
            if opt_name:
                print(f"      - {opt_type}: {opt_name} {opt_val}")


def main():
    api_key = os.environ.get("LOSTARK_API_KEY", "")
    if not api_key:
        print("Error: LOSTARK_API_KEY not set")
        print("  export LOSTARK_API_KEY='your_key_here'")
        sys.exit(1)

    for search_name, config in SEARCHES.items():
        cat_code = ACCESSORY_CATS[config["category"]]
        etc_opts = build_etc_options(config["filters"])

        print(f"\nSearching: {search_name}")
        filter_desc = ", ".join(f"{n} {lo}~{hi}" for n, lo, hi in config["filters"])
        print(f"  Filters: {filter_desc}")

        try:
            result = search_auction(api_key, cat_code, etc_opts)
            print_results(result, search_name)
        except Exception as e:
            print(f"  Error: {e}")

        time.sleep(1)


if __name__ == "__main__":
    main()
