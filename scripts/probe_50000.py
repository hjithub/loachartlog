"""
One-off: fully paginate category 50000 (enhancement/honing materials) and
report alive vs dead items, to decide whether/how to add it to
fetch_movers.py. Temporary — deleted after use.

Usage:
  LOSTARK_API_KEY=... python3 scripts/probe_50000.py
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

SEARCH_API_URL = 'https://developer-lostark.game.onstove.com/markets/items'
MAX_PAGES = 30

MAX_RETRIES = 3
RETRY_DELAY = 2


def _request(body, api_key):
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(
        SEARCH_API_URL,
        data=data,
        headers={
            'accept': 'application/json',
            'authorization': f'bearer {api_key}',
            'content-type': 'application/json',
        },
        method='POST',
    )
    delay = RETRY_DELAY
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.URLError as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(delay)
                delay *= 2
            else:
                raise


def fetch_all(cat, api_key):
    items = []
    page = 0
    while page < MAX_PAGES:
        result = _request({"CategoryCode": cat, "PageNo": page}, api_key)
        page_items = result.get('Items') or []
        items.extend(page_items)
        total = result.get('TotalCount', len(items))
        if not page_items or len(items) >= total:
            break
        page += 1
        time.sleep(0.3)
    return items


def main():
    api_key = os.environ.get('LOSTARK_API_KEY', '')
    if not api_key:
        print('Error: LOSTARK_API_KEY not set')
        sys.exit(1)

    items = fetch_all(50000, api_key)
    alive = [i for i in items if (i.get('YDayAvgPrice') or 0) > 0]
    dead = [i for i in items if not (i.get('YDayAvgPrice') or 0) > 0]

    print(f'\n=== Category 50000: {len(items)} total, {len(alive)} alive, {len(dead)} dead ===')
    print(f'ALIVE ({len(alive)}):')
    for i in sorted(alive, key=lambda x: x.get('Name', '')):
        print(f"  {i['Name']} (Id={i['Id']}, Grade={i.get('Grade','')}, "
              f"CurrentMinPrice={i.get('CurrentMinPrice')}, YDayAvgPrice={i.get('YDayAvgPrice')})")
    print(f'DEAD ({len(dead)}):')
    for i in sorted(dead, key=lambda x: x.get('Name', '')):
        print(f"  {i['Name']} (Id={i['Id']}, CurrentMinPrice={i.get('CurrentMinPrice')})")


if __name__ == '__main__':
    main()
