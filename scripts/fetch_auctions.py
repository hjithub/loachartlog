"""
Fetch auction house data for 연마 max-roll accessory presets.
Writes docs/auctions.json for the landing page.

Usage:
  LOSTARK_API_KEY=... python3 scripts/fetch_auctions.py
"""

import urllib.request
import json
import os
import sys
import time
import datetime

API_URL = "https://developer-lostark.game.onstove.com/auctions/items"

# 연마 효과 codes (FirstOption=7)
# (SecondOption, is_percentage)
YEONMA = {
    "추가 피해": (41, True),
    "적에게 주는 피해 증가": (42, True),
    "세레나데, 신앙, 조화 게이지 획득량 증가": (43, True),
    "낙인력": (44, True),
    "공격력 %": (45, True),
    "무기 공격력 %": (46, True),
    "파티원 회복 효과": (47, True),
    "파티원 보호막 효과": (48, True),
    "치명타 적중률": (49, True),
    "치명타 피해": (50, True),
    "아군 공격력 강화 효과": (51, True),
    "아군 피해량 강화 효과": (52, True),
    "공격력 +": (53, False),
    "무기 공격력 +": (54, False),
    "최대 생명력": (55, False),
    "최대 마나": (56, True),
    "상태이상 공격 지속시간": (57, True),
    "전투 중 생명력 회복량": (58, False),
}

SEARCHES = [
    {
        "name": "서폿 1 (생명력/공강/피강)",
        "category": 200000,
        "filters": [
            ("최대 생명력", 6500, 6500),
            ("아군 공격력 강화 효과", 5.0, 5.0),
            ("아군 피해량 강화 효과", 7.5, 7.5),
        ],
    },
    {
        "name": "서폿 2 (게이지/생명력/낙인력)",
        "category": 200000,
        "filters": [
            ("세레나데, 신앙, 조화 게이지 획득량 증가", 6.0, 6.0),
            ("최대 생명력", 6500, 6500),
            ("낙인력", 8.0, 8.0),
        ],
    },
    {
        "name": "목걸이 (공강/피강 + any)",
        "category": 200010,
        "filters": [
            ("아군 공격력 강화 효과", 5.0, 5.0),
            ("아군 피해량 강화 효과", 7.5, 7.5),
        ],
        "excludeFrom": "서폿 1 (생명력/공강/피강)",
    },
    {
        "name": "반지 (게이지/낙인력 + any)",
        "category": 200030,
        "filters": [
            ("세레나데, 신앙, 조화 게이지 획득량 증가", 6.0, 6.0),
            ("낙인력", 8.0, 8.0),
        ],
        "excludeFrom": "서폿 2 (게이지/생명력/낙인력)",
    },
]

MAX_RETRIES = 3
RETRY_DELAY = 2


def build_etc_options(filters):
    opts = []
    for name, min_val, max_val in filters:
        code, is_pct = YEONMA[name]
        api_min = int(min_val * 100) if is_pct else min_val
        api_max = int(max_val * 100) if is_pct else max_val
        opts.append({
            "FirstOption": 7,
            "SecondOption": code,
            "MinValue": api_min,
            "MaxValue": api_max,
        })
    return opts


def fetch_auction(api_key, category_code, etc_options):
    body = {
        "ItemLevelMin": 0,
        "ItemLevelMax": 0,
        "ItemGradeQuality": None,
        "ItemUpgradeLevel": None,
        "ItemTradeAllowCount": None,
        "SkillOptions": [],
        "EtcOptions": etc_options,
        "Sort": "BUY_PRICE",
        "CategoryCode": category_code,
        "CharacterClass": "",
        "ItemTier": 4,
        "ItemGrade": "고대",
        "ItemName": "",
        "PageNo": 0,
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

    delay = RETRY_DELAY
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            if attempt < MAX_RETRIES - 1:
                print(f"  Retry {attempt + 1}/{MAX_RETRIES} after error: {e}")
                time.sleep(delay)
                delay *= 2
            else:
                raise


def extract_item(item):
    info = item.get("AuctionInfo", {})
    options = item.get("Options", [])

    stats = {}
    upgrades = []
    ark_passive = None
    for opt in options:
        t = opt.get("Type", "")
        name = opt.get("OptionName", "")
        val = opt.get("Value", 0)
        if t == "STAT" and name in ("힘", "민첩", "지능", "체력"):
            stats[name] = val
        elif t == "ACCESSORY_UPGRADE":
            upgrades.append({"name": name, "value": val})
        elif t == "ARK_PASSIVE":
            ark_passive = {"name": name, "value": val}

    return {
        "name": item.get("Name", ""),
        "grade": item.get("Grade", ""),
        "tier": item.get("Tier", 0),
        "quality": item.get("GradeQuality", 0),
        "buyPrice": info.get("BuyPrice"),
        "startPrice": info.get("StartPrice"),
        "endDate": info.get("EndDate", ""),
        "tradeAllowCount": info.get("TradeAllowCount", 0),
        "stats": stats,
        "upgrades": upgrades,
        "arkPassive": ark_passive,
    }


def main():
    api_key = os.environ.get("LOSTARK_API_KEY", "")
    if not api_key:
        print("Error: LOSTARK_API_KEY not set")
        sys.exit(1)

    results = []
    for search in SEARCHES:
        etc_opts = build_etc_options(search["filters"])
        print(f"Searching: {search['name']}")

        raw = fetch_auction(api_key, search["category"], etc_opts)
        items = [extract_item(i) for i in (raw.get("Items") or [])]
        total = raw.get("TotalCount", 0)

        entry = {
            "name": search["name"],
            "filters": [
                {"name": f[0], "min": f[1], "max": f[2]}
                for f in search["filters"]
            ],
            "totalCount": total,
            "items": items,
        }
        if "excludeFrom" in search:
            entry["excludeFrom"] = search["excludeFrom"]
        results.append(entry)
        print(f"  Found {total} items")
        time.sleep(1)

    output = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "searches": results,
    }

    os.makedirs("docs", exist_ok=True)
    with open("docs/auctions.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Wrote {sum(s['totalCount'] for s in results)} items to docs/auctions.json")


if __name__ == "__main__":
    main()
