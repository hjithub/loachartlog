"""
Fetch top price-gaining market items, ranked by recent trade count.

Two-stage approach to stay within API rate limits:
  1. Scan broad item categories via the market search endpoint (cheap: one
     call per category, returns every item in it) and compute % change from
     yesterday's average price to the current price for all of them.
  2. Only for the top N gainers, call the per-item detail endpoint to pull
     real daily trade counts (판매 건수) and use that to order the final list.

Writes docs/movers.json for the landing page.

Usage:
  LOSTARK_API_KEY=... python3 scripts/fetch_movers.py
"""

import json
import os
import sys
import time
import datetime
import urllib.request
import urllib.error

SEARCH_API_URL = 'https://developer-lostark.game.onstove.com/markets/items'
DETAIL_API_URL = 'https://developer-lostark.game.onstove.com/markets/items/{}'

CATEGORIES = [90200, 90300, 90400, 90700, 60200, 60300, 60400, 60500]
EXTRA_SEARCHES = [
    {"CategoryCode": 50010, "ItemName": "융화"},
]

# Items craft.html's cost calculator depends on. Kept separately so that page
# stays working even though this script no longer only tracks a whitelist.
CRAFT_WANTED_IDS = {
    6882701, 6882704, 6885705, 6885709,
    6882101, 6882104, 6882107,
    6882301, 6882304, 6884307, 6884308,
    6882401, 6882404, 6884407,
    101063, 101291, 101151, 101221, 101191, 101938,
    6861012, 6861013,
}

# How many top gainers to fetch real trade-count history for. Bounds the
# number of (more expensive, one-call-per-item) detail requests per run.
TOP_N_CANDIDATES = 60

MIN_YDAY_PRICE = 1  # avoid division by ~0 on brand-new/degenerate listings

MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds, doubles each retry


def _request(url, api_key, body=None):
    data = json.dumps(body).encode('utf-8') if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            'accept': 'application/json',
            'authorization': f'bearer {api_key}',
            'content-type': 'application/json',
        },
        method='POST' if body is not None else 'GET',
    )
    delay = RETRY_DELAY
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.URLError as e:
            if attempt < MAX_RETRIES - 1:
                print(f'  Retry {attempt + 1}/{MAX_RETRIES} after error: {e}')
                time.sleep(delay)
                delay *= 2
            else:
                raise


def search_items(body, api_key):
    """Fetch all items matching a category/name search."""
    result = _request(SEARCH_API_URL, api_key, body)
    return result.get('Items', [])


def get_item_detail(item_id, api_key):
    """Fetch single-item detail including recent daily Stats (trade count)."""
    return _request(DETAIL_API_URL.format(item_id), api_key)


def most_recent_trade_count(detail):
    """Pull today's/most-recent trade count out of an item detail response.

    The endpoint returns a JSON list containing a single object for the item;
    that object has a 'Stats' list of daily entries like
    {"Date": "2026-07-16", "AvgPrice": ..., "TradeCount": ...}.
    """
    if isinstance(detail, list):
        if not detail:
            return None
        detail = detail[0]
    stats = detail.get('Stats') or []
    if not stats:
        return None
    latest = max(stats, key=lambda s: s.get('Date', ''))
    return latest.get('TradeCount')


def write_craft_prices(all_items):
    """Emit docs/prices.json (legacy format) for craft.html, reusing data
    already fetched in the category scan above at no extra API cost."""
    prices = {}
    for item in all_items.values():
        if item['Id'] in CRAFT_WANTED_IDS:
            prices[item['Name']] = {
                'id': item['Id'],
                'currentMinPrice': item['CurrentMinPrice'],
                'yDayAvgPrice': item['YDayAvgPrice'],
                'recentPrice': item['RecentPrice'],
                'bundleCount': item['BundleCount'],
                'icon': item['Icon'],
            }

    output = {
        'updated_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'prices': prices,
    }
    with open('docs/prices.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f'Wrote {len(prices)} items to docs/prices.json (for craft.html)')


def main():
    api_key = os.environ.get('LOSTARK_API_KEY', '')
    if not api_key:
        print('Error: LOSTARK_API_KEY not set')
        sys.exit(1)

    all_items = {}  # Id -> item dict, deduped across overlapping category calls

    for cat in CATEGORIES:
        items = search_items({"CategoryCode": cat}, api_key)
        for item in items:
            all_items[item['Id']] = item
        print(f'Category {cat}: {len(items)} items ({len(all_items)} total so far)')
        time.sleep(0.5)

    for search in EXTRA_SEARCHES:
        items = search_items(search, api_key)
        for item in items:
            all_items[item['Id']] = item
        print(f'Search {search}: {len(items)} items ({len(all_items)} total so far)')
        time.sleep(0.5)

    # Stage 1: compute % change for everything we scanned, for free.
    movers = []
    for item in all_items.values():
        yday = item.get('YDayAvgPrice')
        current = item.get('CurrentMinPrice')
        if not yday or yday < MIN_YDAY_PRICE or current is None:
            continue
        pct_change = (current - yday) / yday * 100
        if pct_change <= 0:
            continue
        movers.append({
            'id': item['Id'],
            'name': item['Name'],
            'grade': item.get('Grade', ''),
            'icon': item.get('Icon', ''),
            'bundleCount': item.get('BundleCount', 1),
            'currentPrice': current,
            'yDayAvgPrice': yday,
            'pctChange': round(pct_change, 2),
        })

    movers.sort(key=lambda m: m['pctChange'], reverse=True)
    candidates = movers[:TOP_N_CANDIDATES]
    print(f'{len(movers)} items rose in price; fetching trade counts for top {len(candidates)}')

    write_craft_prices(all_items)

    # Stage 2: only the top gainers get an expensive per-item detail call.
    for m in candidates:
        try:
            detail = get_item_detail(m['id'], api_key)
            m['tradeCount'] = most_recent_trade_count(detail)
        except Exception as e:
            print(f"  Error fetching detail for {m['name']}: {e}")
            m['tradeCount'] = None
        time.sleep(0.3)

    # Final ordering: among the top gainers, most-traded first. Items whose
    # trade count we couldn't fetch sink to the bottom rather than disappear.
    candidates.sort(key=lambda m: (m['tradeCount'] is None, -(m['tradeCount'] or 0)))

    output = {
        'updated_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'items': candidates,
    }

    os.makedirs('docs', exist_ok=True)
    with open('docs/movers.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'Wrote {len(candidates)} movers to docs/movers.json')
    for m in candidates:
        tc = m['tradeCount']
        tc_str = f'{tc:,}' if tc is not None else '?'
        print(f"  {m['name']}: +{m['pctChange']}%  ({tc_str} traded)")


if __name__ == '__main__':
    main()
